"""Regression tests for the auto_retry_cap guard in TaskStore.reconcile_stranded_tasks.

Why this exists: before this guard, the reconciler unconditionally re-queued any
stranded IN_PROGRESS task on startup regardless of its ``auto_retry_count``. A
crash-recovered task that had already exhausted its dispatch budget would be
re-queued, fail again, get blocked again, get auto-retried again, and re-enter
the same loop on every reconciler pass \u2014 a silent retry-storm that masked the
braindead config. The guard now surfaces those tasks for human review with a
WARNING instead.
"""
from __future__ import annotations

import asyncio
import time

from tasks.store import TaskStore
from tasks.models import Task, TaskStatus, TaskPriority


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _force_stale(store: TaskStore, task_id: str, updated_at: float) -> None:
    """Poke ``updated_at`` directly into the in-memory doc so the stranded
    candidate survives ``store.update()`` which would re-touch the timestamp
    back to \"now\" and disqualify the candidate.
    """
    if store._mode != "memory":
        raise NotImplementedError("_force_stale only supported for in-memory store")
    doc = store._mem.get(task_id)
    assert doc is not None
    doc["updated_at"] = updated_at


async def _seed(store: TaskStore, *, status: str, auto_retry_count: int) -> str:
    task = Task(
        owner_id="system",
        title="reconciler-cap-test",
        status=TaskStatus(status),
        priority=TaskPriority.MEDIUM,
        pending_agent_run=False,
        auto_retry_count=auto_retry_count,
    )
    await store.create(task)
    return task.task_id


def test_reconciler_skips_task_at_auto_retry_cap() -> None:
    """A stranded IN_PROGRESS task whose auto_retry_count == cap is left AS-IS."""
    store = TaskStore()
    cutoff = time.time() - 600
    task_id = _run(_seed(store, status="in_progress", auto_retry_count=5))
    _force_stale(store, task_id, cutoff)

    reconciled = _run(store.reconcile_stranded_tasks(stale_threshold_s=300.0, auto_retry_cap=5))

    assert reconciled == 0, "cap-hit task MUST NOT be re-queued"
    post = _run(store.get(task_id))
    assert post is not None
    assert post.status == TaskStatus.IN_PROGRESS, "cap-hit task MUST stay IN_PROGRESS for human review"
    assert post.pending_agent_run is False, "pending_agent_run MUST remain False (still stranded)"


def test_reconciler_requeues_task_under_auto_retry_cap() -> None:
    """Sanity: a stranded IN_PROGRESS task below the cap is STILL re-queued."""
    store = TaskStore()
    cutoff = time.time() - 600
    task_id = _run(_seed(store, status="in_progress", auto_retry_count=2))
    _force_stale(store, task_id, cutoff)

    reconciled = _run(store.reconcile_stranded_tasks(stale_threshold_s=300.0, auto_retry_cap=5))

    assert reconciled == 1, "below-cap stranded task MUST be re-queued"
    post = _run(store.get(task_id))
    assert post is not None
    assert post.status == TaskStatus.TODO, "reconciler re-queues to TODO"
    assert post.pending_agent_run is True, "pending_agent_run must be set so dispatcher picks it up"


def test_reconciler_explicit_cap_lowered_respects_guard() -> None:
    """Explicit auto_retry_cap=2: a task at count=2 is left alone; count=1 is re-queued."""
    store = TaskStore()
    cutoff = time.time() - 600

    cap_hit = _run(_seed(store, status="in_progress", auto_retry_count=2))
    under_cap = _run(_seed(store, status="in_progress", auto_retry_count=1))

    _force_stale(store, cap_hit, cutoff)
    _force_stale(store, under_cap, cutoff)

    reconciled = _run(store.reconcile_stranded_tasks(stale_threshold_s=300.0, auto_retry_cap=2))

    assert reconciled == 1
    cap_hit_post = _run(store.get(cap_hit))
    assert cap_hit_post is not None and cap_hit_post.status == TaskStatus.IN_PROGRESS
    under_cap_post = _run(store.get(under_cap))
    assert under_cap_post is not None and under_cap_post.status == TaskStatus.TODO
