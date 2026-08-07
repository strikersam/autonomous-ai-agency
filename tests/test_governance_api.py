"""Tests for the governance HTTP surface and the AgentRunner integration.

The dispatch-transparency tests at the bottom are the ones that matter most:
they pin CLAUDE.md §0 (no user-visible behaviour change) for the seam that
touches every agent tool call in the platform.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.governance_router import build_governance_router
from packages.governance.approvals import ApprovalStore
from packages.governance.audit import AuditEvent, AuditLog
from packages.governance.policy import PolicyEngine, reset_policy_engine


ADMIN = {"email": "admin@example.com", "role": "admin"}
VIEWER = {"email": "viewer@example.com", "role": "viewer"}


def _client(user: dict) -> TestClient:
    app = FastAPI()
    app.include_router(build_governance_router(lambda: user))
    return TestClient(app)


@pytest.fixture(autouse=True)
def isolated_governance():
    from packages.governance import approvals as approvals_module
    from packages.governance import audit as audit_module
    from packages.governance import sandbox as sandbox_module

    audit_module.reset_audit_log(AuditLog(capacity=100))
    approvals_module.reset_approval_store(ApprovalStore())
    reset_policy_engine(PolicyEngine.from_file("config/agent_policy.yaml"))
    yield
    audit_module.reset_audit_log(None)
    approvals_module.reset_approval_store(None)
    reset_policy_engine(None)
    sandbox_module.reset_sandbox_manager(None)


# ── Authorization ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/governance/status"),
        ("get", "/api/governance/policy"),
        ("get", "/api/governance/audit"),
        ("get", "/api/governance/metrics"),
        ("get", "/api/governance/approvals"),
        ("get", "/api/governance/sandboxes"),
        ("post", "/api/governance/policy/reload"),
        ("post", "/api/governance/sandboxes/reap"),
    ],
)
def test_every_route_requires_admin(method, path):
    """An audit trail is an inventory of what the platform touches.

    That is exactly what an attacker wants first, so reads are admin-gated
    too — not only the mutating routes.
    """
    response = getattr(_client(VIEWER), method)(path)
    assert response.status_code == 403, path


def test_admin_can_read_status():
    response = _client(ADMIN).get("/api/governance/status")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "observe"
    assert body["enforcing"] is False
    assert "sandbox" in body


def test_status_reports_the_real_sandbox_backend():
    """No Docker daemon and no E2B in CI means the honest answer is 'local'."""
    body = _client(ADMIN).get("/api/governance/status").json()
    assert body["sandbox"]["backend"] in {"docker", "e2b", "local", "unknown"}


# ── Policy ───────────────────────────────────────────────────────────────────


def test_policy_endpoint_returns_the_effective_document():
    body = _client(ADMIN).get("/api/governance/policy").json()
    assert body["mode"] == "observe"
    assert "baseline" in body
    assert "research" in body["groups"]


def test_policy_response_contains_no_secret_values():
    blob = _client(ADMIN).get("/api/governance/policy").text.lower()
    for marker in ("ghp_", "sk-ant-", "nvapi-", "csk-", "gsk_", "password="):
        assert marker not in blob


def test_policy_reload_rereads_the_file():
    body = _client(ADMIN).post("/api/governance/policy/reload").json()
    assert body["reloaded"] is True
    assert body["mode"] == "observe"


def test_there_is_no_endpoint_that_edits_policy():
    """Policy is a git-reviewed file.

    An HTTP mutation route would make "who changed the rules" unanswerable and
    would let anyone who steals an admin session silently disable the controls.
    """
    app = FastAPI()
    app.include_router(build_governance_router(lambda: ADMIN))
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set())
        if path == "/api/governance/policy":
            assert methods == {"GET"}, "policy must be read-only over HTTP"


# ── Simulation ───────────────────────────────────────────────────────────────


def test_simulate_predicts_a_decision_without_performing_it():
    """The tool that makes turning on enforcement safe."""
    response = _client(ADMIN).post(
        "/api/governance/policy/simulate",
        json={"tool": "read_file", "args": {"path": ".env"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["classified_surface"] == "filesystem"
    assert body["classified_action"] == ".env"
    assert body["decision"]["decision"] == "deny"
    assert body["would_block"] is True


def test_simulate_respects_the_requested_policy_group():
    response = _client(ADMIN).post(
        "/api/governance/policy/simulate",
        json={"tool": "write_file", "args": {"path": "a.py"}, "policy_group": "research"},
    )
    body = response.json()
    assert body["decision"]["group"] == "research"
    assert body["would_block"] is True, "research declares write: [] — no writes"


def test_simulate_requires_a_tool():
    assert _client(ADMIN).post("/api/governance/policy/simulate", json={}).status_code == 400


def test_simulate_rejects_an_unknown_surface():
    response = _client(ADMIN).post(
        "/api/governance/policy/simulate",
        json={"tool": "read_file", "surface": "telepathy"},
    )
    assert response.status_code == 400


# ── Audit ────────────────────────────────────────────────────────────────────


def test_audit_endpoint_returns_recorded_events():
    from packages.governance.audit import get_audit_log

    get_audit_log().record(AuditEvent(agent_id="agent:coder", action="read", surface="filesystem"))
    body = _client(ADMIN).get("/api/governance/audit").json()
    assert body["count"] == 1
    assert body["events"][0]["agent_id"] == "agent:coder"


def test_audit_endpoint_filters():
    from packages.governance.audit import get_audit_log

    log = get_audit_log()
    log.record(AuditEvent(agent_id="agent:a", surface="tool", decision="allow"))
    log.record(AuditEvent(agent_id="agent:b", surface="network", decision="deny"))
    body = _client(ADMIN).get("/api/governance/audit?decision=deny").json()
    assert body["count"] == 1
    assert body["events"][0]["agent_id"] == "agent:b"


def test_audit_endpoint_never_returns_a_secret():
    from packages.governance.audit import get_audit_log

    get_audit_log().record(
        AuditEvent(action="clone", arguments={"github_token": "ghp_abcdefghijklmnop1234"})
    )
    assert "ghp_abcdefghijklmnop1234" not in _client(ADMIN).get("/api/governance/audit").text


def test_metrics_expose_the_would_block_signal():
    body = _client(ADMIN).get("/api/governance/metrics").json()
    assert "would_block" in body["audit"]
    assert body["mode"] == "observe"


# ── Approvals ────────────────────────────────────────────────────────────────


def test_pending_approvals_are_listed_and_resolvable():
    from packages.governance.approvals import get_approval_store

    request = get_approval_store().create(
        agent_id="agent:coder", surface="tool", action="github_merge_pr",
        reason="baseline requires approval", rule_id="baseline.tool.require_approval",
    )
    client = _client(ADMIN)
    assert client.get("/api/governance/approvals").json()["count"] == 1

    response = client.post(
        f"/api/governance/approvals/{request.approval_id}/approve", json={"note": "ok"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approved"
    assert body["resolved_by"] == "admin@example.com", "the decider must be named"
    assert client.get("/api/governance/approvals").json()["count"] == 0


def test_denying_an_approval_records_the_denier():
    from packages.governance.approvals import get_approval_store

    request = get_approval_store().create(
        agent_id="agent:coder", surface="tool", action="deploy", reason="r", rule_id="r"
    )
    body = _client(ADMIN).post(
        f"/api/governance/approvals/{request.approval_id}/deny", json={"note": "not now"}
    ).json()
    assert body["status"] == "denied"
    assert body["resolved_note"] == "not now"


def test_resolving_an_unknown_approval_is_404():
    assert _client(ADMIN).post("/api/governance/approvals/nope/approve").status_code == 404


# ── Sandboxes ────────────────────────────────────────────────────────────────


def test_sandbox_listing_reports_profiles():
    body = _client(ADMIN).get("/api/governance/sandboxes").json()
    assert body["count"] == 0
    assert "browser" in body["profiles"] and "security" in body["profiles"]


def test_destroying_an_unknown_sandbox_is_404():
    assert _client(ADMIN).delete("/api/governance/sandboxes/sbx_nope").status_code == 404


def test_reap_is_safe_when_there_is_nothing_to_reap():
    body = _client(ADMIN).post("/api/governance/sandboxes/reap").json()
    assert body["count"] == 0


# ── AgentRunner dispatch transparency (CLAUDE.md §0) ─────────────────────────


class _StubRunner:
    """Minimal stand-in exposing only what the governance seam touches."""

    agent_name = "Test Coder"
    user_email = "sam@example.com"

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def _dispatch_tool_unguarded(self, tool, args, user_id=None, memory_store=None):
        self.calls.append((tool, args, user_id, memory_store))
        if tool == "explode":
            raise ValueError("tool blew up")
        return f"result-of-{tool}"

    # Bind the real implementation under test.
    from agent.loop import AgentRunner as _Real

    _dispatch_tool = _Real._dispatch_tool


async def test_dispatch_returns_the_unguarded_result_unchanged():
    """The wrapper must be a pass-through in observe mode."""
    reset_policy_engine(PolicyEngine.from_file("config/agent_policy.yaml"))
    runner = _StubRunner()
    result = await runner._dispatch_tool("read_file", {"path": "a.py"}, "user-1", None)
    assert result == "result-of-read_file"
    assert runner.calls == [("read_file", {"path": "a.py"}, "user-1", None)]


async def test_dispatch_propagates_exceptions_unchanged():
    """A tool that raises must still raise — governance may not swallow errors."""
    reset_policy_engine(PolicyEngine.from_file("config/agent_policy.yaml"))
    runner = _StubRunner()
    with pytest.raises(ValueError, match="tool blew up"):
        await runner._dispatch_tool("explode", {}, None, None)


async def test_dispatch_bypasses_governance_entirely_when_disabled(monkeypatch):
    from packages.config import settings

    monkeypatch.setattr(settings, "governance_enabled_raw", "false", raising=False)
    runner = _StubRunner()
    assert await runner._dispatch_tool("read_file", {"path": "a.py"}) == "result-of-read_file"


async def test_dispatch_audits_the_call_with_agent_identity():
    from packages.governance.audit import get_audit_log

    reset_policy_engine(PolicyEngine.from_file("config/agent_policy.yaml"))
    runner = _StubRunner()
    await runner._dispatch_tool("read_file", {"path": "a.py"}, None, None)
    events = get_audit_log().recent(10)
    assert events, "the call must be audited"
    assert events[0]["agent_id"] == "agent:test-coder"
    assert events[0]["owner"] == "sam@example.com"
    assert events[0]["tool"] == "read_file"


async def test_dispatch_reuses_one_session_id_across_calls():
    """Per-session budgets and audit correlation both depend on this."""
    from packages.governance.audit import get_audit_log

    reset_policy_engine(PolicyEngine.from_file("config/agent_policy.yaml"))
    runner = _StubRunner()
    await runner._dispatch_tool("read_file", {"path": "a.py"})
    await runner._dispatch_tool("list_files", {"path": "."})
    sessions = {e["session_id"] for e in get_audit_log().recent(10)}
    assert len(sessions) == 1, f"expected one session, got {sessions}"


async def test_dispatch_blocks_and_returns_a_message_in_enforce_mode():
    """A blocked call returns a readable result, it does not raise."""
    import yaml

    with open("config/agent_policy.yaml", encoding="utf-8") as fh:
        document = yaml.safe_load(fh)
    document["mode"] = "enforce"
    reset_policy_engine(PolicyEngine(document))

    runner = _StubRunner()
    result = await runner._dispatch_tool("read_file", {"path": ".env"}, None, None)
    assert isinstance(result, str)
    assert "[governance]" in result
    assert runner.calls == [], "the blocked tool must never have run"
