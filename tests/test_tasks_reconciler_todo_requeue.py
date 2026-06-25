"""Tests: reconciler handles TODO tasks with pending_agent_run=False.

Covers the CodeRabbit #724 feedback: the reconciler's unqueued_todo loop
(tasks with status=TODO and pending_agent_run=False) was not explicitly tested.
"""
from __future__ import annotations

import time
import pytest
from tasks.models import Task, TaskStatus
from tasks.store import TaskStore


@pytest.fixture()
def store():
    return TaskStore()  # in-memory mode


def _make_task(status: TaskStatus, pending: bool, age_s: float = 0.0, **kw) -> Task:
    t = Task(title="test", owner_id="u1", status=status, **kw)
    t.pending_agent_run = pending
    t.updated_at = time.time() - age_s
    return t


# ── TODO + pending_agent_run=False ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_reconcile_requeues_unqueued_todo(store):
    """A TODO task with pending_agent_run=False must be re-queued by the reconciler."""
    task = _make_task(TaskStatus.TODO, pending=False)
    await store.create(task)

    reconciled = await store.reconcile_stranded_tasks()
    assert reconciled == 1

    updated = await store.get(task.task_id)
    assert updated.pending_agent_run is True
    assert updated.status == TaskStatus.TODO
    log_types = [e.get("event_type") for e in (updated.execution_log or [])]
    assert "reconciled" in log_types


@pytest.mark.asyncio
async def test_reconcile_skips_todo_already_queued(store):
    """A TODO task with pending_agent_run=True does NOT need reconciliation."""
    task = _make_task(TaskStatus.TODO, pending=True)
    await store.create(task)

    reconciled = await store.reconcile_stranded_tasks()
    assert reconciled == 0


@pytest.mark.asyncio
async def test_reconcile_skips_done_task(store):
    """A DONE task is never touched by the reconciler regardless of pending flag."""
    task = _make_task(TaskStatus.DONE, pending=False)
    await store.create(task)

    reconciled = await store.reconcile_stranded_tasks()
    assert reconciled == 0


@pytest.mark.asyncio
async def test_reconcile_skips_active_task(store):
    """A TODO task currently in the active set must not be re-queued."""
    task = _make_task(TaskStatus.TODO, pending=False)
    await store.create(task)

    reconciled = await store.reconcile_stranded_tasks(active_task_ids={task.task_id})
    assert reconciled == 0


@pytest.mark.asyncio
async def test_reconcile_handles_mixed_tasks(store):
    """Only eligible tasks get reconciled; others stay untouched."""
    already_queued = _make_task(TaskStatus.TODO, pending=True)
    unqueued = _make_task(TaskStatus.TODO, pending=False)
    done_task  = _make_task(TaskStatus.DONE, pending=False)

    for t in [already_queued, unqueued, done_task]:
        await store.create(t)

    reconciled = await store.reconcile_stranded_tasks()
    assert reconciled == 1

    u = await store.get(unqueued.task_id)
    assert u.pending_agent_run is True
    aq = await store.get(already_queued.task_id)
    assert aq.pending_agent_run is True  # unchanged
