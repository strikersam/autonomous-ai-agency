"""Pre-execution approval gate tests (Autonomy Charter Gate Matrix / P0).

A ``requires_approval`` task must NEVER be executed by the autonomous dispatcher
until a human approves it: the dispatcher parks it (no runtime call),
``approve_execution()`` re-queues it, and a rejection blocks it.
"""
from __future__ import annotations

import pytest

from tasks.models import Task, TaskStatus
from tasks.service import TaskExecutionCoordinator, TaskWorkflowService
from tasks.store import TaskStore


class _RecordingRuntimeManager:
    """Records whether execute() was ever reached; raises so we never need a
    full fake result (we only assert *whether* the gate let the task through)."""

    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, spec):
        self.calls += 1
        raise RuntimeError("reached runtime")


@pytest.fixture()
def store() -> TaskStore:
    return TaskStore()


@pytest.fixture()
def workflow(store: TaskStore) -> TaskWorkflowService:
    return TaskWorkflowService(store=store)


def _coordinator(store: TaskStore, rm: _RecordingRuntimeManager) -> TaskExecutionCoordinator:
    return TaskExecutionCoordinator(
        store=store,
        workflow=TaskWorkflowService(store=store),
        runtime_manager=rm,
        workspace_root="/tmp/workspace",  # nosec B108 - never written; the runtime stub raises before any file I/O
    )


@pytest.mark.asyncio
async def test_requires_approval_task_is_gated_not_executed(store):
    rm = _RecordingRuntimeManager()
    task = Task(
        owner_id="o@x.com",
        title="Deploy to production",
        requires_approval=True,
        pending_agent_run=True,
    )
    await store.create(task)

    updated = await _coordinator(store, rm).execute(task.task_id)

    assert rm.calls == 0, "runtime must NOT run for an unapproved requires_approval task"
    assert updated.execution_approved is False
    assert updated.pending_agent_run is False  # parked so the dispatcher won't re-pick it


@pytest.mark.asyncio
async def test_non_approval_task_runs_normally(store):
    rm = _RecordingRuntimeManager()
    task = Task(owner_id="o@x.com", title="Routine bugfix", requires_approval=False, pending_agent_run=True)
    await store.create(task)

    await _coordinator(store, rm).execute(task.task_id)

    assert rm.calls == 1  # no gate → reaches the runtime


@pytest.mark.asyncio
async def test_approve_execution_requeues_for_run(store, workflow):
    task = Task(owner_id="o@x.com", title="Deploy", requires_approval=True, pending_agent_run=False)
    await store.create(task)

    workflow.approve_execution(task, actor="boss@x.com", approved=True)

    assert task.execution_approved is True
    assert task.status is TaskStatus.IN_PROGRESS
    assert task.pending_agent_run is True


@pytest.mark.asyncio
async def test_approved_task_passes_the_gate(store):
    rm = _RecordingRuntimeManager()
    task = Task(
        owner_id="o@x.com",
        title="Deploy",
        requires_approval=True,
        execution_approved=True,  # already approved
        pending_agent_run=True,
    )
    await store.create(task)

    await _coordinator(store, rm).execute(task.task_id)

    assert rm.calls == 1, "an approved requires_approval task must reach the runtime"


@pytest.mark.asyncio
async def test_reject_execution_moves_to_wont_do(store, workflow):
    task = Task(owner_id="o@x.com", title="Deploy", requires_approval=True, pending_agent_run=True)
    await store.create(task)

    workflow.approve_execution(task, actor="boss@x.com", approved=False, reason="not now")

    # Rejection is a human decision, not a system failure — terminal WONT_DO,
    # never BLOCKED/FAILED (which the auto-retry + backlog machinery would sweep).
    assert task.execution_approved is False
    assert task.status is TaskStatus.WONT_DO
    assert task.pending_agent_run is False
    # WONT_DO is reopenable via Retry.
    workflow.retry(task, actor="boss@x.com")
    assert task.status in {TaskStatus.TODO, TaskStatus.IN_PROGRESS}


@pytest.mark.asyncio
async def test_outward_facing_task_is_auto_gated(store, monkeypatch):
    # An outward-facing autonomous task (opens a PR) never sets requires_approval,
    # so it must be promoted at dispatch and parked for the Telegram prompt.
    monkeypatch.setenv("AGENCY_GATE_OUTWARD_FACING", "true")
    rm = _RecordingRuntimeManager()
    task = Task(
        owner_id="o@x.com",
        title="Fix issue #42",
        task_type="issue_intake",       # commits + PR → outward-facing
        requires_approval=False,
        pending_agent_run=True,
    )
    await store.create(task)

    updated = await _coordinator(store, rm).execute(task.task_id)

    assert rm.calls == 0, "outward-facing task must NOT run before approval"
    assert updated.requires_approval is True     # promoted by the dispatcher
    assert updated.pending_agent_run is False     # parked at the gate


@pytest.mark.asyncio
async def test_internal_task_is_not_auto_gated(store, monkeypatch):
    # An internal task (research/scheduling) stays fully autonomous.
    monkeypatch.setenv("AGENCY_GATE_OUTWARD_FACING", "true")
    rm = _RecordingRuntimeManager()
    task = Task(
        owner_id="o@x.com",
        title="Scan trends",
        task_type="trend_scoping",       # internal → not gated
        requires_approval=False,
        pending_agent_run=True,
    )
    await store.create(task)

    await _coordinator(store, rm).execute(task.task_id)

    assert rm.calls == 1, "internal task must reach the runtime without a prompt"


@pytest.mark.asyncio
async def test_outward_facing_gate_respects_disable_flag(store, monkeypatch):
    monkeypatch.setenv("AGENCY_GATE_OUTWARD_FACING", "false")
    rm = _RecordingRuntimeManager()
    task = Task(
        owner_id="o@x.com",
        title="Fix issue #42",
        task_type="issue_intake",
        requires_approval=False,
        pending_agent_run=True,
    )
    await store.create(task)

    await _coordinator(store, rm).execute(task.task_id)

    assert rm.calls == 1, "with the gate disabled, outward-facing tasks stay autonomous"
