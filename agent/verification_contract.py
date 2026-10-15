"""agent/verification_contract.py — the verification contract a run is held to.

Before the executor touches a file, the plan is turned into a contract: the
acceptance criteria, the risk tier, the verification strategies that apply and
why, the checks that must produce trustworthy results, and the retry budget.
The contract is persisted with the plan's spec (``services/spec_store.py``)
and fingerprinted, so the evidence report written at the end of the run
(``agent/verification_evidence.py``) can prove which contract it was judged
against. An agent cannot quietly redefine the criteria after its work fails:
``amend_contract`` refuses machine actors and keeps the history.

Risk is classified from paths, not from how the task was worded, and is
re-classified from the files the run actually changed; the stricter tier wins.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

CONTRACT_SCHEMA_VERSION = 1

RiskTier = Literal["low", "medium", "high"]
StrategyName = Literal[
    "static", "unit", "ui", "independent_review", "human_approval",
    "property", "differential", "regression",
]
_TIER_ORDER: dict[str, int] = {"low": 0, "medium": 1, "high": 2}

# High risk beyond the risky-module list in agent/verification_strategies.py:
# governance, deployment, CI permissions, data migrations and secrets.
_HIGH_RISK_EXTRA = (
    re.compile(r"(^|/)governance(/|\.py$)"),
    re.compile(r"(^|/)\.github/workflows/"),
    re.compile(r"(^|/)(deploy|migrations?)(/|\.py$)"),
    re.compile(r"(^|/)render\.yaml$"),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"(^|/)packages/auth/"),
    re.compile(r"(^|/)proxy\.py$"),
)
_LOW_RISK_SUFFIXES = (".md", ".rst", ".txt")
_UI_SUFFIXES = (".jsx", ".tsx", ".js", ".ts", ".css", ".html", ".vue", ".svelte")
_BEHAVIOUR_PRESERVING = re.compile(r"\b(refactor|migrat|rename|replace|port|extract)", re.IGNORECASE)
_PURE_LOGIC = re.compile(r"\b(pars|serializ|policy|transition|calculat|validat)", re.IGNORECASE)


class AcceptanceCriterion(BaseModel):
    """One testable statement the run must satisfy, and the checks that prove it."""

    criterion_id: str
    description: str = Field(..., min_length=1, max_length=1000)
    source: Literal["step", "goal", "invariant"]
    step_id: int | None = None
    required_strategies: list[StrategyName] = Field(default_factory=list)
    mandatory: bool = True


class StrategySelection(BaseModel):
    """A verification strategy chosen for this change, and why."""

    name: StrategyName
    reason: str
    mandatory: bool


class ContractAmendment(BaseModel):
    """A recorded change to the criteria, made by a person."""

    version: int
    actor: str
    reason: str
    at: float = Field(default_factory=time.time)


class VerificationContract(BaseModel):
    """What a run must prove, persisted before execution begins."""

    schema_version: int = CONTRACT_SCHEMA_VERSION
    contract_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    version: int = 1
    session_id: str | None = None
    goal: str
    scope_files: list[str] = Field(default_factory=list)
    criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    invariants: list[str] = Field(default_factory=list)
    risk_tier: RiskTier = "medium"
    risk_reasons: list[str] = Field(default_factory=list)
    strategies: list[StrategySelection] = Field(default_factory=list)
    pass_conditions: list[str] = Field(default_factory=list)
    failure_conditions: list[str] = Field(default_factory=list)
    max_rework_cycles: int = 2
    per_file_retries: int = 3
    time_budget_s: float = 0.0
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    amendments: list[ContractAmendment] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)

    def fingerprint(self) -> str:
        """Hash of what the run is judged against (criteria, risk, strategies)."""
        body = {
            "goal": self.goal,
            "criteria": [c.model_dump() for c in self.criteria],
            "invariants": self.invariants,
            "risk_tier": self.risk_tier,
            "strategies": [s.model_dump() for s in self.strategies],
            "version": self.version,
        }
        raw = json.dumps(body, sort_keys=True, default=str).encode()
        return hashlib.sha256(raw).hexdigest()[:16]

    def mandatory_strategies(self) -> list[str]:
        """Names of the strategies whose checks must pass."""
        return [s.name for s in self.strategies if s.mandatory]


def stricter(a: str, b: str) -> RiskTier:
    """The stricter of two risk tiers."""
    return a if _TIER_ORDER.get(a, 1) >= _TIER_ORDER.get(b, 1) else b  # type: ignore[return-value]


def classify_risk(paths: list[str]) -> tuple[RiskTier, list[str]]:
    """Risk tier for a set of changed paths, with the reasons.

    No paths is medium: an unknown change is not assumed safe.
    """
    from agent.verification_strategies import touches_risky_module

    norm = [p.replace("\\", "/") for p in paths if p]
    if not norm:
        return "medium", ["no files named; treated as medium risk until the change is known"]
    high = [p for p in norm if touches_risky_module([p]) or any(r.search(p) for r in _HIGH_RISK_EXTRA)]
    if high:
        return "high", [f"touches a security, governance or deployment path: {p}" for p in high[:10]]
    if all(p.endswith(_LOW_RISK_SUFFIXES) or p.startswith("docs/") for p in norm):
        return "low", ["documentation or text only"]
    return "medium", ["changes application behaviour"]


def _has(paths: list[str], suffixes: tuple[str, ...]) -> bool:
    return any(p.endswith(suffixes) for p in paths)


def select_strategies(tier: str, paths: list[str], goal: str = "") -> list[StrategySelection]:
    """Pick the strategies that apply to this change and its risk tier."""
    out: list[StrategySelection] = []
    py = _has(paths, (".py",))
    if py:
        out.append(StrategySelection(name="static", reason="Python changed: it must byte-compile", mandatory=True))
        out.append(StrategySelection(
            name="unit", mandatory=tier != "low",
            reason="Python behaviour changed: the matching tests/test_<module>*.py must run and pass",
        ))
    if _has(paths, _UI_SUFFIXES) or any(p.startswith("frontend/") for p in paths):
        out.append(StrategySelection(name="ui", reason="UI changed: each changed page is screenshotted", mandatory=True))
    out.append(StrategySelection(
        name="independent_review", mandatory=True,
        reason="A reviewer that did not write the change judges the diff against the goal (rule 49)",
    ))
    if tier == "high":
        out.append(StrategySelection(
            name="human_approval", mandatory=True,
            reason="High risk: a person approves before the task is done; verification is not authorization",
        ))
    if _BEHAVIOUR_PRESERVING.search(goal):
        out.append(StrategySelection(
            name="differential", mandatory=False,
            reason="Behaviour-preserving change: compare old and new outputs where the old code is a valid oracle",
        ))
    if _PURE_LOGIC.search(goal):
        out.append(StrategySelection(
            name="property", mandatory=False,
            reason="Deterministic logic: state invariants as properties over generated inputs",
        ))
    out.append(StrategySelection(
        name="regression", mandatory=False,
        reason="Every confirmed defect is a candidate for a permanent regression test",
    ))
    return out


def _step_criteria(steps: list[dict[str, Any]], strategies: list[str]) -> tuple[list[AcceptanceCriterion], list[str]]:
    criteria: list[AcceptanceCriterion] = []
    assumptions: list[str] = []
    per_step = [s for s in ("static", "unit", "ui") if s in strategies]
    for step in steps:
        sid = int(step.get("id") or len(criteria) + 1)
        desc = str(step.get("description") or f"step {sid}")[:300]
        acceptance = str(step.get("acceptance") or "").strip()
        if not acceptance:
            acceptance = f"'{desc}' is applied, passes the step verifier, and its executable checks pass"
            assumptions.append(
                f"Step {sid} had no acceptance test from the planner; assumed the conservative default: {acceptance}"
            )
        criteria.append(AcceptanceCriterion(
            criterion_id=f"step-{sid}", description=acceptance[:1000], source="step",
            step_id=sid, required_strategies=per_step,  # type: ignore[arg-type]
        ))
    return criteria, assumptions


def build_contract(
    plan: Any, *, session_id: str | None = None, time_budget_s: float = 0.0, max_rework_cycles: int = 2,
) -> VerificationContract:
    """Turn an ``AgentPlan`` (or its dict) into the contract the run is held to."""
    data = plan.model_dump() if hasattr(plan, "model_dump") else dict(plan or {})
    steps = [s for s in data.get("steps") or [] if isinstance(s, dict)]
    goal = str(data.get("goal") or "").strip() or "(no goal given)"
    scope = list(dict.fromkeys(f for s in steps for f in (s.get("files") or [])))
    tier, reasons = classify_risk(scope)
    if data.get("requires_risky_review") or any(s.get("risky") for s in steps):
        tier, reasons = "high", reasons + ["the planner flagged a security-sensitive step"]
    strategies = select_strategies(tier, scope, goal)
    names = [s.name for s in strategies]
    criteria, assumptions = _step_criteria(steps, names)
    criteria.append(AcceptanceCriterion(
        criterion_id="goal", source="goal", required_strategies=["independent_review"],
        description=f"The change accomplishes the goal and nothing it did not ask for: {goal[:800]}",
    ))
    if not steps:
        assumptions.append("The plan had no steps; only the goal criterion applies")
    return VerificationContract(
        session_id=session_id, goal=goal[:2000], scope_files=scope[:200], criteria=criteria,
        invariants=[
            "Files outside the plan are not changed",
            "Evidence is bound to the final content of every changed file",
            "No check that did not run, could not run or timed out counts as a pass",
        ],
        risk_tier=tier, risk_reasons=reasons, strategies=strategies,
        pass_conditions=[
            "Every step applied and every mandatory check passed on the final content",
            "The independent reviewer approved and its approval agrees with the evidence",
        ],
        failure_conditions=[
            "A step failed or a mandatory check failed",
            "The independent reviewer rejected the change",
        ],
        max_rework_cycles=max_rework_cycles, per_file_retries=3, time_budget_s=float(time_budget_s or 0.0),
        assumptions=assumptions,
    )


def amend_contract(
    contract: VerificationContract, *, actor: str, reason: str, criteria: list[AcceptanceCriterion],
) -> VerificationContract:
    """A new contract version with changed criteria; only a person may amend.

    Raises ``PermissionError`` for an agent, runtime or system actor: the agent
    whose work failed must not be the one that moves the goalposts.
    """
    from tasks.verification import is_human_actor

    if not is_human_actor(actor):
        raise PermissionError(f"{actor!r} may not amend acceptance criteria; a person must")
    if not reason.strip():
        raise ValueError("An amendment needs a reason")
    new_version = contract.version + 1
    return contract.model_copy(update={
        "version": new_version,
        "criteria": list(criteria),
        "amendments": [*contract.amendments, ContractAmendment(version=new_version, actor=actor, reason=reason[:1000])],
    })
