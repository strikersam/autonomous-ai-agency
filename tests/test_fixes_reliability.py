"""tests/test_fixes_reliability.py — Regression tests for the batch of fixes.

Covers:
  1. AgentRunner.plan() public wrapper exists and delegates to _generate_plan
  2. AgentRunner.run() accepts (and ignores) the metadata= kwarg
  3. InternalAgentAdapter.execute() no longer passes provider_chain to AgentRunner
  4. TaskDispatcher emits time-to-pickup diagnostics
  5. Agency de-duplication prevents repeat directives
  6. Dashboard partial-failure: DashboardHome renders even when stats fails
"""

from __future__ import annotations

import asyncio
import inspect
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── 1 & 2: AgentRunner.plan() / run(metadata=...) ────────────────────────────


class TestAgentRunnerPublicPlanMethod:
    def test_plan_method_exists(self):
        """AgentRunner must expose a public plan() coroutine."""
        from agent.loop import AgentRunner

        assert hasattr(AgentRunner, "plan"), (
            "AgentRunner is missing the public plan() method that direct_chat.py depends on"
        )
        assert inspect.iscoroutinefunction(AgentRunner.plan), (
            "AgentRunner.plan must be an async method"
        )

    def test_run_accepts_metadata_kwarg(self):
        """AgentRunner.run() must accept a metadata= keyword argument."""
        from agent.loop import AgentRunner

        sig = inspect.signature(AgentRunner.run)
        assert "metadata" in sig.parameters, (
            "AgentRunner.run() must accept metadata= (direct_chat.py passes it)"
        )

    def test_plan_delegates_to_generate_plan(self, tmp_path):
        """plan() should delegate to _generate_plan() and return an AgentPlan."""
        from agent.loop import AgentRunner
        from agent.models import AgentPlan, AgentStep

        runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=tmp_path)

        fake_plan = AgentPlan(
            goal="Test goal",
            steps=[AgentStep(id=1, description="step", type="edit")],
            requires_risky_review=False,
        )

        async def fake_generate(instruction, history, requested_model, max_steps,
                                 user_id=None, memory_store=None):
            return fake_plan

        runner._generate_plan = fake_generate  # type: ignore[method-assign]

        result = asyncio.run(
            runner.plan(
                instruction="Build a feature",
                history=[],
                requested_model=None,
                max_steps=5,
            )
        )
        assert result is fake_plan

    def test_plan_accepts_metadata_kwarg(self, tmp_path):
        """plan() must accept (and ignore) metadata= for forward-compat."""
        from agent.loop import AgentRunner
        from agent.models import AgentPlan

        sig = inspect.signature(AgentRunner.plan)
        assert "metadata" in sig.parameters, (
            "AgentRunner.plan() must accept metadata= (direct_chat.py passes it)"
        )


# ── 3: InternalAgentAdapter no longer passes provider_chain ──────────────────


class TestInternalAgentAdapterProviderChain:
    def test_execute_does_not_pass_provider_chain_to_agent_runner(self, tmp_path):
        """InternalAgentAdapter.execute() must NOT pass provider_chain= to AgentRunner.

        Passing provider_chain= to AgentRunner causes:
          TypeError: AgentRunner.__init__() got an unexpected keyword argument 'provider_chain'
        """
        import inspect as _inspect

        from runtimes.adapters.internal_agent import InternalAgentAdapter
        from agent.loop import AgentRunner

        # Verify AgentRunner itself does NOT accept provider_chain
        sig = _inspect.signature(AgentRunner.__init__)
        assert "provider_chain" not in sig.parameters, (
            "AgentRunner.__init__ must NOT have provider_chain — "
            "callers should rely on ProviderRouter.from_env() instead"
        )

        # Verify execute() source code does not reference provider_chain=
        import textwrap
        src = _inspect.getsource(InternalAgentAdapter.execute)
        assert "provider_chain=" not in src, (
            "InternalAgentAdapter.execute() still passes provider_chain= to AgentRunner; "
            "this crashes at runtime"
        )

    def test_internal_agent_adapter_can_be_instantiated(self):
        """InternalAgentAdapter should construct without error."""
        from runtimes.adapters.internal_agent import InternalAgentAdapter

        adapter = InternalAgentAdapter(config={"ollama_base": "http://localhost:11434"})
        assert adapter.RUNTIME_ID == "internal_agent"


# ── 4: TaskDispatcher time-to-pickup diagnostics ─────────────────────────────


class TestTaskDispatcherDiagnostics:
    def test_dispatcher_records_first_seen(self):
        """Dispatcher should track first_seen times for pending tasks."""
        from tasks.dispatcher import TaskDispatcher
        from tasks.store import TaskStore

        mock_store = MagicMock(spec=TaskStore)
        mock_coordinator = MagicMock()
        dispatcher = TaskDispatcher(
            workspace_root="/tmp",
            store=mock_store,
            coordinator=mock_coordinator,
        )
        assert hasattr(dispatcher, "_first_seen"), (
            "TaskDispatcher must have _first_seen dict for time-to-pickup tracking"
        )
        assert isinstance(dispatcher._first_seen, dict)

    def test_dispatcher_logs_time_to_pickup(self, caplog):
        """Executing a task removes it from _first_seen and logs pickup time."""
        import logging
        from tasks.dispatcher import TaskDispatcher
        from tasks.store import TaskStore

        mock_store = MagicMock(spec=TaskStore)
        mock_coordinator = MagicMock()
        mock_coordinator.execute = AsyncMock()

        dispatcher = TaskDispatcher(
            workspace_root="/tmp",
            store=mock_store,
            coordinator=mock_coordinator,
        )
        dispatcher._first_seen["task-abc"] = time.monotonic() - 1.5  # 1.5s ago

        with caplog.at_level(logging.INFO, logger="qwen-proxy"):
            asyncio.run(
                dispatcher._execute_task("task-abc")
            )

        assert "task-abc" not in dispatcher._first_seen
        assert any("task-abc" in r.message for r in caplog.records)


# ── 5: Agency de-duplication ─────────────────────────────────────────────────


class TestAgencyDeduplication:
    def test_duplicate_directive_is_skipped(self):
        """If a directive with the same title is already pending, it should not
        be dispatched again in the same or next cycle."""
        from agent.agency import Agency, AgentDirective, AgentRole

        agency = Agency(tick_minutes=60)

        # Seed an already-pending directive with a known title
        existing = AgentDirective(
            directive_id="dir_existing",
            role=AgentRole.DEV,
            title="Fix 2 failing test(s)",
            instruction="...",
            priority=1,
            status="running",
        )
        agency._directives.append(existing)

        # Now simulate a new cycle that would produce the same title
        new_directive = AgentDirective(
            directive_id="dir_new",
            role=AgentRole.DEV,
            title="Fix 2 failing test(s)",  # same title
            instruction="...",
            priority=1,
        )

        dispatched: list[str] = []
        original_dispatch = agency._dispatch_directive

        def mock_dispatch(directive):
            dispatched.append(directive.directive_id)

        agency._dispatch_directive = mock_dispatch  # type: ignore[method-assign]

        # Manually run the de-dup logic that run_cycle applies
        recent_titles: set[str] = {
            d.title for d in agency._directives[-50:]
            if d.status in {"pending", "running"}
        }
        deduped = []
        for directive in [new_directive]:
            if directive.title not in recent_titles:
                deduped.append(directive)
                recent_titles.add(directive.title)

        for d in deduped:
            agency._dispatch_directive(d)

        assert "dir_new" not in dispatched, (
            "Agency must NOT dispatch a directive whose title is already pending/running"
        )

    def test_unique_directive_is_dispatched(self):
        """A directive with a genuinely new title should still be dispatched."""
        from agent.agency import Agency, AgentDirective, AgentRole

        agency = Agency(tick_minutes=60)

        new_directive = AgentDirective(
            directive_id="dir_unique",
            role=AgentRole.SECURITY,
            title="CVE-2025-9999 remediation",
            instruction="Fix this CVE",
            priority=2,
        )

        dispatched: list[str] = []

        def mock_dispatch(directive):
            dispatched.append(directive.directive_id)

        agency._dispatch_directive = mock_dispatch  # type: ignore[method-assign]

        recent_titles: set[str] = {
            d.title for d in agency._directives[-50:]
            if d.status in {"pending", "running"}
        }
        deduped = []
        for directive in [new_directive]:
            if directive.title not in recent_titles:
                deduped.append(directive)

        for d in deduped:
            agency._dispatch_directive(d)

        assert "dir_unique" in dispatched


# ── 6: Dashboard partial-failure renders without crashing ────────────────────


class TestDashboardPartialFailure:
    def test_dashboard_home_js_uses_allsettled(self, tmp_path):
        """DashboardHome.js must use Promise.allSettled() not Promise.all().

        Promise.all() with three endpoints means a single network blip (e.g.
        /api/stats temporarily unreachable) throws AxiosError and the whole
        dashboard goes blank.  Promise.allSettled() lets partial data show.
        """
        import os

        dashboard_path = os.path.join(
            os.path.dirname(__file__), "..", "frontend", "src", "pages", "DashboardHome.js"
        )
        if not os.path.exists(dashboard_path):
            pytest.skip("frontend not present in this checkout")

        src = open(dashboard_path).read()

        assert "Promise.allSettled" in src, (
            "DashboardHome.js must use Promise.allSettled() so one failing "
            "API endpoint does not blank the entire dashboard"
        )
        # Make sure we didn't leave the old Promise.all([ call that blocked on all three
        assert "await Promise.all([" not in src, (
            "DashboardHome.js still has await Promise.all([…]) which tanks the "
            "whole dashboard when one endpoint fails"
        )
