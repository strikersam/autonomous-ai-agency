"""Tests for agent/verification_evidence.py and its gate in tasks/verification.py.

Each test names the scenario from the verification brief it covers. Step
dicts mirror what ``AgentRunner._execute_step`` returns (see
tests/test_verification_lifecycle_integration.py for the real loop).
"""
from __future__ import annotations

from typing import Any

import pytest

from agent.models import AgentPlan, AgentStep
from agent.verification_contract import build_contract
from agent.verification_evidence import (
    CheckResult,
    EvidenceReport,
    build_report,
    check_binding,
)
from packages.config import settings
from tasks import verification as tv
from tasks.models import Task, TaskStatus

APPROVED = {"verdict": "APPROVED", "security": "PASS", "correctness": "PASS", "notes": "looks right"}


def _contract(files: list[str] | None = None, steps: int = 1):
    files = files or ["calc.py"]
    return build_contract(AgentPlan(goal="Fix add", steps=[
        AgentStep(id=i, description=f"step {i}", files=files, type="edit") for i in range(1, steps + 1)
    ]), session_id="sess")


def _check(strategy: str, status: str, files: list[str], fp: str = "h1", sid: int = 1, **kw: Any) -> dict:
    return CheckResult(check_id=f"{strategy}:x", strategy=strategy, status=status, files=files,
                       fingerprints={f: fp for f in files}, step_id=sid, **kw).model_dump()


def _step(sid: int = 1, status: str = "applied", files=("calc.py",), checks=None, fp: str = "h1", **kw):
    files = list(files)
    if checks is None:
        checks = [_check("static", "passed", files, fp, sid), _check("unit", "passed", files, fp, sid)]
    return {"step_id": sid, "description": f"step {sid}", "status": status, "changed_files": files,
            "check_results": checks, "file_fingerprints": {f: fp for f in files},
            "executed_checks": [f"pytest -x tests/test_calc.py: passed"] if status == "applied" else [], **kw}


def _raw(contract, steps, judge=APPROVED, **kw) -> dict:
    report = build_report(contract, steps=steps, judge=judge, **kw)
    return {"judge": judge, "steps": steps, "verification_contract": contract.model_dump(),
            "verification_report": report.model_dump()}


@pytest.fixture(autouse=True)
def _policy_on(monkeypatch):
    monkeypatch.setattr(settings, "verification_policy_enforced_raw", "true")
    monkeypatch.setattr(settings, "task_verification_required_raw", "true")


# 1. A valid implementation passes and produces evidence.
def test_valid_run_is_verified_with_mapped_criteria():
    report = build_report(_contract(), steps=[_step()], judge=APPROVED, source_revision="abc123")
    assert report.verdict == "VERIFIED"
    assert {c.criterion_id: c.status for c in report.criteria} == {"step-1": "passed", "goal": "passed"}
    assert report.source_revision == "abc123" and report.file_fingerprints == {"calc.py": "h1"}
    assert len(report.checks) == 2 and not report.findings


# 2 + 8. A failing check is an actionable, classified defect.
def test_failed_check_fails_with_actionable_defect_and_regression_candidate():
    checks = [_check("static", "passed", ["calc.py"]),
              _check("unit", "failed", ["calc.py"], output_tail="assert 6 == 5", exit_code=1)]
    report = build_report(_contract(), steps=[_step(status="failed", checks=checks,
                                                    failure_phase="empirical_verification",
                                                    issues=["Scoped tests failed"])], judge=APPROVED)
    assert report.verdict == "FAILED"
    assert any("assert 6 == 5" in d for d in report.defects())
    assert report.regression_candidates


# 3. Claiming success is not evidence.
def test_approval_without_any_executed_check_is_not_verified():
    checks = [_check("static", "not_run", ["calc.py"], reason="AGENT_EMPIRICAL_VERIFY is off"),
              _check("unit", "not_run", ["calc.py"], reason="AGENT_EMPIRICAL_VERIFY is off")]
    report = build_report(_contract(), steps=[_step(checks=checks)], judge=APPROVED)
    assert report.verdict == "INCONCLUSIVE"
    assert any("AGENT_EMPIRICAL_VERIFY is off" in g for g in report.not_executed)


# 4. A missing mandatory check prevents a verified verdict.
def test_missing_unit_check_blocks_verified():
    report = build_report(_contract(), steps=[_step(checks=[_check("static", "passed", ["calc.py"])])],
                          judge=APPROVED)
    assert report.verdict == "INCONCLUSIVE"
    assert any("no passing unit check" in f.message for f in report.findings)


# 5. An unavailable or timed-out check is blocked, never a pass.
@pytest.mark.parametrize("status,phase_kind", [("unavailable", "environment"), ("timed_out", "timeout")])
def test_unrunnable_check_is_blocked(status, phase_kind):
    checks = [_check("static", "passed", ["calc.py"]), _check("unit", status, ["calc.py"])]
    step = _step(status="failed", checks=checks, failure_phase="empirical_verification", issues=["x"])
    report = build_report(_contract(), steps=[step], judge=APPROVED)
    assert report.verdict == "BLOCKED"
    assert phase_kind in {f.kind for f in report.findings}


def test_unavailable_check_on_applied_step_is_inconclusive():
    checks = [_check("static", "passed", ["calc.py"]), _check("unit", "unavailable", ["calc.py"])]
    assert build_report(_contract(), steps=[_step(checks=checks)], judge=APPROVED).verdict == "INCONCLUSIVE"


# 6. A flaky test is not proof.
def test_flaky_check_is_not_trusted():
    checks = [_check("static", "passed", ["calc.py"]),
              _check("unit", "untrusted", ["calc.py"], reason="flaky: failed then passed on identical code", attempts=2)]
    step = _step(status="failed", checks=checks, failure_phase="empirical_verification", issues=["flaky"])
    report = build_report(_contract(), steps=[step], judge=APPROVED)
    assert report.verdict == "INCONCLUSIVE"
    assert "flaky" in {f.kind for f in report.findings}


# 9. Changes after verification invalidate the evidence.
def test_check_on_content_that_later_changed_is_stale():
    first = _step(sid=1, fp="h1")
    second = _step(sid=2, fp="h2", checks=[_check("static", "passed", ["calc.py"], "h2", 2)])
    report = build_report(_contract(steps=2), steps=[first, second], judge=APPROVED)
    stale = [c for c in report.checks if c.reason.startswith("stale")]
    assert stale and report.verdict == "INCONCLUSIVE"


def test_check_superseded_by_a_fresh_pass_is_not_a_finding():
    first = _step(sid=1, fp="h1")
    second = _step(sid=2, fp="h2")
    report = build_report(_contract(steps=2), steps=[first, second], judge=APPROVED)
    assert report.verdict == "VERIFIED"
    assert any(c.reason.startswith("superseded") for c in report.checks)


# 10. Independent verification that contradicts the evidence is rejected.
def test_reviewer_approval_contradicted_by_a_failed_step_is_a_failure():
    ok = _step(sid=1)
    bad = _step(sid=2, status="failed", checks=[_check("unit", "failed", ["calc.py"], sid=2)],
                failure_phase="empirical_verification", issues=["1 failed"])
    contract = _contract(steps=2)
    raw = _raw(contract, [ok, bad])
    legacy = tv._judge_report(raw)
    assert legacy is not None and legacy.passed  # the old rule would have passed this
    verdict = tv.verification_from_run(raw)
    assert verdict.verdict == "FAIL" and verdict.verifier == tv.EVIDENCE_VERIFIER
    assert any("contract_violation" in d for d in verdict.defects_found)


def test_rejected_review_fails_even_with_green_checks():
    report = build_report(_contract(), steps=[_step()], judge={"verdict": "REJECTED", "notes": "wrong file"})
    assert report.verdict == "FAILED"


def test_missing_review_is_blocked():
    report = build_report(_contract(), steps=[_step()], judge={})
    assert report.verdict == "BLOCKED"


def test_time_budget_cut_leaves_criteria_unverified():
    report = build_report(_contract(steps=2), steps=[_step()], judge=APPROVED, time_budget_exceeded=True)
    assert report.verdict == "INCONCLUSIVE"
    assert {c.criterion_id: c.status for c in report.criteria}["step-2"] == "unverified"


# 11. High-risk changes keep the human approval gate, out of the autopilot's reach.
def test_verified_high_risk_change_is_held_for_a_person():
    contract = _contract(["packages/auth/rbac.py"])
    raw = _raw(contract, [_step(files=["packages/auth/rbac.py"])])
    assert raw["verification_report"]["verdict"] == "VERIFIED"
    assert raw["verification_report"]["requires_human_approval"] is True
    task = Task(owner_id="o", title="t", status=TaskStatus.IN_PROGRESS)
    tv.settle_success(task, raw, actor="runtime:internal_agent")
    assert task.status == TaskStatus.IN_REVIEW and tv.HIGH_RISK_TAG in task.tags
    assert task.verification.passed  # verified, but verification is not authorization
    from tasks.service import _is_outward_facing
    assert _is_outward_facing(task)  # review autopilot skips risk:* tags


def test_risk_is_reclassified_from_actual_changes():
    contract = _contract(["calc.py"])  # planned as medium
    report = build_report(contract, steps=[_step(files=["key_store.py"])], judge=APPROVED)
    assert report.risk_tier == "high" and report.requires_human_approval


def test_medium_risk_verified_run_completes():
    task = Task(owner_id="o", title="t", status=TaskStatus.IN_PROGRESS)
    tv.settle_success(task, _raw(_contract(), [_step()]), actor="runtime:internal_agent")
    assert task.status == TaskStatus.DONE
    assert any("Evidence report" in e for e in task.verification.evidence)


# 12. Secrets are redacted before persistence.
def test_secrets_in_check_output_are_redacted():
    token = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
    check = CheckResult(check_id="unit:pytest", strategy="unit", status="failed",
                        command=f"pytest --token={token}", output_tail=f"Authorization: Bearer {token}")
    dumped = str(check.model_dump())
    assert token not in dumped


# Binding: a report must match the contract it claims.
def test_report_bound_to_a_different_contract_is_inconclusive():
    raw = _raw(_contract(), [_step()])
    other = _contract(["other.py"])
    assert check_binding(raw["verification_report"], other.model_dump())
    raw["verification_contract"] = other.model_dump()
    assert tv.evidence_decision(raw)[0] == "INCONCLUSIVE"
    assert tv.verification_from_run(raw) is None  # approval withheld
    assert "evidence report is INCONCLUSIVE" in tv.unbacked_note(raw)


def test_evidence_failure_alone_starts_bounded_rework():
    bad = _step(status="failed", checks=[_check("unit", "failed", ["calc.py"])],
                failure_phase="empirical_verification", issues=["1 failed"])
    raw = _raw(_contract(), [bad], judge={"verdict": "APPROVED"})
    task = Task(owner_id="o", title="t", status=TaskStatus.IN_PROGRESS)
    tv.settle_success(task, raw, actor="runtime:internal_agent")
    assert task.verification.verdict == "FAIL"
    assert task.status == TaskStatus.IN_PROGRESS and task.pending_agent_run  # sent back with defects
    assert "Independent verification failed" in task.comments[-1].body


# 14. Compatibility: runs without a report and the off switch keep the old rules.
def test_runs_without_a_report_keep_legacy_behaviour():
    raw = {"judge": APPROVED, "steps": [_step()]}
    new, old = tv.verification_from_run(raw), tv._judge_report(raw)
    assert new.model_dump(exclude={"verified_at"}) == old.model_dump(exclude={"verified_at"})


def test_policy_off_records_but_does_not_enforce(monkeypatch):
    monkeypatch.setattr(settings, "verification_policy_enforced_raw", "false")
    raw = _raw(_contract(), [_step(checks=[_check("static", "passed", ["calc.py"])])])
    assert raw["verification_report"]["verdict"] == "INCONCLUSIVE"
    assert tv.verification_from_run(raw).passed  # legacy judge+executed_checks rule only
    assert tv.approval_reason(_raw(_contract(["key_store.py"]), [_step(files=["key_store.py"])])) is None


def test_report_round_trips():
    report = build_report(_contract(), steps=[_step()], judge=APPROVED)
    assert EvidenceReport.model_validate(report.model_dump()) == report


def test_report_build_failure_fails_closed(monkeypatch, tmp_path):
    """Verification infrastructure failure must never read as success."""
    import asyncio

    from agent import verification_runtime as vr

    def boom(*a, **k):
        raise RuntimeError("bug")

    monkeypatch.setattr(vr, "build_report", boom)
    contract = _contract()
    report = asyncio.run(vr.finalize_verification(
        root=tmp_path, contract=contract, spec_id=None, steps=[_step()], judge=APPROVED,
        ui_evidence=[], commits=[], time_budget_exceeded=False))
    assert report["verdict"] == "INCONCLUSIVE"
    raw = {"judge": APPROVED, "steps": [_step()], "verification_contract": contract.model_dump(),
           "verification_report": report}
    assert tv.evidence_decision(raw)[0] == "INCONCLUSIVE"
    assert tv.verification_from_run(raw) is None  # approval withheld
