"""tests/test_phase6_workflow.py — Phase 6: workflow engine, safe_agency, Task fields.

All tests are pure-Python with no network calls and no external services.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(**kwargs):
    """Create a minimal Task for testing."""
    from tasks.models import Task
    defaults = dict(owner_id="u-test", title="Test task about security fixes")
    defaults.update(kwargs)
    return Task(**defaults)


def _make_store(task=None):
    """Return a MagicMock TaskStore with async get/update."""
    store = MagicMock()
    store.get = AsyncMock(return_value=task)
    store.update = AsyncMock()
    return store


# ---------------------------------------------------------------------------
# 1. WorkflowPhase enum
# ---------------------------------------------------------------------------

def test_workflow_phases_exist():
    from agent.workflow import WorkflowPhase
    required = {
        "CLASSIFY", "PLAN", "SELECT_SPECIALIST", "PREFLIGHT",
        "EXECUTE", "VERIFY", "JUDGE", "SUMMARIZE",
        "DONE", "FAILED", "BLOCKED",
    }
    defined = {p.name for p in WorkflowPhase}
    assert required <= defined, f"Missing phases: {required - defined}"


def test_workflow_phase_is_str():
    from agent.workflow import WorkflowPhase
    # Str mixin means the enum value IS a string
    assert isinstance(WorkflowPhase.DONE, str)
    assert WorkflowPhase.DONE == "done"


# ---------------------------------------------------------------------------
# 2. classify_domain
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("Fix SQL injection vulnerability in auth module", "security"),
    ("Add unit tests for checkout flow", "testing"),
    ("Write runbook for on-call rotation", "docs"),
    ("Set up Kubernetes cluster with Helm charts", "infra"),
    ("Implement dark mode toggle for settings page", "dev"),  # no keyword → default dev
    ("Completely unrelated task about cooking", "dev"),   # default fallback
])
def test_classify_domain(text, expected):
    from agent.workflow import classify_domain
    assert classify_domain(text) == expected


def test_classify_domain_case_insensitive():
    from agent.workflow import classify_domain
    assert classify_domain("FIX XSS VULNERABILITY") == "security"
    assert classify_domain("Write DOCS for the API") == "docs"


# ---------------------------------------------------------------------------
# 3. WorkflowTransition model
# ---------------------------------------------------------------------------

def test_workflow_transition_defaults():
    from agent.workflow import WorkflowPhase, WorkflowTransition
    t = WorkflowTransition(phase=WorkflowPhase.CLASSIFY)
    assert t.actor == "system:workflow"
    assert t.completed_at is None
    assert isinstance(t.entered_at, float)
    assert t.metadata == {}


def test_workflow_transition_serialises():
    from agent.workflow import WorkflowPhase, WorkflowTransition
    t = WorkflowTransition(phase=WorkflowPhase.EXECUTE, notes="running")
    d = t.model_dump()
    assert d["phase"] == "execute"
    assert "entered_at" in d
    assert d["notes"] == "running"


# ---------------------------------------------------------------------------
# 4. Task model — workflow fields
# ---------------------------------------------------------------------------

def test_task_has_workflow_fields():
    task = _make_task()
    assert task.workflow_phase is None
    assert task.workflow_history == []


def test_task_workflow_phase_set():
    task = _make_task()
    task.workflow_phase = "classify"
    assert task.workflow_phase == "classify"


def test_task_workflow_history_append():
    from agent.workflow import WorkflowPhase, WorkflowTransition
    task = _make_task()
    tr = WorkflowTransition(phase=WorkflowPhase.CLASSIFY)
    task.workflow_history.append(tr.model_dump())
    assert len(task.workflow_history) == 1
    assert task.workflow_history[0]["phase"] == "classify"


# ---------------------------------------------------------------------------
# 5. WorkflowEngine — classify phase
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_workflow_engine_classify_sets_domain():
    from agent.workflow import WorkflowEngine, WorkflowPhase
    task = _make_task(title="Fix SQL injection in login", description="security audit")
    store = _make_store(task=task)
    engine = WorkflowEngine(store)

    # Run through just the CLASSIFY phase
    next_phase = engine._phase_classify(task)

    assert task.workflow_phase == WorkflowPhase.CLASSIFY.value
    assert next_phase == WorkflowPhase.PLAN
    # Domain should be stored in a log entry
    log_events = [e.event_type for e in task.execution_log]
    assert "workflow_classify" in log_events


@pytest.mark.asyncio
async def test_workflow_engine_classify_default_domain():
    from agent.workflow import WorkflowEngine, WorkflowPhase
    task = _make_task(title="Miscellaneous thing", description="")
    store = _make_store(task=task)
    engine = WorkflowEngine(store)
    engine._phase_classify(task)
    # Should not raise; default domain is 'dev'
    classify_log = [e for e in task.execution_log if e.event_type == "workflow_classify"]
    assert classify_log[0].metadata["domain"] == "dev"


# ---------------------------------------------------------------------------
# 6. WorkflowEngine — judge and summarize phases
# ---------------------------------------------------------------------------

def test_phase_judge_pass():
    from agent.workflow import WorkflowEngine, WorkflowPhase
    engine = WorkflowEngine(MagicMock())
    task = _make_task()
    task.result = "PR #42 created: https://github.com/owner/repo/pull/42"
    task.error_message = None
    next_phase = engine._phase_judge(task)
    assert next_phase == WorkflowPhase.SUMMARIZE


def test_phase_judge_fail_on_error():
    from agent.workflow import WorkflowEngine, WorkflowPhase
    engine = WorkflowEngine(MagicMock())
    task = _make_task()
    task.result = None
    task.error_message = "Runtime timed out"
    next_phase = engine._phase_judge(task)
    assert next_phase == WorkflowPhase.SUMMARIZE   # always summarize


def test_phase_summarize_done_on_success():
    from agent.workflow import WorkflowEngine, WorkflowPhase
    engine = WorkflowEngine(MagicMock())
    task = _make_task()
    task.result = "Done — PR opened"
    task.error_message = None
    next_phase = engine._phase_summarize(task)
    assert next_phase == WorkflowPhase.DONE


def test_phase_summarize_failed_on_error():
    from agent.workflow import WorkflowEngine, WorkflowPhase
    engine = WorkflowEngine(MagicMock())
    task = _make_task()
    task.result = None
    task.error_message = "Something went wrong"
    next_phase = engine._phase_summarize(task)
    assert next_phase == WorkflowPhase.FAILED


def test_phase_summarize_truncates_long_result():
    from agent.workflow import WorkflowEngine, WorkflowPhase
    engine = WorkflowEngine(MagicMock())
    task = _make_task()
    task.result = "x" * 5000
    task.error_message = None
    engine._phase_summarize(task)
    summary_log = [e for e in task.execution_log if e.event_type == "workflow_summary"]
    assert len(summary_log[0].message) <= 2001  # 2000 + ellipsis


# ---------------------------------------------------------------------------
# 7. WorkflowEngine.run() — full happy path (mocked phases)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_workflow_engine_run_happy_path():
    """run() must call store.update after each phase and reach DONE."""
    from agent.workflow import WorkflowEngine, WorkflowPhase
    task = _make_task()
    task.result = "All done"
    task.error_message = None
    store = _make_store(task=task)
    engine = WorkflowEngine(store)

    # Mock the heavy phases so the test doesn't need real infra
    # Use async stubs — _dispatch handles both sync and async transparently
    async def _stub_plan(t):       return WorkflowPhase.SELECT_SPECIALIST
    async def _stub_select(t):     return WorkflowPhase.PREFLIGHT
    async def _stub_preflight(t):  return WorkflowPhase.EXECUTE
    async def _stub_execute(t):    return WorkflowPhase.VERIFY
    async def _stub_verify(t):     return WorkflowPhase.JUDGE

    engine._phase_plan             = _stub_plan
    engine._phase_select_specialist = _stub_select
    engine._phase_preflight        = _stub_preflight
    engine._phase_execute          = _stub_execute
    engine._phase_verify           = _stub_verify

    final_task = await engine.run(task)

    assert final_task.workflow_phase == WorkflowPhase.DONE.value
    assert store.update.call_count >= 3   # classify, execute, done at minimum


@pytest.mark.asyncio
async def test_workflow_engine_run_respects_max_phases():
    """Infinite loops: engine must stop at max_phases."""
    from agent.workflow import WorkflowEngine, WorkflowPhase
    task = _make_task()
    store = _make_store(task=task)
    engine = WorkflowEngine(store)

    call_count = 0
    def _looping_classify(t):  # sync stub — _dispatch handles both sync/async
        nonlocal call_count
        call_count += 1
        t.workflow_phase = WorkflowPhase.CLASSIFY.value  # prevent advance
        return WorkflowPhase.CLASSIFY   # loop forever

    engine._phase_classify = _looping_classify

    final_task = await engine.run(task, max_phases=5)

    assert call_count <= 5
    assert final_task.workflow_phase == WorkflowPhase.FAILED.value


# ---------------------------------------------------------------------------
# 8. safe_agency — unit tests with mocked httpx
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verify_pr_exists_true():
    from agent.safe_agency import verify_pr_exists
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"state": "open", "merged": False}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = await verify_pr_exists("fake-token", "owner", "repo", 42)
    assert result is True


@pytest.mark.asyncio
async def test_verify_pr_exists_false_on_404():
    from agent.safe_agency import verify_pr_exists
    mock_resp = MagicMock()
    mock_resp.status_code = 404

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = await verify_pr_exists("fake-token", "owner", "repo", 99)
    assert result is False


@pytest.mark.asyncio
async def test_safe_create_branch_new():
    from agent.safe_agency import safe_create_branch
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"ref": "refs/heads/feature/foo", "object": {"sha": "abc123"}}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = await safe_create_branch("fake-token", "owner", "repo", "feature/foo", "abc123")
    assert result["ref"] == "refs/heads/feature/foo"


@pytest.mark.asyncio
async def test_safe_create_branch_existing():
    """422 (already exists) should fetch existing ref, not raise."""
    from agent.safe_agency import safe_create_branch
    mock_post = MagicMock()
    mock_post.status_code = 422
    mock_post.raise_for_status = MagicMock(side_effect=Exception("should not be called"))
    mock_post.json.return_value = {"message": "Reference already exists"}

    mock_get = MagicMock()
    mock_get.status_code = 200
    mock_get.raise_for_status = MagicMock()
    mock_get.json.return_value = {"object": {"sha": "existing-sha"}}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_post)
        mock_client.get = AsyncMock(return_value=mock_get)
        mock_client_cls.return_value = mock_client

        result = await safe_create_branch("fake-token", "owner", "repo", "feature/foo", "base-sha")
    assert result["object"]["sha"] == "existing-sha"


@pytest.mark.asyncio
async def test_safe_create_pr():
    from agent.safe_agency import safe_create_pr
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"number": 55, "html_url": "https://github.com/o/r/pull/55"}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = await safe_create_pr(
            "token", "owner", "repo",
            title="feat: add thing", body="body text",
            head="feature/thing", base="master",
        )
    assert result["number"] == 55


# ---------------------------------------------------------------------------
# 9. tasks/service.py — workflow_phase wired into execute() path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_sets_workflow_classify_phase(monkeypatch):
    """execute() must set workflow_phase=classify before runtime dispatch."""
    from tasks.models import Task, TaskStatus
    from tasks.service import TaskExecutionCoordinator

    task = _make_task(title="Fix XSS in login")
    task.pending_agent_run = True

    # Minimal mocks for the coordinator
    store = _make_store(task=task)
    workflow_svc = MagicMock()
    workflow_svc.transition = MagicMock()
    workflow_svc._select_agent = AsyncMock(return_value=None)
    workflow_svc.add_comment = MagicMock()

    runtime_manager = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "done"
    mock_result.model_used = "test-model"
    mock_result.tokens_used = 100
    mock_result.cost_usd = 0.001
    mock_result.error_message = None
    mock_decision = MagicMock()
    mock_decision.selected_runtime_id = "internal_agent"
    mock_decision.fallback_runtime_id = None
    mock_decision.fallback_attempted = False
    mock_decision.model_used = "test-model"
    mock_decision.reason = "default"
    runtime_manager.execute = AsyncMock(return_value=(mock_result, mock_decision))

    coordinator = TaskExecutionCoordinator(
        store=store,
        workflow=workflow_svc,
        agent_store=MagicMock(),
        runtime_manager=runtime_manager,
    )
    # Stub _apply_result to avoid deep execution
    coordinator._apply_result = AsyncMock()

    await coordinator.execute(task.task_id)

    phases_logged = [
        e.event_type for e in task.execution_log
        if e.event_type.startswith("workflow_")
    ]
    assert "workflow_classify" in phases_logged
    assert "workflow_execute" in phases_logged
