"""tests/test_e2b_task_wiring.py — Task.company_id → spec.context repo_url wiring.

Covers the TaskExecutionCoordinator changes that route onboarded-company
tasks against the REAL company repo inside the E2B sandbox:

  * Task with company_id + E2B on + company has RepoConnection → spec.context
    gets repo_url / base_branch / github_token.
  * Task with company_id + E2B OFF → spec.context unchanged (legacy path).
  * Task without company_id → spec.context unchanged regardless of E2B.
  * Company with no RepoConnection → spec.context unchanged.
"""
from __future__ import annotations

import os
import tempfile
from typing import Any

import pytest

from tasks.models import Task, TaskCreateRequest, TaskUpdateRequest
from tasks.service import TaskExecutionCoordinator


@pytest.fixture(autouse=True)
def _clean_e2b_env(monkeypatch):
    for k in ("E2B_API_KEY", "E2B_ENABLED", "RUNTIME_E2B_ENABLED",
              "E2B_TEMPLATE", "E2B_TIMEOUT_SEC", "AGENT_SANDBOX_MODE",
              "GITHUB_TOKEN", "GH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    yield


# ── Task model ────────────────────────────────────────────────────────────


def test_task_has_company_id_field():
    """Task.company_id is an optional additive field, defaults None."""
    task = Task(owner_id="user-1", title="test")
    assert task.company_id is None


def test_task_create_request_accepts_company_id():
    """TaskCreateRequest accepts an optional company_id."""
    req = TaskCreateRequest(title="test", company_id="comp_123")
    assert req.company_id == "comp_123"


def test_task_create_request_company_id_optional():
    """TaskCreateRequest.company_id defaults to None (additive, no breaking change)."""
    req = TaskCreateRequest(title="test")
    assert req.company_id is None


def test_task_update_request_accepts_company_id():
    """TaskUpdateRequest accepts an optional company_id."""
    req = TaskUpdateRequest(company_id="comp_456")
    assert req.company_id == "comp_456"


# ── TaskExecutionCoordinator._build_spec wiring ──────────────────────────


class _FakeRepoConnection:
    """Minimal stand-in for models.company_graph.RepoConnection."""
    def __init__(self, owner: str, repo: str, default_branch: str = "main"):
        self.owner = owner
        self.repo = repo
        self.default_branch = default_branch
        self.token_ref = None


class _FakeCompany:
    """Minimal stand-in for models.company_graph.Company."""
    def __init__(self, repo_connection: _FakeRepoConnection | None = None):
        self.repo_connection = repo_connection
        self.company_id = "comp_test_123"


class _FakeCompanyGraphStore:
    """Stand-in for CompanyGraphStore that returns a configured company."""
    def __init__(self, company: _FakeCompany | None = None):
        self._company = company

    def get_company(self, company_id: str):
        if self._company is None:
            return None
        return self._company


def _build_coordinator(*, company_store=None) -> TaskExecutionCoordinator:
    """Build a TaskExecutionCoordinator with stubbed dependencies and an
    optional company_graph_store."""
    # Use a fake task store / agent store that aren't hit during _build_spec
    class _FakeStore:
        async def get(self, _id):
            return None
        async def update(self, _t):
            pass
    return TaskExecutionCoordinator(
        store=_FakeStore(),
        agent_store=None,  # not used by _build_spec
        runtime_manager=None,  # not used by _build_spec
        workspace_root=os.path.join(
            tempfile.gettempdir(), "test-workspace"
        ),  # nosec B108 — test fixture, not attacker-controlled
        company_graph_store=company_store,
    )


def _make_task(company_id: str | None = None) -> Task:
    return Task(
        owner_id="user-1",
        title="test task",
        company_id=company_id,
    )


def test_build_spec_no_company_id_unchanged(monkeypatch):
    """No company_id → spec.context has no repo_url (legacy path)."""
    monkeypatch.delenv("E2B_API_KEY", raising=False)
    coord = _build_coordinator()
    task = _make_task(company_id=None)
    spec = coord._build_spec(task, agent=None)
    assert "repo_url" not in spec.context
    assert "base_branch" not in spec.context
    assert "github_token" not in spec.context


def test_build_spec_company_id_e2b_off_unchanged(monkeypatch):
    """company_id set but E2B off → spec.context unchanged (no company repo wiring)."""
    monkeypatch.delenv("E2B_API_KEY", raising=False)
    coord = _build_coordinator()
    task = _make_task(company_id="comp_test_123")
    spec = coord._build_spec(task, agent=None)
    # Even though company_id is set, E2B is off so the wiring is skipped.
    assert "repo_url" not in spec.context


def test_build_spec_company_id_e2b_on_with_repo_connection(monkeypatch):
    """company_id + E2B on + company has RepoConnection → spec.context wired."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    monkeypatch.setenv("E2B_ENABLED", "true")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token_xyz")
    repo_conn = _FakeRepoConnection(owner="acme", repo="platform", default_branch="main")
    company = _FakeCompany(repo_connection=repo_conn)
    store = _FakeCompanyGraphStore(company=company)
    coord = _build_coordinator(company_store=store)
    task = _make_task(company_id="comp_test_123")
    spec = coord._build_spec(task, agent=None)
    assert spec.context.get("repo_url") == "https://github.com/acme/platform"
    assert spec.context.get("base_branch") == "main"
    assert spec.context.get("github_token") == "ghp_test_token_xyz"
    assert spec.context.get("company_id") == "comp_test_123"


def test_build_spec_company_id_e2b_on_no_repo_connection(monkeypatch):
    """company_id + E2B on + company has NO RepoConnection → spec.context unchanged."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    monkeypatch.setenv("E2B_ENABLED", "true")
    company = _FakeCompany(repo_connection=None)  # URL-only company
    store = _FakeCompanyGraphStore(company=company)
    coord = _build_coordinator(company_store=store)
    task = _make_task(company_id="comp_test_123")
    spec = coord._build_spec(task, agent=None)
    assert "repo_url" not in spec.context


def test_build_spec_company_id_e2b_on_company_not_found(monkeypatch):
    """company_id + E2B on + company doesn't exist → spec.context unchanged."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    monkeypatch.setenv("E2B_ENABLED", "true")
    store = _FakeCompanyGraphStore(company=None)  # company not found
    coord = _build_coordinator(company_store=store)
    task = _make_task(company_id="comp_unknown")
    spec = coord._build_spec(task, agent=None)
    assert "repo_url" not in spec.context


def test_build_spec_company_id_uses_custom_default_branch(monkeypatch):
    """company's RepoConnection.default_branch flows through to spec.context."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    monkeypatch.setenv("E2B_ENABLED", "true")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token")
    repo_conn = _FakeRepoConnection(owner="acme", repo="platform", default_branch="develop")
    company = _FakeCompany(repo_connection=repo_conn)
    store = _FakeCompanyGraphStore(company=company)
    coord = _build_coordinator(company_store=store)
    task = _make_task(company_id="comp_test_123")
    spec = coord._build_spec(task, agent=None)
    assert spec.context.get("base_branch") == "develop"


def test_build_spec_company_resolution_failure_is_graceful(monkeypatch):
    """If the company store raises, _build_spec must NOT crash — it logs and
    continues with the legacy (no repo_url) spec."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    monkeypatch.setenv("E2B_ENABLED", "true")

    class _ExplodingStore:
        def get_company(self, company_id):
            raise RuntimeError("MongoDB connection refused")

    coord = _build_coordinator(company_store=_ExplodingStore())
    task = _make_task(company_id="comp_test_123")
    # Must not raise
    spec = coord._build_spec(task, agent=None)
    assert "repo_url" not in spec.context


def test_build_spec_company_id_no_token_still_resolves(monkeypatch):
    """company_id + E2B on but no GITHUB_TOKEN → repo_url is set but token is empty."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    monkeypatch.setenv("E2B_ENABLED", "true")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    repo_conn = _FakeRepoConnection(owner="acme", repo="platform")
    company = _FakeCompany(repo_connection=repo_conn)
    store = _FakeCompanyGraphStore(company=company)
    coord = _build_coordinator(company_store=store)
    task = _make_task(company_id="comp_test_123")
    spec = coord._build_spec(task, agent=None)
    assert spec.context.get("repo_url") == "https://github.com/acme/platform"
    assert spec.context.get("github_token") == ""  # empty, not None — clone will use bare URL


# ── _resolve_company_repo ────────────────────────────────────────────────


def test_resolve_company_repo_returns_none_when_not_found(monkeypatch):
    """_resolve_company_repo returns None when the company doesn't exist."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    monkeypatch.setenv("E2B_ENABLED", "true")
    store = _FakeCompanyGraphStore(company=None)
    coord = _build_coordinator(company_store=store)
    result = coord._resolve_company_repo("comp_unknown")
    assert result is None


def test_resolve_company_repo_returns_none_when_no_connection(monkeypatch):
    """_resolve_company_repo returns None when the company has no RepoConnection."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    monkeypatch.setenv("E2B_ENABLED", "true")
    company = _FakeCompany(repo_connection=None)
    store = _FakeCompanyGraphStore(company=company)
    coord = _build_coordinator(company_store=store)
    result = coord._resolve_company_repo("comp_test_123")
    assert result is None


def test_resolve_company_repo_returns_dict_when_resolved(monkeypatch):
    """_resolve_company_repo returns {repo_url, base_branch, github_token}."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    monkeypatch.setenv("E2B_ENABLED", "true")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token")
    repo_conn = _FakeRepoConnection(owner="acme", repo="platform", default_branch="main")
    company = _FakeCompany(repo_connection=repo_conn)
    store = _FakeCompanyGraphStore(company=company)
    coord = _build_coordinator(company_store=store)
    result = coord._resolve_company_repo("comp_test_123")
    assert result is not None
    assert result["repo_url"] == "https://github.com/acme/platform"
    assert result["base_branch"] == "main"
    assert result["github_token"] == "ghp_test_token"
