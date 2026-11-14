"""packages/runs/lease.py — the one run lease, with a fencing token.

The lease document lives in ``task_run_leases``, keyed by ``task_id`` for task
runs and by ``run:<run_id>`` for orchestrator runs. It carries ``holder``,
``run_id``, ``token`` and ``expires_at``. ``token`` grows by one on every
successful acquire, so a worker that lost its lease holds a smaller token than
the new holder and every fenced write it attempts fails.

This module is the only code that writes the document; ``TaskStore`` delegates
here. Mongo uses the raw Motor collection (``MongoStore`` unwraps on
subscript), SQLite the single statement helpers, memory a process local dict.
Releasing keeps the document (holder cleared, already expired) so the token
never resets.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable

from packages.config import runs_settings
from packages.runs.backend import DocTable, MemoryTable, table_for
from packages.storage.state_persistence import parse_expiry

log = logging.getLogger("qwen-proxy")

LEASE_COLLECTION = "task_run_leases"
_CAS_ATTEMPTS = 3


def run_lease_key(run_id: str) -> str:
    """The lease key of an orchestrator run (task runs use their ``task_id``)."""
    return f"run:{run_id}"


def remaining_s(doc: dict[str, Any] | None, now: float | None = None) -> float:
    """Seconds left on a lease document; ``0`` when missing, malformed or expired."""
    if not doc:
        return 0.0
    expires = parse_expiry(doc.get("expires_at"))
    if expires is None:
        return 0.0
    return max(expires - (time.time() if now is None else now), 0.0)


def _takeable(doc: dict[str, Any], holder: str, now: float) -> bool:
    if doc.get("holder") == holder:
        return True
    expires = parse_expiry(doc.get("expires_at"))
    return expires is None or expires < now


class RunLease:
    """Acquire, renew and release leases on one storage backend (``None`` = memory)."""

    def __init__(self, db: Any = None) -> None:
        self._memory: dict[str, MemoryTable] = {}
        self._table: DocTable = table_for(db, LEASE_COLLECTION, self._memory)

    @property
    def durable(self) -> bool:
        """True when the lease is shared across processes (Mongo or SQLite)."""
        return self._table.kind != "memory"

    async def acquire(self, key: str, holder: str, ttl_s: float, run_id: str | None = None,
                      *, now: float | None = None) -> int | None:
        """Take the lease; return the new fencing token, or ``None`` when someone else holds it.

        Succeeds when the lease is absent, expired, or already *holder*'s. Every
        success increments the token, including a re-acquire by the same holder.
        """
        now = time.time() if now is None else now
        fields = {"holder": holder, "run_id": run_id, "expires_at": now + ttl_s, "acquired_at": now}
        for _ in range(_CAS_ATTEMPTS):
            if await self._table.insert_if_absent(key, {**fields, "token": 1}):
                return 1
            current = await self._table.get(key)
            if current is None:
                continue
            if not _takeable(current, holder, now):
                return None
            old = current.get("token")
            token = int(old or 0) + 1
            taken = await self._table.compare_and_set(
                key, {"token": old}, {**fields, "token": token},
                any_of=[{"expires_at": ("lt", now)}, {"holder": holder}],
            )
            if taken:
                return token
        return None

    async def renew(self, key: str, holder: str, token: int, ttl_s: float,
                    *, now: float | None = None) -> bool:
        """Extend *holder*'s lease; False when the lease moved on (a newer token exists)."""
        now = time.time() if now is None else now
        return await self._table.compare_and_set(
            key, {"holder": holder, "token": token}, {"expires_at": now + ttl_s, "renewed_at": now}
        )

    async def release(self, key: str, holder: str, token: int | None = None) -> bool:
        """Give the lease up if *holder* (and *token*, when given) still own it."""
        expect: dict[str, Any] = {"holder": holder}
        if token is not None:
            expect["token"] = token
        return await self._table.compare_and_set(
            key, expect, {"holder": "", "expires_at": 0.0, "released_at": time.time()}
        )

    async def current(self, key: str) -> dict[str, Any] | None:
        """The lease document for *key*, or ``None``."""
        return await self._table.get(key)


class LeaseHeartbeat:
    """Renews a held lease in the background; sets ``lost`` when it can no longer.

    A renewal that returns False (a newer token exists) marks the lease lost at
    once. A renewal that raises is retried until the lease would have expired
    since the last success; only then is it lost. Never raises.
    """

    def __init__(self, lease: RunLease, key: str, holder: str, token: int, *,
                 ttl_s: float | None = None, renew_s: float | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._lease, self._key, self._holder, self._token = lease, key, holder, token
        self._ttl_s = float(ttl_s if ttl_s is not None else runs_settings.lease_ttl_s())
        self._renew_s = float(renew_s if renew_s is not None else runs_settings.lease_renew_s())
        self._clock = clock
        self._task: asyncio.Task[None] | None = None
        self.lost = asyncio.Event()

    def start(self) -> None:
        """Begin renewing on the running loop (idempotent)."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name=f"lease-heartbeat:{self._key}")

    async def stop(self) -> None:
        """Stop renewing. Does not release the lease."""
        task, self._task = self._task, None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            log.warning("lease heartbeat for %s ended with an error", self._key, exc_info=True)

    async def _run(self) -> None:
        last_ok = self._clock()
        while not self.lost.is_set():
            await asyncio.sleep(self._renew_s)
            try:
                ok = await self._lease.renew(self._key, self._holder, self._token, self._ttl_s)
            except Exception:
                log.warning("lease renewal for %s failed; retrying", self._key, exc_info=True)
                if self._clock() - last_ok >= self._ttl_s:
                    self._mark_lost("renewals failed for a whole TTL")
                continue
            if not ok:
                self._mark_lost("a newer holder took the lease")
                continue
            last_ok = self._clock()

    def _mark_lost(self, why: str) -> None:
        log.warning("lease %s lost (token %s): %s", self._key, self._token, why)
        self.lost.set()
