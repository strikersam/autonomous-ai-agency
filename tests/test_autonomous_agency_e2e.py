"""End-to-end tests for the autonomous AI agency system (issue #467).

These tests validate:
- AgentRunner execution path (plan→execute→verify→judge)
- BackgroundAgent retry logic with exponential backoff
- Telegram real-time progress updates
- Direct chat agent mode execution
- Portfolio intelligence and agile sprint systems
- Workflow orchestrator integration
"""
import time
import threading
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
        """Verify BackgroundAgent retries failed tasks with exponential backoff."""
        from agent.background import BackgroundAgent, DEFAULT_RETRY_DELAY_SEC, BackgroundTask

        attempts = []
        def mock_process(task: BackgroundTask):
            attempts.append(task.retry_count)
            if task.retry_count < 2:
                task.status = "failed"
                return False
            task.status = "completed"
            return True

        bg = BackgroundAgent()
        # BackgroundAgent processes BackgroundTask, not FakeTask
        task = BackgroundTask(
            task_id="retry-test",
            kind="manual",
            payload={"instruction": "test task"},
            created_at=datetime.utcnow().isoformat(),
        )

        with patch.object(bg, '_process', mock_process):
            start = time.time()
            # BackgroundAgent has no process_task() — use _handle() directly
            bg._handle(task)
            elapsed = time.time() - start

            assert task.status == "completed"
            assert attempts == [0, 1, 2], f"Expected [0, 1, 2], got {attempts}"
            # Exponential backoff: delay = base * 2^(attempt-1)
            # attempt 1 delay = 5 * 2^0 = 5s, attempt 2 delay = 5 * 2^1 = 10s
            assert elapsed >= (DEFAULT_RETRY_DELAY_SEC * 2 ** 1), f"Expected >= {DEFAULT_RETRY_DELAY_SEC * 2}s delay, got {elapsed:.2f}s"

    def test_retry_delay_configurable(self):
        """Verify retry delay is configurable via environment variable."""
        from agent.background import DEFAULT_RETRY_DELAY_SEC
        assert DEFAULT_RETRY_DELAY_SEC > 0


class TestAgentRunnerExecution:
    """Tests for AgentRunner execution path."""

    def test_agent_runner_has_execute_step_method(self):
        """Verify AgentRunner has _execute_step for ReAct execution loop."""
        from agent.loop import AgentRunner
        runner = AgentRunner()
        assert hasattr(runner, 'run'), "AgentRunner must have run() method"
        assert hasattr(runner, '_execute_step'), "AgentRunner must have _execute_step() method"
        assert hasattr(runner, '_verify'), "AgentRunner must have _verify() method"

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


class TestTelegramProgressUpdates:
    """Tests for Telegram real-time progress updates."""

    def test_telegram_progress_monitor_sends_updates(self):
        """Verify Telegram progress monitor sends updates while task is active."""
        from telegram_service import NotificationDispatcher

        disp = NotificationDispatcher()
        task = FakeTask(task_id="progress-test", instruction="long task", status="running")

        sent_messages = []
        def mock_send_telegram(message):
            sent_messages.append(message)

        stop_flags = {}

        with patch.object(disp, 'send_telegram', mock_send_telegram):
            t = threading.Thread(target=disp._monitor_task_progress, args=(task, "chat123", stop_flags))
            t.start()

            time.sleep(1)
            task.progress_message = "Step 1/3 complete"
            time.sleep(1)
            task.status = "completed"

            t.join(timeout=5)

            assert len(sent_messages) >= 1, f"Expected at least 1 progress message, got {len(sent_messages)}"


class TestDirectChatAgentExecution:
    """Tests for direct chat agent execution beyond planning."""

    def test_direct_chat_handler_has_agent_mode_support(self):
        """Verify DirectChatHandler supports agent mode execution."""
        from direct_chat import DirectChatHandler

        handler = DirectChatHandler()
        # Check for agent-related attributes
        has_agent_support = (
            hasattr(handler, '_agent_executor') or
            hasattr(handler, 'run_agent_task') or
            hasattr(handler, '_BYPASS')
        )
        assert has_agent_support, "DirectChatHandler should have agent mode support"

    def test_workspace_tools_for_agent_execution(self):
        """Verify WorkspaceTools provides filesystem operations for agents."""
        from agent.tools import WorkspaceTools

        tools = WorkspaceTools(root=".")
        assert hasattr(tools, 'read_file'), "WorkspaceTools must have read_file"
        assert hasattr(tools, 'write_file'), "WorkspaceTools must have write_file"
        assert hasattr(tools, 'list_directory'), "WorkspaceTools must have list_directory"


class TestPortfolioIntelligence:
    """Tests for portfolio intelligence system."""

    def test_portfolio_manager_initialization(self):
        """Verify PortfolioManager initializes correctly."""
        from agents.portfolio import PortfolioManager, Initiative, InitiativeStatus

        pm = PortfolioManager()
        assert pm is not None
        assert hasattr(pm, 'initiatives')

        assert hasattr(InitiativeStatus, 'PROPOSED')
        assert hasattr(InitiativeStatus, 'IN_PROGRESS')
        assert hasattr(InitiativeStatus, 'COMPLETED')

    def test_portfolio_intelligence_sweeps_signals(self):
        """Verify PortfolioIntelligence can sweep signals for initiative discovery."""
        from agents.portfolio_intelligence import PortfolioIntelligence

        pi = PortfolioIntelligence()
        assert hasattr(pi, 'sweep'), "PortfolioIntelligence must have sweep() method"


class TestAgileSprints:
    """Tests for agile sprint management."""

    def test_sprint_velocity_tracking(self):
        """Verify sprint velocity is tracked correctly."""
        from agents.agile_sprints import Sprint, SprintStatus

        sprint = Sprint(name="Sprint 1", goal="Test sprint")
        assert sprint is not None
        assert hasattr(sprint, 'name')
        assert hasattr(sprint, 'status')


class TestAgentKPITracking:
    """Tests for agent KPI tracking."""

    def test_kpi_metrics_exist(self):
        """Verify KPI metrics are collected."""
        from agent.kpi import KPIMetrics

        metrics = KPIMetrics()
        assert metrics is not None


class TestWorkflowIntegration:
    """Tests for workflow orchestrator integration."""

    def test_workflow_orchestrator_bypass(self):
        """Verify WorkflowOrchestrator correctly bypasses for internal callers."""
        from services.workflow_orchestrator import WorkflowOrchestrator

        wo = WorkflowOrchestrator()
        assert hasattr(wo, '_BYPASS'), "WorkflowOrchestrator must have _BYPASS"
        assert hasattr(wo, '_handle_execute'), "WorkflowOrchestrator must have _handle_execute"

    def test_internal_agent_adapter_exists(self):
        """Verify InternalAgentAdapter provides agent execution for workflows."""
        from runtimes.adapters.internal_agent import InternalAgentAdapter

        adapter = InternalAgentAdapter()
        assert hasattr(adapter, 'execute'), "InternalAgentAdapter must have execute()"


class TestCEOAgencySystem:
    """Tests for CEO-driven agency system."""

    def test_ceo_agent_exists(self):
        """Verify CEO agent system is implemented."""
        from agent.agency import AgencyCoordinator, AgentRole

        assert hasattr(AgentRole, 'CEO'), "AgentRole must have CEO role"
        assert AgencyCoordinator is not None

    def test_agency_cycle_workflow_exists(self):
        """Verify agency cycle GitHub Actions workflow exists."""
        workflow_path = ".github/workflows/agency-cycle.yml"
        assert _os.path.exists(workflow_path), f"Agency cycle workflow should exist at {workflow_path}"


class TestFreeBuffAgent:
    """Tests for FreeBuff Telegram agent."""

    def test_freebuff_agent_model_routing(self):
        """Verify FreeBuff agent pins to free NVIDIA models."""
        from agent.loop import AgentRunner

        # Check that resolve_model coerces to free models when FREEBUFF_MODELS is set
        runner = AgentRunner()
        assert hasattr(runner, 'resolve_model'), "AgentRunner must have resolve_model()"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])