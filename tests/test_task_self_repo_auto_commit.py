"""tests/test_task_self_repo_auto_commit.py — TaskExecutionCoordinator._build_spec
self-repo autonomous-shipping wiring.

Covers the follow-up fix: portfolio-materialized and ceo_direct GitHub-issue
tasks were being picked up and "executed" (agent plans/applies/verifies/judges)
but auto_commit defaulted to False and no repo_url/base_branch/github_token
were ever injected for self-repo (non-company) tasks — so the agent's file
changes sat in an ephemeral worktree that got deleted unconditionally after
the run. No commit, no push, no PR, ever. This tests that
_build_spec() now injects auto_commit=True + repo context for the task
types meant to ship code (portfolio_initiative / issue / quick_note), while
leaving report-only task types and company-bound tasks untouched.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from tasks.models import Task
from tasks.service import TaskExecutionCoordinator, TaskWorkflowService
from tasks.store import TaskStore


@pytest.fixture()
def coordinator() -> TaskExecutionCoordinator:
    store = TaskStore()
    return TaskExecutionCoordinator(
        store=store,
        workflow=TaskWorkflowService(store=store),
    )


# Stub GitHub credential for mocked calls (a named constant, not a literal
# default arg, so Bandit B107 "possible hardcoded password" doesn't fire).
STUB_GH_CREDENTIAL = "stub-gh-credential"


def _mock_gh(repo="owner/repo", token=STUB_GH_CREDENTIAL):
    return (
        patch("agent.agency._gh_repo", return_value=repo),
        patch("agent.agency._gh_token", return_value=token),
    )


@pytest.mark.parametrize("task_type", ["portfolio_initiative", "issue", "quick_note"])
def test_ship_code_task_types_get_auto_commit_and_repo_context(coordinator, task_type):
    task = Task(owner_id="system", title="Fix the bug", task_type=task_type)
    repo_patch, token_patch = _mock_gh()
    with repo_patch, token_patch:
        spec = coordinator._build_spec(task, agent=None)

    assert spec.context["auto_commit"] is True
    assert spec.context["repo_url"] == "https://github.com/owner/repo"
    assert spec.context["base_branch"] == "master"
    assert spec.context["github_token"] == STUB_GH_CREDENTIAL


def test_report_only_task_type_stays_report_only(coordinator):
    """Task types not in the ship-code set (e.g. "general") must NOT get
    auto_commit — matches the SCOUT role's read-only contract."""
    task = Task(owner_id="system", title="Research X", task_type="general")
    repo_patch, token_patch = _mock_gh()
    with repo_patch, token_patch:
        spec = coordinator._build_spec(task, agent=None)

    assert "auto_commit" not in spec.context
    assert "repo_url" not in spec.context


def test_flag_off_falls_back_to_report_only(coordinator):
    """SELF_REPO_AUTO_COMMIT_ENABLED=false is the rollback lever — even with
    valid GitHub credentials, the task must stay report-only."""
    from packages.config import settings
    task = Task(owner_id="system", title="Fix the bug", task_type="issue")
    repo_patch, token_patch = _mock_gh()
    with repo_patch, token_patch, \
         patch.object(settings, "self_repo_auto_commit_enabled", "false"):
        spec = coordinator._build_spec(task, agent=None)

    assert "auto_commit" not in spec.context
    assert "repo_url" not in spec.context


def test_no_github_credentials_falls_back_to_report_only(coordinator):
    """If no GitHub repo/token is configured, the task must stay report-only
    rather than half-configuring auto_commit with nowhere to push."""
    task = Task(owner_id="system", title="Fix the bug", task_type="issue")
    with patch("agent.agency._gh_repo", return_value=""), \
         patch("agent.agency._gh_token", return_value=""):
        spec = coordinator._build_spec(task, agent=None)

    assert "auto_commit" not in spec.context
    assert "repo_url" not in spec.context


def test_gh_resolution_exception_falls_back_to_report_only(coordinator):
    """A resolution error (e.g. agent.agency import failure) must never crash
    _build_spec() — the task just stays report-only."""
    task = Task(owner_id="system", title="Fix the bug", task_type="portfolio_initiative")
    with patch("agent.agency._gh_repo", side_effect=RuntimeError("boom")):
        spec = coordinator._build_spec(task, agent=None)

    assert "auto_commit" not in spec.context


def test_company_bound_task_does_not_use_self_repo_path(coordinator):
    """A task with company_id set must go through the existing E2B
    company-repo wiring, not the self-repo path — even if its task_type
    happens to match the ship-code set. e2b_config off means neither path
    injects context, which is the current (unchanged) company-task default
    when E2B isn't configured."""
    task = Task(owner_id="system", title="Fix the bug", task_type="issue", company_id="co_123")
    repo_patch, token_patch = _mock_gh()
    with repo_patch, token_patch, patch("services.e2b_config.e2b_enabled", return_value=False):
        spec = coordinator._build_spec(task, agent=None)

    # company_id branch taken (not self-repo branch) — self-repo's
    # auto_commit/repo_url must NOT appear since e2b is off and
    # _resolve_company_repo was never reached to set them either.
    assert "auto_commit" not in spec.context
    assert "repo_url" not in spec.context


def test_agent_initiated_writes_to_master_are_blocked_by_autonomy_gate():
    """Belt-and-suspenders: even with auto_commit=True, the hard security
    control in agent/autonomy_gate.py must still refuse any agent-initiated
    write to master/main — this is what makes turning auto_commit on safe."""
    from agent.autonomy_gate import assert_agent_can_write, assert_agent_can_merge, AutonomyViolation

    with pytest.raises(AutonomyViolation):
        assert_agent_can_write("master", agent_initiated=True, action="push")
    with pytest.raises(AutonomyViolation):
        assert_agent_can_write("main", agent_initiated=True, action="push")
    with pytest.raises(AutonomyViolation):
        assert_agent_can_merge(agent_initiated=True)
    # A feature branch is fine.
    assert_agent_can_write("agent/task-abc123", agent_initiated=True, action="push")
