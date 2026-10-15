"""tasks/review_autopilot.py — a verifier clears the review queue instead of a person.

The operator asked for this: tasks waiting on them ("To be approved" before a
run, "Review" after one) had become the agency's bottleneck. Each pass, gated
by the live ``AGENCY_REVIEW_AUTOPILOT`` control (default on):

1. **Before a run.** Every task parked at the approval gate (CEO triage takes
   its share first) is read by a reviewer model, including ones created gated:
   the operator asked for all of them. It is approved unless it is
   sloppy: vague, contradictory, not actionable, inventing names or URLs, or
   asking for something destructive or irreversible. A declined task stays
   for the person, with the reviewer's reason as a comment, and is not asked
   about again.
2. **After a run.** A task in review whose run already holds a passing verdict
   is marked done. One that links a pull request is checked by the
   independent verifier (tests in E2B, screenshots, reviewer model); a PASS
   marks it done. One with neither is sent back for one fresh run, which the
   agent loop's judge will verify; this also clears the tasks the 2026-10-11
   "diff unavailable" judge bug parked.

Outward-facing work (deploy, release, external writes) is never touched at
either gate: those stay with a person. Every decision is logged on the task.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from tasks.models import Task, TaskComment, TaskStatus
from tasks.service import TaskWorkflowService, _is_outward_facing
from tasks.store import TaskStore, get_task_store

log = logging.getLogger("qwen-proxy")

ACTOR = "agent:verifier"
DECLINED = "review_autopilot_declined"
REQUEUED = "review_autopilot_requeued"
_PLAN_CHECKS_PER_PASS = 20
_RUN_CHECKS_PER_PASS = 2
_REQUEUES_PER_PASS = 5
_SCAN = 200
_PR_RE = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/pull/\d+")

_PLAN_PROMPT = (
    "You approve tasks for an autonomous software agency before they run. A person "
    "used to do this and became the bottleneck. APPROVE unless the task is sloppy: "
    "too vague to act on or to tell when it is done, self-contradictory, inventing "
    "URLs, names or identifiers, or asking for something destructive or "
    "irreversible (deleting data or branches, force-pushing, spending money, "
    "touching credentials, contacting people outside the team). Respond with ONLY "
    "a JSON object with keys: verdict (APPROVED or REJECTED) and notes (one or two "
    "sentences a person can act on)."
)


@dataclass
class AutopilotResult:
    """What one pass decided."""

    approved: int = 0
    declined: int = 0
    completed: int = 0
    requeued: int = 0
    failed: int = 0
    notes: list[str] = field(default_factory=list)


def enabled() -> bool:
    """Read the live ``AGENCY_REVIEW_AUTOPILOT`` control."""
    from packages.config import settings

    return bool(getattr(settings, "agency_review_autopilot", True))


def _logged(task: Task, event_type: str) -> bool:
    return any(e.event_type == event_type for e in task.execution_log)


def _brief(task: Task) -> str:
    return "\n".join([
        f"Title: {task.title}",
        f"Type: {task.task_type or 'task'}  Priority: {getattr(task.priority, 'value', task.priority)}",
        f"Description:\n{(task.description or '')[:3000]}",
    ])


async def _judge_plan(task: Task) -> dict[str, Any] | None:
    """The reviewer model's verdict on a task that has not run; None if none answered."""
    from agent.loop import _resolve_role_model
    from packages.ai.failover_client import failover_chat_completion
    from tasks.independent_verifier import _parse_json

    payload = {
        "model": _resolve_role_model("judge"),
        "messages": [{"role": "system", "content": _PLAN_PROMPT},
                     {"role": "user", "content": _brief(task)}],
        "stream": False,
    }
    for _ in range(2):
        try:
            fo = await failover_chat_completion(payload, timeout_sec=90.0)
        except Exception as exc:  # noqa: BLE001 - no model: leave the task, try next pass
            log.warning("Review autopilot: no reviewer model available: %s", exc)
            return None
        parsed = _parse_json(fo.text or "")
        if parsed:
            return parsed
    return None


Apply = Callable[[Task], None]


async def _save_if_unchanged(store: TaskStore, seen: Task, apply: Apply) -> bool:
    """Apply a decision to the stored task only if nobody touched it meanwhile.

    Judging and verifying take minutes; a person may approve, reject or edit
    the task in that time. Their change wins: the decision is dropped.
    """
    fresh = await store.get(seen.task_id)
    if fresh is None or (fresh.status, fresh.execution_approved, len(fresh.execution_log)) != (
        seen.status, seen.execution_approved, len(seen.execution_log)
    ):
        log.info("Review autopilot: %s changed while it was being checked; left as it is", seen.task_id)
        return False
    apply(fresh)
    await store.update(fresh)
    return True


def _decline(why: str, prefix: str) -> Apply:
    def apply(task: Task) -> None:
        task.comments.append(TaskComment(author=ACTOR, body=f"{prefix}: {why}"))
        task.add_log(f"Review autopilot left this for a person: {why}", event_type=DECLINED,
                     actor=ACTOR, task_status=task.status)
    return apply


async def _decide_gated(task: Task, workflow: TaskWorkflowService) -> tuple[str, Apply] | None:
    """The decision on one parked task, or None when no reviewer answered."""
    verdict = await _judge_plan(task)
    if verdict is None:
        return None
    notes = str(verdict.get("notes") or "")[:600]
    if not str(verdict.get("verdict", "")).upper().startswith("APPROVED"):
        return "declined", _decline(notes, "Not approved automatically")

    def approve(t: Task) -> None:
        workflow.approve_execution(t, actor=ACTOR, approved=True)
        t.add_log(f"Approved by the review autopilot: {notes}", event_type="review_autopilot_approved",
                  actor=ACTOR, task_status=t.status)
    return "approved", approve


async def _gate_pass(store: TaskStore, workflow: TaskWorkflowService, result: AutopilotResult) -> None:
    parked = await store.list_awaiting_approval(limit=_SCAN)
    todo = [t for t in parked if not _is_outward_facing(t) and not _logged(t, DECLINED)]
    for task in todo[:_PLAN_CHECKS_PER_PASS]:
        try:
            decision = await _decide_gated(task, workflow)
            if decision and await _save_if_unchanged(store, task, decision[1]):
                setattr(result, decision[0], getattr(result, decision[0]) + 1)
                log.info("Review autopilot: %s %s", decision[0], task.task_id)
        except Exception:
            log.exception("Review autopilot: gate decision failed for %s", task.task_id)


class _RecordedRun:
    """A finished task's stored output, in the shape the independent verifier reads."""

    def __init__(self, task: Task) -> None:
        texts = [task.result or ""] + [c.body for c in task.comments]
        self.output = "\n".join(t for t in texts if t)
        self.metadata: dict[str, Any] = {}
        self.artifacts: list[Any] = []
        self.runtime_id = task.last_runtime_id or "runtime"


def _pull_request_linked(task: Task) -> bool:
    return bool(_PR_RE.search(_RecordedRun(task).output))


def _complete(workflow: TaskWorkflowService, message: str, verdict: Any = None) -> Apply:
    def apply(task: Task) -> None:
        if verdict is not None:
            task.verification = verdict
        workflow.transition(task, TaskStatus.DONE, actor=ACTOR, message=message)
    return apply


async def _verify_run(task: Task, workflow: TaskWorkflowService) -> tuple[str, Apply]:
    """Run the independent verifier on a finished task's PR; complete it on PASS."""
    from tasks import independent_verifier as iv
    from tasks.verification import verification_from_run

    verdict = verification_from_run(await iv.verify(task, _RecordedRun(task)))
    if verdict is None or not verdict.passed:
        why = (verdict.notes if verdict else "the verifier gave no verdict")[:400]
        return "failed", _fail(workflow, f"The independent verifier did not pass it: {why}")
    verdict.verifier = ACTOR
    return "completed", _complete(workflow, "Verified and completed by the review autopilot", verdict)


def _fail(workflow: TaskWorkflowService, why: str) -> Apply:
    """Work that failed or cannot be verified leaves the review lane (operator,
    2026-10-15); the dispatcher's capped reconciler retries FAILED tasks."""
    def apply(task: Task) -> None:
        task.error_message = why[:4000]
        workflow.transition(task, TaskStatus.FAILED, actor=ACTOR, message=f"Moved out of review: {why[:300]}")
    return apply


def _failed_verdict_reason(task: Task) -> str:
    v = task.verification
    defects = "; ".join((v.defects_found or [])[:3]) if v else ""
    return f"Verification failed: {defects or (v.notes if v else '') or 'no detail given'}"


def _requeue(workflow: TaskWorkflowService) -> Apply:
    """One fresh run, verified by the agent loop's judge."""
    def apply(task: Task) -> None:
        task.add_log("Review autopilot sent this back for one fresh, verified run", event_type=REQUEUED,
                     actor=ACTOR, task_status=task.status)
        workflow.transition(task, TaskStatus.IN_PROGRESS, actor=ACTOR,
                            message="Re-run requested by the review autopilot", pending_agent_run=True)
    return apply


async def _review_one(task: Task, workflow: TaskWorkflowService,
                      budget: dict[str, int]) -> tuple[str, Apply] | None:
    """The decision on one in-review task, or None to leave it for a later pass.

    Only a verified task is completed; one that failed verification, or still
    cannot be verified after its one fresh run, is moved to FAILED.
    """
    if task.verification is not None and task.verification.passed:
        return "completed", _complete(workflow, "Already verified; completed by the review autopilot")
    if task.verification is not None:
        return "failed", _fail(workflow, _failed_verdict_reason(task))
    if _logged(task, DECLINED):  # left in review by an earlier version of this pass
        return "failed", _fail(workflow, "The verifier could not pass it")
    if _pull_request_linked(task):
        if budget["runs"] <= 0:
            return None
        budget["runs"] -= 1
        return await _verify_run(task, workflow)
    if task.agent_id and not _logged(task, REQUEUED):
        if budget["requeues"] <= 0:
            return None
        budget["requeues"] -= 1
        return "requeued", _requeue(workflow)
    why = "still unverified after a fresh run" if _logged(task, REQUEUED) else "nothing the verifier can check"
    return "failed", _fail(workflow, f"Could not be verified: {why}")


async def _review_pass(store: TaskStore, workflow: TaskWorkflowService, result: AutopilotResult) -> None:
    in_review = await store.list_all(status=TaskStatus.IN_REVIEW, limit=_SCAN)
    budget = {"runs": _RUN_CHECKS_PER_PASS, "requeues": _REQUEUES_PER_PASS}
    for task in in_review:
        if _is_outward_facing(task):
            continue
        try:
            decision = await _review_one(task, workflow, budget)
            if decision and await _save_if_unchanged(store, task, decision[1]):
                setattr(result, decision[0], getattr(result, decision[0]) + 1)
                log.info("Review autopilot: %s %s", decision[0], task.task_id)
        except Exception:
            log.exception("Review autopilot: review decision failed for %s", task.task_id)


async def run_review_autopilot(store: TaskStore | None = None) -> AutopilotResult:
    """One pass over both queues. Never raises."""
    result = AutopilotResult()
    if not enabled():
        return result
    store = store or get_task_store()
    workflow = TaskWorkflowService(store=store)
    for step in (_gate_pass, _review_pass):
        try:
            await step(store, workflow, result)
        except Exception:
            log.exception("Review autopilot: %s failed", step.__name__)
    if result.approved or result.declined or result.completed or result.requeued or result.failed:
        log.info("Review autopilot: approved=%d declined=%d completed=%d requeued=%d failed=%d",
                 result.approved, result.declined, result.completed, result.requeued, result.failed)
    return result


_running: asyncio.Task | None = None


def schedule(store: TaskStore | None = None) -> None:
    """Start a pass in the background unless one is still running.

    Verifying a run can take minutes (E2B, tests, reviewer model); the
    dispatcher must keep picking up tasks meanwhile.
    """
    global _running
    if _running is not None and not _running.done():
        return
    _running = asyncio.get_running_loop().create_task(run_review_autopilot(store))
