"""Phase 2 C: WorkflowRun is mirrored into a RunRecord (packages/runs/orchestrator_binding.py)."""
from __future__ import annotations

import pytest

from packages.runs import orchestrator_binding
from packages.runs.models import RunState
from packages.runs.store import RunStore, get_run_store, set_run_store


@pytest.fixture(autouse=True)
def _fresh_store(monkeypatch):
    monkeypatch.setenv("RUNS_LEDGER_ENABLED", "true")
    set_run_store(RunStore())
    yield
    set_run_store(None)


def _fake_orchestrator(fail_phase=None):
    from services.workflow_orchestrator import get_workflow_orchestrator, reset_orchestrator

    reset_orchestrator()
    orchestrator = get_workflow_orchestrator()

    def handler(phase):
        async def run_phase(run, req):
            if phase == fail_phase:
                raise RuntimeError("phase broke")
        return run_phase

    orchestrator._phase_handlers = {p: handler(p) for p in orchestrator._phase_handlers}
    return orchestrator


@pytest.mark.anyio
@pytest.mark.parametrize("fail", [False, True])
async def test_a_golden_path_run_is_mirrored_to_its_terminal_state(fail):
    from services.workflow_orchestrator import ExecutionRequest, Phase

    orchestrator = _fake_orchestrator(Phase.PERSIST if fail else None)
    run = await orchestrator.execute(
        ExecutionRequest(request="Mirror this golden path run", auto_approve=True, max_steps=1))
    assert run.status == ("failed" if fail else "done")
    record = await get_run_store().get(run.run_id)
    assert record is not None and record.workflow_id == run.run_id and record.task_id is None
    assert record.state is (RunState.FAILED if fail else RunState.SUCCEEDED)
    assert record.phase == run.current_phase
    if fail:
        assert "phase broke" in record.failure_reason


@pytest.mark.anyio
async def test_a_run_paused_at_the_approval_gate_waits_for_approval():
    from services.workflow_orchestrator import ExecutionRequest

    run = await _fake_orchestrator().execute(
        ExecutionRequest(request="Pause me at the gate", auto_approve=False, max_steps=1))
    assert run.status == "awaiting_approval"
    record = await get_run_store().get(run.run_id)
    assert record.state is RunState.WAITING_FOR_APPROVAL
    assert record.waiting_reason == "approval_gate"


@pytest.mark.anyio
async def test_mirroring_never_raises_and_respects_the_ledger_switch(monkeypatch):
    from services.workflow_orchestrator import WorkflowRun

    run = WorkflowRun(status="running")
    monkeypatch.setenv("RUNS_LEDGER_ENABLED", "false")
    await orchestrator_binding.mirror_run(run)
    assert await get_run_store().get(run.run_id) is None

    monkeypatch.setenv("RUNS_LEDGER_ENABLED", "true")

    class _Broken:
        async def get(self, run_id):
            raise RuntimeError("store down")

    monkeypatch.setattr("packages.runs.store.get_run_store", lambda: _Broken())
    await orchestrator_binding.mirror_run(run)  # logged, not raised


@pytest.mark.anyio
async def test_a_terminal_mirror_is_not_moved_again():
    from services.workflow_orchestrator import WorkflowRun

    run = WorkflowRun(status="running")
    await orchestrator_binding.mirror_run(run)
    run.status = "done"
    await orchestrator_binding.mirror_run(run)
    run.status = "failed"
    await orchestrator_binding.mirror_run(run)
    assert (await get_run_store().get(run.run_id)).state is RunState.SUCCEEDED
