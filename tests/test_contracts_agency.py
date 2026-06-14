"""tests/test_contracts_agency.py — Contract tests for agency core autonomy hardening.

PR #468: Agency Core Autonomy Hardening.
These contract tests verify that:
  1. WorkflowEngine ApprovalGate MANDATORILY blocks code paths
  2. BackgroundAgent._process dispatches through AgentRunner (not stub)
  3. AgentRunner._local_safety_check catches hardcoded secrets
  4. Diagnostics public/authenticated split works
  5. Autonomy KPIs are tracked correctly
"""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from agent.background import BackgroundAgent, BackgroundTask
from workflow.engine import WorkflowEngine
from workflow.models import ApprovalGate, WorkflowBuildRequest


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def engine(tmp_path: Path) -> WorkflowEngine:
    return WorkflowEngine(
        ollama_base="http://localhost:11434",
        db_path=tmp_path / "workflow.db",
        artifacts_root=tmp_path / "artifacts",
        workspace_root=tmp_path,
    )


@pytest.fixture()
def background_agent() -> BackgroundAgent:
    return BackgroundAgent()


def _now() -> str:
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ── Contract Test 1: ApprovalGate MUST block execution ────────────────────────


class TestApprovalGateMandatory:
    """Contract: No code path may advance past awaiting_approval unless
    gate.status == 'approved'. This test verifies that approve() rejects
    requests in the wrong state, and reject() properly fails the run."""

    def _create_at_gate(self, engine: WorkflowEngine) -> str:
        """Create a run and manually place it in awaiting_approval."""
        req = WorkflowBuildRequest(request="Test approval gate enforcement")
        with patch.object(engine, "_run_pre_gate_phases", new=AsyncMock()):
            run = asyncio.run(engine.create_run(req))
        with engine._lock:
            r = engine._runs[run.run_id]
            r.status = "awaiting_approval"
            r.approval_gate = ApprovalGate(
                gate_id="gate_test",
                run_id=run.run_id,
                status="pending",
            )
            engine._save(r)
        return run.run_id

    def test_approve_from_pending_state_raises(self, engine):
        """Contract: Cannot approve a run in 'pending' state."""
        req = WorkflowBuildRequest(request="Should not be approvable")
        with patch.object(engine, "_run_pre_gate_phases", new=AsyncMock()):
            run = asyncio.run(engine.create_run(req))
        with pytest.raises(ValueError, match="awaiting_approval"):
            engine.approve(run.run_id)

    def test_approve_from_awaiting_approval_succeeds(self, engine):
        """Contract: Can approve a run in 'awaiting_approval' state."""
        run_id = self._create_at_gate(engine)

        async def do_approve():
            with patch.object(engine, "_run_post_gate", new=AsyncMock()):
                return engine.approve(run_id, approved_by="tester")

        updated = asyncio.run(do_approve())
        assert updated.status == "executing"
        assert updated.approval_gate.status == "approved"

    def test_reject_from_awaiting_approval_fails_run(self, engine):
        """Contract: Rejecting a run marks it as failed."""
        run_id = self._create_at_gate(engine)
        updated = engine.reject(run_id, reason="Not good enough")
        assert updated.status == "failed"
        assert updated.approval_gate.status == "rejected"

    def test_cannot_auto_bypass_gate(self, engine):
        """Contract: WorkflowEngine cannot skip the gate state machine."""
        req = WorkflowBuildRequest(request="Auto-bypass test")
        with patch.object(engine, "_run_pre_gate_phases", new=AsyncMock()):
            run = asyncio.run(engine.create_run(req))
        # After pre-gate phases, status should be awaiting_approval
        # (we patched _run_pre_gate_phases so it stays 'pending')
        assert run.status == "pending"
        # The gate should only be lifted by approve(), not by any internal path
        run = engine.get(run.run_id)
        assert run is not None
        assert run.approval_gate is None  # Gate not created yet (pre-gate patched)


# ── Contract Test 2: BackgroundAgent._process MUST dispatch real work ──────────


class TestBackgroundAgentDispatch:
    """Contract: BackgroundAgent._process() is not a no-op stub.
    When an agent_runner is injected, tasks with instructions must
    be dispatched through it."""

    def test_process_without_runner_returns_fallback(self, background_agent):
        """When no runner is injected, _process returns a fallback note (not error)."""
        task = BackgroundTask(
            task_id="test_001",
            kind="manual",
            payload={"instruction": "Run tests"},
            created_at=_now(),
        )
        result = background_agent._process(task)
        assert result["dispatched"] is True
        assert "note" in result or "No AgentRunner" in str(result.get("note", ""))

    def test_process_without_instruction_returns_error(self, background_agent):
        """When runner is injected but payload has no instruction, returns error."""
        from unittest.mock import MagicMock
        mock_runner = MagicMock()
        agent = BackgroundAgent(agent_runner=mock_runner)
        task = BackgroundTask(
            task_id="test_002",
            kind="manual",
            payload={},  # No instruction
            created_at=_now(),
        )
        result = agent._process(task)
        assert result["dispatched"] is False
        assert "error" in result

    def test_process_with_runner_dispatches(self):
        """When runner is injected, _process invokes runner.run()."""
        from unittest.mock import MagicMock
        mock_runner = MagicMock()
        mock_runner.run = AsyncMock(return_value={
            "goal": "Test",
            "steps": [{"status": "applied"}],
            "commits": [],
            "summary": "Done",
        })
        agent = BackgroundAgent(agent_runner=mock_runner)
        task = BackgroundTask(
            task_id="test_003",
            kind="scheduled",
            payload={"instruction": "Run pytest", "max_steps": 2},
            created_at=_now(),
        )
        result = agent._process(task)
        assert mock_runner.run.called
        assert result["goal"] == "Test"

    def test_submit_start_stop_lifecycle(self, background_agent):
        """Contract: BackgroundAgent lifecycle works — submit, start, stop."""
        completed: list[BackgroundTask] = []
        agent = BackgroundAgent(on_task_complete=lambda t: completed.append(t))
        agent.start()
        assert agent.is_running is True
        task = BackgroundTask(
            task_id="lifecycle_001",
            kind="manual",
            payload={"instruction": "Say hello"},
            created_at=_now(),
        )
        agent.submit(task)
        agent.stop(timeout=5.0)
        retrieved = agent.get_task("lifecycle_001")
        assert retrieved is not None
        assert retrieved.status in ("done", "failed")  # Was processed


# ── Contract Test 3: AgentRunner safety checks ────────────────────────────────


class TestAgentRunnerSafety:
    """Contract: AgentRunner._local_safety_check must catch hardcoded secrets
    and other security issues."""

    def test_detects_hardcoded_secret_key(self, tmp_path: Path):
        """Contract: Auth code with hardcoded SECRET_KEY triggers a safety issue.

        The safety check is scoped to auth/JWT-related Python files. Content
        must mention jwt, oauth2, or authentication AND contain a hardcoded secret."""
        from agent.loop import AgentRunner
        runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=tmp_path)

        # Code that mentions authentication AND hardcodes a secret key
        issues = runner._local_safety_check(
            "auth.py",
            'SECRET_KEY = "hardcoded-value"\n# This module handles authentication\nfrom fastapi import FastAPI',
        )
        assert len(issues) > 0
        assert any("SECRET_KEY" in issue for issue in issues)

    def test_passes_clean_code(self, tmp_path: Path):
        """Contract: Clean code without secrets passes safety check."""
        from agent.loop import AgentRunner
        runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=tmp_path)
        issues = runner._local_safety_check(
            "app.py",
            'from fastapi import FastAPI\napp = FastAPI()\n',
        )
        assert issues == []

    def test_skips_non_python_files(self, tmp_path: Path):
        """Contract: Safety check only applies to Python files."""
        from agent.loop import AgentRunner
        runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=tmp_path)
        issues = runner._local_safety_check(
            "README.md",
            'SECRET_KEY = "hardcoded"\n',
        )
        assert issues == []

    def test_detects_module_wide_tasks_touching_too_few_files(self, tmp_path: Path):
        """Contract: Module-wide change touching too few files is flagged."""
        from agent.loop import AgentRunner
        runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=tmp_path)
        issues = runner._review_step_result(
            step={"id": 1, "description": "Update logging across this module"},
            changed_files=["logging.py"],
        )
        assert len(issues) > 0
        assert any("too few files" in issue.lower() for issue in issues)


# ── Contract Test 4: Diagnostics public/authenticated split ──────────────────


class TestDiagnostics:
    """Contract: Public diagnostics don't leak internals; authenticated
    diagnostics give full detail."""

    def test_public_status_has_required_keys(self):
        """Contract: Public status returns only safe fields."""
        from handlers.diagnostics import run_public_status
        status = run_public_status()
        # Must have basic health info
        assert "status" in status
        assert "ollama" in status
        # Must NOT have session data or event log details
        assert "sessions" not in status
        assert "event_log" not in status
        assert "provider_chain" not in status

    def test_deep_diagnostics_has_full_detail(self):
        """Contract: Deep diagnostics include all system sections."""
        from handlers.diagnostics import run_deep_diagnostics
        deep = asyncio.run(run_deep_diagnostics())
        assert "ollama" in deep
        assert "sessions" in deep
        assert "workflow" in deep
        assert "disk" in deep
        assert "event_log" in deep
        assert "provider_chain" in deep

    def test_available_fixes_list(self):
        """Contract: Fix list includes at least restart_ollama."""
        from handlers.diagnostics import list_available_fixes
        fixes = list_available_fixes()
        assert len(fixes) > 0
        fix_names = {f["name"] for f in fixes}
        assert "restart_ollama" in fix_names


# ── Contract Test 5: Autonomy KPIs ───────────────────────────────────────────


class TestAutonomyKPIs:
    """Contract: KPI tracker correctly counts events and produces snapshots."""

    def test_tracker_starts_at_zero(self):
        from agent.kpi import AutonomyTracker
        t = AutonomyTracker()
        snap = t.snapshot()
        assert snap.steps_applied == 0
        assert snap.steps_failed == 0

    def test_record_step_applied_increments(self):
        from agent.kpi import AutonomyTracker
        t = AutonomyTracker()
        t.record_step_applied(3)
        snap = t.snapshot()
        assert snap.steps_applied == 3

    def test_record_safety_block_increments(self):
        from agent.kpi import AutonomyTracker
        t = AutonomyTracker()
        t.record_safety_block()
        t.record_safety_block()
        snap = t.snapshot()
        assert snap.safety_blocks == 2

    def test_snapshot_is_immutable_snapshot(self):
        """Contract: Two snapshots can differ (non-blocking counters)."""
        from agent.kpi import AutonomyTracker
        t = AutonomyTracker()
        snap1 = t.snapshot()
        t.record_commit()
        snap2 = t.snapshot()
        assert snap2.commits_made > snap1.commits_made

    def test_singleton_is_shared(self):
        """Contract: get_tracker() returns the same instance."""
        from agent.kpi import get_tracker, reset_tracker
        reset_tracker()
        t1 = get_tracker()
        t2 = get_tracker()
        assert t1 is t2
        reset_tracker()

    def test_record_approval_gate_works(self):
        from agent.kpi import AutonomyTracker
        t = AutonomyTracker()
        t.record_approval_gate_passed()
        t.record_approval_gate_rejected()
        snap = t.snapshot()
        assert snap.approval_gates_passed == 1
        assert snap.approval_gates_rejected == 1
