"""Adversarial edge-case tests for sticky (session-scoped) approval grants.

Each test targets a boundary the happy-path suite in test_governance_grants.py
does not exercise: cross-session lookalikes, the exact TTL boundary, the
credential surface at lookup time, re-decision of already-resolved requests,
authorization of every grant route, and the store's memory bound.
"""
from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.governance_router import build_governance_router
from packages.config import control_overrides
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


def _client(user: dict | None = None, *, unauthenticated: bool = False) -> TestClient:
    def _current_user():
        if unauthenticated:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return user

    app = FastAPI()
    app.include_router(build_governance_router(_current_user))
    return TestClient(app)


def _set_flag(monkeypatch, enabled: bool) -> None:
    from packages.config import settings

    monkeypatch.setattr(
        settings, "governance_session_grants_enabled_raw", "true" if enabled else "false"
    )


def _pending(session_id: str = "sess-1", action: str = "deploy_prod", surface: str = "tool"):
    return approvals_module.get_approval_store().create(
        agent_id="agent:coder", surface=surface, action=action, reason="r",
        rule_id="x", session_id=session_id,
    )


async def _assert_asks_a_human(identity, tool: str = "deploy_prod") -> None:
    task = asyncio.create_task(GovernanceGate().guard(identity, tool, {}))
    await asyncio.sleep(0.1)
    assert len(approvals_module.get_approval_store().pending()) == 1
    task.cancel()


# -- 1. action scope does not widen -------------------------------------------


@pytest.mark.parametrize(
    "surface,action",
    [
        ("shell", "deploy_prod"),   # same action, different surface
        ("tool", "DEPLOY_PROD"),    # same surface, case-variant action
        ("tool", "deploy_prod "),   # same surface, trailing whitespace action
        ("tool", "deploy_prod2"),   # prefix-lookalike action
        ("tool", "deploy"),         # prefix of the granted action
    ],
)
def test_action_grant_does_not_cover_other_surface_or_action(surface, action):
    store = GrantStore()
    store.grant("sess-1", "action", "tool", "deploy_prod", "admin", 60)
    assert store.has_grant("sess-1", surface, action) is None


async def test_action_grant_on_one_surface_does_not_skip_approval_on_another():
    identity = resolve_identity(agent_name="coder", owner="sam", session_id="sess-1")
    approvals_module.get_grant_store().grant("sess-1", "action", "shell", "deploy_prod", "admin", 60)
    await _assert_asks_a_human(identity, "deploy_prod")


# -- 2. session grant does not leak across session ids ------------------------


@pytest.mark.parametrize(
    "lookup",
    [
        "sess-10",       # suffix lookalike
        "sess-1x",       # suffix lookalike
        "xsess-1",       # prefix lookalike
        "sess",          # prefix of the id
        "SESS-1",        # case variant
        "Sess-1",        # case variant
        "sess_1",        # separator variant
        "sess-2",        # different session
        "sess-1\x00",    # NUL-suffixed
    ],
)
def test_session_grant_does_not_leak_to_other_session_ids(lookup):
    store = GrantStore()
    store.grant("sess-1", "session", "tool", "a", "admin", 60)
    assert store.has_grant(lookup, "tool", "a") is None
    assert store.has_grant(lookup, "shell", "anything") is None


@pytest.mark.parametrize("lookup", [" sess-1", "sess-1 ", "\tsess-1\n"])
def test_whitespace_padded_session_id_resolves_to_the_same_session(lookup):
    """Documented behaviour: surrounding whitespace is stripped on issue and lookup.

    Session ids are system-generated, so padding is normalisation, not a way to
    reach another session. (Changed from the QA draft, which asserted no match.)
    """
    store = GrantStore()
    store.grant("sess-1", "session", "tool", "a", "admin", 60)
    assert store.has_grant(lookup, "tool", "a") is not None


@pytest.mark.parametrize("session_id", ["ANONYMOUS", "Anonymous", " anonymous ", "AnOnYmOuS"])
def test_anonymous_lookalikes_cannot_be_granted(session_id):
    """The anonymous sentinel is matched case-insensitively, after stripping."""
    store = GrantStore()
    assert store.grant(session_id, "session", "tool", "a", "admin", 60) is None
    assert store.has_grant(session_id, "tool", "a") is None


async def test_session_grant_does_not_reach_a_different_session_at_gate_level():
    approvals_module.get_grant_store().grant("sess-1", "session", "tool", "x", "admin", 60)
    other = resolve_identity(agent_name="coder", owner="sam", session_id="sess-2")
    await _assert_asks_a_human(other)


# -- 3. TTL boundary (patched clock) ------------------------------------------


def test_grant_expiry_at_exact_ttl_boundary(monkeypatch):
    clock = {"now": 1000.0}
    fake_time = SimpleNamespace(monotonic=lambda: clock["now"], time=time.time)
    monkeypatch.setattr(approvals_module, "time", fake_time)

    store = GrantStore()
    grant = store.grant("sess-1", "session", "tool", "a", "admin", 60)
    grant.created_at = 1000.0

    clock["now"] = 1059.999
    assert store.has_grant("sess-1", "tool", "a") is not None
    clock["now"] = 1060.0  # exactly ttl elapsed: must already be expired
    assert store.has_grant("sess-1", "tool", "a") is None
    assert store.list_grants() == []


def test_grant_expired_is_not_listed_even_before_lookup(monkeypatch):
    clock = {"now": 500.0}
    monkeypatch.setattr(
        approvals_module, "time", SimpleNamespace(monotonic=lambda: clock["now"], time=time.time)
    )
    store = GrantStore()
    grant = store.grant("sess-1", "session", "tool", "a", "admin", 30)
    grant.created_at = 500.0
    clock["now"] = 530.0
    assert store.list_grants() == []


# -- 4. revoke then re-check --------------------------------------------------


async def test_revoked_grant_stops_short_circuiting_approval():
    identity = resolve_identity(agent_name="coder", owner="sam", session_id="sess-1")
    store = approvals_module.get_grant_store()
    grant = store.grant("sess-1", "session", "tool", "x", "admin", 60)

    first = await asyncio.wait_for(GovernanceGate().guard(identity, "deploy_prod", {}), timeout=5)
    assert first.allowed is True
    assert first.approval_id == f"grant:{grant.grant_id}"

    assert store.revoke(grant.grant_id) is True
    await _assert_asks_a_human(identity)


# -- 5. credential surface refused at lookup ----------------------------------


def test_credential_grant_created_directly_in_store_is_not_returned_by_lookup():
    # Build the grant in a store that skips the issue-time exclusion, then hand
    # it to the default (production) store so only the lookup-time check runs.
    raw = GrantStore(excluded_surfaces=frozenset())
    assert raw.grant("sess-1", "session", "credential", "read_secret", "admin", 60) is not None
    default = GrantStore()
    default._grants.update(raw._grants)
    approvals_module.reset_grant_store(default)
    assert default.has_grant("sess-1", "credential", "read_secret") is None


def test_credential_grant_refused_by_enforcement_lookup_path(monkeypatch):
    _set_flag(monkeypatch, True)
    raw = GrantStore(excluded_surfaces=frozenset())
    raw.grant("sess-1", "session", "credential", "read_secret", "admin", 60)
    default = GrantStore()
    default._grants.update(raw._grants)
    approvals_module.reset_grant_store(default)
    identity = resolve_identity(agent_name="coder", owner="sam", session_id="sess-1")
    decision = SimpleNamespace(
        surface=SimpleNamespace(value="credential"), action="read_secret",
        rule_id="r", reason="r",
    )
    assert GovernanceGate._find_grant(identity, decision, _settings()) is None


def _settings():
    from packages.config import settings

    return settings


# -- 6. grants never turn a DENY into allow -----------------------------------


@pytest.mark.parametrize("scope", ["action", "session"])
async def test_grant_cannot_override_deny(scope):
    identity = resolve_identity(agent_name="coder", owner="sam", session_id="sess-1")
    approvals_module.get_grant_store().grant("sess-1", scope, "tool", "rm_all", "admin", 60)
    result = await asyncio.wait_for(GovernanceGate().guard(identity, "rm_all", {}), timeout=5)
    assert result.allowed is False
    assert approvals_module.get_approval_store().pending() == []


# -- 7. approve-with-scope on resolved / expired requests ---------------------


def test_scope_on_denied_request_creates_no_grant():
    req = _pending()
    client = _client(ADMIN)
    assert client.post(f"/api/governance/approvals/{req.approval_id}/deny").status_code == 200
    body = client.post(
        f"/api/governance/approvals/{req.approval_id}/approve", json={"scope": "session"}
    ).json()
    assert body["status"] == "denied"
    assert body["grant"] is None
    assert approvals_module.get_grant_store().list_grants() == []


def test_scope_on_already_approved_request_must_not_widen_it():
    """First decision wins: a later scoped re-approval must not mint a grant."""
    req = _pending()
    client = _client(ADMIN)
    first = client.post(f"/api/governance/approvals/{req.approval_id}/approve").json()
    assert first["status"] == "approved"
    second = client.post(
        f"/api/governance/approvals/{req.approval_id}/approve", json={"scope": "session"}
    ).json()
    assert second["status"] == "approved"
    assert second["grant"] is None
    assert approvals_module.get_grant_store().list_grants() == []


def test_scope_on_expired_pending_request_must_not_create_grant():
    """A request past its TTL is still PENDING until something marks it expired.

    resolve() does not check expiry, so the expired request can still be approved.
    The grant must not be issued from that stale approval.
    """
    req = _pending()
    req.created_at -= req.ttl_s + 1
    assert req.expired is True
    body = _client(ADMIN).post(
        f"/api/governance/approvals/{req.approval_id}/approve", json={"scope": "session"}
    ).json()
    assert body["grant"] is None
    assert approvals_module.get_grant_store().list_grants() == []


def test_scope_on_already_marked_expired_request_creates_no_grant():
    req = _pending()
    req.created_at -= req.ttl_s + 1
    approvals_module.get_approval_store().pending()  # marks it EXPIRED
    body = _client(ADMIN).post(
        f"/api/governance/approvals/{req.approval_id}/approve", json={"scope": "action"}
    ).json()
    assert body["status"] == "expired"
    assert body["grant"] is None
    assert approvals_module.get_grant_store().list_grants() == []


# -- 8. authorization on every grant route ------------------------------------


def test_non_admin_cannot_approve_with_scope_and_request_stays_pending():
    req = _pending()
    response = _client(VIEWER).post(
        f"/api/governance/approvals/{req.approval_id}/approve", json={"scope": "session"}
    )
    assert response.status_code == 403
    assert approvals_module.get_approval_store().get(req.approval_id).status.value == "pending"
    assert approvals_module.get_grant_store().list_grants() == []


def test_non_admin_cannot_list_or_revoke_grants():
    grant = approvals_module.get_grant_store().grant("sess-1", "session", "tool", "a", "admin", 60)
    client = _client(VIEWER)
    assert client.get("/api/governance/grants").status_code == 403
    assert client.delete(f"/api/governance/grants/{grant.grant_id}").status_code == 403
    assert approvals_module.get_grant_store().has_grant("sess-1", "tool", "a") is not None


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/governance/grants"),
        ("delete", "/api/governance/grants/gnt_x"),
        ("post", "/api/governance/approvals/appr_x/approve"),
    ],
)
def test_unauthenticated_callers_get_401(method, path):
    response = getattr(_client(unauthenticated=True), method)(path)
    assert response.status_code == 401


@pytest.mark.parametrize("scope", ["forever", "ONCE", "Session", "", "all", "null"])
def test_unknown_scope_values_are_422(scope):
    req = _pending()
    response = _client(ADMIN).post(
        f"/api/governance/approvals/{req.approval_id}/approve", json={"scope": scope}
    )
    assert response.status_code == 422
    assert approvals_module.get_approval_store().get(req.approval_id).status.value == "pending"


def test_null_scope_is_422():
    req = _pending()
    response = _client(ADMIN).post(
        f"/api/governance/approvals/{req.approval_id}/approve", json={"scope": None}
    )
    assert response.status_code == 422


# -- 9. flag off -------------------------------------------------------------


async def test_flag_off_ignores_grants_created_while_flag_was_on(monkeypatch):
    identity = resolve_identity(agent_name="coder", owner="sam", session_id="sess-1")
    approvals_module.get_grant_store().grant("sess-1", "session", "tool", "x", "admin", 60)
    _set_flag(monkeypatch, False)
    await _assert_asks_a_human(identity)


def test_flag_off_approve_with_scope_issues_no_grant_and_still_approves(monkeypatch):
    _set_flag(monkeypatch, False)
    req = _pending()
    body = _client(ADMIN).post(
        f"/api/governance/approvals/{req.approval_id}/approve", json={"scope": "action"}
    ).json()
    assert body["status"] == "approved"
    assert body["grant"] is None


# -- 10. TTL control override -------------------------------------------------


def test_ttl_control_override_applies_to_new_grants():
    from packages.config import settings

    try:
        control_overrides.apply_overrides({"GOVERNANCE_GRANT_TTL_S": "120"})
        assert settings.governance_grant_ttl_s == 120
        req = _pending()
        grant = _client(ADMIN).post(
            f"/api/governance/approvals/{req.approval_id}/approve", json={"scope": "session"}
        ).json()["grant"]
        assert grant["ttl_s"] == 120
    finally:
        control_overrides.apply_overrides({})
    assert settings.governance_grant_ttl_s == 3600


def test_ttl_control_override_below_minimum_is_rejected():
    from packages.config.control_registry import coerce

    with pytest.raises(ValueError):
        coerce("GOVERNANCE_GRANT_TTL_S", "30")


def test_ttl_override_does_not_change_already_issued_grant_lifetime():
    from packages.config import settings

    try:
        grant = approvals_module.get_grant_store().grant("sess-1", "session", "tool", "a", "admin", 3600)
        control_overrides.apply_overrides({"GOVERNANCE_GRANT_TTL_S": "60"})
        assert settings.governance_grant_ttl_s == 60
        assert grant.ttl_s == 3600
    finally:
        control_overrides.apply_overrides({})


# -- 11. store bound ----------------------------------------------------------


def test_default_grant_store_is_capped_at_500():
    store = GrantStore()
    for i in range(600):
        store.grant(f"sess-{i}", "session", "tool", "a", "admin", 3600)
    assert len(store.list_grants()) == 500


def test_flood_evicts_oldest_grant_and_victim_fails_closed():
    store = GrantStore(capacity=5)
    store.grant("victim", "session", "tool", "a", "admin", 3600)
    for i in range(5):
        store.grant(f"attacker-{i}", "session", "tool", "a", "admin", 3600)
    assert store.has_grant("victim", "tool", "a") is None
    assert len(store.list_grants()) == 5


def test_capacity_is_clamped_to_at_least_one():
    store = GrantStore(capacity=0)
    store.grant("s1", "session", "tool", "a", "admin", 60)
    store.grant("s2", "session", "tool", "a", "admin", 60)
    assert len(store.list_grants()) == 1
