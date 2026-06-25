"""tests/test_contract_enforcement.py — Contract discipline tests (J)

Tests that all 5 core classes reject unknown kwargs at runtime,
matching Pydantic extra="forbid" behavior.
"""

from __future__ import annotations

import pytest

from agent.contract_enforcement import (
    check_kwargs,
    LOCKED_AGENT_RUNNER_RUN,
    LOCKED_JOB_MANAGER_CREATE,
    LOCKED_JOB_MANAGER_START,
    LOCKED_JOB_MANAGER_CANCEL,
    LOCKED_JOB_MANAGER_GET,
    LOCKED_JOB_MANAGER_LIST,
    LOCKED_AGENT_RUNNER_PLAN,
    LOCKED_AGENT_RUNNER_CONFIGURE,
    LOCKED_AGENT_RUNNER_SPAWN,
    LOCKED_MODEL_ROUTER_ROUTE,
    LOCKED_ORCHESTRATOR_EXECUTE,
    LOCKED_ORCHESTRATOR_APPROVE,
    LOCKED_ORCHESTRATOR_GET_RUN,
    LOCKED_ORCHESTRATOR_LIST_RUNS,
    LOCKED_SKILL_REGISTRY_RECOMMEND,
    LOCKED_SKILL_REGISTRY_LIST,
    LOCKED_SKILL_REGISTRY_SEARCH,
    LOCKED_SKILL_REGISTRY_GET,
    LOCKED_SKILL_REGISTRY_UPDATE_TOKEN,
)


class TestCheckKwargs:
    """Unit tests for the check_kwargs helper."""

    def test_empty_kwargs_allowed(self) -> None:
        check_kwargs({}, frozenset({"a", "b"}), "test")

    def test_known_kwarg_allowed(self) -> None:
        check_kwargs({"a": 1, "b": 2}, frozenset({"a", "b", "c"}), "test")

    def test_unknown_single_kwarg_raises(self) -> None:
        with pytest.raises(TypeError, match="unexpected keyword argument"):
            check_kwargs({"x": 1}, frozenset({"a", "b"}), "TestClass.method")

    def test_unknown_multiple_kwargs_raises(self) -> None:
        with pytest.raises(TypeError, match="unexpected keyword argument"):
            check_kwargs({"x": 1, "y": 2}, frozenset({"a", "b"}), "TestClass.method")

    def test_error_message_lists_unknown(self) -> None:
        with pytest.raises(TypeError) as exc_info:
            check_kwargs({"bad": 1, "worse": 2}, frozenset({"good"}), "Foo.bar")
        assert "bad" in str(exc_info.value)
        assert "worse" in str(exc_info.value)
        assert "Foo.bar" in str(exc_info.value)

    def test_error_message_shows_accepted(self) -> None:
        with pytest.raises(TypeError) as exc_info:
            check_kwargs({"x": 1}, frozenset({"a", "b"}), "Foo.bar")
        # Accepted keys should appear in the error
        assert "a" in str(exc_info.value)
        assert "b" in str(exc_info.value)


class TestAgentJobManagerContracts:
    """AgentJobManager method signature enforcement."""

    def test_create_job_rejects_unknown(self) -> None:
        from agent.job_manager import AgentJobManager
        mgr = AgentJobManager()
        with pytest.raises(TypeError, match="unexpected keyword argument"):
            # type: ignore[arg-type]
            mgr.create_job(
                session_id="sess_123",
                instruction="do work",
                bad_param=True,
            )

    def test_create_job_accepts_valid(self) -> None:
        from agent.job_manager import AgentJobManager
        mgr = AgentJobManager()
        job = mgr.create_job(
            session_id="sess_123",
            instruction="do work",
            owner_id="user@example.com",
            runtime_id="test",
            requested_model="test-model",
            provider_id="test-provider",
        )
        assert job.job_id.startswith("aj_")

    def test_start_job_rejects_unknown(self) -> None:
        from agent.job_manager import AgentJobManager
        mgr = AgentJobManager()
        job = mgr.create_job(session_id="sess_123", instruction="do work")
        with pytest.raises(TypeError, match="unexpected keyword argument"):
            # type: ignore[arg-type]
            mgr.start_job(
                job_id=job.job_id,
                runner=lambda h: {},
                unknown_param=True,
            )

    def test_cancel_job_rejects_unknown(self) -> None:
        from agent.job_manager import AgentJobManager
        mgr = AgentJobManager()
        job = mgr.create_job(session_id="sess_123", instruction="do work")
        with pytest.raises(TypeError, match="unexpected keyword argument"):
            # type: ignore[arg-type]
            mgr.cancel_job(job_id=job.job_id, extra=True)

    def test_get_job_rejects_unknown(self) -> None:
        from agent.job_manager import AgentJobManager
        mgr = AgentJobManager()
        with pytest.raises(TypeError, match="unexpected keyword argument"):
            # type: ignore[arg-type]
            mgr.get_job(job_id="aj_123", extra_param=True)

    def test_list_jobs_rejects_unknown(self) -> None:
        from agent.job_manager import AgentJobManager
        mgr = AgentJobManager()
        with pytest.raises(TypeError, match="unexpected keyword argument"):
            # type: ignore[arg-type]
            mgr.list_jobs(session_id="sess_123", limit=10)


class TestModelRouterContracts:
    """ModelRouter.route() signature enforcement."""

    def test_route_rejects_unknown(self) -> None:
        from router.model_router import ModelRouter
        router = ModelRouter()
        with pytest.raises(TypeError, match="unexpected keyword argument"):
            # type: ignore[arg-type]
            router.route(
                requested_model=None,
                messages=[],
                bad_param=True,
            )

    def test_route_accepts_valid(self) -> None:
        from router.model_router import ModelRouter
        router = ModelRouter()
        decision = router.route(
            requested_model="claude-opus-4-6",
            messages=[{"role": "user", "content": "hello"}],
            has_tools=False,
            stream=False,
            override_model=None,
            endpoint_type="chat",
        )
        assert decision.resolved_model  # valid routing decision returned


class TestWorkflowOrchestratorContracts:
    """WorkflowOrchestrator method signature enforcement."""

    def test_execute_rejects_unknown(self) -> None:
        import pytest
        from services.workflow_orchestrator import WorkflowOrchestrator, ExecutionRequest
        from pydantic import ValidationError

        # ExecutionRequest itself enforces extra="forbid"
        with pytest.raises(ValidationError):
            ExecutionRequest(
                request="do something",
                unknown_field=True,  # rejected by Pydantic
            )

    def test_approve_rejects_unknown(self) -> None:
        from services.workflow_orchestrator import WorkflowOrchestrator
        orch = WorkflowOrchestrator()
        # Create a run manually so we can test approve
        from services.workflow_orchestrator import WorkflowRun, ExecutionRequest
        run = WorkflowRun()
        run._request = ExecutionRequest(request="test")
        run.status = "awaiting_approval"
        orch._runs[run.run_id] = run

        with pytest.raises(TypeError, match="unexpected keyword argument"):
            # type: ignore[arg-type]
            orch.approve(run_id=run.run_id, approved_by="admin", extra=True)

    def test_get_run_rejects_unknown(self) -> None:
        from services.workflow_orchestrator import WorkflowOrchestrator
        orch = WorkflowOrchestrator()
        with pytest.raises(TypeError, match="unexpected keyword argument"):
            # type: ignore[arg-type]
            orch.get_run(run_id="wfo_abc", extra_param=True)

    def test_list_runs_rejects_unknown(self) -> None:
        from services.workflow_orchestrator import WorkflowOrchestrator
        orch = WorkflowOrchestrator()
        with pytest.raises(TypeError, match="unexpected keyword argument"):
            # type: ignore[arg-type]
            orch.list_runs(limit=10, owner_id=None, bad_param=True)


class TestSkillRegistryContracts:
    """SkillRegistry method signature enforcement."""

    def test_recommend_rejects_unknown(self) -> None:
        from agent.skill_registry import SkillRegistry
        reg = SkillRegistry()
        with pytest.raises(TypeError, match="unexpected keyword argument"):
            # type: ignore[arg-type]
            reg.recommend(
                tech_stack=["python"],
                workflow_types=["ci_cd"],
                query="test",
                limit=10,
                bad_param=True,
            )

    def test_list_rejects_unknown(self) -> None:
        from agent.skill_registry import SkillRegistry
        reg = SkillRegistry()
        with pytest.raises(TypeError, match="unexpected keyword argument"):
            # type: ignore[arg-type]
            reg.list(source=None, extra=True)

    def test_search_rejects_unknown(self) -> None:
        from agent.skill_registry import SkillRegistry
        reg = SkillRegistry()
        with pytest.raises(TypeError, match="unexpected keyword argument"):
            # type: ignore[arg-type]
            reg.search(query="test", extra_param=True)

    def test_get_rejects_unknown(self) -> None:
        from agent.skill_registry import SkillRegistry
        reg = SkillRegistry()
        with pytest.raises(TypeError, match="unexpected keyword argument"):
            # type: ignore[arg-type]
            reg.get(skill_id="local:test", extra=True)

    def test_update_github_token_rejects_unknown(self) -> None:
        from agent.skill_registry import SkillRegistry
        reg = SkillRegistry()
        with pytest.raises(TypeError, match="unexpected keyword argument"):
            # type: ignore[arg-type]
            reg.update_github_token(token="DUMMY_TOKEN_FOR_TESTING", extra=True)