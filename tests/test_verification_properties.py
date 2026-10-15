"""Property and differential tests for the verification decision.

Inputs come from a seeded generator (stdlib ``random``) rather than a property
library, so no new dependency; every failure message names its seed, and
``_run_for(seed)`` reproduces the input exactly. There is no automatic
shrinking: a counterexample found here is minimised by hand and kept as a
named regression test in tests/test_verification_evidence.py (as was done for
``test_check_superseded_by_a_fresh_pass_is_not_a_finding``).
"""
from __future__ import annotations

import random
from typing import Any

import pytest

from agent.models import AgentPlan, AgentStep
from agent.verification_contract import (
    AcceptanceCriterion,
    VerificationContract,
    amend_contract,
    build_contract,
)
from agent.verification_evidence import CheckResult, EvidenceReport, build_report
from packages.config import settings
from tasks import verification as tv
from tasks.models import Task, TaskStatus

SEEDS = range(400)
_FILES = ["calc.py", "util.py", "docs/notes.md", "frontend/src/App.jsx", "key_store.py"]
_STATUSES = ["passed", "passed", "passed", "failed", "not_run", "unavailable", "timed_out", "untrusted"]
_JUDGES = [{"verdict": "APPROVED"}, {"verdict": "APPROVED_WITH_CONDITIONS"}, {"verdict": "REJECTED"},
           {"verdict": "BLOCKED"}, {}]


def _run_for(seed: int) -> tuple[VerificationContract, list[dict[str, Any]], dict[str, Any], bool]:
    rng = random.Random(seed)
    clean = rng.random() < 0.4  # mostly-green runs, so VERIFIED is actually exercised
    n = rng.randint(1, 4)
    plan_steps, steps = [], []
    for sid in range(1, n + 1):
        files = rng.sample(_FILES, rng.randint(1, 2))
        plan_steps.append(AgentStep(id=sid, description=f"s{sid}", files=files, type="edit"))
        fp = rng.choice(["h1", "h2"])
        statuses = ["passed"] * 12 + ["not_run"] if clean else _STATUSES
        kinds = ["static", "unit"] if clean else rng.sample(["static", "unit"], rng.randint(0, 2))
        checks = [CheckResult(check_id=f"{k}:{sid}", strategy=k, status=rng.choice(statuses), step_id=sid,
                              files=files, fingerprints={f: fp if clean else rng.choice([fp, fp, "h0"]) for f in files},
                              reason="" if clean else rng.choice(["", "flaky: x", "stale: x"])).model_dump()
                  for k in kinds]
        steps.append({"step_id": sid, "description": f"s{sid}", "changed_files": files,
                      "status": "applied" if clean else rng.choice(["applied", "applied", "failed"]),
                      "failure_phase": rng.choice(["empirical_verification", "verification", None]),
                      "check_results": checks, "file_fingerprints": {f: fp for f in files},
                      "executed_checks": ["pytest"] if rng.random() < 0.7 else []})
    contract = build_contract(AgentPlan(goal="g", steps=plan_steps), session_id="s")
    if clean:
        return contract, steps, rng.choice(_JUDGES[:2] * 4 + _JUDGES), False
    ran = steps[: rng.randint(max(1, n - 1), n)]
    return contract, ran, rng.choice(_JUDGES), rng.random() < 0.1


@pytest.fixture(autouse=True)
def _policy_on(monkeypatch):
    monkeypatch.setattr(settings, "verification_policy_enforced_raw", "true")
    monkeypatch.setattr(settings, "task_verification_required_raw", "true")
    monkeypatch.setattr(settings, "agent_ui_evidence_raw", "true")


def test_property_verified_implies_complete_trustworthy_evidence():
    for seed in SEEDS:
        contract, steps, judge, cut = _run_for(seed)
        report = build_report(contract, steps=steps, judge=judge, time_budget_exceeded=cut)
        if report.verdict != "VERIFIED":
            continue
        ctx = f"seed={seed}"
        assert not cut and len(steps) == len(contract.criteria) - 1, ctx
        assert str(judge.get("verdict", "")).startswith("APPROVED"), ctx
        assert all(s["status"] == "applied" for s in steps), ctx
        assert not [c for c in report.checks if c.status in {"failed", "timed_out", "unavailable"}], ctx
        for step in steps:
            if any(f.endswith(".py") for f in step["changed_files"]):
                for strategy in ("static", "unit"):
                    assert any(c.strategy == strategy and c.status == "passed" for c in report.checks), ctx


def test_property_a_failing_check_never_verifies():
    for seed in SEEDS:
        contract, steps, judge, cut = _run_for(seed)
        target = next((c for s in steps for c in s["check_results"]), None)
        if target is None:
            continue
        target["status"] = "failed"
        report = build_report(contract, steps=steps, judge=judge, time_budget_exceeded=cut)
        assert report.verdict == "FAILED", f"seed={seed}"


def test_property_decision_is_deterministic():
    for seed in SEEDS:
        contract, steps, judge, cut = _run_for(seed)
        a = build_report(contract, steps=steps, judge=judge, time_budget_exceeded=cut)
        b = build_report(contract, steps=steps, judge=judge, time_budget_exceeded=cut)
        assert (a.verdict, a.reasons, a.requires_human_approval) == (b.verdict, b.reasons, b.requires_human_approval)


def test_property_report_and_contract_round_trip():
    for seed in SEEDS:
        contract, steps, judge, cut = _run_for(seed)
        report = build_report(contract, steps=steps, judge=judge, time_budget_exceeded=cut)
        assert EvidenceReport.model_validate(report.model_dump()) == report, f"seed={seed}"
        assert VerificationContract.model_validate(contract.model_dump()).fingerprint() == contract.fingerprint()


def test_differential_evidence_policy_is_never_looser_than_the_legacy_rule():
    """Differential: the pre-existing judge+executed_checks rule is the oracle for
    permissiveness. The new gate may withhold or fail what it passed, never pass
    what it withheld or failed."""
    for seed in SEEDS:
        contract, steps, judge, cut = _run_for(seed)
        report = build_report(contract, steps=steps, judge=judge, time_budget_exceeded=cut)
        raw = {"judge": judge, "steps": steps, "verification_contract": contract.model_dump(),
               "verification_report": report.model_dump()}
        legacy, new = tv._judge_report(raw), tv.verification_from_run(raw)
        if new is not None and new.passed:
            assert legacy is not None and legacy.passed, f"seed={seed}: looser than legacy"
            assert report.verdict == "VERIFIED", f"seed={seed}"
        if report.verdict == "FAILED":
            assert new is not None and new.verdict == "FAIL", f"seed={seed}"


def test_property_secrets_never_reach_the_report():
    rng = random.Random(7)
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    for i in range(200):
        token = "ghp_" + "".join(rng.choice(alphabet) for _ in range(36))
        noise = "".join(rng.choice(alphabet + " \n:=") for _ in range(rng.randint(0, 80)))
        text = rng.choice([f"{noise} {token}", f"Authorization: Bearer {token}", f"token={token} {noise}"])
        check = CheckResult(check_id="unit:x", strategy="unit", status="failed", output_tail=text,
                            command=text, reason=text, step_id=1, files=["calc.py"]).model_dump()
        contract = build_contract(AgentPlan(goal="g", steps=[AgentStep(id=1, description="s", files=["calc.py"], type="edit")]))
        step = {"step_id": 1, "status": "failed", "changed_files": ["calc.py"], "issues": [text],
                "description": "s", "check_results": [check], "file_fingerprints": {}}
        dumped = str(build_report(contract, steps=[step], judge={"verdict": "APPROVED", "notes": text}).model_dump())
        assert token not in dumped, f"case {i}"


def test_property_rework_budget_is_never_exceeded():
    for seed in range(50):
        rng = random.Random(seed)
        task = Task(owner_id="o", title="t", status=TaskStatus.IN_PROGRESS)
        reworks = 0
        for _ in range(rng.randint(1, 8)):
            task.verification = tv.TaskVerification(verdict="FAIL", verifier="verifier:evidence",
                                                    defects_found=["[implementation_defect] x"])
            status, _, _ = tv.rework_or_park(task, "runtime:internal_agent")
            if status == TaskStatus.IN_PROGRESS:
                reworks += 1
            else:
                break
        assert reworks <= tv.MAX_AUTO_REWORK, f"seed={seed}"


def test_property_no_machine_actor_can_amend_criteria():
    contract = build_contract(AgentPlan(goal="g", steps=[AgentStep(id=1, description="s", files=["a.py"], type="edit")]))
    rng = random.Random(11)
    prefixes = ["agent:", "runtime:", "system:", "verifier:", "judge:", "ceo:", "workflow:", "service:"]
    for _ in range(100):
        actor = rng.choice(prefixes) + "".join(rng.choice("abcxyz-_") for _ in range(rng.randint(1, 10)))
        with pytest.raises(PermissionError):
            amend_contract(contract, actor=actor, reason="r",
                           criteria=[AcceptanceCriterion(criterion_id="goal", description="d", source="goal")])
