"""tasks/run_lease.py — one run per task, across processes (atomic checkout).

Adapted from Paperclip's atomic task checkout. ``TaskExecutionCoordinator.execute``
and ``/api/autonomy/tick`` both take this claim before running a task.

When the store's run lease is durable (Mongo or SQLite, ``packages/runs/lease.py``)
the lease alone decides, plus a process local set so two coroutines of this
process cannot both run the task under the one process wide holder id. The
``shared_state`` claim (Redis when ``REDIS_URL`` is set) is skipped there: it
could otherwise keep a recovered task blocked beyond the lease's own expiry.
Stores without a durable lease keep the old order: the ``shared_state`` lock,
then the store's lease when it has one.
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any

from services.shared_state import claim as _shared_claim, release as _shared_release

log = logging.getLogger("qwen-proxy")

# One holder id per process: the run lease in TaskStore is what stops the web
# process, the worker and the cron tick from running the same task at once.
_RUN_LEASE_HOLDER = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
# Kept at an hour until the dispatcher renews the lease with a heartbeat
# (packages/runs/lease.py LeaseHeartbeat, RUNS_LEASE_TTL_SEC): a shorter TTL
# without renewal would let a second process take over a task still running.
_RUN_LEASE_TTL_S = 3600.0
# Tasks this process holds a durable lease for: (fencing token, monotonic expiry).
# The expiry mirrors the lease TTL, so a release that never ran cannot block
# the task in this process for longer than the lease itself would.
_local_claims: dict[str, tuple[int, float]] = {}


async def claim_task_run_token(store: Any, task_id: str, run_id: str | None = None) -> int | None:
    """Claim *task_id* for this process; the lease's fencing token, or ``None`` if refused.

    ``0`` means claimed without a fencing token (a store with no token support).
    """
    if _durable(store):
        return await _claim_durable(store, task_id, run_id)
    if not await _shared_claim(f"task:active:{task_id}", ttl=int(_RUN_LEASE_TTL_S)):
        return None
    if not _supports_lease(store):
        return 0
    try:
        if await store.acquire_run_lease(task_id, _RUN_LEASE_HOLDER, _RUN_LEASE_TTL_S):
            return 0
    except Exception:
        # Fail closed: without the lease a second process may be running it.
        log.warning("Run lease for task %s unavailable; skipping this dispatch", task_id,
                    exc_info=True)
    await _shared_release(f"task:active:{task_id}")
    return None


async def _claim_durable(store: Any, task_id: str, run_id: str | None) -> int | None:
    held = _local_claims.get(task_id)
    if held is not None and held[1] > time.monotonic():
        return None
    expiry = time.monotonic() + _RUN_LEASE_TTL_S
    _local_claims[task_id] = (0, expiry)  # reserve before the await so a sibling coroutine sees it
    try:
        token = await store.acquire_run_lease_token(
            task_id, _RUN_LEASE_HOLDER, _RUN_LEASE_TTL_S, run_id
        )
    except Exception:
        log.warning("Run lease for task %s unavailable; skipping this dispatch", task_id,
                    exc_info=True)
        token = None
    if token is None:
        _local_claims.pop(task_id, None)
        return None
    _local_claims[task_id] = (token, expiry)
    return token


async def claim_task_run(store: Any, task_id: str) -> bool:
    """Take the run claim for *task_id* (see the module docstring), or nothing."""
    return await claim_task_run_token(store, task_id) is not None


async def release_task_run(store: Any, task_id: str) -> None:
    """Release what ``claim_task_run`` took. Never raises."""
    if _durable(store):
        token, _ = _local_claims.pop(task_id, (0, 0.0))
        await _release_lease(store, task_id, token or None)
        return
    if _supports_lease(store):
        await _release_lease(store, task_id, None)
    await _shared_release(f"task:active:{task_id}")


async def _release_lease(store: Any, task_id: str, token: int | None) -> None:
    try:
        if token is None:
            await store.release_run_lease(task_id, _RUN_LEASE_HOLDER)
        else:
            await store.release_run_lease(task_id, _RUN_LEASE_HOLDER, token)
    except Exception:
        log.warning("Run lease release for task %s failed; it expires on its own",
                    task_id, exc_info=True)


def _durable(store: Any) -> bool:
    """True when *store* has a cross process lease with fencing tokens."""
    if not callable(getattr(type(store), "acquire_run_lease_token", None)):
        return False
    try:
        return getattr(store, "has_durable_run_lease", False) is True
    except Exception:
        return False


def _supports_lease(store: Any) -> bool:
    """True for stores whose class implements the run lease (``TaskStore`` does).

    Checked on the class, not the instance, so a bare ``MagicMock`` store in a
    unit test falls back to the in-process lock alone instead of failing closed.
    """
    return callable(getattr(type(store), "acquire_run_lease", None))
