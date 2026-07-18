"""The reconciler must not re-queue tasks parked at the pre-execution gate.

Regression: the gate parks a ``requires_approval`` task by clearing
``pending_agent_run`` (status stays TODO). The reconciler's second pass
re-queued every TODO task with ``pending_agent_run=False``, so the dispatcher
re-picked the parked task, the gate re-parked it, and the "⏸ Task awaiting
approval" Telegram notification was re-sent on every reconcile cycle
(~5 min + every server restart) until a human approved.
"""
from __future__ import annotations

import pytest

from tasks.models import Task, TaskStatus
from tasks.service import TaskExecutionCoordinator, TaskWorkflowService
from tasks.store import TaskStore


@pytest.fixture()
def store() -> TaskStore:
    return TaskStore()


@pytest.mark.asyncio
async def test_reconciler_skips_gate_parked_tasks(store):
    parked = Task(
        owner_id="system:trend-scoping",
        title="trend task",
        requires_approval=True,
        pending_agent_run=False,  # parked by the gate
    )
    plain = Task(owner_id="o@x.com", title="never queued", pending_agent_run=False)
    approved = Task(
        owner_id="o@x.com", title="approved gated task",
        requires_approval=True, execution_approved=True, pending_agent_run=False,
    )
    for t in (parked, plain, approved):
        await store.create(t)

    await store.reconcile_stranded_tasks()

    assert (await store.get(parked.task_id)).pending_agent_run is False, \
        "gate-parked task must stay parked until a human approves"
    assert (await store.get(plain.task_id)).pending_agent_run is True
    assert (await store.get(approved.task_id)).pending_agent_run is True, \
        "an approved gated task is ordinary work and may be re-queued"


@pytest.mark.asyncio
async def test_gate_notifies_only_on_first_park(store, monkeypatch):
    notified: list[str] = []
    monkeypatch.setattr(
        TaskExecutionCoordinator, "_notify_execution_gate",
        staticmethod(lambda task: notified.append(task.task_id)),
    )
    task = Task(
        owner_id="o@x.com", title="Deploy",
        requires_approval=True, pending_agent_run=True,
    )
    await store.create(task)
    coordinator = TaskExecutionCoordinator(
        store=store,
        workflow=TaskWorkflowService(store=store),
        workspace_root="/tmp/workspace",  # nosec B108 - gate parks before any file I/O
    )

    await coordinator.execute(task.task_id)
    assert notified == [task.task_id]

    # Simulate something re-arming the parked task: re-park must not re-notify.
    reloaded = await store.get(task.task_id)
    reloaded.pending_agent_run = True
    await store.update(reloaded)
    await coordinator.execute(task.task_id)

    assert notified == [task.task_id], "re-parking must not send a second notification"


@pytest.mark.asyncio
async def test_gate_renotifies_after_reject_and_retry(store, monkeypatch):
    """A reject + human Retry starts a NEW approval cycle → fresh notification."""
    notified: list[str] = []
    monkeypatch.setattr(
        TaskExecutionCoordinator, "_notify_execution_gate",
        staticmethod(lambda task: notified.append(task.task_id)),
    )
    task = Task(
        owner_id="o@x.com", title="Deploy",
        requires_approval=True, pending_agent_run=True,
    )
    await store.create(task)
    workflow = TaskWorkflowService(store=store)
    coordinator = TaskExecutionCoordinator(
        store=store,
        workflow=workflow,
        workspace_root="/tmp/workspace",  # nosec B108 - gate parks before any file I/O
    )

    await coordinator.execute(task.task_id)
    assert notified == [task.task_id]

    reloaded = await store.get(task.task_id)
    workflow.approve_execution(reloaded, actor="boss@x.com", approved=False, reason="not now")
    workflow.retry(reloaded, actor="boss@x.com")
    await store.update(reloaded)
    await coordinator.execute(task.task_id)

    assert notified == [task.task_id, task.task_id], \
        "a renewed approval cycle after reject+retry must notify again"
