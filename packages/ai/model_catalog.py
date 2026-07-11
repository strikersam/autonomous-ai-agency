"""packages/ai/model_catalog.py — UNIT 8: free-LLM-API model catalog sync.

Advisory-only mirror of the model catalog (``config/models.yaml`` + the
active BrainConfig) to the DB so external services can query which
models are available without re-implementing the catalog loader.

Hard constraints (from the UNIT 8 plan):

  1. **Flag-gated, default OFF.** The catalog sync + the
     ``GET /api/catalog/models`` endpoint are disabled unless
     ``FREELLM_API_MODEL_CATALOG_ENABLED=true``. The flag is the rollout
     lever — flip it on a single instance to verify the shape before
     turning it on everywhere.

  2. **Advisory-only.** The catalog mirror NEVER changes brain routing.
     ``resolve_component_model()`` always reads the in-process catalog
     + the BrainConfig cache; this module is purely for observability
     by external services.

  3. **Dual-storage.** Mongo primary, sqlite mirror — same pattern as
     ``brain_config.py``. Either backend failing is non-fatal; the other
     still serves reads.

  4. **Never raises.** All public methods swallow exceptions and return
     safe defaults (empty list / None). A DB outage can't brick the
     catalog endpoint.

The catalog mirror is a single Mongo document keyed ``_id="model_catalog"``
in the ``app_settings`` collection (mirroring brain_config's home). The
document shape::

    {
      "_id": "model_catalog",
      "catalog_version": 1,
      "safe_default": {"provider": "nvidia", "model": "z-ai/glm-5.2"},
      "recommended_priority": ["ollama", "cerebras", "groq", "nvidia"],
      "providers": {
        "nvidia": {
          "display_name": "NVIDIA NIM (free, broad catalogue)",
          "tier": "free",
          "key_env": "NVIDIA_API_KEY",
          "base_url_env": "NVIDIA_BASE_URL",
          "default_base_url": "https://integrate.api.nvidia.com",
          "role_presets": {"planner": "...", "executor": "...", ...},
          "candidates": ["...", "..."],
          "key_present": true,
          "active": false,
        },
        ...
      },
      "active_brain": {
        "primary_provider": "nvidia",
        "planner_model": "...",
        "executor_model": "...",
        "verifier_model": "...",
        "judge_model": "...",
        "updated_at": "...",
        "updated_by": "...",
      },
      "mirrored_at": "2026-07-11T...",
    }

The ``key_present`` per-provider flag and the ``active_brain`` block are
the live-derived fields — everything else is a verbatim copy of the
catalog. External services can use this to render a provider picker
without needing to load the YAML or query the brain config.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any

from pydantic import BaseModel, Field

from packages.ai.brain_config import (
    BrainConfig,
    PROVIDER_BASE_URL_ENV,
    PROVIDER_CANDIDATES,
    PROVIDER_DEFAULT_BASE_URL,
    PROVIDER_DISPLAY_NAMES,
    PROVIDER_KEY_ENV,
    PROVIDER_PRESETS,
    PROVIDER_TIERS,
    RECOMMENDED_PROVIDER_PRIORITY,
    SAFE_DEFAULT_MODEL,
    SAFE_DEFAULT_PROVIDER,
    _load_models_yaml,
    all_provider_ids,
    provider_base_url,
    provider_key_present,
)

log = logging.getLogger("model_catalog")


# ── Pydantic models ────────────────────────────────────────────────────────


class CatalogProviderEntry(BaseModel):
    """One provider's catalog entry in the mirrored document."""
    provider_id: str
    display_name: str
    tier: str  # free | paid | local
    key_env: str | None = None
    base_url_env: str | None = None
    default_base_url: str = ""
    role_presets: dict[str, str] = Field(default_factory=dict)
    candidates: list[str] = Field(default_factory=list)
    # Live-derived (not in the YAML catalog):
    key_present: bool = False
    base_url: str = ""
    active: bool = False  # True when this is the active brain's primary


class CatalogActiveBrain(BaseModel):
    """Snapshot of the active brain config at mirror time."""
    primary_provider: str = ""
    planner_model: str = ""
    executor_model: str = ""
    verifier_model: str = ""
    judge_model: str = ""
    updated_at: str = ""
    updated_by: str = ""


class CatalogMirror(BaseModel):
    """The full mirrored catalog document."""
    catalog_version: int = 1
    safe_default: dict[str, str] = Field(default_factory=dict)
    recommended_priority: list[str] = Field(default_factory=list)
    providers: list[CatalogProviderEntry] = Field(default_factory=list)
    active_brain: CatalogActiveBrain = Field(default_factory=CatalogActiveBrain)
    mirrored_at: str = ""


# ── Store ─────────────────────────────────────────────────────────────────


_CATALOG_DOC_ID = "model_catalog"
_CATALOG_COLLECTION = "app_settings"
_CACHE_TTL_SECONDS = 30.0  # longer than brain_config's 5s — catalog rarely changes


class ModelCatalogStore:
    """Dual-storage catalog mirror (Mongo primary, sqlite mirror).

    All public methods are async and never raise — on any storage error
    they fall back to building the catalog in-memory from the loaded
    YAML + the brain config cache.
    """

    def __init__(self) -> None:
        self._cache: CatalogMirror | None = None
        self._cache_at: float = 0.0
        self._lock = asyncio.Lock()

    # ── Public API ──────────────────────────────────────────────────────

    async def get_catalog(self) -> CatalogMirror:
        """Return the mirrored catalog.

        Resolution order:
          1. In-process cache (if fresh)
          2. Mongo ``app_settings`` doc
          3. Sqlite mirror
          4. Build in-memory from the loaded YAML + brain config cache

        Never raises — falls back to the in-memory build on any error.
        """
        if self._cache is not None and (time.monotonic() - self._cache_at) < _CACHE_TTL_SECONDS:
            return self._cache

        async with self._lock:
            if self._cache is not None and (time.monotonic() - self._cache_at) < _CACHE_TTL_SECONDS:
                return self._cache

            cfg = await self._load_unlocked()
            self._cache = cfg
            self._cache_at = time.monotonic()
            return cfg

    async def sync_catalog(self, *, actor: str = "sync") -> CatalogMirror:
        """Force a rebuild + persist. Returns the synced catalog.

        Used by the ``POST /api/admin/maintenance/sync-catalog`` endpoint
        and the periodic background sync (when the flag is on).
        """
        async with self._lock:
            cfg = self._build_in_memory()
            await self._persist_unlocked(cfg)
            self._cache = cfg
            self._cache_at = time.monotonic()
            log.info("model_catalog: synced by %s (%d providers)",
                     actor, len(cfg.providers))
            return cfg

    def invalidate(self) -> None:
        """Clear the in-process cache."""
        self._cache = None
        self._cache_at = 0.0

    # ── Build (in-memory from loaded YAML + brain config cache) ─────────

    def _build_in_memory(self) -> CatalogMirror:
        """Build a CatalogMirror from the loaded YAML + brain config cache.

        This is the fallback when no DB doc is present, and the source
        of truth that gets persisted on sync.
        """
        # Load the active brain config (best-effort — never raises).
        active_brain = self._read_active_brain_config()

        # Build per-provider entries.
        providers: list[CatalogProviderEntry] = []
        active_primary = (active_brain.primary_provider or "").strip()
        for pid in all_provider_ids():
            entry = CatalogProviderEntry(
                provider_id=pid,
                display_name=PROVIDER_DISPLAY_NAMES.get(pid, pid),
                tier=PROVIDER_TIERS.get(pid, "unknown"),
                key_env=PROVIDER_KEY_ENV.get(pid),
                base_url_env=PROVIDER_BASE_URL_ENV.get(pid),
                default_base_url=PROVIDER_DEFAULT_BASE_URL.get(pid, ""),
                role_presets=dict(PROVIDER_PRESETS.get(pid, {})),
                candidates=list(PROVIDER_CANDIDATES.get(pid, [])),
                key_present=provider_key_present(pid),
                base_url=provider_base_url(pid),
                active=(pid == active_primary),
            )
            providers.append(entry)

        return CatalogMirror(
            catalog_version=1,
            safe_default={
                "provider": SAFE_DEFAULT_PROVIDER,
                "model": SAFE_DEFAULT_MODEL,
            },
            recommended_priority=list(RECOMMENDED_PROVIDER_PRIORITY),
            providers=providers,
            active_brain=active_brain,
            mirrored_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

    def _read_active_brain_config(self) -> CatalogActiveBrain:
        """Best-effort read of the active BrainConfig cache.

        Returns an empty CatalogActiveBrain on any error (e.g. cache cold).
        """
        try:
            from packages.ai.brain_config import _store, _CACHE_TTL_SECONDS as BRAIN_TTL
            if _store is not None and _store._cache is not None:
                if (time.monotonic() - _store._cache_at) < BRAIN_TTL:
                    cfg: BrainConfig = _store._cache
                    return CatalogActiveBrain(
                        primary_provider=str(cfg.primary_provider),
                        planner_model=str(cfg.planner_model),
                        executor_model=str(cfg.executor_model),
                        verifier_model=str(cfg.verifier_model),
                        judge_model=str(cfg.judge_model),
                        updated_at=str(cfg.updated_at),
                        updated_by=str(cfg.updated_by),
                    )
        except Exception as exc:  # noqa: BLE001 — defensive
            log.debug("model_catalog: brain config cache read failed (%s)", exc)
        return CatalogActiveBrain()

    # ── Storage backends ────────────────────────────────────────────────

    async def _load_unlocked(self) -> CatalogMirror:
        """Read the persisted catalog from Mongo or sqlite. Falls back to
        in-memory build on any error."""
        # 1. Try Mongo.
        try:
            from backend.server import get_db
            db = get_db()
            collection = getattr(db, _CATALOG_COLLECTION, None)
            if collection is not None:
                doc = await collection.find_one({"_id": _CATALOG_DOC_ID})
                if doc:
                    return self._from_doc(doc)
        except Exception as exc:
            log.debug("model_catalog: Mongo read failed (%s) — trying sqlite mirror", exc)

        # 2. Sqlite mirror.
        try:
            cfg = self._load_sqlite_mirror()
            if cfg is not None:
                return cfg
        except Exception as exc:
            log.debug("model_catalog: sqlite mirror read failed (%s) — building in-memory", exc)

        # 3. Build in-memory.
        return self._build_in_memory()

    async def _persist_unlocked(self, cfg: CatalogMirror) -> None:
        """Persist *cfg* to Mongo (primary) and sqlite (mirror). Either
        backend failing is non-fatal."""
        # 1. Mongo (upsert).
        try:
            from backend.server import get_db
            db = get_db()
            collection = getattr(db, _CATALOG_COLLECTION, None)
            if collection is not None:
                doc = cfg.model_dump(mode="json")
                doc["_id"] = _CATALOG_DOC_ID
                await collection.update_one(
                    {"_id": _CATALOG_DOC_ID},
                    {"$set": doc},
                    upsert=True,
                )
        except Exception as exc:
            log.warning("model_catalog: Mongo persist failed (%s) — sqlite mirror only", exc)

        # 2. Sqlite mirror (always — even when Mongo succeeds).
        try:
            self._save_sqlite_mirror(cfg)
        except Exception as exc:
            log.warning("model_catalog: sqlite mirror persist failed (%s)", exc)

    # ── Sqlite mirror ───────────────────────────────────────────────────

    _MIRROR_TABLE = "model_catalog_mirror"
    _MIRROR_ROW_ID = "model_catalog"
    _MIRROR_DDL = (
        "CREATE TABLE IF NOT EXISTS model_catalog_mirror "
        "(id TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )

    def _load_sqlite_mirror(self) -> CatalogMirror | None:
        import sqlite3
        path = self._mirror_db_path()
        if not path or not os.path.isfile(path):
            return None
        conn = sqlite3.connect(path)
        try:
            cur = conn.cursor()
            cur.execute(self._MIRROR_DDL)
            cur.execute(
                "SELECT data FROM model_catalog_mirror WHERE id = ?",
                (self._MIRROR_ROW_ID,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return CatalogMirror.model_validate_json(row[0])
        finally:
            conn.close()

    def _save_sqlite_mirror(self, cfg: CatalogMirror) -> None:
        import sqlite3
        path = self._mirror_db_path()
        if not path:
            return
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        conn = sqlite3.connect(path)
        try:
            cur = conn.cursor()
            cur.execute(self._MIRROR_DDL)
            cur.execute(
                "INSERT OR REPLACE INTO model_catalog_mirror (id, data, updated_at) VALUES (?, ?, ?)",
                (
                    self._MIRROR_ROW_ID,
                    cfg.model_dump_json(),
                    cfg.mirrored_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def _mirror_db_path(self) -> str:
        # Mirror the brain_config mirror's path derivation so a test that
        # points SQLITE_DB_PATH at a tmp dir isolates both mirrors.
        base = os.environ.get("SQLITE_DB_PATH", ".data/agency.db")
        if base.endswith(".db"):
            return base[:-3] + "_catalog.db"
        return base + "_catalog.db"

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _from_doc(doc: dict[str, Any]) -> CatalogMirror:
        """Build a CatalogMirror from a Mongo doc, dropping Mongo's ``_id``."""
        data = {k: v for k, v in doc.items() if k != "_id"}
        return CatalogMirror.model_validate(data)


# ── Singleton accessor ─────────────────────────────────────────────────────


_store: ModelCatalogStore | None = None
_store_lock = asyncio.Lock()


async def get_model_catalog_store() -> ModelCatalogStore:
    """Return the process-wide ModelCatalogStore singleton."""
    global _store
    if _store is None:
        async with _store_lock:
            if _store is None:
                _store = ModelCatalogStore()
    return _store


async def get_catalog() -> CatalogMirror:
    """Convenience wrapper used by the GET /api/catalog/models endpoint."""
    store = await get_model_catalog_store()
    return await store.get_catalog()


async def sync_catalog(*, actor: str = "sync") -> CatalogMirror:
    """Convenience wrapper used by the POST sync endpoint + background loop."""
    store = await get_model_catalog_store()
    return await store.sync_catalog(actor=actor)


def invalidate_catalog_cache() -> None:
    """Clear the singleton's cache (used by tests)."""
    global _store
    if _store is not None:
        _store.invalidate()


def is_catalog_enabled() -> bool:
    """Check the runtime flag (default OFF).

    When False, the ``GET /api/catalog/models`` endpoint returns 503 and
    the background sync loop is a no-op. The flag is the rollout lever.
    """
    try:
        from packages.config import settings
        return settings.is_freellm_api_model_catalog_enabled
    except Exception:
        # Defensive: if settings can't be loaded, default to OFF.
        return False
