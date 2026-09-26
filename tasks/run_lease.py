"""tasks/run_lease.py — one run per task, across processes (atomic checkout).

Adapted from Paperclip's atomic task checkout. ``TaskExecutionCoordinator.execute``
and ``/api/autonomy/tick`` both take this claim before running a task. It layers
the cross-process lease in ``TaskStore`` on top of the in-process
``shared_state`` lock. The lock alone does not span the web process and the worker
when ``REDIS_URL`` is unset.
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from services.shared_state import claim as _shared_claim, release as _shared_release

log = logging.getLogger("qwen-proxy")

# One holder id per process: the run lease in TaskStore is what stops the web
# process, the worker and the cron tick from running the same task at once.
_RUN_LEASE_HOLDER = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
_RUN_LEASE_TTL_S = 3600.0


async def claim_task_run(store: Any, task_id: str) -> bool:
    """Take both the in-process lock and the cross-process run lease, or neither."""
    if not await _shared_claim(f"task:active:{task_id}", ttl=int(_RUN_LEASE_TTL_S)):
        return False
    if not _supports_lease(store):
        return True
    try:
        if await store.acquire_run_lease(task_id, _RUN_LEASE_HOLDER, _RUN_LEASE_TTL_S):
            return True
    except Exception:
        # Fail closed: without the lease a second process may be running it.
        log.warning("Run lease for task %s unavailable; skipping this dispatch", task_id,
                    exc_info=True)
    await _shared_release(f"task:active:{task_id}")
    return False


async def release_task_run(store: Any, task_id: str) -> None:
    """Release what ``claim_task_run`` took. Never raises."""
    if not _supports_lease(store):
        await _shared_release(f"task:active:{task_id}")
        return
    try:
        await store.release_run_lease(task_id, _RUN_LEASE_HOLDER)
    except Exception:
        log.warning("Run lease release for task %s failed; it expires on its own",
                    task_id, exc_info=True)
    await _shared_release(f"task:active:{task_id}")


def _supports_lease(store: Any) -> bool:
    """True for stores whose class implements the run lease (``TaskStore`` does).

    Checked on the class, not the instance, so a bare ``MagicMock`` store in a
    unit test falls back to the in-process lock alone instead of failing closed.
    """
    return callable(getattr(type(store), "acquire_run_lease", None))
