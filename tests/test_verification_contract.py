"""Tests for agent/verification_contract.py — the contract a run is held to."""
from __future__ import annotations

import pytest

from agent.models import AgentPlan, AgentStep
from agent.verification_contract import (
    AcceptanceCriterion,
    VerificationContract,
    amend_contract,
    build_contract,
    classify_risk,
    select_strategies,
    stricter,
)


def _plan(files: list[str], *, goal: str = "Fix the adder", acceptance: str = "", risky: bool = False) -> AgentPlan:
    return AgentPlan(goal=goal, steps=[
        AgentStep(id=1, description="Edit the module", files=files, type="edit", acceptance=acceptance, risky=risky),
    ])


@pytest.mark.parametrize("paths,tier", [
    (["docs/guide.md"], "low"),
    (["README.md", "notes.txt"], "low"),
    (["services/billing.py"], "medium"),
    ([], "medium"),
    (["packages/auth/rbac.py"], "high"),
    (["key_store.py"], "high"),
    (["governance/policy.py"], "high"),
    (["deploy/render.sh"], "high"),
    (["docs/guide.md", "agent/tools.py"], "high"),
    ([".github/workflows/ci.yml"], "high"),
])
def test_classify_risk_from_paths(paths, tier):
    assert classify_risk(paths)[0] == tier


def test_stricter_tier_wins():
    assert stricter("low", "high") == "high"
    assert stricter("medium", "low") == "medium"


def test_python_change_requires_static_and_unit_and_review():
    strategies = {s.name: s for s in select_strategies("medium", ["services/calc.py"], "Fix calc")}
    assert strategies["static"].mandatory and strategies["unit"].mandatory
    assert strategies["independent_review"].mandatory
    assert "human_approval" not in strategies


def test_high_risk_requires_human_approval():
    names = {s.name: s.mandatory for s in select_strategies("high", ["key_store.py"])}
    assert names["human_approval"] is True


def test_low_risk_unit_is_advisory_and_ui_is_mandatory_for_frontend():
    low = {s.name: s.mandatory for s in select_strategies("low", ["scripts/tool.py"])}
    assert low["unit"] is False and low["static"] is True
    ui = {s.name: s.mandatory for s in select_strategies("medium", ["frontend/src/App.jsx"])}
    assert ui["ui"] is True


def test_refactor_goal_recommends_differential_but_does_not_require_it():
    picks = {s.name: s.mandatory for s in select_strategies("medium", ["a.py"], "Refactor the parser")}
    assert picks["differential"] is False and picks["property"] is False


def test_build_contract_records_criteria_and_conservative_assumption():
    contract = build_contract(_plan(["calc.py"]), session_id="s1", time_budget_s=60)
    ids = [c.criterion_id for c in contract.criteria]
    assert ids == ["step-1", "goal"]
    assert contract.criteria[0].required_strategies == ["static", "unit"]
    assert any("no acceptance test" in a for a in contract.assumptions)
    assert contract.session_id == "s1" and contract.time_budget_s == 60


def test_planner_acceptance_text_becomes_the_criterion():
    contract = build_contract(_plan(["calc.py"], acceptance="add(2, 3) returns 5"))
    assert contract.criteria[0].description == "add(2, 3) returns 5"
    assert not contract.assumptions


def test_planner_risky_flag_raises_tier_even_for_innocent_paths():
    assert build_contract(_plan(["calc.py"], risky=True)).risk_tier == "high"


def test_fingerprint_is_stable_and_changes_with_criteria():
    contract = build_contract(_plan(["calc.py"]))
    clone = VerificationContract.model_validate(contract.model_dump())
    assert clone.fingerprint() == contract.fingerprint()
    changed = contract.model_copy(update={"criteria": contract.criteria[:1]})
    assert changed.fingerprint() != contract.fingerprint()


def test_agent_cannot_amend_criteria():
    contract = build_contract(_plan(["calc.py"]))
    weaker = [AcceptanceCriterion(criterion_id="goal", description="anything", source="goal")]
    for actor in ("agent:dev", "runtime:internal_agent", "judge", "verifier:evidence", "system"):
        with pytest.raises(PermissionError):
            amend_contract(contract, actor=actor, reason="tests keep failing", criteria=weaker)


def test_person_amendment_is_versioned_and_recorded():
    contract = build_contract(_plan(["calc.py"]))
    new = [AcceptanceCriterion(criterion_id="goal", description="add handles ints only", source="goal")]
    amended = amend_contract(contract, actor="owner@example.com", reason="scope narrowed", criteria=new)
    assert amended.version == 2 and amended.amendments[-1].actor == "owner@example.com"
    assert amended.fingerprint() != contract.fingerprint()
    assert contract.version == 1  # the original is untouched
    with pytest.raises(ValueError):
        amend_contract(contract, actor="owner@example.com", reason="  ", criteria=new)
