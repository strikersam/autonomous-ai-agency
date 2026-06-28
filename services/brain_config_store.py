"""services/brain_config_store.py — DB-persisted, UI-switchable "brain" config.

Implements the architectural change specified in
``docs/plans/db-brain-switcher.md`` (PR #824):

* One Pydantic ``BrainConfig`` model holds the active provider + the
  per-role (planner / executor / verifier / judge) model ids.
* Persistence is a single document in the ``app_settings`` Mongo
  collection keyed ``_id="brain_config"``, **mirrored to a sqlite row**
  so the no-Mongo CI/dev path still works. This mirrors the dual-storage
  pattern used by ``key_store.py`` and the company-graph store.
* An in-process cache with a short TTL (5s) + explicit ``invalidate()``
  on write so a UI change is picked up by the next agent run without a
  restart — the core call-time resolution requirement of the plan.
* ``get_brain_config()`` never raises: on any store error it returns the
  safe default so a DB outage can never brick the agent loop.

The store deliberately keeps **only model ids and provider names** —
never API keys. Keys stay in env (``NVIDIA_API_KEY`` / ``CEREBRAS_API_KEY``
/ ``GROQ_API_KEY`` / ``OLLAMA_BASE``) so a leaked DB document does not
leak credentials.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Literal

from pydantic import BaseModel, Field

log = logging.getLogger("brain_config_store")

# ── Safe default ────────────────────────────────────────────────────────────
#
# The plan's hard constraint #1: "Never land on a dead model. Always keep a
# known-good fallback." The 49B Nemotron Super is the live-verified (2026-06-20
# probe) model the rest of the codebase already uses as its free-brain default
# (see ``brain_policy.DEFAULT_FREE_NVIDIA_MODEL``). A bad DB write or a corrupt
# config doc must never displace it.
SAFE_DEFAULT_PROVIDER: str = "nvidia"
SAFE_DEFAULT_MODEL: str = "nvidia/llama-3.3-nemotron-super-49b-v1.5"

# Provider ids the Brain card recognises. The Literal keeps the Pydantic model
# strict so a typo in the UI ("cerebrass") fails validation instead of
# silently storing an unusable provider.
BrainProvider = Literal["nvidia", "cerebras", "groq", "ollama"]

# Per-provider sensible presets surfaced by the UI's "presets" dropdown.
# Operators can still type any model id — these are just convenience defaults.
PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "cerebras": {
        "planner":   "qwen-3-coder-480b",
        "executor":  "qwen-3-coder-480b",
        "verifier":  "llama-3.3-70b",
        "judge":     "llama-3.3-70b",
    },
    "groq": {
        "planner":   "deepseek-r1-distill-llama-70b",
        "executor":  "llama-3.3-70b-versatile",
        "verifier":  "deepseek-r1-distill-llama-70b",
        "judge":     "llama-3.3-70b-versatile",
    },
    "nvidia": {
        "planner":   "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        "executor":  "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        "verifier":  "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        "judge":     "nvidia/llama-3.3-nemotron-super-49b-v1.5",
    },
    "ollama": {
        "planner":   "deepseek-r1:32b",
        "executor":  "qwen3-coder:30b",
        "verifier":  "deepseek-r1:32b",
        "judge":     "deepseek-r1:32b",
    },
}

# Env-var names each provider reads its API key from. Used by the GET endpoint
# to surface "key present" flags to the UI without exposing the key itself.
PROVIDER_KEY_ENV: dict[str, str | None] = {
    "nvidia":  "NVIDIA_API_KEY",
    "cerebras": "CEREBRAS_API_KEY",
    "groq":    "GROQ_API_KEY",
    "ollama":  None,  # local — no key
}

# Env-var name each provider reads its base URL from (optional override).
PROVIDER_BASE_URL_ENV: dict[str, str | None] = {
    "nvidia":   "NVIDIA_BASE_URL",
    "cerebras": "CEREBRAS_BASE_URL",
    "groq":     "GROQ_BASE_URL",
    "ollama":   "OLLAMA_BASE",
}

# Default public base URL for each provider (used when no env override).
PROVIDER_DEFAULT_BASE_URL: dict[str, str] = {
    "nvidia":   "https://integrate.api.nvidia.com",
    "cerebras": "https://api.cerebras.ai",
    "groq":     "https://api.groq.com/openai",
    "ollama":   "http://localhost:11434",
}


def resolve_hermes_base_url() -> str:
    """Resolve the base URL of the agency's own Hermes server.

    Precedence: ``HERMES_BASE_URL`` env → ``http://localhost:8100`` default.
    In docker-compose the backend gets ``HERMES_BASE_URL=http://hermes:8100``
    so the Hermes runtime (``services/hermes_server.py``) is reachable with no
    extra config. Sync + never raises; safe for the adapter's hot path.
    """
    return (os.environ.get("HERMES_BASE_URL") or "http://localhost:8100").strip().rstrip("/")


def resolve_ollama_base_url() -> str:
    """Resolve the Ollama base URL the UI controls — DB value wins over env.

    Precedence:
      1. The ``ollama_base_url`` saved from the Brain card (read synchronously
         from the sqlite mirror, which is written on every Apply even when Mongo
         is primary). This is how the operator points the brain at a local /
         tunnelled Ollama **from the UI, with no env/redeploy**.
      2. ``OLLAMA_BASE`` / ``OLLAMA_BASE_URL`` env (legacy / dev).
      3. ``http://localhost:11434`` default.

    Sync + never raises so it is safe to call from hot resolution paths
    (``provider_base_url``, ``brain_policy``, the internal-agent adapter).
    """
    try:
        cfg = BrainConfigStore()._load_sqlite_mirror()
        if cfg is not None:
            ui_url = (getattr(cfg, "ollama_base_url", "") or "").strip()
            if ui_url:
                return ui_url.rstrip("/")
    except Exception:  # pragma: no cover - defensive; never break resolution
        pass
    env_url = (os.environ.get("OLLAMA_BASE") or os.environ.get("OLLAMA_BASE_URL") or "").strip()
    return (env_url or "http://localhost:11434").rstrip("/")


def provider_base_url(provider: str) -> str:
    """Return the OpenAI-compatible base URL for *provider* (env- and UI-aware)."""
    # Ollama's base URL is UI-configurable (DB-persisted) so a local/tunnelled
    # Ollama can be the brain without touching Render env. DB value wins.
    if provider == "ollama":
        return resolve_ollama_base_url()
    env_key = PROVIDER_BASE_URL_ENV.get(provider)
    if env_key:
        v = (os.environ.get(env_key) or "").strip()
        if v:
            return v.rstrip("/")
    return PROVIDER_DEFAULT_BASE_URL.get(provider, "")


def provider_api_key(provider: str) -> str | None:
    """Return the live API key for *provider* (env-only — never persisted)."""
    env_key = PROVIDER_KEY_ENV.get(provider)
    if not env_key:
        return None
    return (os.environ.get(env_key) or "").strip() or None


def provider_key_present(provider: str) -> bool:
    """True when the env var for *provider*'s key is set (or it's Ollama)."""
    if provider == "ollama":
        return True
    return bool(provider_api_key(provider))


# ── Pydantic model ──────────────────────────────────────────────────────────


class BrainConfig(BaseModel):
    """The agency's active brain — provider + per-role models.

    Stored as a single document. All fields are model ids / provider names —
    no API keys. ``max_tokens`` is the planner/executor budget; the verifier
    and judge get smaller budgets hardcoded in ``agent/loop.py``.
    """

    primary_provider: BrainProvider = Field(
        default=SAFE_DEFAULT_PROVIDER,
        description="Which provider's endpoint the brain routes to",
    )
    planner_model: str = Field(default=SAFE_DEFAULT_MODEL, min_length=1, max_length=200)
    executor_model: str = Field(default=SAFE_DEFAULT_MODEL, min_length=1, max_length=200)
    verifier_model: str = Field(default=SAFE_DEFAULT_MODEL, min_length=1, max_length=200)
    judge_model: str = Field(default=SAFE_DEFAULT_MODEL, min_length=1, max_length=200)
    max_tokens: int = Field(default=4096, ge=256, le=32768)
    # UI-configurable Ollama base URL (a tunnel URL when the brain runs on a
    # local/remote Ollama). Empty → fall back to OLLAMA_BASE env / localhost.
    # Lets the operator point the brain at their own GPU from the Brain card
    # with no Render env edit. Never holds a secret.
    ollama_base_url: str = Field(default="", max_length=300)
    updated_at: str = Field(default="")
    updated_by: str = Field(default="")


def default_brain_config() -> BrainConfig:
    """Return the safe-default brain (used on first boot + store errors)."""
    return BrainConfig()


# Priority order for auto-selecting the default brain when no config has been
# saved yet: the recommended free-cloud chain (Cerebras → Groq → NVIDIA NIM).
# The first provider whose API key is present in env wins. Cerebras leads because
# it serves even the 480B Qwen3-Coder at wafer-scale speed (no 480B latency tax)
# on a generous, non-expiring free tier; Groq is the fast second; NIM is the
# always-on safe floor. Ollama is intentionally excluded — it's local and not
# reachable from the cloud backend, so it must be chosen explicitly in the UI.
RECOMMENDED_PROVIDER_PRIORITY: tuple[str, ...] = ("cerebras", "groq", "nvidia")


def recommended_brain_config() -> BrainConfig:
    """Return the recommended default brain based on which provider keys are present.

    Walks :data:`RECOMMENDED_PROVIDER_PRIORITY` and selects the first provider
    whose API key is configured in env, seeding the per-role models from
    :data:`PROVIDER_PRESETS`. Falls back to the safe NIM default when no cloud
    key is present. Never raises.

    This makes the agency self-configuring: drop a ``CEREBRAS_API_KEY`` into the
    Render env and the next agent run uses the recommended Cerebras chain with no
    UI click and no redeploy — while a saved UI config always takes precedence
    (this function is only consulted when no config has been persisted yet).
    """
    for provider in RECOMMENDED_PROVIDER_PRIORITY:
        if provider_api_key(provider):
            preset = PROVIDER_PRESETS.get(provider)
            if preset:
                return BrainConfig(
                    primary_provider=provider,  # type: ignore[arg-type]
                    planner_model=preset["planner"],
                    executor_model=preset["executor"],
                    verifier_model=preset["verifier"],
                    judge_model=preset["judge"],
                )
    return default_brain_config()


# ── Patch model ─────────────────────────────────────────────────────────────


class BrainConfigPatch(BaseModel):
    """Editable subset of ``BrainConfig`` sent by PATCH /admin/api/policy/brain.

    All fields are optional — only the supplied ones are merged. The store
    fills ``updated_at`` / ``updated_by`` automatically.
    """

    primary_provider: BrainProvider | None = None
    planner_model: str | None = Field(default=None, min_length=1, max_length=200)
    executor_model: str | None = Field(default=None, min_length=1, max_length=200)
    verifier_model: str | None = Field(default=None, min_length=1, max_length=200)
    judge_model: str | None = Field(default=None, min_length=1, max_length=200)
    max_tokens: int | None = Field(default=None, ge=256, le=32768)
    # Empty string is allowed (clears the override → fall back to env/localhost);
    # min_length is therefore 0, unlike the model fields.
    ollama_base_url: str | None = Field(default=None, max_length=300)


# ── Store ───────────────────────────────────────────────────────────────────

# Mongo collection + document key. The ``app_settings`` collection is the
# established home for single-doc settings (provider_policy lives in the
# ``providers`` collection for legacy reasons; app_settings is the cleaner
# new home, mirroring how scheduler_store / decisions_store keep their
# one-per-instance state).
_BRAIN_DOC_ID = "brain_config"
_BRAIN_COLLECTION = "app_settings"

# Cache TTL — short so a UI Apply is picked up within seconds, but non-zero so
# the hot agent loop doesn't hit the DB on every planner/executor call.
_CACHE_TTL_SECONDS = 5.0


class BrainConfigStore:
    """Dual-storage brain config store (Mongo primary, sqlite mirror).

    The store is a singleton accessed via ``get_brain_config_store()`` so the
    cache is shared process-wide. All public methods are async and never
    raise — on any storage error they fall back to the safe default.
    """

    def __init__(self) -> None:
        self._cache: BrainConfig | None = None
        self._cache_at: float = 0.0
        self._lock = asyncio.Lock()

    # ── Public API ──────────────────────────────────────────────────────

    async def get_brain_config(self) -> BrainConfig:
        """Return the active brain config.

        Resolution order:
          1. In-process cache (if fresh)
          2. Mongo ``app_settings`` doc
          3. Sqlite mirror (no-Mongo path)
          4. Safe default

        Never raises — a DB error returns the safe default so the agent loop
        can keep running. This is the plan's "Brain resolution is hot-path →
        never throw" mitigation.
        """
        # Fast path: cache hit.
        if self._cache is not None and (time.monotonic() - self._cache_at) < _CACHE_TTL_SECONDS:
            return self._cache

        async with self._lock:
            # Re-check after acquiring the lock (another coroutine may have
            # just refreshed).
            if self._cache is not None and (time.monotonic() - self._cache_at) < _CACHE_TTL_SECONDS:
                return self._cache

            cfg = await self._load_unlocked()
            self._cache = cfg
            self._cache_at = time.monotonic()
            return cfg

    async def set_brain_config(
        self,
        patch: BrainConfigPatch,
        *,
        actor: str,
    ) -> BrainConfig:
        """Merge *patch* into the current config and persist.

        Returns the applied config. Persists to Mongo (primary) and sqlite
        (mirror) so either backend can serve the next read. Invalidates the
        in-process cache so the next ``get_brain_config()`` reflects the
        write immediately (no restart needed).
        """
        async with self._lock:
            current = await self._load_unlocked()
            merged = current.model_copy(
                update={
                    k: v
                    for k, v in patch.model_dump(exclude_none=True).items()
                    if v is not None
                }
            )
            # Stamp audit fields.
            merged.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            merged.updated_by = (actor or "unknown")[:200]

            await self._persist_unlocked(merged)
            # Refresh cache so the next get() returns the new value immediately.
            self._cache = merged
            self._cache_at = time.monotonic()
            return merged

    def invalidate(self) -> None:
        """Clear the in-process cache.

        Called by the admin API after a successful PATCH (defensive — the
        write path already refreshes the cache) and by tests that patch the
        store directly.
        """
        self._cache = None
        self._cache_at = 0.0

    # ── Storage backends ────────────────────────────────────────────────

    async def _load_unlocked(self) -> BrainConfig:
        """Read the persisted config from Mongo (primary) or sqlite (mirror).

        Falls back to the safe default on any error.
        """
        # 1. Try Mongo.
        try:
            from backend.server import get_db  # local import — avoids cycle
            db = get_db()
            collection = getattr(db, _BRAIN_COLLECTION, None)
            if collection is None:
                # STORAGE_BACKEND=sqlite exposes a synthetic collection.
                raise RuntimeError(f"collection {_BRAIN_COLLECTION!r} not present")
            doc = await collection.find_one({"_id": _BRAIN_DOC_ID})
            if doc:
                return self._from_doc(doc)
        except Exception as exc:
            log.debug("brain_config_store: Mongo read failed (%s) — trying sqlite mirror", exc)

        # 2. Sqlite mirror (no-Mongo path / CI).
        try:
            cfg = self._load_sqlite_mirror()
            if cfg is not None:
                return cfg
        except Exception as exc:
            log.debug("brain_config_store: sqlite mirror read failed (%s) — using safe default", exc)

        # 3. No persisted config yet → recommended free-cloud chain based on
        # which provider keys are present (Cerebras → Groq → NIM), falling back
        # to the safe NIM default. A saved UI config (steps 1-2) always wins.
        return recommended_brain_config()

    async def _persist_unlocked(self, cfg: BrainConfig) -> None:
        """Persist *cfg* to Mongo (primary) and sqlite (mirror).

        Either backend failing is non-fatal — the other still serves reads.
        """
        # 1. Mongo (upsert).
        try:
            from backend.server import get_db
            db = get_db()
            collection = getattr(db, _BRAIN_COLLECTION, None)
            if collection is not None:
                doc = cfg.model_dump(mode="json")
                doc["_id"] = _BRAIN_DOC_ID
                await collection.update_one(
                    {"_id": _BRAIN_DOC_ID},
                    {"$set": doc},
                    upsert=True,
                )
        except Exception as exc:
            log.warning("brain_config_store: Mongo persist failed (%s) — sqlite mirror only", exc)

        # 2. Sqlite mirror (always — even when Mongo succeeds, so a later
        # Mongo outage can still serve reads from the mirror).
        try:
            self._save_sqlite_mirror(cfg)
        except Exception as exc:
            log.warning("brain_config_store: sqlite mirror persist failed (%s)", exc)

    # ── Sqlite mirror ───────────────────────────────────────────────────
    #
    # The mirror is a tiny JSON blob in a single-row sqlite table. We use the
    # aiosqlite connection that db/sqlite_store.py already manages when
    # STORAGE_BACKEND=sqlite, and a standalone fallback file otherwise so the
    # store still works in tests that don't boot the full DB stack.

    # The table name + row id are static class constants — never user input.
    # We inline them as string literals (rather than f-strings) so Bandit's
    # B608 hardcoded-SQL check doesn't flag a non-existent injection vector.
    # Mirror what db/sqlite_store.py does for its own internal tables.
    _MIRROR_TABLE = "brain_config_mirror"
    _MIRROR_ROW_ID = "brain_config"
    _MIRROR_DDL = (
        "CREATE TABLE IF NOT EXISTS brain_config_mirror "
        "(id TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )

    def _load_sqlite_mirror(self) -> BrainConfig | None:
        import sqlite3
        path = self._mirror_db_path()
        if not path or not os.path.isfile(path):
            return None
        conn = sqlite3.connect(path)
        try:
            cur = conn.cursor()
            cur.execute(self._MIRROR_DDL)
            cur.execute(
                "SELECT data FROM brain_config_mirror WHERE id = ?",
                (self._MIRROR_ROW_ID,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return BrainConfig.model_validate_json(row[0])
        finally:
            conn.close()

    def _save_sqlite_mirror(self, cfg: BrainConfig) -> None:
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
                "INSERT OR REPLACE INTO brain_config_mirror (id, data, updated_at) VALUES (?, ?, ?)",
                (
                    self._MIRROR_ROW_ID,
                    cfg.model_dump_json(),
                    cfg.updated_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def _mirror_db_path(self) -> str:
        # The mirror lives in its own file (``brain_config.db`` next to the
        # main agency DB) so a stale mirror can never collide with the
        # sqlite_store's tables, and tests that wipe /tmp dirs don't lose
        # the production brain config (and vice-versa).
        #
        # ``SQLITE_DB_PATH`` is honoured when set so test fixtures can point
        # the mirror at an isolated tmp dir.
        base = os.environ.get("SQLITE_DB_PATH", ".data/agency.db")
        # If the caller set a path that ends in .db, derive the brain mirror
        # name from it so tests get isolation for free.
        if base.endswith(".db"):
            return base[:-3] + "_brain.db"
        return base + "_brain.db"

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _from_doc(doc: dict[str, Any]) -> BrainConfig:
        """Build a ``BrainConfig`` from a Mongo doc, dropping Mongo's ``_id``."""
        data = {k: v for k, v in doc.items() if k != "_id"}
        return BrainConfig.model_validate(data)


# ── Singleton accessor ──────────────────────────────────────────────────────

_store: BrainConfigStore | None = None
_store_lock = asyncio.Lock()


async def get_brain_config_store() -> BrainConfigStore:
    """Return the process-wide ``BrainConfigStore`` singleton."""
    global _store
    if _store is None:
        async with _store_lock:
            if _store is None:
                _store = BrainConfigStore()
    return _store


async def get_brain_config() -> BrainConfig:
    """Convenience wrapper used by the agent loop + brain resolver."""
    store = await get_brain_config_store()
    return await store.get_brain_config()


async def set_brain_config(patch: BrainConfigPatch, *, actor: str) -> BrainConfig:
    """Convenience wrapper used by the admin API endpoints."""
    store = await get_brain_config_store()
    cfg = await store.set_brain_config(patch, actor=actor)
    # Also invalidate the brain_policy resolver cache so the next agent run
    # picks up the new provider/model immediately.
    try:
        from brain_policy import invalidate_brain_cache
        invalidate_brain_cache()
    except Exception:  # noqa: BLE001 — best-effort
        pass
    return cfg


def invalidate_brain_config_cache() -> None:
    """Clear the singleton's cache (used by tests + brain_policy invalidation)."""
    global _store
    if _store is not None:
        _store.invalidate()


# ── Role resolver (used by agent/loop.py at call time) ─────────────────────
#
# The plan's core change: move model resolution from import-time env
# (agent/loop.py:114-127) to a call-time resolver with precedence:
#
#     requested_model  →  BrainConfig (DB)  →  env var  →  safe default
#
# Synchronous variant ``resolve_role_model_sync`` is used by the hot agent
# loop to avoid an await on every planner/executor call. It reads the
# process-wide cache; if the cache is cold or stale it falls back to env /
# safe default rather than blocking on the DB — the async ``get_brain_config``
# refresh happens opportunistically in the background.

_ROLE_TO_DB_FIELD = {
    "planner": "planner_model",
    "executor": "executor_model",
    "verifier": "verifier_model",
    "judge": "judge_model",
}

_ROLE_TO_ENV_VAR = {
    "planner": "AGENT_PLANNER_MODEL",
    "executor": "AGENT_EXECUTOR_MODEL",
    "verifier": "AGENT_VERIFIER_MODEL",
    "judge": "AGENT_JUDGE_MODEL",
}

# The "shared" env override the existing import-time constants consult.
_ROLE_TO_FALLBACK_ENV_VAR = {
    "planner": "NVIDIA_DEFAULT_MODEL",
    "verifier": "NVIDIA_DEFAULT_MODEL",
    # executor + judge have no NVIDIA_DEFAULT_MODEL fallback in the
    # existing code — they go straight to the safe default.
}


def resolve_role_model_sync(role: str, requested: str | None = None) -> str:
    """Synchronous call-time resolver for an agent role model id.

    Precedence (highest to lowest):
      1. ``requested`` — the per-call override (e.g. a sub-agent config)
      2. BrainConfig DB field for this role (if cache is fresh)
      3. Env var (``AGENT_<ROLE>_MODEL``)
      4. Safe default (``nvidia/llama-3.3-nemotron-super-49b-v1.5``)

    Never raises — returns the safe default on any error so the agent loop
    can keep running even if the cache is in a weird state.
    """
    # 1. Per-call override wins.
    if requested and requested.strip():
        return requested.strip()

    field = _ROLE_TO_DB_FIELD.get(role)
    if field:
        # 2. BrainConfig cache (if fresh).
        try:
            if _store is not None and _store._cache is not None:
                if (time.monotonic() - _store._cache_at) < _CACHE_TTL_SECONDS:
                    val = getattr(_store._cache, field, None)
                    if val and val.strip():
                        return val.strip()
        except Exception:  # noqa: BLE001 — defensive
            pass

    # 3. Env var (kept working so nothing regresses).
    env_var = _ROLE_TO_ENV_VAR.get(role)
    if env_var:
        v = (os.environ.get(env_var) or "").strip()
        if v:
            return v
    fallback_env = _ROLE_TO_FALLBACK_ENV_VAR.get(role)
    if fallback_env:
        v = (os.environ.get(fallback_env) or "").strip()
        if v:
            return v

    # 4. Safe default.
    return SAFE_DEFAULT_MODEL


async def resolve_role_model(role: str, requested: str | None = None) -> str:
    """Async variant — refreshes the cache if stale before resolving.

    Used by code paths that already await (the workflow orchestrator). The
    hot ``AgentRunner`` loop uses the sync variant to avoid an await per
    step.
    """
    if requested and requested.strip():
        return requested.strip()
    try:
        await get_brain_config()  # refreshes cache if stale
    except Exception:  # noqa: BLE001 — never block resolution
        pass
    return resolve_role_model_sync(role, requested)


async def refresh_brain_config_cache() -> BrainConfig:
    """Force a cache refresh (used by tests + the GET /admin/api/policy/brain endpoint)."""
    store = await get_brain_config_store()
    store.invalidate()
    return await store.get_brain_config()
