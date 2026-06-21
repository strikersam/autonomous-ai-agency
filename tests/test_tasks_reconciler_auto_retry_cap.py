"""Regression tests for the auto_retry_cap guard in TaskStore.reconcile_stranded_tasks.

Why this exists: before this guard, the reconciler unconditionally re-queued any
stranded IN_PROGRESS task on startup regardless of its ``auto_retry_count``. A
crash-recovered task that had already exhausted its dispatch budget would be
re-queued, fail again, get blocked again, get auto-retried again, and re-enter
the same loop on every reconciler pass — a silent retry-storm that masked the
braindead config. The guard now surfaces those tasks for human review with a
WARNING instead.
"""
from __future__ import annotations

import asyncio
import time

from tasks.store import TaskStore
from tasks.models import TaskStatus


async def _make_task(store: TaskStore, *, status: str, auto_retry_count: int) -> str:
    """Seed a stranded-shape task via the public store.create API."""
    task = await _build_task(status=status, auto_retry_count=auto_retry_count)
    await store.create(task)
    return task.task_id


async def _build_task(*, status: str, auto_retry_count: int):
    from tasks.models import Task, TaskPriority
    return Task(
        owner_id="system",
        title="reconciler-cap-test",
        status=TaskStatus(status),
        priority=TaskPriority.MEDIUM,
        pending_agent_run=False,
        auto_retry_count=auto_retry_count,
    )


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_reconciler_skips_task_at_auto_retry_cap() -> None:
    """A stranded IN_PROGRESS task whose auto_retry_count == cap is left AS-IS."""
    store = TaskStore()
    cutoff = time.time() - 600  # well past stale_threshold_s
    task_id = _run(_make_task(store, status="in_progress", auto_retry_count=5))

    # Pre-conditions: task is currently stranded (in_progress, pending_agent_run=False).
    pre = _run(store.get(task_id))
    assert pre is not None
    assert pre.status == TaskStatus.IN_PROGRESS
    assert pre.pending_agent_run is False
    # Force the updated_at back past the cutoff so it is eligible for reconciliation.
    pre.updated_at = cutoff
    _run(store.update(pre))

    # Act: reconciler with the default cap (env TASK_AUTO_RETRY_MAX not set).
    reconciled = _run(store.reconcile_stranded_tasks(stale_threshold_s=300.0, auto_retry_cap=5))

    # Post: zero tasks re-queued because the only candidate is at the cap.
    assert reconciled == 0, "cap-hit task MUST NOT be re-queued"
    post = _run(store.get(task_id))
    assert post is not None
    assert post.status == TaskStatus.IN_PROGRESS, "cap-hit task MUST stay IN_PROGRESS for human review"
    assert post.pending_agent_run is False, "pending_agent_run MUST remain False (still stranded)"


def test_reconciler_requeues_task_under_auto_retry_cap() -> None:
    """Sanity: a stranded IN_PROGRESS task below the cap is STILL re-queued."""
    store = TaskStore()
    cutoff = time.time() - 600
    task_id = _run(_make_task(store, status="in_progress", auto_retry_count=2))

    pre = _run(store.get(task_id))
    assert pre is not None
    pre.updated_at = cutoff
    _run(store.update(pre))

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

    cap_hit = _run(_make_task(store, status="in_progress", auto_retry_count=2))
    under_cap = _run(_make_task(store, status="in_progress", auto_retry_count=1))

    for tid in (cap_hit, under_cap):
        t = _run(store.get(tid))
        assert t is not None
        t.updated_at = cutoff
        _run(store.update(t))

    reconciled = _run(store.reconcile_stranded_tasks(stale_threshold_s=300.0, auto_retry_cap=2))

    assert reconciled == 1
    cap_hit_post = _run(store.get(cap_hit))
    assert cap_hit_post is not None and cap_hit_post.status == TaskStatus.IN_PROGRESS
    under_cap_post = _run(store.get(under_cap))
    assert under_cap_post is not None and under_cap_post.status == TaskStatus.TODO
