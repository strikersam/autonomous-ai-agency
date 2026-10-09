"""Tests for sticky (session-scoped) approval grants."""
from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.governance_router import build_governance_router
from packages.governance import approvals as approvals_module
from packages.governance import audit as audit_module
from packages.governance.approvals import ApprovalStore, GrantStore
from packages.governance.audit import AuditLog
from packages.governance.enforcement import GovernanceGate
from packages.governance.identity import resolve_identity
from packages.governance.policy import PolicyEngine, reset_policy_engine

ADMIN = {"email": "admin@example.com", "role": "admin"}
VIEWER = {"email": "viewer@example.com", "role": "viewer"}


@pytest.fixture(autouse=True)
def isolated():
    audit_module.reset_audit_log(AuditLog(capacity=100))
    approvals_module.reset_approval_store(ApprovalStore())
    approvals_module.reset_grant_store(GrantStore())
    reset_policy_engine(PolicyEngine({
        "mode": "enforce",
        "baseline": {"tool": {"require_approval": ["deploy_prod", "other_tool"], "deny": ["rm_all"]}},
    }))
    yield
    audit_module.reset_audit_log(None)
    approvals_module.reset_approval_store(None)
    approvals_module.reset_grant_store(None)
    reset_policy_engine(None)


def _client(user: dict) -> TestClient:
    app = FastAPI()
    app.include_router(build_governance_router(lambda: user))
    return TestClient(app)


def _set_flag(monkeypatch, enabled: bool) -> None:
    from packages.config import settings

    monkeypatch.setattr(
        settings, "governance_session_grants_enabled_raw", "true" if enabled else "false"
    )


# -- store semantics ----------------------------------------------------------


def test_once_scope_never_creates_a_grant():
    store = GrantStore()
    assert store.grant("s1", "once", "tool", "deploy_prod", "admin", 60) is None
    assert store.list_grants() == []


def test_action_scope_matches_same_surface_and_action_only():
    store = GrantStore()
    store.grant("s1", "action", "tool", "deploy_prod", "admin", 60)
    assert store.has_grant("s1", "tool", "deploy_prod") is not None
    assert store.has_grant("s1", "tool", "other_tool") is None
    assert store.has_grant("s1", "shell", "deploy_prod") is None
    assert store.has_grant("s2", "tool", "deploy_prod") is None


def test_session_scope_covers_any_action_in_that_session_only():
    store = GrantStore()
    store.grant("s1", "session", "tool", "deploy_prod", "admin", 60)
    assert store.has_grant("s1", "shell", "anything") is not None
    assert store.has_grant("s2", "shell", "anything") is None


def test_grants_expire():
    store = GrantStore()
    grant = store.grant("s1", "session", "tool", "a", "admin", 60)
    grant.created_at -= 61
    assert store.has_grant("s1", "tool", "a") is None
    assert store.list_grants() == []


@pytest.mark.parametrize("session_id", ["", "anonymous", "   "])
def test_no_grant_for_anonymous_sessions(session_id):
    store = GrantStore()
    assert store.grant(session_id, "session", "tool", "a", "admin", 60) is None
    assert store.has_grant(session_id, "tool", "a") is None


def test_credential_surface_is_never_granted():
    store = GrantStore()
    assert store.grant("s1", "action", "credential", "read_secret", "admin", 60) is None
    store.grant("s1", "session", "tool", "a", "admin", 60)
    assert store.has_grant("s1", "credential", "read_secret") is None


def test_revoke_removes_the_grant():
    store = GrantStore()
    grant = store.grant("s1", "session", "tool", "a", "admin", 60)
    assert store.revoke(grant.grant_id) is True
    assert store.revoke(grant.grant_id) is False
    assert store.has_grant("s1", "tool", "a") is None


def test_lookup_failure_fails_closed():
    store = GrantStore()
    store.grant("s1", "session", "tool", "a", "admin", 60)
    store._lock = None  # any error inside lookup must mean "no grant"
    assert store.has_grant("s1", "tool", "a") is None


# -- enforcement --------------------------------------------------------------


async def test_grant_short_circuits_approval_and_is_audited():
    gate = GovernanceGate()
    identity = resolve_identity(agent_name="coder", owner="sam", session_id="sess-1")
    grant = approvals_module.get_grant_store().grant(
        "sess-1", "action", "tool", "deploy_prod", "admin", 60
    )
    result = await asyncio.wait_for(gate.guard(identity, "deploy_prod", {}), timeout=5)
    assert result.allowed is True
    assert result.approval_id == f"grant:{grant.grant_id}"
    assert approvals_module.get_approval_store().pending() == []
    events = audit_module.get_audit_log().recent(10, session_id="sess-1")
    assert events[0]["result_status"] == "approved"
    assert events[0]["approval_id"] == f"grant:{grant.grant_id}"


async def _assert_asks_a_human(identity, tool: str = "deploy_prod") -> None:
    task = asyncio.create_task(GovernanceGate().guard(identity, tool, {}))
    await asyncio.sleep(0.1)
    assert len(approvals_module.get_approval_store().pending()) == 1
    task.cancel()


async def test_action_grant_does_not_cover_a_different_action():
    identity = resolve_identity(agent_name="coder", owner="sam", session_id="sess-1")
    approvals_module.get_grant_store().grant("sess-1", "action", "tool", "deploy_prod", "admin", 60)
    await _assert_asks_a_human(identity, "other_tool")


async def test_grant_never_overrides_deny():
    identity = resolve_identity(agent_name="coder", owner="sam", session_id="sess-1")
    approvals_module.get_grant_store().grant("sess-1", "session", "tool", "x", "admin", 60)
    result = await GovernanceGate().guard(identity, "rm_all", {})
    assert result.allowed is False


async def test_flag_off_means_grants_are_not_consulted(monkeypatch):
    _set_flag(monkeypatch, False)
    identity = resolve_identity(agent_name="coder", owner="sam", session_id="sess-1")
    approvals_module.get_grant_store().grant("sess-1", "session", "tool", "x", "admin", 60)
    await _assert_asks_a_human(identity)


async def test_broken_grant_store_falls_back_to_asking(monkeypatch):
    def boom():
        raise RuntimeError("store down")

    monkeypatch.setattr(approvals_module, "get_grant_store", boom)
    identity = resolve_identity(agent_name="coder", owner="sam", session_id="sess-1")
    await _assert_asks_a_human(identity)


# -- router -------------------------------------------------------------------


def _pending(session_id: str = "sess-1", action: str = "deploy_prod", surface: str = "tool"):
    return approvals_module.get_approval_store().create(
        agent_id="agent:coder", surface=surface, action=action, reason="r",
        rule_id="x", session_id=session_id,
    )


def test_approve_without_body_is_backward_compatible():
    req = _pending()
    response = _client(ADMIN).post(f"/api/governance/approvals/{req.approval_id}/approve")
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["grant"] is None
    assert approvals_module.get_grant_store().list_grants() == []


def test_approve_with_note_only_issues_no_grant():
    req = _pending()
    response = _client(ADMIN).post(
        f"/api/governance/approvals/{req.approval_id}/approve", json={"note": "ok"}
    )
    assert response.json()["grant"] is None


@pytest.mark.parametrize("scope", ["action", "session"])
def test_approve_with_scope_creates_grant_for_the_admin(scope):
    req = _pending()
    response = _client(ADMIN).post(
        f"/api/governance/approvals/{req.approval_id}/approve", json={"scope": scope}
    )
    grant = response.json()["grant"]
    assert grant["scope"] == scope
    assert grant["granted_by"] == "admin@example.com"
    assert grant["session_id"] == "sess-1"
    assert approvals_module.get_grant_store().has_grant("sess-1", "tool", "deploy_prod")


def test_invalid_scope_is_rejected():
    req = _pending()
    response = _client(ADMIN).post(
        f"/api/governance/approvals/{req.approval_id}/approve", json={"scope": "forever"}
    )
    assert response.status_code == 422


def test_approve_scope_ignored_when_flag_off(monkeypatch):
    _set_flag(monkeypatch, False)
    req = _pending()
    response = _client(ADMIN).post(
        f"/api/governance/approvals/{req.approval_id}/approve", json={"scope": "session"}
    )
    assert response.status_code == 200
    assert response.json()["grant"] is None
    assert approvals_module.get_grant_store().list_grants() == []


def test_approve_scope_refused_for_credential_and_anonymous():
    client = _client(ADMIN)
    cred = _pending(surface="credential")
    anon = _pending(session_id="")
    for req in (cred, anon):
        body = client.post(
            f"/api/governance/approvals/{req.approval_id}/approve", json={"scope": "session"}
        ).json()
        assert body["status"] == "approved"
        assert body["grant"] is None


def test_grant_uses_configured_ttl(monkeypatch):
    from packages.config import settings

    monkeypatch.setattr(settings, "governance_grant_ttl_s", 90)
    req = _pending()
    grant = _client(ADMIN).post(
        f"/api/governance/approvals/{req.approval_id}/approve", json={"scope": "session"}
    ).json()["grant"]
    assert grant["ttl_s"] == 90


def test_list_and_revoke_grants():
    store = approvals_module.get_grant_store()
    grant = store.grant("sess-1", "session", "tool", "a", "admin", 60)
    client = _client(ADMIN)
    listed = client.get("/api/governance/grants").json()
    assert listed["count"] == 1 and listed["grants"][0]["grant_id"] == grant.grant_id
    assert client.delete(f"/api/governance/grants/{grant.grant_id}").status_code == 200
    assert client.get("/api/governance/grants").json()["count"] == 0
    assert client.delete(f"/api/governance/grants/{grant.grant_id}").status_code == 404


@pytest.mark.parametrize(
    "method,path",
    [("get", "/api/governance/grants"), ("delete", "/api/governance/grants/gnt_x")],
)
def test_grant_routes_require_admin(method, path):
    assert getattr(_client(VIEWER), method)(path).status_code == 403
