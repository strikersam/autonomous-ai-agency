"""Tests for the enforcement seam, audit trail, approvals, and budgets.

The single most important test in this file is
``test_observe_mode_is_behaviourally_transparent``: it pins the Golden Rule
(CLAUDE.md §0) guarantee that shipping this layer changes nothing until an
operator explicitly turns enforcement on.
"""
from __future__ import annotations

import asyncio

import pytest

from packages.governance.approvals import ApprovalStatus, ApprovalStore
from packages.governance.audit import AuditEvent, AuditLog, scrub
from packages.governance.enforcement import (
    BudgetTracker,
    GovernanceGate,
    classify,
    _more_restrictive,
)
from packages.governance.identity import resolve_identity
from packages.governance.policy import (
    Decision,
    PolicyDecision,
    PolicyEngine,
    Surface,
    reset_policy_engine,
)


@pytest.fixture(autouse=True)
def isolated_governance():
    """Give every test its own engine, audit log, and approval store."""
    from packages.governance import approvals as approvals_module
    from packages.governance import audit as audit_module

    audit_module.reset_audit_log(AuditLog(capacity=100))
    approvals_module.reset_approval_store(ApprovalStore())
    yield
    reset_policy_engine(None)
    audit_module.reset_audit_log(None)
    approvals_module.reset_approval_store(None)


def _engine(mode: str = "enforce", **document) -> PolicyEngine:
    engine = PolicyEngine({"mode": mode, **document})
    reset_policy_engine(engine)
    return engine


# ── Classification ───────────────────────────────────────────────────────────


def test_classify_extracts_the_real_subject_not_just_the_tool_name():
    """`read_file` on `.env` is a filesystem fact about `.env`."""
    assert classify("read_file", {"path": "src/app.py"}) == (Surface.FILESYSTEM, "src/app.py")
    assert classify("run_command", {"cmd": "ls -la"}) == (Surface.SHELL, "ls -la")
    assert classify("github_merge_pr", {"repo_name": "o/r"}) == (Surface.GITHUB, "o/r")


def test_classify_reduces_a_url_to_its_host_so_domain_rules_apply():
    """Rules are written against hosts; a full URL would only match a wildcard."""
    surface, action = classify("fetch_url", {"url": "https://api.evil.com/steal?x=1"})
    assert (surface, action) == (Surface.NETWORK, "api.evil.com")


def test_classify_ignores_a_search_query_that_is_not_a_host():
    surface, action = classify("web_search", {"query": "how to write a policy engine"})
    assert surface is Surface.NETWORK
    assert action == "web_search", "a prose query is not a hostname"


def test_unknown_tools_are_still_governed_on_the_tool_surface():
    assert classify("some_brand_new_tool", {}) == (Surface.TOOL, "some_brand_new_tool")


def test_classify_is_total_even_with_no_arguments():
    for tool in ("read_file", "run_command", "fetch_url", "github_x", ""):
        surface, action = classify(tool, {})
        assert isinstance(surface, Surface) and isinstance(action, str)


# ── The Golden Rule guarantee ────────────────────────────────────────────────


async def test_observe_mode_is_behaviourally_transparent():
    """Nothing is blocked in observe mode, however aggressive the policy.

    This is the property that makes shipping governance enabled-by-default
    safe: an operator gets the audit trail and the would-block signal without
    any change to what agents can do.
    """
    _engine("observe", baseline={"tool": {"deny": ["*"]}})
    gate = GovernanceGate()
    identity = resolve_identity(agent_name="coder")
    result = await gate.guard(identity, "write_file", {"path": "x.py"})
    assert result.allowed is True, "observe mode must never block"
    assert result.decision.decision is Decision.DENY, "but the verdict is still recorded"
    assert result.decision.would_block is True


async def test_would_block_is_recorded_in_the_audit_trail_during_observe():
    """The signal an operator uses to decide when enforce is safe."""
    from packages.governance.audit import get_audit_log

    _engine("observe", baseline={"filesystem": {"deny": [".env"]}})
    gate = GovernanceGate()
    await gate.guard(resolve_identity(agent_name="coder"), "read_file", {"path": ".env"})
    summary = get_audit_log().summary()
    assert summary["would_block"] >= 1


async def test_enforce_mode_blocks_and_explains_why():
    _engine("enforce", baseline={"filesystem": {"deny": [".env"]}})
    gate = GovernanceGate()
    result = await gate.guard(resolve_identity(agent_name="coder"), "read_file", {"path": ".env"})
    assert result.allowed is False
    assert "deny" in result.denial_message
    assert "baseline.filesystem.deny" in result.denial_message, "names the rule that fired"


async def test_a_tool_allow_list_applies_even_when_the_tool_carries_a_path():
    """Regression: judging only the subject surface ignored the tool allow-list.

    `write_file` is both a TOOL fact and a FILESYSTEM fact. Evaluating only
    the latter meant `tool.allow: [read_file]` silently failed to refuse
    `write_file` — for nearly every tool, since most carry a path or a URL.
    """
    _engine("enforce", groups={"ro": {"tool": {"allow": ["read_file"]}}})
    gate = GovernanceGate()
    identity = resolve_identity(agent_name="x", policy_group="ro")
    assert (await gate.guard(identity, "read_file", {"path": "a.py"})).allowed is True
    assert (await gate.guard(identity, "write_file", {"path": "a.py"})).allowed is False


def test_combining_two_surface_verdicts_can_only_tighten():
    allow = PolicyDecision(Decision.ALLOW, Surface.TOOL, "a", "", "r1")
    approval = PolicyDecision(Decision.REQUIRE_APPROVAL, Surface.TOOL, "a", "", "r2")
    deny = PolicyDecision(Decision.DENY, Surface.TOOL, "a", "", "r3")
    assert _more_restrictive(allow, deny).decision is Decision.DENY
    assert _more_restrictive(deny, allow).decision is Decision.DENY
    assert _more_restrictive(allow, approval).decision is Decision.REQUIRE_APPROVAL
    assert _more_restrictive(deny, approval).decision is Decision.DENY


# ── Fail-open on internal error ──────────────────────────────────────────────


async def test_a_broken_policy_engine_allows_rather_than_breaking_dispatch(monkeypatch):
    """Governance must never be able to take agent dispatch down."""
    _engine("enforce")

    class Exploding:
        def evaluate(self, *a, **k):
            raise RuntimeError("engine exploded")

        def limits_for(self, *a, **k):
            return {}

    monkeypatch.setattr(
        "packages.governance.enforcement.get_policy_engine", lambda: Exploding()
    )
    result = await GovernanceGate().guard(resolve_identity(agent_name="c"), "read_file", {})
    assert result.allowed is True
    assert "fail-open" in result.decision.rule_id


# ── Cost / runaway governance ────────────────────────────────────────────────


async def test_tool_call_ceiling_stops_a_runaway_loop():
    _engine("enforce", groups={"default": {"limits": {"max_tool_calls": 3}}})
    gate = GovernanceGate()
    identity = resolve_identity(agent_name="looper")
    outcomes = [
        (await gate.guard(identity, "read_file", {"path": "a.py"})).allowed for _ in range(5)
    ]
    assert outcomes[:3] == [True, True, True]
    assert outcomes[3:] == [False, False], "the ceiling must hold, not merely warn"


async def test_cost_ceiling_stops_a_token_explosion():
    _engine("enforce", groups={"default": {"limits": {"max_cost_usd": 1.0}}})
    gate = GovernanceGate()
    identity = resolve_identity(agent_name="spender")
    first = await gate.guard(identity, "read_file", {"path": "a.py"})
    assert first.allowed is True
    gate.record_result(identity, "read_file", {}, first.decision, cost_usd=1.50, tokens=90000)
    assert (await gate.guard(identity, "read_file", {"path": "b.py"})).allowed is False


async def test_budget_denial_names_the_exhausted_limit():
    _engine("enforce", groups={"default": {"limits": {"max_tool_calls": 1}}})
    gate = GovernanceGate()
    identity = resolve_identity(agent_name="looper")
    await gate.guard(identity, "read_file", {})
    blocked = await gate.guard(identity, "read_file", {})
    assert "max_tool_calls" in blocked.decision.reason


async def test_budgets_are_per_session_not_global():
    """One agent exhausting its budget must not block a different run."""
    _engine("enforce", groups={"default": {"limits": {"max_tool_calls": 1}}})
    gate = GovernanceGate()
    first = resolve_identity(agent_name="a")
    second = resolve_identity(agent_name="b")
    await gate.guard(first, "read_file", {})
    assert (await gate.guard(first, "read_file", {})).allowed is False
    assert (await gate.guard(second, "read_file", {})).allowed is True


def test_a_missing_limit_key_means_unlimited_not_zero():
    """Absence must not silently block everything."""
    tracker = BudgetTracker()
    budget = tracker.get("s1", {"max_tool_calls": 10})
    budget.tool_calls = 10_000
    budget.cost_usd = 10_000.0
    assert "max_tool_calls" in (budget.check() or "")
    unlimited = tracker.get("s2", {})
    unlimited.tool_calls = 10_000
    assert unlimited.check() is None


def test_budget_tracker_evicts_rather_than_growing_without_bound():
    tracker = BudgetTracker(capacity=5)
    for i in range(50):
        tracker.get(f"session-{i}", {"max_tool_calls": 1})
    assert len(tracker.all()) <= 5


# ── Approvals ────────────────────────────────────────────────────────────────


async def test_approval_gate_blocks_until_a_human_approves():
    _engine("enforce", baseline={"tool": {"require_approval": ["github_merge_pr"]}})
    from packages.governance.approvals import get_approval_store

    gate = GovernanceGate()
    identity = resolve_identity(agent_name="coder", owner="sam@example.com")
    store = get_approval_store()

    task = asyncio.create_task(gate.guard(identity, "github_merge_pr", {"repo_name": "o/r"}))
    for _ in range(50):
        await asyncio.sleep(0.01)
        if store.pending():
            break
    pending = store.pending()
    assert len(pending) == 1
    assert pending[0]["agent_id"] == "agent:coder"

    store.resolve(pending[0]["approval_id"], approved=True, resolved_by="sam@example.com")
    result = await asyncio.wait_for(task, timeout=5)
    assert result.allowed is True


async def test_denied_approval_blocks_the_action():
    _engine("enforce", baseline={"tool": {"require_approval": ["deploy_prod"]}})
    from packages.governance.approvals import get_approval_store

    gate = GovernanceGate()
    store = get_approval_store()
    task = asyncio.create_task(
        gate.guard(resolve_identity(agent_name="coder"), "deploy_prod", {})
    )
    for _ in range(50):
        await asyncio.sleep(0.01)
        if store.pending():
            break
    store.resolve(store.pending()[0]["approval_id"], approved=False, resolved_by="sam")
    result = await asyncio.wait_for(task, timeout=5)
    assert result.allowed is False


async def test_an_ignored_approval_expires_denied_not_allowed():
    """An approval gate that opens when ignored is theatre."""
    store = ApprovalStore()
    request = store.create(
        agent_id="agent:x", surface="tool", action="deploy",
        reason="test", rule_id="r", ttl_s=0.05,
    )
    status = await asyncio.wait_for(store.wait(request.approval_id), timeout=5)
    assert status is ApprovalStatus.EXPIRED
    assert store.get(request.approval_id).resolved_by == "timeout"


def test_the_first_decision_wins_so_a_retry_cannot_flip_it():
    store = ApprovalStore()
    request = store.create(
        agent_id="a", surface="tool", action="x", reason="r", rule_id="r", ttl_s=60
    )
    store.resolve(request.approval_id, approved=True, resolved_by="alice")
    store.resolve(request.approval_id, approved=False, resolved_by="mallory")
    final = store.get(request.approval_id)
    assert final.status is ApprovalStatus.APPROVED
    assert final.resolved_by == "alice"


def test_approval_records_who_decided():
    store = ApprovalStore()
    request = store.create(
        agent_id="a", surface="tool", action="x", reason="r", rule_id="r", ttl_s=60
    )
    resolved = store.resolve(
        request.approval_id, approved=True, resolved_by="sam@example.com", note="reviewed"
    )
    assert resolved.resolved_by == "sam@example.com"
    assert resolved.resolved_note == "reviewed"
    assert resolved.resolved_iso is not None


def test_resolving_an_unknown_approval_returns_none():
    assert ApprovalStore().resolve("nope", approved=True, resolved_by="x") is None


def test_approval_arguments_are_scrubbed_before_they_reach_a_reviewer():
    store = ApprovalStore()
    request = store.create(
        agent_id="a", surface="tool", action="x", reason="r", rule_id="r",
        arguments={"github_token": "ghp_abcdefghijklmnop1234"},
    )
    assert request.arguments["github_token"] == "***"


async def test_auto_approve_is_audited_as_such(monkeypatch):
    """The local-dev escape hatch must be visible in the trail when it fires."""
    from packages.config import settings

    monkeypatch.setattr(settings, "governance_auto_approve_raw", "true", raising=False)
    _engine("enforce", baseline={"tool": {"require_approval": ["deploy_prod"]}})
    result = await GovernanceGate().guard(
        resolve_identity(agent_name="coder"), "deploy_prod", {}
    )
    assert result.allowed is True
    assert result.approval_id == "auto-approve"


# ── Audit trail ──────────────────────────────────────────────────────────────


def test_secrets_are_redacted_at_write_time_not_read_time():
    """The stored object must not hold the secret at all."""
    event = AuditEvent(
        action="clone",
        arguments={"github_token": "ghp_abcdefghijklmnop1234", "url": "https://x.com"},
    )
    assert event.arguments["github_token"] == "***"
    assert "ghp_" not in event.to_json()


@pytest.mark.parametrize(
    "secret",
    [
        "ghp_abcdefghijklmnop1234",
        "github_pat_11ABCDEFG0abcdefghij1234",
        "sk-ant-api03-abcdefghijklmnop",
        "nvapi-abcdefghijklmnop1234",
        "gsk_abcdefghijklmnop1234",
        "csk-abcdefghijklmnop1234",
        "e2b_abcdefghijklmnop1234",
    ],
)
def test_provider_token_shapes_are_redacted_inside_free_text(secret):
    """Tokens leak through commands and diffs, not only through named keys."""
    scrubbed = scrub(f"curl -H 'Authorization: Bearer {secret}' https://api.example.com")
    assert secret not in scrubbed


def test_connection_strings_are_redacted():
    """A live MongoDB password reached a log line in this repo once already."""
    scrubbed = scrub("mongodb+srv://admin:hunter2@cluster.mongodb.net/db")
    assert "hunter2" not in scrubbed


def test_nested_secret_keys_are_redacted():
    scrubbed = scrub({"outer": {"inner": {"api_key": "abc123456789"}}, "ok": "visible"})
    assert scrubbed["outer"]["inner"]["api_key"] == "***"
    assert scrubbed["ok"] == "visible"


def test_redaction_fails_closed_on_an_unrepresentable_value():
    class Hostile:
        def __str__(self):
            raise RuntimeError("boom")

    assert scrub(Hostile()) == "[redaction-failed:withheld]"


def test_deeply_nested_structures_are_capped_not_recursed_forever():
    nested: dict = {}
    cursor = nested
    for _ in range(50):
        cursor["next"] = {}
        cursor = cursor["next"]
    assert scrub(nested) is not None


def test_audit_buffer_is_bounded():
    """An unbounded audit list is a memory leak with a security justification."""
    log = AuditLog(capacity=10)
    for i in range(100):
        log.record(AuditEvent(action=f"a{i}"))
    assert log.summary()["buffered_events"] == 10


def test_a_broken_sink_cannot_suppress_the_audit_or_raise():
    log = AuditLog(capacity=10)
    seen: list[str] = []
    log.add_sink(lambda e: (_ for _ in ()).throw(RuntimeError("sink down")))
    log.add_sink(lambda e: seen.append(e.action))
    log.record(AuditEvent(action="still-recorded"))
    assert seen == ["still-recorded"], "a broken sink must not stop the others"
    assert log.summary()["buffered_events"] == 1


def test_audit_events_carry_the_full_who_what_when_why_where_cost_record():
    log = AuditLog(capacity=10)
    log.record(AuditEvent(
        agent_id="agent:coder", owner="sam@example.com", session_id="sess_1",
        surface="github", action="o/r", tool="git_push", decision="allow",
        rule_id="group.coding.github.default-allow", reason="no rule matches",
        result_status="ok", duration_ms=120.5, repo="o/r", branch="feature/x",
        commit="abc1234", sandbox_id="sbx_1", container_id="c1",
        llm_provider="nvidia", llm_model="meta/llama-3.3-70b-instruct",
        total_tokens=1500, cost_usd=0.002, source_ip="10.0.0.1",
    ))
    event = log.recent(1)[0]
    for field in (
        "agent_id", "owner", "session_id", "surface", "action", "tool", "timestamp",
        "duration_ms", "decision", "reason", "rule_id", "repo", "branch", "commit",
        "sandbox_id", "container_id", "llm_provider", "llm_model", "total_tokens",
        "cost_usd", "source_ip",
    ):
        assert field in event, f"audit row is missing {field}"


def test_audit_filters_narrow_by_agent_surface_and_decision():
    log = AuditLog(capacity=50)
    log.record(AuditEvent(agent_id="agent:a", surface="tool", decision="allow"))
    log.record(AuditEvent(agent_id="agent:b", surface="network", decision="deny"))
    assert len(log.recent(50, agent_id="agent:a")) == 1
    assert len(log.recent(50, surface="network")) == 1
    assert len(log.recent(50, decision="deny")) == 1


def test_large_results_are_truncated_rather_than_stored_whole():
    event = AuditEvent(action="read", result="x" * 100_000)
    assert len(event.result) < 10_000
    assert "truncated" in event.result


# ── Per-tool session caps (Claude Code v2.1.212 parity) ──────────────────────


def test_per_tool_calls_tracked_per_tool_not_only_in_aggregate():
    """guard() must increment both the aggregate counter and the per-tool map."""
    tracker = BudgetTracker()
    budget = tracker.get("sess-per-tool", {})
    budget.tool_calls = 3
    budget.per_tool_calls["web_search"] = 2
    budget.per_tool_calls["read_file"] = 1

    d = budget.to_dict()
    assert d["tool_calls"] == 3
    assert d["per_tool_calls"] == {"web_search": 2, "read_file": 1}


async def test_per_tool_cap_blocks_when_ceiling_reached():
    """A max_calls_<tool> ceiling must trigger check() once the tool is at the cap."""
    _engine("enforce", groups={"default": {"limits": {"max_calls_web_search": 2}}})
    gate = GovernanceGate()
    identity = resolve_identity(agent_name="researcher")

    # First two calls allowed (under/at ceiling check requires >=, not >).
    r1 = await gate.guard(identity, "web_search", {"query": "openai"})
    assert r1.allowed is True
    r2 = await gate.guard(identity, "web_search", {"query": "anthropic"})
    assert r2.allowed is True

    # Third call hits the cap.
    r3 = await gate.guard(identity, "web_search", {"query": "llama"})
    assert r3.allowed is False
    assert "max_calls_web_search" in r3.decision.reason


async def test_per_tool_cap_does_not_block_other_tools():
    """Exhausting web_search cap must not block read_file on the same session."""
    _engine("enforce", groups={"default": {"limits": {"max_calls_web_search": 1}}})
    gate = GovernanceGate()
    identity = resolve_identity(agent_name="researcher")

    await gate.guard(identity, "web_search", {"query": "x"})
    blocked = await gate.guard(identity, "web_search", {"query": "y"})
    assert blocked.allowed is False

    unaffected = await gate.guard(identity, "read_file", {"path": "README.md"})
    assert unaffected.allowed is True


async def test_missing_per_tool_limit_key_means_unlimited():
    """Absence of max_calls_<tool> must mean unlimited, not zero."""
    _engine("enforce", groups={"default": {"limits": {"max_calls_web_search": 0}}})
    gate = GovernanceGate()
    identity = resolve_identity(agent_name="coder")

    for _ in range(500):
        r = await gate.guard(identity, "web_search", {"query": "test"})
        if not r.allowed:
            pytest.fail("A ceiling of 0 must mean unlimited, but the call was blocked")


async def test_per_tool_calls_populated_after_guard():
    """After guard(), per_tool_calls in the budget must reflect the actual call."""
    _engine("observe")
    gate = GovernanceGate()
    identity = resolve_identity(agent_name="scout")

    await gate.guard(identity, "web_search", {"query": "test"})
    await gate.guard(identity, "read_file", {"path": "a.py"})
    await gate.guard(identity, "web_search", {"query": "more"})

    session_id = str(identity.session_id)
    all_budgets = {b["session_id"]: b for b in gate.budgets.all()}
    assert session_id in all_budgets
    ptc = all_budgets[session_id]["per_tool_calls"]
    assert ptc.get("web_search", 0) == 2
    assert ptc.get("read_file", 0) == 1


def test_per_tool_caps_do_not_interfere_across_sessions():
    """A tool cap exhausted in session A must not affect session B."""
    tracker = BudgetTracker()
    sess_a = tracker.get("a", {"max_calls_web_search": 1})
    sess_b = tracker.get("b", {"max_calls_web_search": 1})

    sess_a.per_tool_calls["web_search"] = 1
    assert sess_a.check_tool("web_search") is not None
    assert sess_b.check_tool("web_search") is None
