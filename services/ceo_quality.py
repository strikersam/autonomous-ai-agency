"""services/ceo_quality.py — judging what came back, and what to do about it.

The other half of the CEO's micro-management: :mod:`services.ceo_micromanager`
decides *what work to hand out and to whom*; this module decides *whether what
came back is acceptable* and *what happens when it is not*.

Splitting the two is not cosmetic. The planning side reaches for the brain and
the runtime registry; this side is pure, synchronous, side-effect-free
decision logic. Keeping it separate is what lets the anti-slop gate be tested
exhaustively without mocking anything, and keeps both modules inside the
repository's 800-line limit.

Everything here is re-exported from ``services.ceo_micromanager`` so existing
import sites keep working.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from services.ceo_micromanager import (
    MicroManagerConfig,
    SubtaskPlan,
    Tier,
    get_config,
    next_tier,
)

log = logging.getLogger("agency.ceo.quality")


# ── Anti-slop quality gate ────────────────────────────────────────────────────


#: Phrases that mean an agent gave up. Matched case-insensitively against the
#: summary's *first sentence* only. When an agent genuinely refuses, the refusal
#: is the opening statement — "I am unable to complete this task…". Scanning the
#: whole summary, or even a fixed-length prefix, rejects honest reports that
#: merely mention a failure further down ("…the legacy shim still logs 'unable
#: to complete' on timeout, which I left alone"), which would escalate good work
#: for describing a bug it correctly declined to fix.
_GIVE_UP_MARKERS = (
    "i cannot",
    "i can't",
    "i am unable",
    "i'm unable",
    "unable to complete",
    "unable to proceed",
    "failed to complete",
    "no changes were made",
    "could not determine",
    "escalate to",
)

_TEST_PATH_RE = re.compile(r"(^|/)(tests?|__tests__|spec)/|(^|/)test_[^/]+\.py$|\.test\.[jt]sx?$")

#: Sentence terminators used to isolate the opening claim of a summary.
_SENTENCE_END_RE = re.compile(r"[.!?\n]")


def first_sentence(text: str, *, cap: int = 240) -> str:
    """Return the opening sentence of *text*, capped at *cap* characters.

    Used to test whether an agent's summary *opens* with a refusal, rather than
    merely containing the words somewhere.
    """
    head = text.strip()[:cap]
    match = _SENTENCE_END_RE.search(head)
    return head[: match.start()] if match else head


@dataclass
class QualityVerdict:
    """The CEO's judgement on one specialist result."""

    accepted: bool
    #: 0.0–1.0. Informational — the accept/reject decision is in ``accepted``.
    score: float
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"accepted": self.accepted, "score": round(self.score, 2), "reasons": list(self.reasons)}


def touched_tests(changed_files: list[str]) -> bool:
    """True when any changed path looks like a test file."""
    return any(_TEST_PATH_RE.search(p.replace("\\", "/")) for p in changed_files if p)


def assess_quality(
    plan: SubtaskPlan,
    result: dict[str, Any],
    *,
    config: MicroManagerConfig | None = None,
) -> QualityVerdict:
    """Decide whether a specialist result is good enough to accept.

    This is the anti-slop gate. Its job is to catch the failure mode where an
    agent reports success having done nothing — an empty summary, a polite
    refusal, or a code change with no test behind it. A rejected result is
    re-delegated one tier up; it is never recorded as done.

    The gate is deliberately mechanical rather than an LLM judgement: it runs on
    every subtask in an unattended loop, so it has to be cheap, deterministic,
    and impossible to talk out of.

    File-based checks are conditional on ``result["files_reported"]``. Only some
    runtime adapters (internal_agent, e2b) report which files they touched;
    hermes, claude_code and goose return prose only. Applying "you changed no
    files" to a runtime that *cannot say* would reject every successful subtask
    it ran, so when files were not reported the gate records that it could not
    verify and judges on the remaining signals instead.
    """
    config = config or get_config()
    reasons: list[str] = []
    hard_reject = False
    score = 1.0

    if result.get("status") != "ok":
        err = str(result.get("error") or "runtime reported failure")
        return QualityVerdict(accepted=False, score=0.0, reasons=[f"execution failed: {err[:200]}"])

    summary = str(result.get("summary") or "").strip()
    if not summary:
        return QualityVerdict(accepted=False, score=0.0, reasons=["no summary reported"])

    if len(summary) < config.min_output_chars:
        reasons.append(f"summary too short ({len(summary)} < {config.min_output_chars} chars)")
        score -= 0.3

    opening = first_sentence(summary).lower()
    for marker in _GIVE_UP_MARKERS:
        if marker in opening:
            reasons.append(f"agent reported it did not complete the work ({marker!r})")
            hard_reject = True
            score = 0.0
            break

    changed_files = [str(f) for f in (result.get("changed_files") or []) if f]
    files_reported = bool(result.get("files_reported"))
    if plan.writes_code:
        if not files_reported:
            reasons.append("runtime does not report changed files — file checks skipped")
            score -= 0.1
        elif not changed_files:
            # The strongest slop signal available: the agent said it succeeded,
            # on a runtime that does report file changes, having changed none.
            reasons.append("claimed success but changed no files")
            hard_reject = True
            score = 0.0
        elif config.require_tests_for_code and not touched_tests(changed_files):
            reasons.append("source files changed but no test file was added or updated")
            score -= 0.3

    # Acceptance is categorical: only the hard signals above reject. The soft
    # penalties are recorded as a score for the ledger and the dashboard, but
    # they never gate on their own.
    #
    # They used to. With a 0.5 threshold, a terse summary (-0.3) plus a missing
    # test (-0.3) landed on 0.4 and rejected — escalating a correct-but-brief
    # change through the whole tier ladder, even though each signal is
    # documented and tested as "a warning, not a hard reject". Two warnings
    # silently becoming an error is the kind of emergent threshold behaviour
    # that is expensive on an unattended loop and hard to reason about, so the
    # numeric gate is gone and the categorical one is the only one left.
    score = max(0.0, min(1.0, score))
    return QualityVerdict(accepted=not hard_reject, score=score, reasons=reasons)


# ── Escalation decision ───────────────────────────────────────────────────────


@dataclass
class EscalationDecision:
    """What the CEO does next with a subtask that did not pass the gate."""

    #: ``"retry"`` to re-delegate at ``tier``; ``"give_up"`` when the ladder or
    #: the attempt budget is exhausted.
    action: str
    tier: Tier | None = None
    reason: str = ""

    @property
    def should_retry(self) -> bool:
        return self.action == "retry"


def decide_escalation(
    plan: SubtaskPlan,
    verdict: QualityVerdict,
    *,
    attempts_used: int,
    config: MicroManagerConfig | None = None,
) -> EscalationDecision:
    """Decide whether to re-delegate a failed subtask, and to which tier.

    Two independent bounds stop this from looping: the ladder itself (a subtask
    at SENIOR has nowhere to escalate to) and ``max_attempts_per_subtask``.
    Both are checked here so no caller can accidentally bypass one.
    """
    config = config or get_config()
    if verdict.accepted:
        return EscalationDecision(action="give_up", reason="already accepted")
    if not config.escalation_enabled:
        return EscalationDecision(action="give_up", reason="escalation disabled")
    if attempts_used >= config.max_attempts_per_subtask:
        return EscalationDecision(
            action="give_up",
            reason=f"attempt budget exhausted ({attempts_used}/{config.max_attempts_per_subtask})",
        )
    promoted = next_tier(plan.tier)
    if promoted is None:
        return EscalationDecision(
            action="give_up", reason="already at the top of the tier ladder"
        )
    return EscalationDecision(
        action="retry",
        tier=promoted,
        reason=f"escalating {plan.tier.value} → {promoted.value}: " + "; ".join(verdict.reasons[:3]),
    )
