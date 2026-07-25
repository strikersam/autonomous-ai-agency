"""Tests for the CEO micro-management layer.

Covers the three decisions the CEO makes about delegated work:
  - how a request is split into subtasks and which tier each one starts at
  - whether a returned result is good enough to accept (the anti-slop gate)
  - what happens to a result that is not (the escalation ladder)

Plus the durable ledger those decisions are recorded in, and the 24x7
supervisor that sweeps it.
"""
from __future__ import annotations

import asyncio
import time

import pytest

from services.ceo_micromanager import (
    TIER_LADDER,
    MicroManagerConfig,
    SubtaskPlan,
    Tier,
    _extract_json_object,
    build_subtask_brief,
    decompose,
    fallback_decomposition,
    next_tier,
    resolve_runtime,
    starting_tier,
    tier_profile,
)
from services.ceo_quality import assess_quality, decide_escalation, touched_tests


def _plan(**kw) -> SubtaskPlan:
    base = dict(
        subtask_id="st-1",
        title="Add a health method",
        scope="Add a health() method to ProviderX.",
        outcome="ProviderX.health() returns {status, latency_ms}.",
    )
    base.update(kw)
    return SubtaskPlan(**base)


def _ok_result(**kw) -> dict:
    base = {
        "status": "ok",
        "summary": "Added the health() method to ProviderX and a test covering it.",
        "changed_files": ["providers/x.py", "tests/test_x.py"],
        "files_reported": True,
    }
    base.update(kw)
    return base


# ── Tier ladder ───────────────────────────────────────────────────────────────


def test_tier_ladder_is_ordered_cheapest_first():
    assert TIER_LADDER == [Tier.INTERN, Tier.JUNIOR, Tier.MIDLEVEL, Tier.SENIOR]


def test_next_tier_walks_up_and_stops_at_the_top():
    assert next_tier(Tier.INTERN) is Tier.JUNIOR
    assert next_tier(Tier.JUNIOR) is Tier.MIDLEVEL
    assert next_tier(Tier.MIDLEVEL) is Tier.SENIOR
    # The top of the ladder must terminate — this is what bounds escalation.
    assert next_tier(Tier.SENIOR) is None


def test_next_tier_accepts_strings_and_unknown_values():
    assert next_tier("intern") is Tier.JUNIOR
    assert next_tier("nonsense") is Tier.SENIOR


def test_tier_profiles_grow_monotonically():
    """A higher tier must never be given a smaller budget than a lower one."""
    steps = [tier_profile(t).max_steps for t in TIER_LADDER]
    files = [tier_profile(t).max_files for t in TIER_LADDER]
    assert steps == sorted(steps)
    assert files == sorted(files)


def test_starting_tier_by_complexity_and_role():
    assert starting_tier("low") is Tier.JUNIOR
    assert starting_tier("medium") is Tier.MIDLEVEL
    assert starting_tier("high") is Tier.SENIOR
    # Read-only recon is cheap; security is never cheap.
    assert starting_tier("high", "scout") is Tier.INTERN
    assert starting_tier("low", "security") is Tier.SENIOR


def test_resolve_runtime_keeps_role_routing_intact():
    """Tier steers cost within the role's list; it never re-routes the role.

    Regression guard: deriving the runtime from the tier alone would have moved
    every dev subtask off claude_code, a routing change nobody asked for.
    """
    prefs = {
        "dev": ["claude_code", "hermes", "internal_agent"],
        "scout": ["internal_agent"],
        "optimizer": ["goose", "aider"],
    }
    assert resolve_runtime("dev", Tier.MIDLEVEL, prefs) == "claude_code"
    assert resolve_runtime("dev", Tier.SENIOR, prefs) == "claude_code"
    assert resolve_runtime("dev", Tier.INTERN, prefs) == "internal_agent"
    assert resolve_runtime("scout", Tier.INTERN, prefs) == "internal_agent"
    # A role with no internal_agent option falls back to its cheapest entry.
    assert resolve_runtime("optimizer", Tier.JUNIOR, prefs) == "aider"
    # An unknown role borrows the dev list rather than failing.
    assert resolve_runtime("unknown", Tier.SENIOR, prefs) == "claude_code"


# ── Subtask brief ─────────────────────────────────────────────────────────────


def test_brief_contains_every_required_section():
    brief = build_subtask_brief(_plan(), goal="Ship provider health checks")
    for heading in (
        "# Context", "# Scope", "# Focus", "# Outcome",
        "# Completion", "# Instruction Priority", "# Mode Restriction",
    ):
        assert heading in brief, f"brief is missing {heading}"


def test_brief_carries_goal_scope_and_tier_remit():
    plan = _plan(tier=Tier.INTERN)
    brief = build_subtask_brief(plan, goal="Ship provider health checks")
    assert "Ship provider health checks" in brief
    assert "Add a health() method to ProviderX." in brief
    # The tier's remit tells the executing agent how much latitude it has.
    assert tier_profile(Tier.INTERN).remit[:40] in brief


def test_brief_includes_upstream_results():
    brief = build_subtask_brief(
        _plan(),
        goal="Ship health checks",
        upstream=[("st-0", "ProviderX lives in providers/x.py and has no health method")],
    )
    assert "st-0" in brief
    assert "providers/x.py" in brief


def test_brief_records_previous_failure_on_escalation():
    brief = build_subtask_brief(
        _plan(tier=Tier.SENIOR),
        goal="Ship health checks",
        previous_failure="claimed success but changed no files",
    )
    assert "# Previous Attempt Failed" in brief
    assert "changed no files" in brief


def test_brief_omits_failure_section_on_first_attempt():
    brief = build_subtask_brief(_plan(), goal="g")
    assert "# Previous Attempt Failed" not in brief


# ── Decomposition ─────────────────────────────────────────────────────────────


def test_fallback_decomposition_is_recon_then_implement():
    plans = fallback_decomposition("Refactor the auth layer", complexity="medium")
    assert len(plans) == 2
    scout, dev = plans
    assert scout.role == "scout"
    assert scout.writes_code is False
    assert dev.role == "dev"
    assert dev.dependencies == [scout.subtask_id]


def test_extract_json_object_handles_fences_and_prose():
    assert _extract_json_object('{"subtasks": []}') == {"subtasks": []}
    assert _extract_json_object('```json\n{"subtasks": []}\n```') == {"subtasks": []}
    assert _extract_json_object('Here you go:\n{"subtasks": [], "x": 1}\nDone.') == {
        "subtasks": [], "x": 1
    }
    assert _extract_json_object("no json here") is None
    assert _extract_json_object("") is None


@pytest.mark.asyncio
async def test_decompose_falls_back_when_llm_disabled():
    config = MicroManagerConfig(llm_decomposition=False)
    plans, strategy = await decompose("Do the thing", config=config)
    assert strategy == "fallback"
    assert len(plans) == 2


@pytest.mark.asyncio
async def test_decompose_uses_llm_split_when_available(monkeypatch):
    async def _fake_call_llm(messages, **kwargs):
        return (
            '{"subtasks": ['
            '{"title": "Find the router", "scope": "Locate the routing table.",'
            ' "outcome": "File named.", "role": "scout", "tier": "intern",'
            ' "files": ["router/x.py"], "depends_on": [], "writes_code": false},'
            '{"title": "Add the route", "scope": "Add the /health route.",'
            ' "outcome": "Route returns 200.", "role": "dev", "tier": "midlevel",'
            ' "files": ["router/x.py"], "depends_on": [0], "writes_code": true}'
            ']}'
        )

    import backend.server
    monkeypatch.setattr(backend.server, "call_llm", _fake_call_llm)

    config = MicroManagerConfig(llm_decomposition=True)
    plans, strategy = await decompose("Add a health route", config=config)

    assert strategy == "llm"
    assert [p.title for p in plans] == ["Find the router", "Add the route"]
    assert plans[0].tier is Tier.INTERN
    assert plans[1].tier is Tier.MIDLEVEL
    # depends_on indices are resolved to the generated subtask ids.
    assert plans[1].dependencies == [plans[0].subtask_id]
    assert plans[0].writes_code is False


@pytest.mark.asyncio
async def test_decompose_falls_back_when_llm_returns_garbage(monkeypatch):
    async def _fake_call_llm(messages, **kwargs):
        return "I'm afraid I can't do that."

    import backend.server
    monkeypatch.setattr(backend.server, "call_llm", _fake_call_llm)

    plans, strategy = await decompose(
        "Add a health route", config=MicroManagerConfig(llm_decomposition=True)
    )
    assert strategy == "fallback"
    assert len(plans) == 2


@pytest.mark.asyncio
async def test_decompose_falls_back_when_llm_raises(monkeypatch):
    async def _boom(messages, **kwargs):
        raise RuntimeError("provider down")

    import backend.server
    monkeypatch.setattr(backend.server, "call_llm", _boom)

    plans, strategy = await decompose(
        "Anything", config=MicroManagerConfig(llm_decomposition=True)
    )
    assert strategy == "fallback"
    assert plans


@pytest.mark.asyncio
async def test_decompose_respects_max_subtasks(monkeypatch):
    many = ",".join(
        f'{{"title": "t{i}", "scope": "s{i}", "outcome": "o{i}", "tier": "junior"}}'
        for i in range(20)
    )

    async def _fake_call_llm(messages, **kwargs):
        return '{"subtasks": [' + many + "]}"

    import backend.server
    monkeypatch.setattr(backend.server, "call_llm", _fake_call_llm)

    config = MicroManagerConfig(llm_decomposition=True, max_subtasks=3)
    plans, strategy = await decompose("Big job", config=config)
    assert strategy == "llm"
    assert len(plans) == 3


@pytest.mark.asyncio
async def test_decompose_drops_subtasks_with_no_scope(monkeypatch):
    """A scopeless subtask would be delegated as an empty instruction."""
    async def _fake_call_llm(messages, **kwargs):
        return (
            '{"subtasks": ['
            '{"title": "empty", "scope": "", "outcome": "x"},'
            '{"title": "real", "scope": "Do the real thing.", "outcome": "y"}'
            ']}'
        )

    import backend.server
    monkeypatch.setattr(backend.server, "call_llm", _fake_call_llm)

    plans, _ = await decompose("x", config=MicroManagerConfig(llm_decomposition=True))
    assert [p.title for p in plans] == ["real"]


# ── Anti-slop quality gate ────────────────────────────────────────────────────


def test_good_result_is_accepted():
    verdict = assess_quality(_plan(), _ok_result())
    assert verdict.accepted is True
    assert verdict.score == 1.0


def test_failed_execution_is_rejected():
    verdict = assess_quality(_plan(), {"status": "error", "error": "runtime down"})
    assert verdict.accepted is False
    assert "runtime down" in verdict.reasons[0]


def test_empty_summary_is_rejected():
    verdict = assess_quality(_plan(), _ok_result(summary="   "))
    assert verdict.accepted is False
    assert verdict.reasons == ["no summary reported"]


def test_give_up_message_is_rejected():
    verdict = assess_quality(
        _plan(), _ok_result(summary="I am unable to complete this task without more context.")
    )
    assert verdict.accepted is False
    assert any("did not complete" in r for r in verdict.reasons)


def test_give_up_marker_later_in_an_honest_report_does_not_reject():
    """An honest report that *mentions* a failure is not itself a failure."""
    summary = (
        "Added the health() method to ProviderX and a regression test. "
        "Note for the reviewer: the legacy shim still logs 'unable to complete' "
        "on timeout, which I left alone as it is out of scope."
    )
    verdict = assess_quality(_plan(), _ok_result(summary=summary))
    assert verdict.accepted is True


def test_claimed_success_with_no_file_changes_is_rejected():
    """The strongest slop signal: said done, changed nothing, on a runtime that reports."""
    verdict = assess_quality(
        _plan(writes_code=True),
        _ok_result(changed_files=[], files_reported=True),
    )
    assert verdict.accepted is False
    assert any("changed no files" in r for r in verdict.reasons)


def test_no_file_changes_is_not_held_against_a_runtime_that_cannot_report():
    """Hermes and claude_code return prose only — they must not be auto-rejected."""
    verdict = assess_quality(
        _plan(writes_code=True),
        _ok_result(changed_files=[], files_reported=False),
    )
    assert verdict.accepted is True
    assert any("does not report changed files" in r for r in verdict.reasons)


def test_research_subtask_is_not_expected_to_change_files():
    verdict = assess_quality(
        _plan(writes_code=False),
        _ok_result(changed_files=[], files_reported=True),
    )
    assert verdict.accepted is True


def test_code_change_without_tests_is_penalised_but_not_fatal():
    verdict = assess_quality(_plan(), _ok_result(changed_files=["providers/x.py"]))
    assert any("no test file" in r for r in verdict.reasons)
    assert verdict.accepted is True  # a warning, not a hard reject
    assert verdict.score < 1.0


def test_test_requirement_can_be_disabled():
    config = MicroManagerConfig(require_tests_for_code=False)
    verdict = assess_quality(_plan(), _ok_result(changed_files=["providers/x.py"]), config=config)
    assert verdict.reasons == []


def test_short_summary_is_penalised():
    verdict = assess_quality(_plan(), _ok_result(summary="done"))
    assert any("too short" in r for r in verdict.reasons)


def test_soft_penalties_never_combine_into_a_rejection():
    """Two documented warnings must not silently become an error.

    Under the previous 0.5 numeric threshold, a terse summary (-0.3) plus a
    missing test (-0.3) landed on 0.4 and rejected — escalating a
    correct-but-brief change through the whole tier ladder even though each
    signal alone is specified as a warning. Acceptance is categorical now.
    """
    verdict = assess_quality(
        _plan(), _ok_result(summary="Added it.", changed_files=["providers/x.py"])
    )
    assert len(verdict.reasons) >= 2, "both soft penalties should be recorded"
    assert verdict.accepted is True
    assert verdict.score < 0.5, "the score still reflects the warnings"


def test_hard_reject_still_wins_over_a_perfect_score():
    verdict = assess_quality(
        _plan(writes_code=True),
        _ok_result(changed_files=[], files_reported=True),
    )
    assert verdict.accepted is False


def test_touched_tests_recognises_common_layouts():
    assert touched_tests(["tests/test_x.py"])
    assert touched_tests(["backend/test_server.py"])
    assert touched_tests(["frontend/src/__tests__/App.test.js"])
    assert touched_tests(["frontend/src/App.test.jsx"])
    assert not touched_tests(["providers/x.py", "docs/changelog.md"])
    assert not touched_tests([])


# ── Escalation ────────────────────────────────────────────────────────────────


def test_accepted_result_does_not_escalate():
    verdict = assess_quality(_plan(), _ok_result())
    decision = decide_escalation(_plan(), verdict, attempts_used=1)
    assert decision.should_retry is False


def test_rejected_result_escalates_one_rung():
    plan = _plan(tier=Tier.JUNIOR)
    verdict = assess_quality(plan, {"status": "error", "error": "boom"})
    decision = decide_escalation(plan, verdict, attempts_used=1)
    assert decision.should_retry is True
    assert decision.tier is Tier.MIDLEVEL
    assert "junior → midlevel" in decision.reason


def test_escalation_stops_at_the_top_of_the_ladder():
    plan = _plan(tier=Tier.SENIOR)
    verdict = assess_quality(plan, {"status": "error", "error": "boom"})
    decision = decide_escalation(plan, verdict, attempts_used=1)
    assert decision.should_retry is False
    assert "top of the tier ladder" in decision.reason


def test_escalation_stops_when_the_attempt_budget_is_spent():
    plan = _plan(tier=Tier.INTERN)
    verdict = assess_quality(plan, {"status": "error", "error": "boom"})
    config = MicroManagerConfig(max_attempts_per_subtask=2)
    assert decide_escalation(plan, verdict, attempts_used=1, config=config).should_retry is True
    assert decide_escalation(plan, verdict, attempts_used=2, config=config).should_retry is False


def test_escalation_can_be_switched_off_entirely():
    plan = _plan(tier=Tier.INTERN)
    verdict = assess_quality(plan, {"status": "error", "error": "boom"})
    config = MicroManagerConfig(escalation_enabled=False)
    decision = decide_escalation(plan, verdict, attempts_used=1, config=config)
    assert decision.should_retry is False
    assert decision.reason == "escalation disabled"


def test_attempt_budget_cannot_exceed_the_ladder_length(monkeypatch):
    """Env misconfiguration must not be able to uncap retries."""
    monkeypatch.setenv("CEO_MAX_ATTEMPTS_PER_SUBTASK", "999")
    assert MicroManagerConfig.from_env().max_attempts_per_subtask == len(TIER_LADDER)


def test_config_clamps_and_survives_garbage_env(monkeypatch):
    monkeypatch.setenv("CEO_MAX_SUBTASKS", "not-a-number")
    monkeypatch.setenv("CEO_MIN_OUTPUT_CHARS", "-5")
    config = MicroManagerConfig.from_env()
    assert config.max_subtasks == 6
    assert config.min_output_chars == 0
