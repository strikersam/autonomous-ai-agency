"""Brain-availability preflight tests (graceful degradation).

When NO LLM brain is configured, the dispatcher must NOT spin up a worktree and
hard-fail every task at EXECUTE. Instead it DEFERS the task — keeps it queued
(``pending_agent_run=True``, status ``TODO``) so it auto-runs once a brain is
configured — and only BLOCKs it after ``_BRAIN_DEFER_LIMIT`` deferrals. A
transient brain/connection error during EXECUTE re-queues rather than FAILs.
"""
from __future__ import annotations

import httpx
import pytest

import tasks.service as svc
from tasks.models import Task, TaskStatus
from tasks.service import TaskExecutionCoordinator, TaskWorkflowService, _BRAIN_DEFER_LIMIT
from tasks.store import TaskStore


class _RecordingRuntimeManager:
    def __init__(self, exc: BaseException | None = None) -> None:
        self.calls = 0
        self._exc = exc or RuntimeError("reached runtime")

    async def execute(self, spec):
        self.calls += 1
        raise self._exc


@pytest.fixture()
def store() -> TaskStore:
    return TaskStore()


def _coordinator(store: TaskStore, rm: _RecordingRuntimeManager) -> TaskExecutionCoordinator:
    return TaskExecutionCoordinator(
        store=store,
        workflow=TaskWorkflowService(store=store),
        runtime_manager=rm,
        workspace_root="/tmp/workspace",  # nosec B108 - runtime stub raises before any I/O
    )


@pytest.fixture()
def no_brain(monkeypatch):
    async def _false() -> bool:
        return False
    monkeypatch.setattr(svc, "_brain_is_configured", _false)


@pytest.fixture()
def has_brain(monkeypatch):
    async def _true() -> bool:
        return True
    monkeypatch.setattr(svc, "_brain_is_configured", _true)


@pytest.mark.asyncio
async def test_no_brain_defers_task_and_keeps_it_queued(store, no_brain):
    rm = _RecordingRuntimeManager()
    task = Task(owner_id="o@x.com", title="Routine bugfix", requires_approval=False, pending_agent_run=True)
    await store.create(task)

    updated = await _coordinator(store, rm).execute(task.task_id)

    assert rm.calls == 0, "no worktree/runtime work when there is no brain"
    assert updated.status is TaskStatus.TODO, "deferred, not failed"
    assert updated.pending_agent_run is True, "stays on the dispatch queue for auto-retry"
    assert any(e.event_type == "brain_unavailable" for e in updated.execution_log)


@pytest.mark.asyncio
async def test_no_brain_blocks_after_defer_limit(store, no_brain):
    rm = _RecordingRuntimeManager()
    task = Task(owner_id="o@x.com", title="Routine bugfix", requires_approval=False, pending_agent_run=True)
    # Pre-seed the deferral budget as already exhausted.
    for _ in range(_BRAIN_DEFER_LIMIT):
        task.add_log("prior defer", event_type="brain_unavailable")
    await store.create(task)

    updated = await _coordinator(store, rm).execute(task.task_id)

    assert rm.calls == 0
    assert updated.status is TaskStatus.BLOCKED
    assert updated.pending_agent_run is False  # parked; dispatcher won't hot-loop it


@pytest.mark.asyncio
async def test_brain_present_passes_preflight(store, has_brain):
    rm = _RecordingRuntimeManager()
    task = Task(owner_id="o@x.com", title="Routine bugfix", requires_approval=False, pending_agent_run=True)
    await store.create(task)

    await _coordinator(store, rm).execute(task.task_id)

    assert rm.calls == 1, "with a brain configured, the task reaches the runtime unchanged"


@pytest.mark.asyncio
async def test_brain_connection_error_requeues_not_fails(store, has_brain):
    rm = _RecordingRuntimeManager(exc=httpx.ConnectError("Connection refused"))
    task = Task(owner_id="o@x.com", title="Routine bugfix", requires_approval=False, pending_agent_run=True)
    await store.create(task)

    updated = await _coordinator(store, rm).execute(task.task_id)

    assert rm.calls == 1
    assert updated.status is TaskStatus.TODO, "connection error re-queues instead of FAILED"
    assert updated.pending_agent_run is True
    assert any(e.event_type == "runtime_unavailable" for e in updated.execution_log)


def test_is_brain_connection_error_matches_typical_failures():
    assert svc._is_brain_connection_error(httpx.ConnectError("x"))
    assert svc._is_brain_connection_error(Exception("All connection attempts failed"))
    assert svc._is_brain_connection_error(Exception("Connection refused"))
    assert not svc._is_brain_connection_error(Exception("ValueError: bad plan output"))
