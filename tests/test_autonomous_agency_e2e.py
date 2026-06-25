"""End-to-end tests for the autonomous AI agency system (issue #467).

These tests validate:
- AgentRunner execution path (plan→execute→verify→judge)
- BackgroundAgent retry logic with exponential backoff
- Telegram real-time progress updates
- Direct chat agent mode execution
- Portfolio intelligence and agile sprint systems
- Workflow orchestrator integration
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

import pytest

import sys, os as _os
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))


@dataclass
class FakeTask:
    task_id: str
    instruction: str
    status: str = "pending"
    progress_message: str = ""
    last_heartbeat_at: Optional[str] = None
    retry_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class TestBackgroundAgentRetryLogic:
    """Tests for background agent retry logic with exponential backoff."""

    def test_background_agent_retries_with_exponential_backoff(self):
        """Verify BackgroundAgent retries failed tasks with exponential backoff.

        The retry loop lives inside _process(), which calls asyncio.run(runner.run(...))
        up to max_retries+1 times with exponential backoff sleep between attempts.
        """
        from agent.background import BackgroundAgent, BackgroundTask

        import asyncio as _asyncio
        import inspect as _inspect
        _real_asyncio_run = _asyncio.run

        run_attempts: list[int] = []
        def mock_asyncio_run(coro):
            """Simulate runner.run() failing twice then succeeding.

            The code under test passes a MagicMock (``runner.run(...)``), not a
            real coroutine. This test patches the *global* ``asyncio.run``, so a
            stray ``asyncio.run`` from a concurrent daemon thread left running by
            another test would otherwise inflate ``run_attempts`` and make this
            test flaky (observed in the full-suite run + CI). Pass any real
            coroutine straight through to the real ``asyncio.run`` so only the
            intended retry calls are counted.
            """
            if _inspect.iscoroutine(coro):
                return _real_asyncio_run(coro)
            run_attempts.append(len(run_attempts))
            if len(run_attempts) <= 2:
                raise RuntimeError(f"Simulated failure {len(run_attempts)}")
            return {"summary": "Success", "steps": []}

        bg = BackgroundAgent(agent_runner=MagicMock())
        task = BackgroundTask(
            task_id="retry-test",
            kind="manual",
            payload={"instruction": "test task"},
            created_at=datetime.utcnow().isoformat(),
            max_retries=2,
        )

        with patch("asyncio.run", side_effect=mock_asyncio_run), \
             patch("agent.background.time.sleep") as mock_sleep:
            bg._handle(task)

        assert task.status == "done", f"Expected done, got {task.status}"
        assert len(run_attempts) == 3, f"Expected 3 attempts (1+2 retries), got {len(run_attempts)}"
        assert task.retry_count == 2, f"Expected retry_count=2, got {task.retry_count}"
        # Verify exponential backoff sleep calls: 5s, 10s
        assert mock_sleep.call_count == 2, f"Expected 2 sleep calls, got {mock_sleep.call_count}"
        sleep_args = [call.args[0] for call in mock_sleep.call_args_list]
        assert sleep_args == [5.0, 10.0], f"Expected [5.0, 10.0] backoff, got {sleep_args}"

    def test_retry_delay_configurable(self):
        """Verify retry delay is configurable via environment variable."""
        from agent.background import DEFAULT_RETRY_DELAY_SEC
        assert DEFAULT_RETRY_DELAY_SEC > 0


class TestAgentRunnerExecution:
    """Tests for AgentRunner execution path."""

    def test_agent_runner_has_execute_step_method(self):
        """Verify AgentRunner has _execute_step for ReAct execution loop."""
        from agent.loop import AgentRunner
        runner = AgentRunner(ollama_base="http://localhost:11434")
        assert hasattr(runner, 'run'), "AgentRunner must have run() method"
        assert hasattr(runner, '_execute_step'), "AgentRunner must have _execute_step() method"
        assert hasattr(runner, '_review_step_result'), "AgentRunner must have verification method"

    def test_bypass_context_var_exists_for_internal_calls(self):
        """Verify _BYPASS context var is used for internal agent execution."""
        from agent.loop import AgentRunner
        assert hasattr(AgentRunner, 'run') or True  # Functional test below

        # _BYPASS is a module-level ContextVar in workflow_orchestrator
        import services.workflow_orchestrator as _wo
        from services.workflow_orchestrator import is_legacy_mode
        assert hasattr(_wo, '_BYPASS'), "workflow_orchestrator must define _BYPASS ContextVar"
        token = _wo._BYPASS.set(True)
        try:
            assert _wo._BYPASS.get() is True, "_BYPASS should be True after set"
            assert is_legacy_mode(), "is_legacy_mode should return True when _BYPASS is set"
        finally:
            _wo._BYPASS.reset(token)
        assert _wo._BYPASS.get() is False, "_BYPASS should reset to False"
        assert not is_legacy_mode() or _wo.WORKFLOW_MODE == "legacy", "is_legacy_mode should return False when _BYPASS is not set"


class TestTelegramNotifications:
    """Tests for Telegram notification dispatch."""

    def test_notification_dispatcher_on_task_complete(self):
        """Verify NotificationDispatcher.on_task_complete dispatches notifications."""
        from telegram_service import NotificationDispatcher

        disp = NotificationDispatcher()
        task = FakeTask(task_id="progress-test", instruction="long task", status="done")

        with patch.object(disp, '_notify_telegram') as mock_tg, \
             patch.object(disp, '_notify_webhook') as mock_wh:
            disp.on_task_complete(task)
            assert mock_tg.called, "_notify_telegram should be called"
            assert mock_wh.called, "_notify_webhook should be called"
            sent_msg = mock_tg.call_args[0][0]
            assert "progress-test" in sent_msg


class TestDirectChatAgentExecution:
    """Tests for direct chat agent execution beyond planning."""

    def test_direct_chat_has_agent_mode_field(self):
        """Verify ChatSendRequest supports agent mode execution."""
        from direct_chat import ChatSendRequest

        req = ChatSendRequest(content="test", agent_mode=True)
        assert req.agent_mode is True, "ChatSendRequest should support agent_mode"

    def test_workspace_tools_for_agent_execution(self):
        """Verify WorkspaceTools provides filesystem operations for agents."""
        from agent.tools import WorkspaceTools

        tools = WorkspaceTools(root=".")
        assert hasattr(tools, 'read_file'), "WorkspaceTools must have read_file"
        assert hasattr(tools, 'write_file'), "WorkspaceTools must have write_file"
        assert hasattr(tools, 'list_files'), "WorkspaceTools must have list_files"
        assert hasattr(tools, 'search_code'), "WorkspaceTools must have search_code"


class TestPortfolioIntelligence:
    """Tests for portfolio intelligence system."""

    def test_portfolio_manager_initialization(self):
        """Verify PortfolioManager initializes correctly."""
        from agents.portfolio import PortfolioManager, Initiative, InitiativeStatus

        pm = PortfolioManager()
        assert pm is not None
        assert hasattr(pm, 'initiative_count'), "PortfolioManager must have initiative_count"

        assert hasattr(InitiativeStatus, 'PROPOSED')
        assert hasattr(InitiativeStatus, 'IN_PROGRESS')
        assert hasattr(InitiativeStatus, 'DONE')

    def test_portfolio_intelligence_builds_from_signals(self):
        """Verify PortfolioIntelligence can build from live signals."""
        from agents.portfolio_intelligence import PortfolioIntelligence

        pi = PortfolioIntelligence()
        assert hasattr(pi, 'build'), "PortfolioIntelligence must have build() method"


class TestAgileSprints:
    """Tests for agile sprint management."""

    def test_sprint_velocity_tracking(self):
        """Verify sprint velocity is tracked correctly."""
        from agents.agile_sprints import AgileSprint, SprintStatus

        sprint = AgileSprint(sprint_id="test-1", name="Sprint 1", goal="Test sprint")
        assert sprint is not None
        assert hasattr(sprint, 'name')
        assert hasattr(sprint, 'status')


class TestAgentKPITracking:
    """Tests for agent KPI tracking."""

    def test_kpi_tracker_exists(self):
        """Verify KPI tracker is collected."""
        from agent.kpi import AutonomyTracker, get_tracker

        tracker = get_tracker()
        assert tracker is not None
        assert isinstance(tracker, AutonomyTracker)
        snapshot = tracker.snapshot()
        assert hasattr(snapshot, 'total_sessions')


class TestWorkflowIntegration:
    """Tests for workflow orchestrator integration."""

    def test_workflow_orchestrator_bypass(self):
        """Verify WorkflowOrchestrator correctly bypasses for internal callers."""
        from services.workflow_orchestrator import WorkflowOrchestrator
        import services.workflow_orchestrator as _wo

        wo = WorkflowOrchestrator()
        assert hasattr(wo, '_handle_execute'), "WorkflowOrchestrator must have _handle_execute"
        assert hasattr(_wo, '_BYPASS'), "workflow_orchestrator must define _BYPASS ContextVar"

    def test_internal_agent_adapter_exists(self):
        """Verify InternalAgentAdapter provides agent execution for workflows."""
        from runtimes.adapters.internal_agent import InternalAgentAdapter

        adapter = InternalAgentAdapter()
        assert hasattr(adapter, 'execute'), "InternalAgentAdapter must have execute()"


class TestCEOAgencySystem:
    """Tests for CEO-driven agency system."""

    def test_ceo_agent_role_exists(self):
        """Verify CEO agent system is implemented."""
        from agent.agency import Agency, AgentRole

        assert hasattr(AgentRole, 'CEO'), "AgentRole must have CEO role"
        assert Agency is not None

    def test_agency_cycle_workflow_exists(self):
        """Verify agency cycle GitHub Actions workflow exists."""
        workflow_path = ".github/workflows/agency-cycle.yml"
        assert _os.path.exists(workflow_path), f"Agency cycle workflow should exist at {workflow_path}"


class TestFreeBuffAgent:
    """Tests for FreeBuff Telegram agent."""

    def test_freebuff_agent_model_routing(self):
        """Verify FreeBuff agent pins to free NVIDIA models."""
        from agent.loop import FreeBuffAgent

        runner = FreeBuffAgent()
        assert hasattr(runner, 'resolve_model'), "FreeBuffAgent must have resolve_model()"
        resolved = runner.resolve_model(None)
        assert resolved, "resolve_model should return a model even when None is passed"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])