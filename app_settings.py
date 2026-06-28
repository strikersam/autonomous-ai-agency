"""app_settings.py — DB-persisted application settings.

A tiny async key/value settings layer backed by ``db.get_store()`` (collection
``app_settings``). Each setting is one document::

    {"key": "onboarding_gate_enabled", "value": <json-serialisable>,
     "updated_at": <epoch>, "updated_by": "<actor>"}

Why a dedicated module:
- The onboarding-gate default and the ephemeral-company TTL must survive
  restarts (the file-based ``.onboarding_state.json`` is per-user, not global),
  so they live in the same store as users/companies.
- ``activation_api.is_user_onboarding_allowed`` is a *sync* function called from
  request handlers; it cannot ``await`` a DB read on the hot path. So we keep an
  in-process cache of the small set of gate-relevant settings and expose sync
  readers (``onboarding_gate_enabled_cached`` / ``ephemeral_ttl_hours_cached``).
  The DB remains the source of truth — the cache is refreshed on every write and
  best-effort warmed at startup via :func:`refresh_cache`.
"""

from __future__ import annotations

import logging
import time
from typing import Any

log = logging.getLogger("qwen-proxy")

# ── Setting keys + defaults ───────────────────────────────────────────────────

# When True (default) the onboarding gate is enforced: a user may only run the
# setup wizard if an admin explicitly added them to the allow-list. When an admin
# turns this OFF, users with no explicit record are allowed by default.
ONBOARDING_GATE_ENABLED_KEY = "onboarding_gate_enabled"
ONBOARDING_GATE_ENABLED_DEFAULT = True

# How long a non-admin (GitHub/Google) user's company survives before the reaper
# destroys it. Admin-created companies ignore this and persist forever.
EPHEMERAL_TTL_HOURS_KEY = "ephemeral_company_ttl_hours"
EPHEMERAL_TTL_HOURS_DEFAULT = 24

_DEFAULTS: dict[str, Any] = {
    ONBOARDING_GATE_ENABLED_KEY: ONBOARDING_GATE_ENABLED_DEFAULT,
    EPHEMERAL_TTL_HOURS_KEY: EPHEMERAL_TTL_HOURS_DEFAULT,
}

# ── In-process cache (mirrors the DB; DB stays source of truth) ───────────────
_cache: dict[str, Any] = dict(_DEFAULTS)
_cache_loaded = False


def _store():
    from db import get_store

    return get_store()


# ── Async accessors (source of truth) ─────────────────────────────────────────

async def get_setting(key: str, default: Any = None) -> Any:
    """Return a setting value from the DB, falling back to *default*.

    *default* falls back to the module default for known keys when omitted.
    """
    if default is None and key in _DEFAULTS:
        default = _DEFAULTS[key]
    try:
        doc = await _store().app_settings.find_one({"key": key})
    except Exception:  # noqa: BLE001 — never let settings break a request
        log.exception("app_settings.get_setting(%s) failed", key)
        return _cache.get(key, default)
    if not doc or "value" not in doc:
        return default
    _cache[key] = doc["value"]
    return doc["value"]


async def set_setting(key: str, value: Any, updated_by: str = "admin") -> None:
    """Persist a setting and refresh the in-process cache."""
    global _cache_loaded
    await _store().app_settings.update_one(
        {"key": key},
        {"$set": {"key": key, "value": value,
                  "updated_at": time.time(), "updated_by": updated_by}},
        upsert=True,
    )
    _cache[key] = value
    # A successful write proves the store is reachable, so the cache for this key
    # is now authoritative — clear the "never warmed" flag.
    _cache_loaded = True


async def all_settings() -> dict[str, Any]:
    """Return the full effective settings dict (DB values over defaults)."""
    out = dict(_DEFAULTS)
    for key in _DEFAULTS:
        out[key] = await get_setting(key)
    return out


async def refresh_cache() -> dict[str, Any]:
    """Warm the in-process cache from the DB. Best-effort; never raises.

    Reads directly from the DB instead of through :func:`get_setting` so
    that a transient DB outage is detected and `_cache_loaded` stays `False`.
    When `get_setting` fails internally it silently returns the in-process
    default, which would cause `refresh_cache` to mark the cache as warmed
    with stale defaults — permanently locking social-login users out of the
    onboarding wizard even after the admin turned the gate OFF.
    """
    global _cache_loaded
    store = _store()
    try:
        for key in _DEFAULTS:
            doc = await store.app_settings.find_one({"key": key})
            if doc and "value" in doc:
                _cache[key] = doc["value"]
        _cache_loaded = True
    except Exception:  # noqa: BLE001 — startup must not crash on this
        log.exception("app_settings.refresh_cache failed")
    return dict(_cache)


def _maybe_schedule_refresh() -> None:
    """If the cache was never warmed (a startup refresh failed), kick off a
    best-effort background refresh so the next sync read self-heals instead of
    being pinned to defaults until the next write.

    No-op when no event loop is running (pure-sync callers) or when the cache is
    already loaded.
    """
    if _cache_loaded:
        return
    try:
        import asyncio
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return  # no running loop — nothing to schedule onto
    loop.create_task(refresh_cache())


# ── Typed helpers ─────────────────────────────────────────────────────────────

def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in ("0", "false", "no", "off", "")
    if value is None:
        return default
    return bool(value)


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def onboarding_gate_enabled_cached() -> bool:
    """Sync read of the gate default from cache (DB is source of truth).

    If the cache was never warmed (a startup refresh failed), schedule a
    best-effort background refresh so the next read self-heals rather than
    staying pinned to the default.
    """
    _maybe_schedule_refresh()
    return _as_bool(
        _cache.get(ONBOARDING_GATE_ENABLED_KEY, ONBOARDING_GATE_ENABLED_DEFAULT),
        ONBOARDING_GATE_ENABLED_DEFAULT,
    )


def ephemeral_ttl_hours_cached() -> int:
    """Sync read of the ephemeral TTL (hours) from cache.

    Self-heals a never-warmed cache via a background refresh (see
    :func:`onboarding_gate_enabled_cached`).
    """
    _maybe_schedule_refresh()
    return _as_int(
        _cache.get(EPHEMERAL_TTL_HOURS_KEY, EPHEMERAL_TTL_HOURS_DEFAULT),
        EPHEMERAL_TTL_HOURS_DEFAULT,
    )


async def onboarding_gate_enabled() -> bool:
    """Async read of the gate default straight from the DB."""
    return _as_bool(await get_setting(ONBOARDING_GATE_ENABLED_KEY),
                    ONBOARDING_GATE_ENABLED_DEFAULT)


async def ephemeral_ttl_hours() -> int:
    """Async read of the ephemeral TTL (hours) straight from the DB."""
    return _as_int(await get_setting(EPHEMERAL_TTL_HOURS_KEY),
                   EPHEMERAL_TTL_HOURS_DEFAULT)


def reset_cache_for_tests() -> None:
    """Reset the in-process cache (tests only)."""
    global _cache, _cache_loaded
    _cache = dict(_DEFAULTS)
    _cache_loaded = False
