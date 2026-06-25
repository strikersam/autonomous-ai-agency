from __future__ import annotations

import os
import secrets
import time
from typing import Any, Literal

from pydantic import BaseModel, Field

from webui.config_store import JsonConfigStore
from webui.url_guard import validate_outbound_url

try:
    from brain_policy import invalidate_brain_cache
except Exception:  # noqa: BLE001 - brain_policy import is best-effort
    def invalidate_brain_cache() -> None:  # type: ignore[no-redef]
        pass


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _validate_provider_base_url(url: str) -> str:
    return validate_outbound_url(url, scheme="http")


class ProviderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    base_url: str = Field(..., min_length=4, max_length=2048)
    api_key: str | None = Field(default=None, min_length=1, max_length=4096)
    default_model: str | None = Field(default=None, max_length=200)
    default_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    kind: Literal["openai_compat", "anthropic"] = "openai_compat"
    # Drag-and-drop priority: higher integer = picked first by brain_policy. New
    # providers default to 0 so existing reorder logic ranks them below any
    # already-bootstrapped providers with positive priority.
    priority: int = Field(default=0, ge=-1000, le=1000)


class ProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    base_url: str | None = Field(default=None, min_length=4, max_length=2048)
    api_key: str | None = Field(default=None, min_length=1, max_length=4096)
    default_model: str | None = Field(default=None, max_length=200)
    default_temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    kind: Literal["openai_compat", "anthropic"] | None = None
    priority: int | None = Field(default=None, ge=-1000, le=1000)


class ProviderRecord(BaseModel):
    provider_id: str
    name: str
    base_url: str
    kind: Literal["openai_compat", "anthropic"] = "openai_compat"
    default_model: str | None = None
    default_temperature: float = 0.2
    has_api_key: bool = False
    created_at: str
    updated_at: str
    priority: int = 0


class ProviderSecret(BaseModel):
    provider_id: str
    base_url: str
    api_key: str | None
    default_model: str | None
    default_temperature: float
    kind: Literal["openai_compat", "anthropic"] = "openai_compat"
    priority: int = 0


def _normalize_base_url(url: str) -> str:
    return url.strip().rstrip("/")


class ProviderManager:
    def __init__(self, store: JsonConfigStore) -> None:
        self._store = store

    def list_public(self) -> list[ProviderRecord]:
        return [self._to_public(item) for item in self._items()]

    def list_admin(self) -> list[ProviderRecord]:
        return [self._to_public(item, include_base=True) for item in self._items()]

    def get_secret(self, provider_id: str) -> ProviderSecret | None:
        for item in self._items():
            if item.get("provider_id") == provider_id:
                try:
                    priority = int(item.get("priority") or 0)
                except (TypeError, ValueError):
                    priority = 0
                return ProviderSecret(
                    provider_id=provider_id,
                    base_url=str(item.get("base_url") or ""),
                    api_key=item.get("api_key") or None,
                    default_model=item.get("default_model") or None,
                    default_temperature=float(item.get("default_temperature") or 0.2),
                    kind=str(item.get("kind") or "openai_compat"),
                    priority=priority,
                )
        return None

    def create(self, body: ProviderCreate) -> ProviderRecord:
        items = self._items()
        provider_id = "prov_" + secrets.token_hex(6)
        now = _now()
        _validate_provider_base_url(body.base_url)
        items.append(
            {
                "provider_id": provider_id,
                "name": body.name.strip(),
                "base_url": _normalize_base_url(body.base_url),
                "api_key": body.api_key,
                "kind": body.kind,
                "default_model": body.default_model,
                "default_temperature": body.default_temperature,
                "priority": body.priority,
                "created_at": now,
                "updated_at": now,
            }
        )
        self._store.save("providers", items)
        # The brain resolver caches the active brain. Re-resolve on the next
        # read so the operator's drag-and-drop reorder takes effect immediately.
        invalidate_brain_cache()
        return self._to_public(items[-1], include_base=True)

    def update(self, provider_id: str, body: ProviderUpdate) -> ProviderRecord | None:
        items = self._items()
        for item in items:
            if item.get("provider_id") != provider_id:
                continue
            if body.name is not None:
                item["name"] = body.name.strip()
            if body.base_url is not None:
                _validate_provider_base_url(body.base_url)
                item["base_url"] = _normalize_base_url(body.base_url)
            if body.api_key is not None:
                item["api_key"] = body.api_key
            if body.default_model is not None:
                item["default_model"] = body.default_model
            if body.default_temperature is not None:
                item["default_temperature"] = body.default_temperature
            if body.kind is not None:
                item["kind"] = body.kind
            if body.priority is not None:
                item["priority"] = body.priority
            item["updated_at"] = _now()
            self._store.save("providers", items)
            invalidate_brain_cache()
            return self._to_public(item, include_base=True)
        return None

    def delete(self, provider_id: str) -> bool:
        items = self._items()
        after = [item for item in items if item.get("provider_id") != provider_id]
        if len(after) == len(items):
            return False
        self._store.save("providers", after)
        invalidate_brain_cache()
        return True

    def reorder(self, provider_ids: list[str]) -> bool:
        """Reorder the provider priority list.

        ``provider_ids`` is the desired ordering (first = highest priority).
        We assign integer priorities so the FIRST element ends up with the
        largest integer (so descending-sort in brain_policy places it first).
        Providers not in the list keep their existing priority — operators
        can issue partial reorders without disturbing the rest.

        Unknown provider_ids are silently ignored (no error). Returns False
        when the request would change nothing (empty / duplicate list).
        """
        items = self._items()
        if not provider_ids:
            return False
        # Dedupe while preserving order; ignore unknown ids so a stale UI
        # snapshot can't crash the brain cache.
        seen: set[str] = set()
        clean_ids: list[str] = []
        for pid in provider_ids:
            if pid not in seen:
                seen.add(pid)
                clean_ids.append(pid)
        # Highest priority = len-1, descending. Anchor at the current top-most
        # priority so a reorder that doesn't mention every provider still
        # leaves untouched records above/below a single mid-range rearrange.
        max_prio = max(int(it.get("priority") or 0) for it in items) if items else 0
        id_to_prio: dict[str, int] = {}
        for idx, pid in enumerate(clean_ids):
            id_to_prio[pid] = max_prio + (len(clean_ids) - idx)
        changed = False
        for it in items:
            pid = str(it.get("provider_id") or "")
            if pid in id_to_prio and int(it.get("priority") or 0) != id_to_prio[pid]:
                it["priority"] = id_to_prio[pid]
                it["updated_at"] = _now()
                changed = True
        if not changed:
            return False
        self._store.save("providers", items)
        invalidate_brain_cache()
        return True

    def ensure_defaults(self, *, local_base_url: str) -> None:
        """Ensure at least one provider exists, seeded from env when empty."""
        items = self._items()
        if items:
            return

        now = _now()
        seeded: list[dict[str, Any]] = []

        # ── Nvidia NIM — first priority (free, no local infra needed) ─────────
        nvidia_key = (
            os.environ.get("NVIDIA_API_KEY")
            or os.environ.get("NVidiaApiKey")
            or ""
        ).strip()
        if nvidia_key:
            nvidia_base = (
                os.environ.get("NVIDIA_BASE_URL")
                or "https://integrate.api.nvidia.com"
            ).rstrip("/")
            seeded.append(
                {
                    "provider_id": "prov_nvidia_nim",
                    "name": "Nvidia NIM (Free)",
                    "base_url": nvidia_base,
                    "api_key": nvidia_key,
                    "kind": "openai_compat",
                    "default_model": (
                        os.environ.get("NVIDIA_DEFAULT_MODEL")
                        or "meta/llama-3.3-70b-instruct"
                    ),
                    "default_temperature": float(
                        os.environ.get("DEFAULT_TEMPERATURE") or 0.2
                    ),
                    "created_at": now,
                    "updated_at": now,
                }
            )

        # ── Local Ollama — fallback when available ────────────────────────────
        seeded.append(
            {
                "provider_id": "prov_local",
                "name": "Local (Ollama via proxy)",
                "base_url": _normalize_base_url(local_base_url),
                "api_key": None,
                "kind": "openai_compat",
                "default_model": os.environ.get("AGENT_EXECUTOR_MODEL") or None,
                "default_temperature": float(os.environ.get("DEFAULT_TEMPERATURE") or 0.2),
                "created_at": now,
                "updated_at": now,
            }
        )

        # ── Any extra OPENAI_COMPAT_* provider from env ───────────────────────
        env_base = os.environ.get("OPENAI_COMPAT_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
        env_key = os.environ.get("OPENAI_COMPAT_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if env_base:
            seeded.append(
                {
                    "provider_id": "prov_env",
                    "name": "Remote (OPENAI_COMPAT_*/OPENAI_*)",
                    "base_url": _normalize_base_url(env_base),
                    "api_key": env_key,
                    "kind": "openai_compat",
                    "default_model": os.environ.get("OPENAI_COMPAT_MODEL") or os.environ.get("OPENAI_MODEL"),
                    "default_temperature": float(os.environ.get("DEFAULT_TEMPERATURE") or 0.2),
                    "created_at": now,
                    "updated_at": now,
                }
            )
        self._store.save("providers", seeded)

    def _items(self) -> list[dict[str, Any]]:
        raw = self._store.load("providers")
        items = raw.get("items")
        return items if isinstance(items, list) else []

    def _to_public(self, item: dict[str, Any], *, include_base: bool = True) -> ProviderRecord:
        api_key = item.get("api_key")
        try:
            priority = int(item.get("priority") or 0)
        except (TypeError, ValueError):
            priority = 0
        return ProviderRecord(
            provider_id=str(item.get("provider_id") or ""),
            name=str(item.get("name") or ""),
            base_url=str(item.get("base_url") or "") if include_base else "",
            kind=str(item.get("kind") or "openai_compat"),
            default_model=item.get("default_model") or None,
            default_temperature=float(item.get("default_temperature") or 0.2),
            has_api_key=bool(api_key),
            priority=priority,
            created_at=str(item.get("created_at") or ""),
            updated_at=str(item.get("updated_at") or ""),
        )
