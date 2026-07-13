"""Regression: the orchestrator bypass is scoped to *sanctioned* execution paths.

Under the default ``AGENCY_WORKFLOW_MODE=orchestrator``, ``AgentRunner.run()`` is
hard-blocked unless the orchestrator ``_BYPASS`` ContextVar is set.

A prior change removed an unconditional bypass from ``InternalAgentAdapter`` so that
*direct* ``/runtimes/{id}/execute`` API callers could not skip workflow approval —
but that left the background ``TaskDispatcher`` (which reaches the runner through the
adapter) permanently blocked, so tasks were marked BLOCKED after 10 retries.

The fix sets the bypass in the sanctioned background caller —
``TaskExecutionCoordinator.execute()`` — which is driven by the dispatcher and, via
the scheduler, by the CEO Agency.  These tests prove:

  1. the coordinator sets the bypass around runtime execution (tasks run), and
  2. the direct adapter path does NOT bypass (direct API callers stay gated).
"""

from __future__ import annotations

import os
import tempfile

import pytest

from runtimes.base import TaskResult, TaskSpec
from tasks.models import Task, TaskStatus
from tasks.service import TaskExecutionCoordinator
from tasks.store import TaskStore


class _Decision:
    """Minimal stand-in for the RoutingDecision the coordinator reads."""

    selected_runtime_id = "internal_agent"
    model_used = "stub-model"
    reason = "test"
    fallback_runtime_id = None
    fallback_attempted = False


async def test_coordinator_sets_bypass_for_sanctioned_execution(monkeypatch):
    monkeypatch.setattr(
        "services.workflow_orchestrator.WORKFLOW_MODE", "orchestrator"
    )
    import services.workflow_orchestrator as wo

    captured: dict = {}

    class _FakeRuntimeManager:
        async def execute(self, spec):  # noqa: ANN001
            # The coordinator must have set the bypass before reaching the runtime.
            captured["legacy_inside"] = wo.is_legacy_mode()
            captured["bypass_inside"] = wo._BYPASS.get()
            return (
                TaskResult(
                    runtime_id="internal_agent",
                    task_id=spec.task_id,
                    success=True,
                    output="ok",
                    model_used="stub-model",
                ),
                _Decision(),
            )

    store = TaskStore(db=None)  # in-memory
    coord = TaskExecutionCoordinator(
        store=store, runtime_manager=_FakeRuntimeManager(), workspace_root="."
    )

    task = Task(owner_id="u1", title="do work", status=TaskStatus.TODO)
    task.pending_agent_run = True
    await store.create(task)

    await coord.execute(task.task_id)

    assert captured.get("legacy_inside") is True
    assert captured.get("bypass_inside") is True
    # No leakage after the coordinator finishes.
    assert wo._BYPASS.get() is False


@pytest.mark.skipif(
    os.environ.get("TESTING", "").lower() == "true",
    reason="CI sets TESTING=true which changes orchestrator mode behavior — "
           "the direct adapter bypass test needs the default orchestrator mode.",
)
async def test_direct_adapter_does_not_bypass(monkeypatch):
    """Calling the adapter directly (the /runtimes/{id}/execute path) must stay gated:
    the runner is invoked WITHOUT the orchestrator bypass set."""
    monkeypatch.setattr(
        "services.workflow_orchestrator.WORKFLOW_MODE", "orchestrator"
    )
    import services.workflow_orchestrator as wo
    from runtimes.adapters.internal_agent import InternalAgentAdapter

    seen: dict = {}

    async def _fake_run(self, *args, **kwargs):  # noqa: ANN001
        seen["legacy_inside"] = wo.is_legacy_mode()
        return {"steps": [], "report": "stub report exceeding twenty characters."}

    monkeypatch.setattr("agent.loop.AgentRunner.run", _fake_run)

    with tempfile.TemporaryDirectory() as tmp:
        adapter = InternalAgentAdapter({"workspace_root": tmp})
        spec = TaskSpec(task_id="t-direct", instruction="x", workspace_path=tmp)
        await adapter.execute(spec)

    # Direct adapter invocation is gated — no bypass was active inside the runner.
    assert seen.get("legacy_inside") is False
    assert wo._BYPASS.get() is False
