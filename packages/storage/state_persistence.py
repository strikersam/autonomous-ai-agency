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
from collections.abc import Coroutine
from typing import Any

log = logging.getLogger("qwen-proxy")

# Strong refs so fire-and-forget tasks are not garbage-collected mid-flight.
_pending: set[asyncio.Task[Any]] = set()
_indexed: set[str] = set()


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
    """Schedule *coro* on the running loop. Returns False (and drops it) when none runs."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        coro.close()
        log.debug("state persistence: no running loop, write dropped")
        return False
    task = loop.create_task(coro)
    _pending.add(task)
    task.add_done_callback(_pending.discard)
    return True


async def ensure_ttl_index(name: str, col: Any, field: str) -> None:
    """Create ``expireAfterSeconds=0`` on *field* once per process. Never raises."""
    if name in _indexed:
        return
    _indexed.add(name)
    try:
        await col.create_index(field, expireAfterSeconds=0, background=True)
    except Exception as exc:  # noqa: BLE001 - expiry is also enforced at read time
        log.debug("state persistence: TTL index on %s.%s not created: %s", name, field, exc)


async def ensure_index(name: str, col: Any, key: str, *, tag: str = "") -> None:
    """Create a plain ascending index once per process. Never raises."""
    marker = f"{name}:{tag or key}"
    if marker in _indexed:
        return
    _indexed.add(marker)
    try:
        await col.create_index(key, background=True)
    except Exception as exc:  # noqa: BLE001 - lookups still work, just unindexed
        log.debug("state persistence: index on %s.%s not created: %s", name, key, exc)


def reset() -> None:
    """Forget index bookkeeping and pending tasks. Test helper."""
    _indexed.clear()
    _pending.clear()
