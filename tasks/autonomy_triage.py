"""tasks/autonomy_triage.py — CEO triage of tasks parked at the approval gate.

The operator wants the agency to keep itself moving and only be asked at merge
time. This pass runs on the dispatcher's cadence and decides, deterministically,
the parked tasks that don't need a human:

* **Approve** a task that was parked only because the dispatcher auto-promoted
  it (``approval_gate_promoted``) and that no longer classifies as outward-facing
  — i.e. PR-only work whose merge is already the human gate.
* **Reject** an auto-promoted parked task that duplicates an older open task
  (same normalised title) — it would only redo work already queued.

Tasks created with ``requires_approval`` on purpose (deploys, auth/secrets
changes, trend items in the 🔴 lane) are never touched: those stay with a human.

Decisions are rule-based on purpose: approving work must not hinge on a free-tier
LLM's judgement, and every decision is written to the task's execution log.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from tasks.models import Task
from tasks.service import TaskWorkflowService, _is_outward_facing
from tasks.store import TaskStore, _ts_to_float, get_task_store

log = logging.getLogger("qwen-proxy")

TRIAGE_ACTOR = "system:ceo-triage"
_SCAN_LIMIT = 200


@dataclass
class TriageResult:
    """Counts of the decisions one triage pass made."""

    approved: int = 0
    rejected: int = 0
    left_for_human: int = 0


def _norm_title(title: str) -> str:
    """Lower-case, strip punctuation and long ids/hashes — but keep short
    numbers, so "Fix issue #41" and "Fix issue #42" stay distinct."""
    no_ids = re.sub(r"\b\w*[0-9a-f]{12,}\w*\b|\b\d{6,}\b", " ", (title or "").lower())
    return " ".join(re.sub(r"[^\w]+|_", " ", no_ids).split())


def _was_auto_promoted(task: Task) -> bool:
    return any(e.event_type == "approval_gate_promoted" for e in task.execution_log)


def _auto_approvable(task: Task) -> bool:
    return _was_auto_promoted(task) and not _is_outward_facing(task)


async def _open_titles(store: TaskStore) -> dict[str, str]:
    """Normalised title → task_id for tasks already queued to run."""
    pending = await store.list_pending(limit=_SCAN_LIMIT)
    return {_norm_title(t.title): t.task_id for t in pending if _norm_title(t.title)}


async def triage_gated_tasks(store: TaskStore | None = None) -> TriageResult:
    """Approve or reject parked tasks that don't need a human. Never raises."""
    store = store or get_task_store()
    result = TriageResult()
    try:
        parked = await store.list_awaiting_approval(limit=_SCAN_LIMIT)
        seen = await _open_titles(store)
    except Exception:
        log.exception("CEO triage: could not list parked tasks")
        return result
    workflow = TaskWorkflowService(store=store)
    # Oldest first, so the original survives and later copies are the duplicates.
    for task in sorted(parked, key=lambda t: _ts_to_float(t.created_at)):
        key = _norm_title(task.title)
        try:
            # Only tasks the dispatcher parked on its own are triage's to
            # decide; a deliberately gated task is always left for a human.
            if not _was_auto_promoted(task):
                result.left_for_human += 1
                continue
            if key and key in seen and seen[key] != task.task_id:
                workflow.approve_execution(
                    task, actor=TRIAGE_ACTOR, approved=False,
                    reason=f"duplicate of open task {seen[key]}",
                )
                result.rejected += 1
            elif _auto_approvable(task):
                workflow.approve_execution(task, actor=TRIAGE_ACTOR, approved=True)
                result.approved += 1
            else:
                result.left_for_human += 1
                continue
            await store.update(task)
            if key and task.execution_approved:
                seen.setdefault(key, task.task_id)
        except Exception:
            log.exception("CEO triage: decision failed for task %s", task.task_id)
    if result.approved or result.rejected:
        log.info(
            "CEO triage: approved=%d rejected=%d left_for_human=%d",
            result.approved, result.rejected, result.left_for_human,
        )
    return result
