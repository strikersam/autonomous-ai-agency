"""tests/test_orchestrator_supervisor.py — Tests for deterministic supervisor (#522)."""
from __future__ import annotations

import asyncio
import time
import pytest


class TestOrchestratorSupervisor:
    """Supervisor startup, stall detection, and alert emission."""

    async def test_start_stop(self):
        from services.orchestrator_supervisor import (
            get_orchestrator_supervisor,
            stop_orchestrator_supervisor,
            _supervisor as _sv_singleton,
        )
        _sv_backup = _sv_singleton

        import services.orchestrator_supervisor as sv_mod
        sv_mod._supervisor = None
        sv = get_orchestrator_supervisor()
        await sv.start()
        assert sv.state.running is True

        await asyncio.sleep(0.1)
        assert sv.state.ticks >= 1

        await sv.stop()
        assert sv.state.running is False
        sv_mod._supervisor = _sv_backup

    async def test_state_initial_values(self):
        from services.orchestrator_supervisor import (
            get_orchestrator_supervisor,
            _supervisor as _sv_singleton,
        )
        _sv_backup = _sv_singleton
        import services.orchestrator_supervisor as sv_mod
        sv_mod._supervisor = None

        sv = get_orchestrator_supervisor()
        assert sv.state.running is False
        assert sv.state.ticks == 0
        assert sv.state.stalled_recovered == 0
        assert sv.state.alerts_emitted == 0
        sv_mod._supervisor = _sv_backup

    async def test_stall_detection_debounce(self, monkeypatch):
        """Supervisor requires 2 consecutive detections before acting."""
        from services.workflow_orchestrator import (
            get_workflow_orchestrator,
            reset_orchestrator,
            WorkflowRun,
            ExecutionRequest,
        )
        from services.orchestrator_supervisor import OrchestratorSupervisor

        reset_orchestrator()
        orch = get_workflow_orchestrator()

        # Create a stalled run (a real in-flight run always has _request set —
        # execute() sets it as the first statement).
        run = WorkflowRun(run_id="stalled-1")
        run._request = ExecutionRequest(request="test")
        run.status = "running"
        run.last_heartbeat = time.time() - 9999  # very stale
        run.retry_count = 0
        orch._runs[run.run_id] = run

        sv = OrchestratorSupervisor()
        monkeypatch.setattr(sv, "_get_orchestrator", lambda: orch)

        # First tick: stall detected but not acted on (debounce)
        await sv._tick()
        assert sv._stall_count.get("stalled-1", 0) == 1
        assert run.status == "running"  # not changed yet

        # Second tick: now acts
        await sv._tick()
        assert sv._stall_count.get("stalled-1", 0) == 0  # cleared after action
        assert run.status == "queued"
        assert run.retry_count >= 1

    async def test_max_retries_exceeded_marks_failed(self, monkeypatch):
        from services.workflow_orchestrator import (
            get_workflow_orchestrator,
            reset_orchestrator,
            WorkflowRun,
            ExecutionRequest,
        )
        from services.orchestrator_supervisor import OrchestratorSupervisor

        reset_orchestrator()
        orch = get_workflow_orchestrator()

        run = WorkflowRun(run_id="dead-run")
        run._request = ExecutionRequest(request="test")
        run.status = "running"
        run.last_heartbeat = time.time() - 9999
        run.retry_count = 5  # already exceeded 3 max
        orch._runs[run.run_id] = run

        sv = OrchestratorSupervisor()
        monkeypatch.setattr(sv, "_get_orchestrator", lambda: orch)
        # Override max retries for test
        monkeypatch.setattr("services.orchestrator_supervisor._MAX_RETRIES", 3)

        # Two ticks to trigger debounce
        await sv._tick()
        await sv._tick()

        assert run.status == "failed"
        assert run.error is not None
        assert "Stalled" in run.error or "retries" in run.error.lower()

    async def test_healthy_run_not_flagged(self, monkeypatch):
        from services.workflow_orchestrator import (
            get_workflow_orchestrator,
            reset_orchestrator,
            WorkflowRun,
        )
        from services.orchestrator_supervisor import OrchestratorSupervisor

        reset_orchestrator()
        orch = get_workflow_orchestrator()

        run = WorkflowRun(run_id="healthy-1")
        run.status = "running"
        run.last_heartbeat = time.time()  # fresh
        run.retry_count = 0
        orch._runs[run.run_id] = run

        sv = OrchestratorSupervisor()
        monkeypatch.setattr(sv, "_get_orchestrator", lambda: orch)

        await sv._tick()
        await sv._tick()

        assert run.status == "running"  # unchanged
        assert sv.state.stalled_recovered == 0

    async def test_stalled_run_without_request_marked_failed(self, monkeypatch):
        """A stalled run with no persisted _request can never be resumed —
        execute(None, ...) raises AttributeError on req.user_id/req.company_id.
        The supervisor must mark it failed instead of enqueuing it."""
        from services.workflow_orchestrator import (
            get_workflow_orchestrator,
            reset_orchestrator,
            WorkflowRun,
        )
        from services.orchestrator_supervisor import OrchestratorSupervisor

        reset_orchestrator()
        orch = get_workflow_orchestrator()

        run = WorkflowRun(run_id="stalled-no-req")
        run.status = "running"
        run.last_heartbeat = time.time() - 9999
        run.retry_count = 0
        # run._request stays None (default)
        orch._runs[run.run_id] = run

        sv = OrchestratorSupervisor()
        monkeypatch.setattr(sv, "_get_orchestrator", lambda: orch)

        # Two ticks to trigger debounce
        await sv._tick()
        await sv._tick()

        assert run.status == "failed"
        assert run.error is not None
        assert "cannot resume" in run.error.lower()

    async def test_done_runs_ignored(self, monkeypatch):
        from services.workflow_orchestrator import (
            get_workflow_orchestrator,
            reset_orchestrator,
            WorkflowRun,
        )
        from services.orchestrator_supervisor import OrchestratorSupervisor

        reset_orchestrator()
        orch = get_workflow_orchestrator()

        run = WorkflowRun(run_id="done-1")
        run.status = "done"  # terminal
        run.last_heartbeat = time.time() - 9999
        orch._runs[run.run_id] = run

        sv = OrchestratorSupervisor()
        monkeypatch.setattr(sv, "_get_orchestrator", lambda: orch)

        await sv._tick()
        assert run.status == "done"  # never touched
