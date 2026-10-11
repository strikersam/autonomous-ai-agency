"""packages/storage/state_persistence.py — shared plumbing for durable in-process stores.

The per-user token ledger, sticky approval grants and the tool-output offload
store keep process memory as their hot-path cache. This module is the thin
bridge that mirrors them into the shared DB (``backend.server.get_db()``, the
same backend ``packages/scheduler/store.py`` uses) so they survive restarts and
hold across workers.

Contract for callers:

* ``collection(name)`` returns ``None`` when the operator switched
  ``AGENCY_STATE_PERSISTENCE_ENABLED`` off or no DB is reachable; callers then
  behave exactly as the in-memory-only code always did.
* ``fire_and_forget(coro)`` pushes a write onto the running loop without ever
  blocking the caller; with no running loop the write is dropped (debug log).
* Every helper swallows its own errors: persistence is an enhancement and must
  never break the path it decorates.
"""
from __future__ import annotations

import asyncio
import logging
import math
import threading
import time
from collections.abc import Coroutine
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger("qwen-proxy")

# Strong refs so fire-and-forget tasks are not garbage-collected mid-flight.
_pending: set[asyncio.Task[Any]] = set()
_MAX_PENDING = 1000  # bounds memory if the DB stalls while writes keep arriving
_indexed: set[str] = set()
_index_retry_at: dict[str, float] = {}
_INDEX_RETRY_S = 60.0
_WARN_EVERY_S = 60.0
_last_warn: dict[str, float] = {}
_last_purge: dict[str, float] = {}
_PURGE_EVERY_S = 300.0  # SQLite has no TTL index: purge expired rows at most this often per collection

# Backend-neutral expiry: every persisted row carries ``expires_at`` (a datetime,
# which MongoDB TTL indexes need) and ``expires_at_ts`` (epoch seconds, a number
# that compares the same on every backend). SQLite stores datetimes as strings,
# so all queries and parsing use the numeric field.
EXPIRES_TS = "expires_at_ts"


def expiry_fields(expires: datetime) -> dict[str, Any]:
    """The ``expires_at`` / ``expires_at_ts`` pair to store for *expires* (UTC)."""
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return {"expires_at": expires, EXPIRES_TS: expires.timestamp()}


def parse_expiry(value: Any) -> float | None:
    """Epoch seconds from a number, datetime or ISO/numeric string; ``None`` if unusable.

    Naive datetimes are UTC (Motor returns them that way). Callers treat ``None``
    as already expired, so a malformed or legacy value fails closed.
    """
    try:
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, datetime):
            ts = (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).timestamp()
        elif isinstance(value, str):
            text = value.strip()
            try:
                ts = float(text)
            except ValueError:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
                ts = (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).timestamp()
        else:
            ts = float(value)
    except (TypeError, ValueError, OverflowError, OSError):
        return None
    return ts if math.isfinite(ts) else None


def doc_expiry(doc: dict[str, Any]) -> float | None:
    """A stored row's expiry in epoch seconds: ``expires_at_ts``, else ``expires_at``."""
    ts = parse_expiry(doc.get(EXPIRES_TS))
    return ts if ts is not None else parse_expiry(doc.get("expires_at"))


def warn_limited(key: str, msg: str, *args: Any) -> None:
    """Log at WARNING at most once per minute per *key*; otherwise at DEBUG.

    A DB outage fails every write, which would otherwise flood the log.
    """
    now = time.monotonic()
    if now - _last_warn.get(key, -_WARN_EVERY_S) >= _WARN_EVERY_S:
        _last_warn[key] = now
        log.warning(msg, *args)
    else:
        log.debug(msg, *args)


def persistence_enabled() -> bool:
    """Read the live operator flag at call time; a broken read keeps the default (on)."""
    try:
        from packages.config import settings

        return bool(settings.agency_state_persistence_enabled)
    except Exception as exc:  # noqa: BLE001 - keep the shipped default
        log.debug("AGENCY_STATE_PERSISTENCE_ENABLED unreadable, keeping it on: %s", exc)
        return True


def collection(name: str) -> Any | None:
    """The DB collection *name*, or ``None`` when persistence is off or unavailable."""
    if not persistence_enabled():
        return None
    try:
        from backend.server import get_db

        return getattr(get_db(), name)
    except Exception as exc:  # noqa: BLE001 - no DB -> memory-only
        log.debug("state persistence: collection %s unavailable: %s", name, exc)
        return None


def fire_and_forget(coro: Coroutine[Any, Any, Any]) -> bool:
    """Schedule *coro* on the running loop. Returns False (and drops it) when it cannot run.

    Dropped when: no loop is running; the loop is not on the main thread (the
    short-lived ``asyncio.run`` loops of ``agent/background.py`` cancel pending
    tasks at exit, and the Motor client is bound to the server loop anyway); or
    ``_MAX_PENDING`` writes are already in flight.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        coro.close()
        log.debug("state persistence: no running loop, write dropped")
        return False
    if threading.current_thread() is not threading.main_thread():
        coro.close()
        log.debug("state persistence: not on the server loop, write dropped")
        return False
    if len(_pending) >= _MAX_PENDING:
        coro.close()
        warn_limited("pending", "state persistence: %d writes pending, dropping new writes", _MAX_PENDING)
        return False
    task = loop.create_task(coro)
    _pending.add(task)
    task.add_done_callback(_pending.discard)
    return True


async def _create_index(name: str, marker: str, make: Any) -> None:
    """Run an index creation once per process; retry after a backoff if it failed."""
    if marker in _indexed or time.monotonic() < _index_retry_at.get(marker, 0.0):
        return
    try:
        await make()
        _indexed.add(marker)
    except Exception as exc:  # noqa: BLE001 - expiry is also enforced at read time
        _index_retry_at[marker] = time.monotonic() + _INDEX_RETRY_S
        log.debug("state persistence: index %s on %s not created: %s", marker, name, exc)


async def _purge_sqlite(name: str, col: Any) -> None:
    """Opportunistically delete expired rows (SQLite has no TTL index); never raises."""
    now = time.monotonic()
    if now - _last_purge.get(name, -_PURGE_EVERY_S) < _PURGE_EVERY_S:
        return
    _last_purge[name] = now
    try:
        from packages.storage.sqlite_atomic import purge_expired

        removed = await purge_expired(col, EXPIRES_TS, time.time())
        if removed:
            log.debug("state persistence: purged %d expired rows from %s", removed, name)
    except Exception as exc:  # noqa: BLE001 - reads filter on expiry anyway
        log.debug("state persistence: purge of %s failed: %s", name, exc)


async def ensure_ttl_index(name: str, col: Any, field: str) -> None:
    """Create ``expireAfterSeconds=0`` on *field*; idempotent, never raises.

    On SQLite there are no TTL indexes: this instead runs the throttled purge.
    """
    from packages.storage.sqlite_atomic import is_sqlite_collection

    if is_sqlite_collection(col):
        await _purge_sqlite(name, col)
        return
    await _create_index(
        name, f"{name}:ttl:{field}",
        lambda: col.create_index(field, expireAfterSeconds=0, background=True),
    )


async def ensure_index(name: str, col: Any, key: str, *, tag: str = "") -> None:
    """Create a plain ascending index; idempotent, never raises."""
    await _create_index(name, f"{name}:{tag or key}", lambda: col.create_index(key, background=True))


def reset() -> None:
    """Forget index bookkeeping and pending tasks. Test helper."""
    _indexed.clear()
    _index_retry_at.clear()
    _last_warn.clear()
    _last_purge.clear()
    _pending.clear()
