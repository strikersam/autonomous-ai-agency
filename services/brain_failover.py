"""services/brain_failover.py — Universal multi-provider brain failover system.

Solves the recurring NVIDIA 429/410 rate-limit problem by treating EVERY
configured provider as a potential brain. When the active provider returns
429 (rate-limited), 410 (gone), or 5xx (server error), this module marks
it as unhealthy with a cooldown period and returns the next healthy
provider in priority order.

Design:
  * **Provider registry**: every provider with an API key in env is a
    candidate brain. The registry is built at call time (not import time)
    so env vars set after boot are honoured.
  * **Circuit breaker**: each provider has a health state — CLOSED
    (healthy), OPEN (rate-limited, in cooldown), HALF_OPEN (cooldown
    expired, next call is a probe). Cooldown is provider-specific
    (NVIDIA gets 60s, others 30s) and doubles on consecutive failures.
  * **Intelligent ordering**: free providers are tried first (nvidia,
    groq, cerebras, zhipu, deepseek, together, dashscope, moonshot),
    then paid (anthropic, openrouter, minimax, google), then local
    (ollama). Within each tier, the provider with the best recent
    latency wins.
  * **Model mapping**: each provider has a default model + a set of
    aliases so the agent's requested model is mapped to the provider's
    equivalent (e.g. "meta/llama-3.3-70b-instruct" on nvidia →
    "llama-3.3-70b-versatile" on groq).
  * **Observability**: /api/brain/failover/status returns the full health
    snapshot for debugging.

Usage in agent/loop.py::

    from services.brain_failover import get_failover_manager

    fm = get_failover_manager()
    for attempt in range(fm.max_attempts()):
        provider = fm.next_provider(exclude=tried)
        if provider is None:
            raise RuntimeError("No healthy brain provider")
        resp = await call_provider(provider, ...)
        if resp.status_code == 429:
            fm.record_failure(provider.id, "rate_limited")
            continue
        if resp.status_code == 410:
            fm.record_failure(provider.id, "gone")
            continue
        if resp.status_code >= 500:
            fm.record_failure(provider.id, "server_error")
            continue
        fm.record_success(provider.id)
        return resp.json()
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("qwen-proxy")


# ── Durable operator state, read from the sync hot path ───────────────────
#
# Two operator-controlled settings gate which providers the failover layer may
# use: the per-provider kill switch (below) and the paid-provider policy. Both
# are read from ``next_provider`` / ``_build_registry``, which run inside the
# event loop and cannot await — so motor is unusable here and pymongo's sync
# client is used instead.
#
# Why Mongo at all, when a local SQLite kv_store already worked: Render's disk is
# ephemeral. State written only to that file is wiped on every deploy, which
# silently re-enabled providers the operator had switched off and reverted the
# paid-provider toggle to false. Mongo is the durable copy; SQLite remains the
# dev/CI backend and a warm local mirror for when Mongo is unreachable.
#
# Three guards keep a slow or dead Mongo from stalling dispatch:
#   * a short read cache (5s for the kill switch, 10s for the paid policy),
#   * a short server-selection timeout (MONGO_SELECTION_TIMEOUT_MS, default 2s),
#   * a 60s backoff after any Mongo error, during which SQLite serves alone.

_PAID_CACHE: tuple[bool, float] = (False, 0.0)
_PAID_CACHE_TTL = 10.0  # seconds — short so the UI toggle takes effect quickly

_KV_COLLECTION = "kv_store"
_PAID_POLICY_KEY = "provider_policy:allow_paid"

_mongo_client: Any = None
_mongo_client_lock = threading.Lock()
_mongo_retry_after: float = 0.0
_MONGO_BACKOFF_SEC = 60.0
_TRUTHY = ("true", "1", "yes", "on")


def _mongo_unavailable(exc: Exception) -> None:
    """Open a short backoff so an unreachable Mongo costs one stall, not many."""
    global _mongo_retry_after
    _mongo_retry_after = time.time() + _MONGO_BACKOFF_SEC
    log.warning(
        "brain_failover: Mongo kv unavailable (%s) — serving operator state from "
        "the local SQLite mirror for %.0fs",
        exc, _MONGO_BACKOFF_SEC,
    )


def _mongo_enabled() -> bool:
    """True when the durable Mongo copy should be used for operator state.

    ``MONGO_URL`` must be set explicitly: the storage layer's default of
    ``mongodb://localhost:27017`` is a placeholder, and treating it as
    configured would add a connection timeout to dispatch on every dev machine
    without a local Mongo. ``TESTING`` disables the path outright so the test
    suite can never mutate a shared operational store.
    """
    if os.environ.get("TESTING", "").strip().lower() in _TRUTHY:
        return False
    if os.environ.get("STORAGE_BACKEND", "mongo").strip().lower() != "mongo":
        return False
    if not (os.environ.get("MONGO_URL") or "").strip():
        return False
    return time.time() >= _mongo_retry_after


def _mongo_db() -> Any:
    """Return a sync pymongo database handle, or ``None`` when unavailable."""
    global _mongo_client
    if not _mongo_enabled():
        return None
    try:
        with _mongo_client_lock:
            if _mongo_client is None:
                from pymongo import MongoClient
                timeout = int(os.environ.get("MONGO_SELECTION_TIMEOUT_MS", "2000"))
                _mongo_client = MongoClient(
                    os.environ["MONGO_URL"],
                    serverSelectionTimeoutMS=timeout,
                    connectTimeoutMS=timeout,
                    socketTimeoutMS=timeout,
                )
        return _mongo_client[os.environ.get("DB_NAME", "llm_platform")]
    except Exception as exc:  # noqa: BLE001 — never brick dispatch on kv failure
        _mongo_unavailable(exc)
        return None


def state_is_durable() -> bool:
    """True when operator state is stored somewhere that survives a redeploy.

    False means the only copy is the local SQLite file. On a host with an
    ephemeral disk (Render) that copy is wiped on every deploy, so switched-off
    providers rejoin the rotation and the paid-provider toggle reverts. The
    Providers screen shows this so the cause is visible rather than mysterious.
    """
    return _mongo_db() is not None


def reset_kv_state() -> None:
    """Drop the cached Mongo client, backoff, and read caches (tests)."""
    global _mongo_client, _mongo_retry_after, _DISABLED_CACHE, _PAID_CACHE
    with _mongo_client_lock:
        client, _mongo_client = _mongo_client, None
    if client is not None:
        try:
            client.close()
        except Exception:  # noqa: BLE001
            pass
    _mongo_retry_after = 0.0
    _DISABLED_CACHE = ({}, 0.0)
    _PAID_CACHE = (False, 0.0)


# ── Per-provider enable/disable (operator-controlled kill switch) ─────────
#
# A provider whose key is invalid, whose account is out of credit, or whose model
# the account cannot access will fail identically forever. Leaving it in the
# rotation costs a wasted attempt on every single call and buries the providers
# that do work. Those states are auto-disabled here and require an explicit
# manual re-enable, because only a human can actually fix them.
#
# Transient states are deliberately NOT auto-disabled: 429 (quota refills), 5xx,
# and network errors already have circuit breakers and cooldowns, and disabling
# on a 429 would permanently switch off every free provider the first time a
# burst hit a rate limit — strictly worse than the problem it solves.
_DISABLED_KEY_PREFIX = "provider_disabled:"
_DISABLED_CACHE: tuple[dict[str, str], float] = ({}, 0.0)
_DISABLED_CACHE_TTL = 5.0


def _kv_path() -> str:
    return os.environ.get("SQLITE_PATH", ".data/agency.db")


def _kv_connect():
    import sqlite3
    conn = sqlite3.connect(_kv_path())
    conn.execute(
        "CREATE TABLE IF NOT EXISTS kv_store (key TEXT PRIMARY KEY, value TEXT)"
    )
    return conn


def _disabled_from_sqlite() -> dict[str, str]:
    """Read the kill-switch set from the local SQLite mirror. Raises on error."""
    conn = _kv_connect()
    rows = conn.execute(
        "SELECT key, value FROM kv_store WHERE key LIKE ?",
        (_DISABLED_KEY_PREFIX + "%",),
    ).fetchall()
    conn.close()
    out: dict[str, str] = {}
    for key, value in rows:
        pid = key[len(_DISABLED_KEY_PREFIX):]
        if pid and value:
            out[pid] = value
    return out


def _disabled_from_mongo() -> dict[str, str] | None:
    """Read the kill-switch set from Mongo, or ``None`` when unavailable."""
    db = _mongo_db()
    if db is None:
        return None
    try:
        docs = list(db[_KV_COLLECTION].find({"kind": "provider_disabled"}))
    except Exception as exc:  # noqa: BLE001
        _mongo_unavailable(exc)
        return None
    out: dict[str, str] = {}
    for doc in docs:
        pid = str(doc.get("_id", ""))[len(_DISABLED_KEY_PREFIX):]
        value = doc.get("value")
        if pid and value:
            out[pid] = str(value)
    return out


def disabled_providers(force: bool = False) -> dict[str, str]:
    """Return ``{provider_id: reason}`` for every disabled provider.

    Mongo is authoritative when configured, because it is the only copy that
    survives a Render deploy. SQLite serves when Mongo is off (dev/CI) or in
    backoff. Cached briefly so the hot path does not hit storage on every
    attempt, and never raises — a storage problem must not take the brain
    offline, so the last known set is returned instead.
    """
    global _DISABLED_CACHE
    cached, at = _DISABLED_CACHE
    if not force and (time.time() - at) < _DISABLED_CACHE_TTL:
        return cached
    out = _disabled_from_mongo()
    if out is None:
        try:
            out = _disabled_from_sqlite()
        except Exception as exc:  # noqa: BLE001
            log.debug("brain_failover: disabled-provider read failed: %s", exc)
            return cached
    _DISABLED_CACHE = (out, time.time())
    return out


def _write_disabled_sqlite(provider_id: str, enabled: bool, reason: str) -> None:
    """Mirror the kill switch to SQLite. Raises on error."""
    conn = _kv_connect()
    key = _DISABLED_KEY_PREFIX + provider_id
    if enabled:
        conn.execute("DELETE FROM kv_store WHERE key = ?", (key,))
    else:
        conn.execute(
            "INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)",
            (key, reason),
        )
    conn.commit()
    conn.close()


def _write_disabled_mongo(provider_id: str, enabled: bool, reason: str) -> bool | None:
    """Persist the kill switch to Mongo. ``None`` when Mongo is not in use."""
    db = _mongo_db()
    if db is None:
        return None
    key = _DISABLED_KEY_PREFIX + provider_id
    try:
        if enabled:
            db[_KV_COLLECTION].delete_one({"_id": key})
        else:
            db[_KV_COLLECTION].update_one(
                {"_id": key},
                {"$set": {
                    "value": reason,
                    "kind": "provider_disabled",
                    "provider_id": provider_id,
                    "updated_at": time.time(),
                }},
                upsert=True,
            )
        return True
    except Exception as exc:  # noqa: BLE001
        _mongo_unavailable(exc)
        return False


def set_provider_enabled(provider_id: str, enabled: bool, reason: str = "") -> None:
    """Enable or disable *provider_id*, persisted across restarts and deploys.

    Written to both stores: Mongo so the setting survives a redeploy, SQLite so
    a Mongo outage still leaves this process with the operator's intent. A
    failure of either store is logged, never raised.
    """
    global _DISABLED_CACHE
    reason = reason or "disabled by operator"
    durable = _write_disabled_mongo(provider_id, enabled, reason)
    try:
        _write_disabled_sqlite(provider_id, enabled, reason)
        local_ok = True
    except Exception as exc:  # noqa: BLE001
        local_ok = False
        log.warning("brain_failover: could not mirror %s enabled=%s to SQLite: %s",
                    provider_id, enabled, exc)
    # ``durable`` is None when Mongo is not in use at all, so "nothing was
    # written" is `not local_ok and durable is not True` — not `durable is False`.
    # Claiming the switch took effect when neither store accepted it would leave
    # the operator trusting a setting that vanishes on the next cache expiry.
    if not local_ok and durable is not True:
        log.error("brain_failover: %s enabled=%s was not persisted anywhere",
                  provider_id, enabled)
        return
    if durable is False:
        log.warning("brain_failover: %s enabled=%s saved locally only — it will "
                    "revert on the next deploy", provider_id, enabled)
    _DISABLED_CACHE = ({}, 0.0)  # force re-read
    log.info("brain_failover: provider %s %s%s", provider_id,
             "ENABLED" if enabled else "DISABLED",
             "" if enabled else f" ({reason})")


def auto_disable_provider(provider_id: str, reason: str) -> None:
    """Disable a provider that failed in a way only a human can fix.

    Idempotent, and never overwrites an existing reason so the first (usually
    most specific) diagnosis is what the operator sees in the UI.
    """
    if provider_id in disabled_providers():
        return
    set_provider_enabled(provider_id, False, f"auto: {reason}")


# Stored reasons are written by ``packages/ai/failover_client._auto_disable`` and
# there are exactly four shapes, plus the manual switch-off. Mapping them here —
# in the module that owns the disabled state — keeps the wording in one place
# instead of a parallel table in the UI that drifts when a reason string changes.
# ``summary`` says what is wrong, ``action`` says what the operator must do, and
# the raw reason is always returned too so nothing is hidden by a failed match.
_REASON_TABLE: tuple[tuple[str, str, str], ...] = (
    ("invalid or expired api key", "Invalid or expired API key",
     "Update the key, then switch it back on."),
    ("out of credit/quota", "Out of credit or quota",
     "Top up the account or wait for the quota to reset, then switch it back on."),
    ("out of credit", "No credit left on the account",
     "Top up the account, then switch it back on."),
    ("no accessible model", "Account cannot access any of this provider's models",
     "Check the account's model entitlements or set a model it can reach."),
)


def describe_disabled_reason(reason: str) -> dict[str, str]:
    """Render a stored disable reason for display.

    Returns ``code`` (the HTTP status that caused it, when the reason carries
    one), ``summary``, ``action``, ``auto`` and the untouched ``reason``. An
    unrecognised reason is passed through as its own summary rather than being
    dropped — a reason the operator cannot read is still better than none.
    """
    raw = (reason or "").strip()
    if not raw:
        return {"code": "", "summary": "", "action": "", "auto": False, "reason": ""}
    auto = raw.startswith("auto:")
    body = raw[len("auto:"):].strip() if auto else raw
    code = ""
    head = body.split(None, 1)[0] if body else ""
    if head.isdigit() and len(head) == 3:
        code, body = head, body[len(head):].strip()
    else:
        # "no accessible model (404 model_not_found)" carries its code inline.
        match = re.search(r"\((\d{3})\b", body)
        if match:
            code = match.group(1)
    lowered = body.lower()
    for needle, summary, action in _REASON_TABLE:
        if needle in lowered:
            return {"code": code, "summary": summary, "action": action,
                    "auto": auto, "reason": raw}
    if not auto:
        return {"code": code, "summary": "Turned off manually",
                "action": "Switch it back on when you want it in the rotation.",
                "auto": False, "reason": raw}
    return {"code": code, "summary": body or raw, "action": "", "auto": True,
            "reason": raw}


def _paid_allowed_mongo() -> bool | None:
    """Read the paid-provider policy from Mongo, or ``None`` when unavailable.

    Checks the ``providers`` document that ``_set_provider_policy`` writes —
    that is the durable record the UI toggle updates — and falls back to the
    mirrored kv key for policies written before the document existed.
    """
    db = _mongo_db()
    if db is None:
        return None
    try:
        doc = db.providers.find_one({"provider_id": "provider_policy"})
        if doc is not None and "allow_paid" in doc:
            return bool(doc.get("allow_paid"))
        kv = db[_KV_COLLECTION].find_one({"_id": _PAID_POLICY_KEY})
    except Exception as exc:  # noqa: BLE001
        _mongo_unavailable(exc)
        return None
    if kv and kv.get("value") is not None:
        return str(kv["value"]).strip().lower() in _TRUTHY
    return False


def _paid_allowed_sqlite() -> bool | None:
    """Read the paid-provider policy from the SQLite mirror, or ``None``."""
    db_path = _kv_path()
    if not os.path.exists(db_path):
        return None
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT value FROM kv_store WHERE key = ?", (_PAID_POLICY_KEY,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return str(row[0]).strip().lower() in _TRUTHY


def _is_paid_allowed_db() -> bool:
    """Check if the DB-stored provider policy allows paid providers.

    Sync + never raises. Mongo is authoritative when configured so the toggle
    survives a redeploy; the SQLite mirror serves dev/CI and Mongo outages.
    Cached for 10s so the hot path (every LLM call) doesn't hit the DB.
    """
    global _PAID_CACHE
    now = time.time()
    cached_val, cached_at = _PAID_CACHE
    if now - cached_at < _PAID_CACHE_TTL:
        return cached_val

    val = _paid_allowed_mongo()
    if val is None:
        try:
            val = _paid_allowed_sqlite()
        except Exception:  # noqa: BLE001 — a kv problem must not enable paid spend
            val = None
    _PAID_CACHE = (bool(val), now)
    return bool(val)


# ── Provider definitions ─────────────────────────────────────────────────

# Anti-wedge valve thresholds. A provider is treated as stuck (rather than
# legitimately cooling) only when its cooldown window is wider than any it could
# have earned. record_failure caps the 429 backoff exponent at 4, so the widest
# legitimate window is `cooldown_seconds * 2**4`; the factor is double that cap
# so the valve can never fire on a healthy backoff ladder. NVIDIA has the
# largest base in the registry at 90s → a real ladder tops out at 1440s, well
# under its 2880s threshold.
_STUCK_PROBE_FACTOR: float = 32.0
_STUCK_PROBE_FLOOR_SEC: float = 900.0


class ProviderHealth(Enum):
    """Circuit-breaker state for a provider."""
    CLOSED = "closed"      # healthy — accepting traffic
    OPEN = "open"          # rate-limited/erroring — in cooldown
    HALF_OPEN = "half_open"  # cooldown expired — next call is a probe


@dataclass
class ProviderInfo:
    """A configured LLM provider with its connection details + health state."""
    id: str
    name: str
    tier: str  # "free" | "paid" | "local"
    base_url: str
    api_key: str
    default_model: str
    # Name of the environment variable this provider's key came from. Carried so
    # the key pool can find sibling keys (`<key_env>_2`, `_3`, …) for rotation
    # without re-deriving the variable name from the provider id — several ids
    # would not round-trip, and a wrong guess silently means "no extra keys".
    key_env: str = ""
    # Models this provider serves. The failover layer maps the requested
    # model to the closest match on this provider.
    models: list[str] = field(default_factory=list)
    # Health state
    health: ProviderHealth = ProviderHealth.CLOSED
    failure_count: int = 0
    last_failure: float = 0.0
    last_success: float = 0.0
    cooldown_until: float = 0.0
    cooldown_seconds: float = 60.0
    # Latency tracking (exponential moving average)
    avg_latency_ms: float = 0.0
    total_calls: int = 0
    total_failures: int = 0
    last_error: str = ""

    @property
    def is_healthy(self) -> bool:
        """True when the provider can accept traffic right now."""
        if self.health == ProviderHealth.CLOSED:
            return True
        if self.health == ProviderHealth.OPEN:
            if time.time() >= self.cooldown_until:
                # Cooldown expired — transition to HALF_OPEN on next call
                self.health = ProviderHealth.HALF_OPEN
                return True
            return False
        if self.health == ProviderHealth.HALF_OPEN:
            return True  # allow one probe call
        return True


# ── Provider registry ────────────────────────────────────────────────────

# All providers we know how to route to. Each entry maps the provider id to
# its env-var name, base URL, default model, and tier.
_PROVIDER_REGISTRY: list[dict[str, Any]] = [
    # ── Free tier (tried first) ──
    {
        "id": "nvidia",
        "name": "NVIDIA NIM",
        "tier": "free",
        "key_env": "NVIDIA_API_KEY",
        "base_url_env": "NVIDIA_BASE_URL",
        "default_base_url": "https://integrate.api.nvidia.com",
        "default_model": "meta/llama-3.3-70b-instruct",
        "models": [
            "meta/llama-3.3-70b-instruct",
            "meta/llama-4-maverick-17b-128e-instruct",
            "meta/llama-4-scout-17b-16e-instruct",
            "z-ai/glm-5.2",
            "z-ai/glm-5.1",
            "nvidia/llama-3.1-nemotron-70b-instruct",
            "meta/llama-3.1-8b-instruct",
            "deepseek-ai/deepseek-r1",
        ],
        "cooldown": 90.0,  # NVIDIA rate limits are ~40 req/min — 90s cooldown
    },
    {
        # tokenin.my.id — free OpenAI-compatible gateway fronting a rotating pool
        # of frontier models. Keep this list in sync with config/models.yaml and
        # packages/ai/brain_config.PROVIDER_CANDIDATES["tokenin"].
        "id": "tokenin",
        "name": "TokenIn (free frontier gateway)",
        "tier": "free",
        "key_env": "TOKENIN_API_KEY",
        "base_url_env": "TOKENIN_BASE_URL",
        "default_base_url": "https://tokenin.my.id/v1",
        "default_model": "myt/glm-5.3-free",
        "models": [
            "myt/glm-5.3-free",
            "myt/deepseek-v4-pro-free",
            "myt/MiniMax-M3-free",
            "myt/mimo-v2.5-free",
            "myt/qwen3.8-max-free",
            "myt/kimi-k3-free",
            "myt/gemini-3.5-flash-free",
            "myt/grok-4.6-free",
            "myt/gpt-5.6-sol-free",
            "myt/claude-opus-4-8-free",
        ],
        # Per-model caps are low (2–7 req/min); cool a spent model briefly so the
        # rotation moves on rather than parking the whole gateway.
        "cooldown": 45.0,
    },
    {
        "id": "groq",
        "name": "Groq",
        "tier": "free",
        "key_env": "GROQ_API_KEY",
        "base_url_env": "GROQ_BASE_URL",
        "default_base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "models": [
            "llama-4-maverick-17b-128e-instruct",
            "llama-4-scout-17b-16e-instruct",
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "deepseek-r1-distill-llama-70b",
        ],
        "cooldown": 30.0,
    },
    {
        "id": "cerebras",
        "name": "Cerebras",
        "tier": "free",
        "key_env": "CEREBRAS_API_KEY",
        "base_url_env": "CEREBRAS_BASE_URL",
        "default_base_url": "https://api.cerebras.ai",
        "default_model": "llama-3.3-70b",
        "models": ["llama-3.3-70b", "llama-3.1-8b", "qwen-3-coder-480b"],
        "cooldown": 30.0,
    },
    {
        "id": "zhipu",
        "name": "ZhipuAI (GLM)",
        "tier": "free",
        "key_env": "ZHIPU_API_KEY",
        "base_url_env": "ZHIPU_BASE_URL",
        "default_base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
        "models": ["glm-4-flash", "glm-4", "glm-4-air", "glm-5.2", "glm-5.1"],
        "cooldown": 30.0,
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "tier": "free",
        "key_env": "DEEPSEEK_API_KEY",
        "base_url_env": "DEEPSEEK_BASE_URL",
        "default_base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "models": ["deepseek-chat", "deepseek-reasoner", "deepseek-coder"],
        "cooldown": 30.0,
    },
    {
        "id": "together",
        "name": "Together AI",
        "tier": "free",
        "key_env": "TOGETHER_API_KEY",
        "base_url_env": "TOGETHER_BASE_URL",
        "default_base_url": "https://api.together.xyz/v1",
        "default_model": "Llama-3.3-70B-Instruct-Turbo-Free",
        "models": ["Llama-3.3-70B-Instruct-Turbo-Free", "Mixtral-8x7B-Instruct-v0.1-Free"],
        "cooldown": 30.0,
    },
    {
        "id": "dashscope",
        "name": "Qwen DashScope",
        "tier": "free",
        "key_env": "DASHSCOPE_API_KEY",
        "base_url_env": "DASHSCOPE_BASE_URL",
        "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "models": ["qwen-plus", "qwen-max", "qwen-turbo", "qwen-coder-plus"],
        "cooldown": 30.0,
    },
    {
        "id": "moonshot",
        "name": "Moonshot (Kimi)",
        "tier": "free",
        "key_env": "MOONSHOT_API_KEY",
        "base_url_env": "MOONSHOT_BASE_URL",
        "default_base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        "cooldown": 30.0,
    },
    {
        "id": "zai",
        "name": "Z.ai (GLM international)",
        "tier": "free",
        "key_env": "ZAI_API_KEY",
        "base_url_env": "ZAI_BASE_URL",
        "default_base_url": "https://api.z.ai/api/paas/v4",
        "default_model": "glm-5.2",
        "models": ["glm-5.2", "glm-5.1", "glm-4-flash", "glm-4", "glm-4-air"],
        "cooldown": 30.0,
    },
    {
        "id": "mistral",
        "name": "Mistral",
        "tier": "free",
        "key_env": "MISTRAL_API_KEY",
        "base_url_env": "MISTRAL_BASE_URL",
        "default_base_url": "https://api.mistral.ai/v1",
        "default_model": "mistral-small-latest",
        "models": ["mistral-small-latest", "mistral-large-latest", "codestral-latest", "mistral-nemo"],
        "cooldown": 30.0,
    },
    # ── Paid tier (tried last, only if ALLOW_PAID_BRAIN=true) ──
    {
        "id": "aerolink",
        "name": "Aerolink (Claude gateway)",
        "tier": "paid",
        "key_env": "AEROLINK_API_KEY",
        "base_url_env": "AEROLINK_BASE_URL",
        "default_base_url": "https://capi.aerolink.lat/v1",
        "default_model": "claude-sonnet-4-6",
        "models": [
            "claude-opus-4-8",
            "claude-opus-4-7",
            "claude-opus-4-6",
            "claude-fable-5",
            "claude-sonnet-5",
            "claude-sonnet-4-6",
            "claude-haiku-4-5-20251001",
        ],
        "cooldown": 30.0,
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "tier": "paid",
        "key_env": "OPENROUTER_API_KEY",
        "base_url_env": "OPENROUTER_BASE_URL",
        "default_base_url": "https://openrouter.ai/api/v1",
        "default_model": "meta-llama/llama-3.3-70b-instruct",
        "models": ["meta-llama/llama-3.3-70b-instruct", "anthropic/claude-3.5-sonnet"],
        "cooldown": 30.0,
    },
    {
        "id": "minimax",
        "name": "MiniMax",
        "tier": "paid",
        "key_env": "MINIMAX_API_KEY",
        "base_url_env": "MINIMAX_BASE_URL",
        "default_base_url": "https://api.minimax.chat/v1",
        "default_model": "MiniMax-Text-01",
        "models": ["MiniMax-Text-01", "abab6.5s-chat"],
        "cooldown": 30.0,
    },
    {
        "id": "google",
        "name": "Google Gemini",
        "tier": "paid",
        "key_env": "GOOGLE_API_KEY",
        "base_url_env": "GOOGLE_BASE_URL",
        # Gemini's OpenAI-compatible surface lives under /v1beta/openai. The bare
        # host resolves to .../v1/chat/completions, which Gemini does not serve —
        # this must stay in sync with config/models.yaml and
        # packages/ai/brain_config.PROVIDER_DEFAULT_BASE_URL, which both use the
        # /v1beta/openai form.
        "default_base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "default_model": "gemini-2.5-flash",
        "models": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
        "cooldown": 30.0,
    },
    {
        "id": "anthropic",
        "name": "Anthropic (Claude)",
        "tier": "paid",
        "key_env": "ANTHROPIC_API_KEY",
        "base_url_env": "ANTHROPIC_BASE_URL",
        "default_base_url": "https://api.anthropic.com",
        "default_model": "claude-sonnet-5",
        "models": ["claude-sonnet-5", "claude-opus-4-8", "claude-fable-5", "claude-haiku-4-5-20251001", "claude-sonnet-4-6"],
        "cooldown": 30.0,
    },
    # ── Local (always available if configured) ──
    {
        "id": "ollama",
        "name": "Local Ollama",
        "tier": "local",
        "key_env": None,
        "base_url_env": "OLLAMA_BASE",
        "default_base_url": "http://localhost:11434",
        "default_model": "llama3.3:70b",
        "models": ["llama3.3:70b", "qwen2.5-coder:32b", "deepseek-r1:32b"],
        "cooldown": 10.0,
    },
]

# Model alias mapping — when the requested model isn't on the provider, map
# it to the closest equivalent. This is what makes "I want llama-3.3-70b" work
# across nvidia, groq, cerebras, together, etc.
_MODEL_ALIASES: dict[str, dict[str, str]] = {
    "meta/llama-3.3-70b-instruct": {
        "groq": "llama-3.3-70b-versatile",
        "cerebras": "llama-3.3-70b",
        "together": "Llama-3.3-70B-Instruct-Turbo-Free",
        "openrouter": "meta-llama/llama-3.3-70b-instruct",
        "ollama": "llama3.3:70b",
        "dashscope": "qwen-plus",  # fallback
        "zhipu": "glm-4-flash",  # fallback
    },
    "z-ai/glm-5.2": {
        "zhipu": "glm-5.2",
        "zai": "glm-5.2",
        "nvidia": "z-ai/glm-5.2",
    },
    "z-ai/glm-5.1": {
        "zhipu": "glm-5.1",
        "zai": "glm-5.1",
        "nvidia": "z-ai/glm-5.1",
    },
    # Llama 4 cross-provider aliases (Meta, July 2026)
    "meta/llama-4-maverick-17b-128e-instruct": {
        "groq": "llama-4-maverick-17b-128e-instruct",
        "nvidia": "meta/llama-4-maverick-17b-128e-instruct",
        "together": "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
        "openrouter": "meta-llama/llama-4-maverick-17b-128e-instruct",
    },
    "meta/llama-4-scout-17b-16e-instruct": {
        "groq": "llama-4-scout-17b-16e-instruct",
        "nvidia": "meta/llama-4-scout-17b-16e-instruct",
        "together": "meta-llama/Llama-4-Scout-17B-16E-Instruct",
        "openrouter": "meta-llama/llama-4-scout-17b-16e-instruct",
    },
    # Claude Sonnet 5 cross-provider alias
    "claude-sonnet-5": {
        "aerolink": "claude-sonnet-5",
        "openrouter": "anthropic/claude-sonnet-5",
        "anthropic": "claude-sonnet-5",
    },
    # Claude Opus 4.8 cross-provider alias — lets a request for the bare model id
    # rotate onto tokenin's free opus (myt/claude-opus-4-8-free) as well as the
    # paid Claude gateways.
    "claude-opus-4-8": {
        "tokenin": "myt/claude-opus-4-8-free",
        "aerolink": "claude-opus-4-8",
        "anthropic": "claude-opus-4-8",
        "openrouter": "anthropic/claude-opus-4-8",
    },
}


# ── Catalog override (UNIT 6) ─────────────────────────────────────────────
#
# The ``_PROVIDER_REGISTRY`` above has hardcoded ``default_model`` and
# ``models`` fields per provider that duplicate the catalog
# (``config/models.yaml`` → ``PROVIDER_CANDIDATES``). UNIT 6 makes the
# catalog the single source of truth for model ids — the registry keeps
# failover-specific fields (``cooldown``, ``name``, ``tier``, ``key_env``,
# ``base_url_env``, ``default_base_url``) but ``default_model`` and
# ``models`` are derived from the catalog at module import time.
#
# This eliminates the "I added a model to the catalog but brain_failover
# still tries the old one" class of bug. The catalog's first candidate is
# the preset (used as ``default_model``); the full candidate list becomes
# ``models`` (the failover chain).
try:
    from packages.ai.brain_config import PROVIDER_CANDIDATES as _CATALOG_CANDIDATES  # noqa: E402

    for _entry in _PROVIDER_REGISTRY:
        _pid = _entry.get("id")
        _cands = _CATALOG_CANDIDATES.get(_pid)
        if _cands:
            _entry["default_model"] = _cands[0]
            _entry["models"] = list(_cands)
except Exception:  # noqa: BLE001 — never break module import
    pass


# ── Failover manager ─────────────────────────────────────────────────────


class BrainFailoverManager:
    """Manages multi-provider brain failover with circuit breakers.

    Thread-safe. Singleton via :func:`get_failover_manager`.
    """

    def __init__(self) -> None:
        self._providers: dict[str, ProviderInfo] = {}
        self._lock = threading.RLock()
        self._last_registry_build = 0.0
        # Rebuild the provider registry every 60s so newly-set env vars are picked up.
        self._registry_ttl = 60.0

    def _build_registry(self) -> None:
        """Build the provider registry from env vars.

        Called lazily and every 60s so newly-set keys are picked up without a restart.
        """
        with self._lock:
            now = time.time()
            if now - self._last_registry_build < self._registry_ttl and self._providers:
                return

            old_providers = self._providers
            self._providers = {}

            for spec in _PROVIDER_REGISTRY:
                pid = spec["id"]
                # Get the API key
                key_env = spec["key_env"]
                if key_env:
                    api_key = (os.environ.get(key_env) or "").strip()
                    if not api_key:
                        continue  # provider not configured
                else:
                    api_key = ""  # ollama — no key

                # Get the base URL
                base_url_env = spec["base_url_env"]
                base_url = spec["default_base_url"]
                if base_url_env:
                    env_url = (os.environ.get(base_url_env) or "").strip()
                    if env_url:
                        base_url = env_url.rstrip("/")

                # For ollama, skip if no base URL configured (not reachable on Render free)
                if pid == "ollama" and base_url == "http://localhost:11434":
                    # Still include it as a last-resort — it might work in dev
                    pass

                # Check if paid providers are allowed — check BOTH the env var
                # AND the DB-stored provider policy (which is what the Providers
                # UI toggle writes to). Either being true allows paid providers.
                if spec["tier"] == "paid":
                    allow_paid = (
                        os.environ.get("ALLOW_PAID_BRAIN", "false").strip().lower() in ("true", "1", "yes", "on")
                        or _is_paid_allowed_db()
                    )
                    if not allow_paid:
                        continue

                # Preserve health state from the old registry
                # Honor NVIDIA_DEFAULT_MODEL env var (set by the free-brain guard
                # and operator config) so the failover uses the same model the
                # rest of the system expects.
                default_model = spec["default_model"]
                if pid == "nvidia":
                    env_model = (os.environ.get("NVIDIA_DEFAULT_MODEL") or "").strip()
                    if env_model:
                        default_model = env_model

                old = old_providers.get(pid)
                if old:
                    info = ProviderInfo(
                        id=pid,
                        name=spec["name"],
                        tier=spec["tier"],
                        base_url=base_url,
                        api_key=api_key,
                        default_model=default_model,
                        models=spec["models"] + ([default_model] if default_model not in spec["models"] else []),
                        cooldown_seconds=spec["cooldown"],
                        key_env=spec.get("key_env", ""),
                        health=old.health,
                        failure_count=old.failure_count,
                        last_failure=old.last_failure,
                        last_success=old.last_success,
                        cooldown_until=old.cooldown_until,
                        avg_latency_ms=old.avg_latency_ms,
                        total_calls=old.total_calls,
                        total_failures=old.total_failures,
                        last_error=old.last_error,
                    )
                else:
                    info = ProviderInfo(
                        id=pid,
                        name=spec["name"],
                        tier=spec["tier"],
                        base_url=base_url,
                        api_key=api_key,
                        default_model=default_model,
                        models=spec["models"] + ([default_model] if default_model not in spec["models"] else []),
                        cooldown_seconds=spec["cooldown"],
                        key_env=spec.get("key_env", ""),
                    )
                self._providers[pid] = info

            self._last_registry_build = now
            log.debug("brain_failover: registry built — %d providers: %s",
                      len(self._providers), list(self._providers.keys()))

    def get_providers(self) -> list[ProviderInfo]:
        """Return all configured providers (health snapshot)."""
        self._build_registry()
        with self._lock:
            return list(self._providers.values())

    def get_provider(self, provider_id: str) -> ProviderInfo | None:
        """Return a specific provider by id."""
        self._build_registry()
        with self._lock:
            return self._providers.get(provider_id)

    def next_provider(
        self,
        *,
        exclude: set[str] | None = None,
        requested_model: str | None = None,
    ) -> ProviderInfo | None:
        """Return the next healthy provider, excluding any in the exclude set.

        Ordering:
          1. Free providers (by avg latency, best first)
          2. Local providers (ollama)
          3. Paid providers (by avg latency)

        When ``requested_model`` is given, providers that have a model alias
        for it are preferred.
        """
        self._build_registry()
        exclude = exclude or set()

        off = disabled_providers()
        with self._lock:
            healthy = [
                p for p in self._providers.values()
                if p.id not in exclude and p.is_healthy and p.id not in off
            ]

        if not healthy:
            return None

        # Prefer providers that can serve the requested model
        if requested_model:
            model_lower = requested_model.lower()
            has_model = [
                p for p in healthy
                if any(model_lower in m.lower() for m in p.models)
                or requested_model in _MODEL_ALIASES and p.id in _MODEL_ALIASES[requested_model]
            ]
            if has_model:
                healthy = has_model

        # Sort by tier (free first, then local, then paid) then by avg latency
        tier_order = {"free": 0, "local": 1, "paid": 2}
        healthy.sort(key=lambda p: (tier_order.get(p.tier, 3), p.avg_latency_ms))

        return healthy[0] if healthy else None

    def record_success(self, provider_id: str, latency_ms: float = 0.0) -> None:
        """Record a successful call — resets the circuit breaker."""
        self._build_registry()
        with self._lock:
            p = self._providers.get(provider_id)
            if not p:
                return
            p.health = ProviderHealth.CLOSED
            p.failure_count = 0
            p.last_success = time.time()
            p.total_calls += 1
            if latency_ms > 0:
                # Exponential moving average
                if p.avg_latency_ms == 0:
                    p.avg_latency_ms = latency_ms
                else:
                    p.avg_latency_ms = 0.7 * p.avg_latency_ms + 0.3 * latency_ms

    def allow_probe(self, provider_id: str) -> None:
        """Permit one probe call without claiming the provider succeeded.

        This is the honest version of "reset the breaker". ``record_success``
        cannot be used for that: it sets ``health = CLOSED`` and
        ``failure_count = 0``, and ``is_healthy`` returns True for CLOSED
        *without ever consulting* ``cooldown_until`` — so calling it on a
        rate-limited provider erases both the cooldown and the exponential
        backoff counter that produced it. A caller that did this whenever every
        provider was cooling created a doom loop: 429 on all providers → all
        marked OPEN → next request resets them all → all hammered again → 429,
        forever, with the backoff pinned at its base value because the counter
        never survived a cycle.

        HALF_OPEN preserves ``failure_count`` and ``cooldown_until``, so if the
        probe fails the next backoff is computed from the *real* failure history
        and keeps growing as it should.
        """
        self._build_registry()
        with self._lock:
            p = self._providers.get(provider_id)
            if p is not None:
                p.health = ProviderHealth.HALF_OPEN

    def seconds_until_recovery(self) -> float | None:
        """Seconds until the soonest cooling provider is probeable again.

        ``None`` when no provider is cooling (nothing to wait for). Lets a
        caller report "retry in 42s" and stop, instead of probing a fleet that
        has already told it to back off.
        """
        self._build_registry()
        now = time.time()
        with self._lock:
            waits = [
                p.cooldown_until - now
                for p in self._providers.values()
                if p.health == ProviderHealth.OPEN and p.cooldown_until > now
            ]
        return min(waits) if waits else None

    def stuck_beyond_cooldown(
        self, provider_id: str, *, factor: float = _STUCK_PROBE_FACTOR
    ) -> bool:
        """True when a provider's cooldown window is wider than any it could
        legitimately have earned.

        The anti-deadlock safety valve. Cooldowns are the correct answer to a
        429, but a corrupted or absurd ``cooldown_until`` must not wedge the
        brain permanently, so a provider stuck well past any real backoff is
        still allowed an occasional probe.

        The threshold must sit strictly *above* the largest legitimate backoff,
        or the valve fires on a healthy ladder and reintroduces the hammering it
        exists to replace. ``record_failure`` caps the exponent at 4, so the
        widest earned window is ``cooldown_seconds * 2**4`` — 1440s for NVIDIA,
        whose 90s base is the largest in the registry. A factor of 4 would have
        put the threshold at 360s (floored to 900s) and so fired on NVIDIA's
        perfectly legitimate 1440s backoff — exactly the provider that
        rate-limits most. ``_STUCK_PROBE_FACTOR`` is therefore double the
        exponent cap, leaving clear headroom above any real ladder.
        """
        with self._lock:
            p = self._providers.get(provider_id)
            if p is None or p.health != ProviderHealth.OPEN:
                return False
            overdue = p.cooldown_until - p.last_failure
            return overdue > max(factor * p.cooldown_seconds, _STUCK_PROBE_FLOOR_SEC)

    def record_failure(
        self,
        provider_id: str,
        reason: str = "unknown",
        status_code: int | None = None,
    ) -> None:
        """Record a provider failure — opens the circuit breaker on threshold."""
        self._build_registry()
        with self._lock:
            p = self._providers.get(provider_id)
            if not p:
                return
            p.failure_count += 1
            p.total_failures += 1
            p.total_calls += 1
            p.last_failure = time.time()
            p.last_error = f"{reason} (status={status_code})" if status_code else reason

            # 410 Gone = permanent — long cooldown (10 min)
            if status_code == 410:
                p.cooldown_until = time.time() + 600.0
                p.health = ProviderHealth.OPEN
                log.warning(
                    "brain_failover: %s marked OPEN (410 Gone — 10min cooldown)",
                    provider_id,
                )
                return

            # 429 / 419 = rate-limited — exponential backoff
            if status_code in (429, 419):
                backoff = p.cooldown_seconds * (2 ** min(p.failure_count - 1, 4))
                p.cooldown_until = time.time() + backoff
                p.health = ProviderHealth.OPEN
                log.warning(
                    "brain_failover: %s marked OPEN (429 rate-limited — %.0fs cooldown, "
                    "failure #%d)",
                    provider_id, backoff, p.failure_count,
                )
                return

            # 5xx = server error — short cooldown
            if status_code and status_code >= 500:
                p.cooldown_until = time.time() + 15.0
                p.health = ProviderHealth.OPEN
                log.warning(
                    "brain_failover: %s marked OPEN (5xx — 15s cooldown)",
                    provider_id,
                )
                return

            # 401/403 = auth failure — long cooldown (5 min) so we don't keep
            # retrying a provider with a bad/expired key. The key won't fix
            # itself in 30s.
            if status_code in (401, 403):
                p.cooldown_until = time.time() + 300.0
                p.health = ProviderHealth.OPEN
                log.warning(
                    "brain_failover: %s marked OPEN (auth %d — 5min cooldown, "
                    "check API key)",
                    provider_id, status_code,
                )
                return

            # 402 = payment required — long cooldown (10 min, quota won't reset soon)
            if status_code == 402:
                p.cooldown_until = time.time() + 600.0
                p.health = ProviderHealth.OPEN
                log.warning(
                    "brain_failover: %s marked OPEN (402 payment required — 10min cooldown)",
                    provider_id,
                )
                return

            # 404 = model not found — medium cooldown (2 min)
            if status_code == 404:
                p.cooldown_until = time.time() + 120.0
                p.health = ProviderHealth.OPEN
                log.warning(
                    "brain_failover: %s marked OPEN (404 not found — 2min cooldown)",
                    provider_id,
                )
                return

            # Other failures — 30s cooldown
            p.cooldown_until = time.time() + p.cooldown_seconds
            p.health = ProviderHealth.OPEN
            log.warning(
                "brain_failover: %s marked OPEN (%s — %.0fs cooldown)",
                provider_id, reason, p.cooldown_seconds,
            )

    def resolve_model(self, provider: ProviderInfo, requested_model: str | None) -> str:
        """Map a requested model to the provider's equivalent.

        If the requested model is in the alias table for this provider, use
        the alias. Otherwise, if the requested model is in the provider's
        model list, use it as-is. Otherwise, fall back to the provider's
        default model.
        """
        if not requested_model:
            return provider.default_model

        # Check aliases first
        aliases = _MODEL_ALIASES.get(requested_model, {})
        if provider.id in aliases:
            return aliases[provider.id]

        # Check if the provider serves this model directly
        if requested_model in provider.models:
            return requested_model

        # Fuzzy match — if the model name contains part of a provider model
        for m in provider.models:
            if requested_model.lower() in m.lower() or m.lower() in requested_model.lower():
                return m

        # Fall back to the provider's default
        return provider.default_model

    def max_attempts(self) -> int:
        """Maximum number of provider attempts before giving up."""
        self._build_registry()
        with self._lock:
            return max(len(self._providers), 1)

    def status_snapshot(self) -> dict[str, Any]:
        """Return a full health snapshot for observability."""
        self._build_registry()
        with self._lock:
            return {
                "providers": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "tier": p.tier,
                        "health": p.health.value,
                        "is_healthy": p.is_healthy,
                        "failure_count": p.failure_count,
                        "total_calls": p.total_calls,
                        "total_failures": p.total_failures,
                        "avg_latency_ms": round(p.avg_latency_ms, 1),
                        "last_success": p.last_success,
                        "last_failure": p.last_failure,
                        "cooldown_until": p.cooldown_until,
                        "last_error": p.last_error,
                        "base_url": p.base_url,
                        "default_model": p.default_model,
                    }
                    for p in self._providers.values()
                ],
                "total_providers": len(self._providers),
                "healthy_providers": sum(1 for p in self._providers.values() if p.is_healthy),
            }


# ── Singleton ────────────────────────────────────────────────────────────

_manager: BrainFailoverManager | None = None
_manager_lock = threading.Lock()


def get_failover_manager() -> BrainFailoverManager:
    """Return the singleton BrainFailoverManager."""
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = BrainFailoverManager()
    return _manager


def reset_failover_manager() -> None:
    """Reset the singleton (for tests)."""
    global _manager
    with _manager_lock:
        _manager = None


def brain_availability_summary() -> dict[str, Any]:
    """Non-secret answer to "can the brain answer a request right now?".

    Three callers need this and must not disagree: the public doctor endpoint
    (so an operator can see a brain outage without authenticating), the CEO
    supervisor (so it does not spend its intervention budget re-driving goals
    at a brain that cannot answer), and the Providers screen. Deriving it here —
    in the module that owns provider state — keeps them consistent.

    ``usable`` is the number of providers that are both switched on and outside
    their circuit-breaker cooldown. **Zero is the condition that blocks tasks**:
    ``failover_chat_completion`` raises "All brain providers exhausted — none
    configured or all in cooldown" when the chain is empty, which surfaces to the
    dispatcher as "No runtime available" and leaves the task BLOCKED.

    Deliberately excludes API keys, key fragments, provider base URLs and raw
    ``last_error`` text (a provider error body can echo a token). Only the
    provider id, its tier, and the pre-mapped human remedy are reported, so this
    is safe to serve unauthenticated.
    """
    # Cached read on purpose: disabled_providers keeps a ~5s cache, which is far
    # fresher than any consumer needs (the supervisor sweeps every 180s) and
    # spares a Mongo/SQLite round-trip on every dashboard poll.
    off = disabled_providers()
    total = 0
    usable = 0
    disabled: list[dict[str, Any]] = []
    cooling: list[str] = []
    try:
        providers = get_failover_manager().get_providers()
    except Exception as exc:  # noqa: BLE001 — a diagnostic must never raise
        log.warning("brain_availability_summary: provider registry unavailable: %s", exc)
        return {
            "total": 0, "usable": 0, "disabled": [], "cooling": [],
            "state_durable": False, "error": str(exc)[:200],
        }

    for p in providers:
        total += 1
        is_off = p.id in off
        if is_off:
            why = describe_disabled_reason(off.get(p.id, ""))
            disabled.append({
                "id": p.id,
                "tier": p.tier,
                "summary": why["summary"],
                "action": why["action"],
                "auto": why["auto"],
            })
        elif not p.is_healthy:
            cooling.append(p.id)
        else:
            usable += 1

    # Guarded for the same reason the registry read is: this function is called
    # by ceo_status without its own try/except, so an exception here would 500
    # the endpoint whose entire purpose is explaining an outage.
    try:
        durable = state_is_durable()
    except Exception as exc:  # noqa: BLE001 — a diagnostic must never raise
        log.debug("brain_availability_summary: durability check failed: %s", exc)
        durable = False

    return {
        "total": total,
        "usable": usable,
        "disabled": disabled,
        "cooling": cooling,
        "state_durable": durable,
    }
