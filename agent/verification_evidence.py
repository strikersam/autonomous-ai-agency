"""agent/verification_evidence.py — evidence reports and the verification decision.

Every check the agent loop executes is recorded as a ``CheckResult`` with one of
six statuses, so "passed", "failed", "never ran", "could not run", "timed out"
and "ran but cannot be trusted" are never collapsed into each other. At the end
of a run ``build_report`` folds those results, the step outcomes and the
independent reviewer's verdict into an ``EvidenceReport`` against the run's
``VerificationContract`` and makes one decision:

* ``VERIFIED``     every step applied, every mandatory check passed on the final
  content of the files it covered, and the reviewer approved;
* ``FAILED``       the work is wrong: a step or check failed, the reviewer
  rejected it, or the reviewer approved work the evidence shows is broken;
* ``BLOCKED``      the checks could not produce a result (environment, timeout,
  reviewer unavailable) — not the agent's fault, not a pass either;
* ``INCONCLUSIVE`` something required is missing, stale or untrustworthy.

The decision is pure and deterministic: the same inputs give the same verdict,
and nothing an agent writes in prose can change it. ``tasks/verification.py``
consults it so a reviewer's approval can never be stronger than the evidence.
Strings are redacted (``packages/security/redact.py``) before they are stored.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from agent.verification_contract import VerificationContract, classify_risk, stricter

REPORT_SCHEMA_VERSION = 1

CheckStatus = Literal["passed", "failed", "not_run", "unavailable", "timed_out", "untrusted"]
FailureClass = Literal[
    "implementation_defect", "contract_violation", "environment", "timeout",
    "verifier_infrastructure", "flaky", "stale_evidence", "incomplete",
]
FinalVerdict = Literal["VERIFIED", "FAILED", "BLOCKED", "INCONCLUSIVE"]

_FAILING = frozenset({"implementation_defect", "contract_violation"})
_BLOCKING = frozenset({"environment", "timeout", "verifier_infrastructure"})
_MAX_TEXT = 2000


def _redact(text: Any, limit: int = _MAX_TEXT) -> str:
    """Redact, then keep the tail (output: the failure is at the end)."""
    from packages.security.redact import redact_secrets

    return redact_secrets(str(text or ""))[-limit:]


def _clean(text: Any, limit: int) -> str:
    """Redact, then keep the head. Redacting first means a secret cut in half
    by the limit is still recognised and removed."""
    from packages.security.redact import redact_secrets

    return redact_secrets(str(text or ""))[:limit]


def _clean_list(v: Any) -> list[str]:
    return [_clean(x, 600) for x in list(v or [])[:200]]


def _clean_keys(v: Any) -> dict[str, str]:
    return {_clean(k, 600): _clean(val, 64) for k, val in dict(v or {}).items()}


def _is_py(path: Any) -> bool:
    return str(path).lower().endswith(".py")


def fingerprint_content(content: str) -> str:
    """Short content hash; evidence is bound to the bytes it checked."""
    return hashlib.sha256((content or "").encode("utf-8", "replace")).hexdigest()[:16]


class CheckResult(BaseModel):
    """One executed (or deliberately not executed) check, as observed."""

    check_id: str
    strategy: str
    status: CheckStatus
    command: str = ""
    exit_code: int | None = None
    step_id: int | None = None
    files: list[str] = Field(default_factory=list)
    fingerprints: dict[str, str] = Field(default_factory=dict)
    started_at: float = Field(default_factory=time.time)
    duration_s: float = 0.0
    output_tail: str = ""
    reason: str = ""
    attempts: int = 1

    @field_validator("command", "reason", mode="before")
    @classmethod
    def _short(cls, v: Any) -> str:
        return _redact(v, 600)

    @field_validator("check_id", "strategy", mode="before")
    @classmethod
    def _ident(cls, v: Any) -> str:
        return _clean(v, 300)

    @field_validator("files", mode="before")
    @classmethod
    def _paths(cls, v: Any) -> list[str]:
        return _clean_list(v)

    @field_validator("fingerprints", mode="before")
    @classmethod
    def _prints(cls, v: Any) -> dict[str, str]:
        return _clean_keys(v)

    @field_validator("output_tail", mode="before")
    @classmethod
    def _tail(cls, v: Any) -> str:
        return _redact(v)


class Finding(BaseModel):
    """A classified, actionable problem the next attempt (or a person) must address."""

    kind: FailureClass
    message: str
    criterion_id: str | None = None
    check_id: str | None = None

    @field_validator("message", mode="before")
    @classmethod
    def _msg(cls, v: Any) -> str:
        return _clean(v, 800)

    @field_validator("criterion_id", "check_id", mode="before")
    @classmethod
    def _ident(cls, v: Any) -> str | None:
        return None if v is None else _clean(v, 300)


class CriterionResult(BaseModel):
    criterion_id: str
    status: Literal["passed", "failed", "unverified"]
    check_ids: list[str] = Field(default_factory=list)
    note: str = ""

    @field_validator("check_ids", mode="before")
    @classmethod
    def _ids(cls, v: Any) -> list[str]:
        return _clean_list(v)


class EvidenceReport(BaseModel):
    """The persisted record of what was verified, how, and the decision."""

    schema_version: int = REPORT_SCHEMA_VERSION
    report_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    contract_id: str
    contract_version: int
    contract_fingerprint: str
    session_id: str | None = None
    source_revision: str | None = None
    commits: list[str] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)
    file_fingerprints: dict[str, str] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    risk_tier: str = "medium"
    checks: list[CheckResult] = Field(default_factory=list)
    criteria: list[CriterionResult] = Field(default_factory=list)
    judge: dict[str, str] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)
    not_executed: list[str] = Field(default_factory=list)
    corrections: list[str] = Field(default_factory=list)
    regression_candidates: list[str] = Field(default_factory=list)
    remaining_risks: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    models_used: list[str] = Field(default_factory=list)
    verdict: FinalVerdict = "INCONCLUSIVE"
    reasons: list[str] = Field(default_factory=list)
    requires_human_approval: bool = False

    @field_validator("not_executed", "corrections", "regression_candidates", "remaining_risks",
                     "limitations", "reasons", mode="before")
    @classmethod
    def _lines(cls, v: Any) -> list[str]:
        return [_clean(x, 600) for x in list(v or [])[:60]]

    @field_validator("commits", "changed_files", "models_used", mode="before")
    @classmethod
    def _idents(cls, v: Any) -> list[str]:
        return _clean_list(v)

    @field_validator("file_fingerprints", mode="before")
    @classmethod
    def _prints(cls, v: Any) -> dict[str, str]:
        return _clean_keys(v)

    def defects(self) -> list[str]:
        """Actionable lines for the agent that has to fix the work."""
        return [f"[{f.kind}] {f.message}" for f in self.findings]


# ── collection ────────────────────────────────────────────────────────────────

def _collect_checks(steps: list[dict[str, Any]]) -> list[CheckResult]:
    out: list[CheckResult] = []
    for step in steps:
        for raw in step.get("check_results") or []:
            try:
                check = CheckResult.model_validate(raw)
            except Exception:  # noqa: BLE001 - a malformed record is untrusted, not dropped
                check = CheckResult(check_id="malformed", strategy="unknown", status="untrusted",
                                    reason="check record failed validation")
            if check.step_id is None:
                check.step_id = step.get("step_id")
            out.append(check)
    return out


def _final_fingerprints(steps: list[dict[str, Any]]) -> dict[str, str]:
    final: dict[str, str] = {}
    for step in steps:
        final.update({k: str(v) for k, v in (step.get("file_fingerprints") or {}).items()})
    return final


def _mark_stale(checks: list[CheckResult], final: dict[str, str]) -> None:
    """A pass on content that later changed is no longer evidence for that file."""
    def fresh(strategy: str, path: str) -> bool:
        return any(c.status == "passed" and c.strategy == strategy and c.fingerprints.get(path) == final[path]
                   for c in checks)

    for check in [c for c in checks if c.status == "passed"]:
        moved = [f for f, fp in check.fingerprints.items() if f in final and final[f] != fp]
        if not moved:
            continue
        # Superseded when a later check of the same kind passed on the final content.
        label = "superseded" if all(fresh(check.strategy, f) for f in moved) else "stale"
        check.status = "untrusted"
        check.reason = f"{label}: {', '.join(moved[:5])} changed after this check ran"


# ── classification ────────────────────────────────────────────────────────────

def _classify_step_failure(step: dict[str, Any]) -> FailureClass:
    statuses = {c.get("status") for c in step.get("check_results") or [] if isinstance(c, dict)}
    phase = step.get("failure_phase") or ""
    if phase == "empirical_verification" and "failed" not in statuses:
        if "timed_out" in statuses:
            return "timeout"
        if "untrusted" in statuses:
            return "flaky"
        if "unavailable" in statuses:
            return "environment"
    if phase in {"verification", "judge"}:
        return "verifier_infrastructure"
    return "implementation_defect"


def _step_findings(steps: list[dict[str, Any]]) -> list[Finding]:
    out: list[Finding] = []
    for step in steps:
        if step.get("status") != "failed":
            continue
        sid = step.get("step_id")
        issues = "; ".join(_clean(i, 300) for i in (step.get("issues") or [])[:3]) or "no detail"
        out.append(Finding(
            kind=_classify_step_failure(step), criterion_id=f"step-{sid}",
            message=f"Step {sid} '{_clean(step.get('description'), 120)}' failed "
                    f"{step.get('failure_phase') or 'execution'}: {issues}",
        ))
    return out


def _check_findings(checks: list[CheckResult]) -> list[Finding]:
    out: list[Finding] = []
    for c in checks:
        if c.status == "failed":
            kind: FailureClass = "implementation_defect"
        elif c.status == "untrusted":
            if c.reason.startswith("superseded"):
                continue
            kind = "stale_evidence" if c.reason.startswith("stale") else "flaky"
        elif c.status == "timed_out":
            kind = "timeout"
        else:
            continue
        out.append(Finding(kind=kind, check_id=c.check_id, criterion_id=f"step-{c.step_id}",
                           message=f"{c.check_id} on {', '.join(c.files[:5]) or 'the change'}: "
                                   f"{c.reason or c.status} {c.output_tail[-400:]}".strip()))
    return out


def _judge_verdict(judge: dict[str, Any]) -> str:
    return str((judge or {}).get("verdict") or "").strip().upper()


def _judge_findings(judge: dict[str, Any], defects: list[Finding]) -> list[Finding]:
    verdict = _judge_verdict(judge)
    notes = str((judge or {}).get("notes") or "")[:500]
    if verdict in {"REJECTED"}:
        return [Finding(kind="implementation_defect", criterion_id="goal",
                        message=f"The independent reviewer rejected the change: {notes or 'no reason given'}")]
    if verdict.startswith("APPROVED"):
        broken = [d for d in defects if d.kind in _FAILING]
        if broken:
            return [Finding(kind="contract_violation", criterion_id="goal",
                            message="The reviewer approved, but the evidence contradicts it: "
                                    + "; ".join(d.message[:160] for d in broken[:3]))]
        return []
    return [Finding(kind="verifier_infrastructure", criterion_id="goal",
                    message=f"No usable independent review ({verdict or 'none'}): {notes or 'no output'}")]


# ── coverage ──────────────────────────────────────────────────────────────────

def _passing(checks: list[CheckResult], strategy: str, files: list[str],
             final: dict[str, str]) -> list[CheckResult]:
    """Passing checks of *strategy* that cover every one of *files* on its final content.

    Matching on files rather than step ids, and on content fingerprints when
    the run recorded them, means a check of some other file, or of an older
    version of this one, never stands in for the check this step needed.
    """
    return [c for c in checks if c.strategy == strategy and c.status == "passed"
            and set(files) <= set(c.files)
            and all(c.fingerprints.get(f) == final[f] for f in files if f in final)]


def _gap_reason(checks: list[CheckResult], strategy: str, step_id: Any) -> str:
    seen = [c for c in checks if c.strategy == strategy and c.step_id == step_id]
    if not seen:
        return "no check ran"
    return "; ".join(f"{c.status}: {c.reason or c.check_id}" for c in seen[:3])


def _coverage(contract: VerificationContract, steps: list[dict[str, Any]],
              checks: list[CheckResult], final: dict[str, str]) -> tuple[list[str], list[Finding]]:
    """Mandatory per-step strategies (static, unit) that produced no passing result."""
    mandatory = set(contract.mandatory_strategies()) & {"static", "unit"}
    gaps: list[str] = []
    findings: list[Finding] = []
    for step in steps:
        if step.get("status") != "applied":
            continue
        py = [str(f) for f in step.get("changed_files") or [] if _is_py(f)]
        if not py:
            continue
        sid = step.get("step_id")
        for strategy in sorted(mandatory):
            if _passing(checks, strategy, py, final):
                continue
            why = _gap_reason(checks, strategy, sid)
            gaps.append(f"Step {sid}: mandatory {strategy} check has no passing result ({why})")
            findings.append(Finding(kind="incomplete", criterion_id=f"step-{sid}",
                                    message=f"Step {sid} has no passing {strategy} check ({why})"))
    return gaps, findings


def _criteria_results(contract: VerificationContract, steps: list[dict[str, Any]],
                      checks: list[CheckResult], findings: list[Finding]) -> list[CriterionResult]:
    by_step = {s.get("step_id"): s for s in steps}
    flagged = {f.criterion_id for f in findings}
    failed_ids = {f.criterion_id for f in findings if f.kind in _FAILING}
    out: list[CriterionResult] = []
    for crit in contract.criteria:
        ids = [c.check_id for c in checks if crit.step_id is not None and c.step_id == crit.step_id]
        if crit.criterion_id in failed_ids:
            status = "failed"
        elif crit.criterion_id in flagged:
            status = "unverified"
        elif crit.step_id is not None and (by_step.get(crit.step_id) or {}).get("status") != "applied":
            status = "unverified"
        else:
            status = "passed"
        out.append(CriterionResult(criterion_id=crit.criterion_id, status=status, check_ids=ids))
    return out


def _verdict(findings: list[Finding], criteria: list[CriterionResult]) -> FinalVerdict:
    kinds = {f.kind for f in findings}
    if kinds & _FAILING:
        return "FAILED"
    if kinds & _BLOCKING:
        return "BLOCKED"
    if kinds or any(c.status != "passed" for c in criteria) or not criteria:
        return "INCONCLUSIVE"
    return "VERIFIED"


def _untested_files(steps: list[dict[str, Any]], checks: list[CheckResult]) -> list[str]:
    covered = {f for c in checks if c.strategy == "unit" and c.status == "passed" for f in c.files}
    changed = {f for s in steps if s.get("status") == "applied" for f in s.get("changed_files") or []}
    return sorted(f for f in changed if _is_py(f) and f not in covered)


def _run_findings(steps: list[dict[str, Any]], planned: int, budget_hit: bool, ui_gap: str | None) -> list[Finding]:
    out: list[Finding] = []
    if budget_hit or len(steps) < planned:
        out.append(Finding(kind="incomplete", message=f"Only {len(steps)} of {planned} planned steps ran"
                           + (" (time budget exceeded)" if budget_hit else "")))
    if ui_gap:
        out.append(Finding(kind="incomplete", message=f"UI evidence missing: {ui_gap}"))
    if not steps:
        out.append(Finding(kind="incomplete", message="No step ran, so nothing was verified"))
    return out


def build_report(
    contract: VerificationContract, *, steps: list[dict[str, Any]], judge: dict[str, Any] | None,
    commits: list[str] | None = None, time_budget_exceeded: bool = False, ui_gap: str | None = None,
    source_revision: str | None = None,
) -> EvidenceReport:
    """Fold a run's observed results into a report and decide the verdict."""
    steps = [s for s in steps or [] if isinstance(s, dict)]
    judge = judge if isinstance(judge, dict) else {}
    checks = _collect_checks(steps)
    final = _final_fingerprints(steps)
    _mark_stale(checks, final)
    defects = _step_findings(steps) + _check_findings(checks)
    gaps, gap_findings = _coverage(contract, steps, checks, final)
    planned = sum(1 for c in contract.criteria if c.source == "step")
    findings = (defects + gap_findings + _judge_findings(judge, defects)
                + _run_findings(steps, planned, time_budget_exceeded, ui_gap))
    criteria = _criteria_results(contract, steps, checks, findings)
    changed = list(dict.fromkeys(f for s in steps for f in s.get("changed_files") or []))
    tier = stricter(contract.risk_tier, classify_risk(changed)[0]) if changed else contract.risk_tier
    verdict = _verdict(findings, criteria)
    untested = _untested_files(steps, checks)
    return EvidenceReport(
        contract_id=contract.contract_id, contract_version=contract.version,
        contract_fingerprint=contract.fingerprint(), session_id=contract.session_id,
        source_revision=source_revision, commits=list(commits or [])[:20], changed_files=changed[:200],
        file_fingerprints=final, risk_tier=tier, checks=checks, criteria=criteria,
        judge={k: _redact(judge.get(k), 1000) for k in ("verdict", "security", "correctness", "notes") if judge.get(k)},
        findings=findings, not_executed=gaps + _advisory_gaps(contract),
        corrections=[str(i) for s in steps for i in s.get("resolved_issues") or []][:40],
        regression_candidates=[f"Add a regression test reproducing {f.check_id or f.criterion_id}: {f.message[:240]}"
                               for f in defects if f.kind == "implementation_defect"][:10],
        remaining_risks=[f"{f} changed with no matching test run" for f in untested][:20],
        limitations=list(contract.limitations),
        models_used=sorted({str(m) for s in steps for m in (s.get("models") or {}).values() if m}),
        verdict=verdict, reasons=[f.message for f in findings][:20] or ["All criteria met with fresh evidence"],
        requires_human_approval=tier == "high",
    )


def _advisory_gaps(contract: VerificationContract) -> list[str]:
    return [f"Advisory {s.name} verification not run automatically: {s.reason}"
            for s in contract.strategies if not s.mandatory]


def check_binding(report: dict[str, Any] | None, contract: dict[str, Any] | None) -> str | None:
    """Why *report* cannot be trusted against *contract*, or None when it is bound to it."""
    if not isinstance(report, dict) or not isinstance(contract, dict):
        return "no evidence report or contract"
    try:
        parsed = VerificationContract.model_validate(contract)
        rep = EvidenceReport.model_validate(report)
    except Exception as exc:  # noqa: BLE001 - an unreadable record is not evidence
        return f"evidence record unreadable: {type(exc).__name__}"
    if rep.contract_id != parsed.contract_id or rep.contract_fingerprint != parsed.fingerprint():
        return "the evidence report was produced against a different verification contract"
    return None
