"""Governance on the MCP HTTP surface — threat-model T11.

Before this, ``mcp_server`` exposed ``clone_repo``, ``write_file``,
``run_command``, ``git_push`` and ``delete_workspace`` over HTTP with no
policy evaluation, no identity, and no audit row — a strictly larger
capability than the governed in-process agent path, reachable by a shorter
route.

The properties pinned here:

  * a tool call is evaluated and audited,
  * ``enforce`` mode actually blocks, and the tool never runs,
  * ``observe`` mode changes nothing (the same Golden Rule guarantee the
    in-process gate has),
  * identity propagates from the caller's headers, and its absence lands on
    the least-privileged group rather than an unrestricted one,
  * a spoofed identity still cannot get past a baseline rule,
  * governance being unavailable degrades to serving, loudly, not crashing.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from packages.governance.audit import AuditLog, reset_audit_log
from packages.governance.policy import PolicyEngine, reset_policy_engine


@pytest.fixture(autouse=True)
def isolated_governance():
    reset_audit_log(AuditLog(capacity=100))
    yield
    reset_audit_log(None)
    reset_policy_engine(None)


@pytest.fixture
def client(monkeypatch):
    """MCP app with the real dispatch but a stubbed tool implementation."""
    import mcp_server.server as server

    calls: list[tuple[str, dict]] = []

    async def fake_handle_tool(name, arguments):
        calls.append((name, arguments))
        return {"ok": True, "tool": name}

    monkeypatch.setattr(server, "_handle_tool", fake_handle_tool)
    test_client = TestClient(server.app)
    test_client.tool_calls = calls  # type: ignore[attr-defined]
    return test_client


def _engine(mode: str, **document) -> PolicyEngine:
    engine = PolicyEngine({"mode": mode, **document})
    reset_policy_engine(engine)
    return engine


def _call(client, tool, arguments=None, headers=None):
    return client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
              "params": {"name": tool, "arguments": arguments or {}}},
        headers=headers or {},
    )


# ── Health ───────────────────────────────────────────────────────────────────


def test_health_reports_whether_governance_is_active(client):
    """An operator must be able to tell a governed server from an ungoverned one."""
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert "governance" in body
    assert body["governance"]["active"] is True


def test_health_never_leaks_a_secret(client):
    assert "MCP_SECRET_TOKEN" not in client.get("/health").text


# ── Enforcement ──────────────────────────────────────────────────────────────


def test_enforce_mode_blocks_and_the_tool_never_runs(client):
    """The decisive test: a blocked call must not reach the workspace."""
    _engine("enforce", baseline={"filesystem": {"deny": [".env"]}})
    response = _call(client, "read_file", {"path": ".env"})
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["isError"] is True
    assert "[governance] denied" in result["content"][0]["text"]
    assert "baseline.filesystem.deny" in result["content"][0]["text"]
    assert client.tool_calls == [], "the blocked tool must never have executed"


def test_observe_mode_lets_the_call_through(client):
    """Same Golden Rule guarantee as the in-process gate."""
    _engine("observe", baseline={"filesystem": {"deny": [".env"]}})
    response = _call(client, "read_file", {"path": ".env"})
    assert response.json()["result"]["isError"] is False
    assert len(client.tool_calls) == 1


def test_approval_gated_actions_are_refused_rather_than_parked(client):
    """No UI is attached to this surface, so holding the socket would hang it."""
    _engine("enforce", baseline={"tool": {"require_approval": ["git_push"]}})
    result = _call(client, "git_push", {}).json()["result"]
    assert result["isError"] is True
    assert "requires human approval" in result["content"][0]["text"]
    assert client.tool_calls == []


def test_allowed_calls_still_execute_and_return_their_result(client):
    _engine("enforce")
    result = _call(client, "read_file", {"path": "README.md"}).json()["result"]
    assert result["isError"] is False
    assert "read_file" in result["content"][0]["text"]
    assert len(client.tool_calls) == 1


# ── Identity ─────────────────────────────────────────────────────────────────


def test_identity_headers_attribute_the_audit_row(client):
    from packages.governance.audit import get_audit_log

    _engine("observe")
    _call(client, "read_file", {"path": "a.py"}, headers={
        "X-Agent-Name": "Research Bot",
        "X-Agent-Owner": "sam@example.com",
        "X-Agent-Repo": "o/r",
        "X-Agent-Branch": "feature/x",
    })
    events = get_audit_log().recent(5)
    assert events, "the MCP call must be audited"
    event = events[0]
    assert event["agent_id"] == "agent:research-bot"
    assert event["owner"] == "sam@example.com"
    assert event["repo"] == "o/r"
    assert event["branch"] == "feature/x"
    assert event["runtime"] == "mcp-server"


def test_missing_identity_lands_on_the_least_privileged_group(client):
    from packages.governance.audit import get_audit_log

    _engine("observe")
    _call(client, "read_file", {"path": "a.py"})
    event = get_audit_log().recent(1)[0]
    assert event["agent_id"] == "agent:unknown"
    assert event["policy_group"] == "default"


def test_a_spoofed_identity_cannot_get_past_a_baseline_rule(client):
    """Headers are a hint, not a credential — and the baseline holds anyway.

    A caller holding the bearer token can claim any agent id. That can move
    them between groups; it must never move them past the organization
    baseline, because `evaluate()` returns on a baseline DENY before any group
    rule is read.
    """
    _engine(
        "enforce",
        baseline={"filesystem": {"deny": [".env"]}},
        groups={"privileged": {"filesystem": {"allow": ["**", ".env"]}}},
    )
    result = _call(
        client, "read_file", {"path": ".env"},
        headers={"X-Agent-Name": "privileged"},
    ).json()["result"]
    assert result["isError"] is True
    assert "baseline.filesystem.deny" in result["content"][0]["text"]
    assert client.tool_calls == []


def test_non_latin1_agent_names_do_not_break_the_call():
    """A display name with an em-dash must not take out the tool call."""
    from agent.mcp_client import MCPClient
    from packages.governance.identity import resolve_identity

    mcp = MCPClient.__new__(MCPClient)
    mcp._governance_identity = resolve_identity(agent_name="Coder — EU", owner="a@b.c")
    headers = mcp._identity_headers()
    # The un-encodable value is dropped; the encodable ones survive.
    assert "X-Agent-Owner" in headers
    for value in headers.values():
        value.encode("latin-1")  # must not raise


def test_client_sends_no_identity_headers_when_none_is_attached():
    from agent.mcp_client import MCPClient

    mcp = MCPClient.__new__(MCPClient)
    assert mcp._identity_headers() == {}


# ── Auditing ─────────────────────────────────────────────────────────────────


def test_a_blocked_call_is_audited_as_blocked(client):
    from packages.governance.audit import get_audit_log

    _engine("enforce", baseline={"filesystem": {"deny": [".env"]}})
    _call(client, "read_file", {"path": ".env"})
    event = get_audit_log().recent(1)[0]
    assert event["result_status"] == "blocked"
    assert event["decision"] == "deny"


def test_a_failing_tool_is_audited_as_an_error(client, monkeypatch):
    import mcp_server.server as server
    from packages.governance.audit import get_audit_log

    async def exploding_tool(name, arguments):
        raise RuntimeError("workspace on fire")

    monkeypatch.setattr(server, "_handle_tool", exploding_tool)
    _engine("observe")
    result = _call(client, "read_file", {"path": "a.py"}).json()["result"]
    assert result["isError"] is True
    # The caller gets a generic message; the audit row keeps the real reason.
    assert "internal error" in result["content"][0]["text"]
    event = get_audit_log().recent(1)[0]
    assert event["result_status"] == "error"
    assert "workspace on fire" in (event["error"] or "")


def test_audit_arguments_are_redacted(client):
    from packages.governance.audit import get_audit_log

    _engine("observe")
    _call(client, "clone_repo", {"repo_url": "https://x", "github_token": "ghp_abcdefghijklmnop1234"})
    event = get_audit_log().recent(1)[0]
    assert event["arguments"]["github_token"] == "***"
    assert "ghp_abcdefghijklmnop1234" not in str(event)


# ── Degradation ──────────────────────────────────────────────────────────────


def test_unknown_tools_are_still_rejected_before_governance(client):
    _engine("enforce")
    body = _call(client, "no_such_tool", {}).json()
    assert "error" in body
    assert body["error"]["code"] == -32601


def test_governance_unavailable_serves_rather_than_crashing(client, monkeypatch):
    """An older image without packages/governance must still work."""
    import mcp_server.governance as gov

    monkeypatch.setattr(gov, "_GOVERNANCE", None)
    assert gov.is_active() is False
    assert gov.status()["active"] is False
    # The guard passes everything through and nothing raises.
    allowed, message, decision = gov.guard(None, "read_file", {"path": ".env"})
    assert allowed is True and decision is None and message == ""
    result = _call(client, "read_file", {"path": ".env"}).json()["result"]
    assert result["isError"] is False


def test_a_broken_policy_engine_fails_open_on_the_mcp_surface(client, monkeypatch):
    """Governance must never be able to take out the tool surface."""
    import mcp_server.governance as gov

    class Exploding:
        def evaluate(self, *a, **k):
            raise RuntimeError("engine exploded")

        def limits_for(self, *a, **k):
            return {}

        @property
        def mode(self):
            raise RuntimeError("engine exploded")

    monkeypatch.setitem(gov._GOVERNANCE, "get_policy_engine", lambda: Exploding())
    allowed, _msg, decision = gov.guard(None, "read_file", {"path": ".env"})
    assert allowed is True
    assert decision is None
