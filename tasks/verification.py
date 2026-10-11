"""tasks/verification.py — rule 49: no task is done without an independent verdict.

A task reaches DONE only when a verifier that did not do the work has returned
PASS or PASS+NOTES. The verdict travels with the task as a report: what was
checked, what was found broken, what got fixed, and the evidence behind it, so
an operator can see the proof instead of trusting a "done".

Two verifiers exist today:

* the agent loop's **judge**, a separate role and model that reviews the whole
  run after the executor and per-step verifier finish (``agent/loop.py``);
* a **person** who reviews the result and accepts it.

The gate lives in ``TaskWorkflowService.transition`` and ``create_task`` (both
see the actor). Code that assigns ``task.status`` directly must call
``settle_success`` instead; the two CEO-dispatch paths in ``backend/server.py``
do. Re-opening a task retires its verdict, so a new run needs a new one. The
gate is the ``TASK_VERIFICATION_REQUIRED`` platform control, on by default.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Literal, Union

from pydantic import BaseModel, Field, field_validator

log = logging.getLogger("qwen-proxy")

Verdict = Literal["PASS", "PASS+NOTES", "FAIL"]
PASSING: frozenset[str] = frozenset({"PASS", "PASS+NOTES"})
_MAX_ITEMS = 40
_MAX_ITEM_CHARS = 600

# Actors that are software, not a person. Anything else is a human user id or
# email. "telegram_bot" is deliberately absent: it relays a person's tap on
# Approve in Telegram (telegram_bot.py), so that decision is a human one.
_MACHINE_PREFIXES = (
    "agent:", "agent-", "runtime:", "system:", "scheduler:", "ceo:", "workflow:",
    "service:", "api_key:", "judge:", "verifier:",
)
_MACHINE_NAMES = frozenset({
    "agent", "ceo", "system", "runtime", "scheduler", "internal_agent", "workflow", "judge", "verifier",
})

WAITING_REASON = "Waiting for an independent verifier (rule 49)"


def _clip(items: list[str]) -> list[str]:
    out = [str(i).strip()[:_MAX_ITEM_CHARS] for i in items if str(i).strip()]
    return out[:_MAX_ITEMS]


class TaskVerification(BaseModel):
    """An independent verifier's report on a task's result."""

    verdict: Verdict
    verifier: str = Field(..., min_length=1, max_length=200)
    checked: list[str] = Field(default_factory=list)
    defects_found: list[str] = Field(default_factory=list)
    fixed: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    notes: str = Field(default="", max_length=4000)
    verified_at: Union[float, str] = Field(default_factory=time.time)

    @field_validator("checked", "defects_found", "fixed", "evidence", mode="before")
    @classmethod
    def _bounded(cls, v: Any) -> list[str]:
        return _clip(list(v or []))

    @property
    def passed(self) -> bool:
        """True for PASS and PASS+NOTES."""
        return self.verdict in PASSING


def is_human_actor(actor: str | None) -> bool:
    """A person (user id or email), as opposed to an agent, runtime or system."""
    a = (actor or "").strip().lower()
    return bool(a) and a not in _MACHINE_NAMES and not a.startswith(_MACHINE_PREFIXES)


def human_acceptance(actor: str) -> TaskVerification:
    """A person accepting the result is the independent verifier."""
    return TaskVerification(
        verdict="PASS",
        verifier=actor,
        checked=[f"Result reviewed and accepted by {actor}"],
    )


def _judge_verdict(judge: dict[str, Any]) -> Verdict | None:
    raw = str(judge.get("verdict") or "").strip().upper()
    if raw == "APPROVED":
        notes_flag = any(str(judge.get(k, "")).upper() == "WARN" for k in ("security", "correctness"))
        return "PASS+NOTES" if notes_flag else "PASS"
    if raw == "APPROVED_WITH_CONDITIONS":
        return "PASS+NOTES"
    if raw in {"REJECTED", "BLOCKED"}:
        return "FAIL"
    return None


def _step_lines(steps: list[dict[str, Any]]) -> tuple[list[str], list[str], list[str]]:
    checked: list[str] = []
    defects: list[str] = []
    fixed: list[str] = []
    for i, step in enumerate(steps, 1):
        desc = str(step.get("description") or f"step {i}")[:200]
        status = step.get("status")
        files = step.get("changed_files") or []
        if status == "applied":
            what = f"{len(files)} file(s)" if files else "no file changes"
            checked.append(f"Step {i} '{desc}': passed the step verifier ({what})")
        elif status == "failed":
            phase = step.get("failure_phase") or "execution"
            issues = "; ".join(str(x) for x in (step.get("issues") or [])[:3]) or "no detail"
            defects.append(f"Step {i} '{desc}' failed {phase}: {issues}")
        for check in step.get("executed_checks") or []:
            checked.append(f"Step {i} '{desc}': ran {check}")
        for issue in step.get("resolved_issues") or []:
            defects.append(f"Step {i} '{desc}': {issue}")
            fixed.append(f"Step {i} '{desc}': fixed on retry, then passed: {issue}")
    return checked, defects, fixed


def _executed(steps: list[dict[str, Any]]) -> bool:
    return any(step.get("executed_checks") for step in steps)


def unbacked_note(raw: dict[str, Any] | None) -> str | None:
    """Why an approving judge did not count as a pass, or None."""
    if not isinstance(raw, dict) or not isinstance(raw.get("judge"), dict):
        return None
    if _judge_verdict(raw["judge"]) in PASSING and not _executed(list(raw.get("steps") or [])):
        return (
            "The reviewing agent approved the change, but no tests or checks were run "
            "against it, so it is not verified yet (rule 49). Enable AGENT_EMPIRICAL_VERIFY "
            "to let agents run them, or check the result yourself."
        )
    return None


def verification_from_run(raw: dict[str, Any] | None) -> TaskVerification | None:
    """Build the report from an agent-loop result; None if no judge ran.

    The judge is a separate role that reviews the finished run, so its verdict
    is the independent one. The per-step lines are the evidence behind it.
    """
    if not isinstance(raw, dict):
        return None
    judge = raw.get("judge") or {}
    verdict = _judge_verdict(judge) if isinstance(judge, dict) else None
    if verdict is None:
        return None
    steps = list(raw.get("steps") or [])
    if verdict in PASSING and not _executed(steps):
        # An approving review of a diff is not proof it works (rule 49:
        # exercise the real artifact). Without an executed check the task
        # waits for a person; unbacked_note() explains why.
        return None
    checked, defects, fixed = _step_lines(steps)
    for key in ("security", "correctness"):
        if judge.get(key):
            checked.append(f"Judge {key} review: {judge[key]}")
    evidence = [f"Commit {c}" for c in (raw.get("commits") or [])][:10]
    if raw.get("pr_url"):
        evidence.append(f"Pull request {raw['pr_url']}")
    evidence += [f"PR blocker: {b}" for b in (raw.get("pr_blockers") or [])]
    if verdict == "FAIL" and judge.get("notes"):
        defects.append(f"Judge: {judge['notes']}")
    return TaskVerification(
        verdict=verdict,
        verifier="agent:judge",
        checked=checked,
        defects_found=defects,
        fixed=fixed,
        evidence=evidence,
        notes=str(judge.get("notes") or "")[:4000],
    )


def verification_required() -> bool:
    """Read the live ``TASK_VERIFICATION_REQUIRED`` control; default on."""
    try:
        from packages.config import settings

        return bool(getattr(settings, "task_verification_required", True))
    except Exception:
        log.warning("verification control unreadable; enforcing rule 49", exc_info=True)
        return True


def has_passing_verdict(task: Any) -> bool:
    """True when the task carries a PASS or PASS+NOTES report."""
    v = getattr(task, "verification", None)
    return bool(v is not None and getattr(v, "verdict", None) in PASSING)


def settle_success(task: Any, raw_result: dict[str, Any] | None, *, actor: str) -> None:
    """Mark a successful run DONE only if an independent verdict allows it.

    For code paths that set ``task.status`` directly instead of going through
    ``TaskWorkflowService.transition``. Attaches the judge's report when the run
    produced one; without a PASS the task waits in review with that reason.
    """
    from tasks.models import TaskStatus

    # Only this run's verdict counts: a verdict already on the task is about
    # earlier work (these paths re-run tasks without going through transition).
    task.verification = verification_from_run(raw_result)
    if not verification_required() or has_passing_verdict(task):
        task.status = TaskStatus.DONE
        return
    if task.verification is not None:  # FAIL
        status, reason, message = rework_or_park(task, actor)
        task.status = status
        task.review_reason = reason
        task.pending_agent_run = status is TaskStatus.IN_PROGRESS
        task.add_log(message, event_type="status_changed", actor=actor, task_status=status)
        return
    note = unbacked_note(raw_result)
    task.status = TaskStatus.IN_REVIEW
    task.review_reason = WAITING_REASON
    task.pending_agent_run = False
    task.add_log(
        f"Not marked done by {actor}: {note or WAITING_REASON}",
        event_type="status_changed",
        actor=actor,
        task_status=TaskStatus.IN_REVIEW,
    )


MAX_AUTO_REWORK = 2


def _automatic_failures(task: Any) -> int:
    """Verification failures since a person last acted on the task."""
    n = 0
    for entry in reversed(list(getattr(task, "execution_log", []) or [])):
        if is_human_actor(getattr(entry, "actor", None)):
            break
        if getattr(entry, "event_type", "") == "verification_failed":
            n += 1
    return n


def rework_or_park(task: Any, actor: str) -> tuple[Any, str | None, str]:
    """A FAIL verdict sends the work back to the agents, with the defects as a
    comment the next run reads, up to MAX_AUTO_REWORK times in a row; after
    that it parks in review for a person instead of looping forever.

    Returns (status, review_reason, log message).
    """
    from tasks.models import TaskComment, TaskStatus

    verdict = task.verification
    prior = _automatic_failures(task)
    problems = "\n".join(f"- {d}" for d in (verdict.defects_found or [])) or f"- {verdict.notes or 'No detail given'}"
    task.comments.append(TaskComment(
        author=verdict.verifier,
        body=f"Independent verification failed. Fix these, then it will be checked again:\n{problems}",
    ))
    task.add_log(
        f"Independent verification FAILED ({verdict.verifier})",
        event_type="verification_failed",
        actor=actor,
        task_status=task.status,
        metadata={"defects_found": verdict.defects_found[:10]},
    )
    if prior + 1 <= MAX_AUTO_REWORK:
        return TaskStatus.IN_PROGRESS, None, f"Verification failed; sent back for rework (attempt {prior + 1} of {MAX_AUTO_REWORK})"
    reason = f"Failed independent verification {prior + 1} times in a row; needs a person"
    return TaskStatus.IN_REVIEW, reason, reason
