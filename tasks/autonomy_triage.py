"""tasks/autonomy_triage.py — CEO triage of tasks parked at the approval gate.

The operator wants the agency to keep itself moving and only be asked at merge
time. This pass runs on the dispatcher's cadence and decides, deterministically,
the parked tasks that don't need a human:

* **Approve** a task that was parked only because the dispatcher auto-promoted
  it (``approval_gate_promoted``) and that no longer classifies as outward-facing
  — i.e. PR-only work whose merge is already the human gate.
* **Approve** a trend-scanner code-change task (created gated, 🔴 lane) when
  ``AGENCY_TRIAGE_APPROVE_TRENDS`` is on: the agent only drafts a PR, which
  still waits for a human merge. These were the bulk of the "To be approved"
  lane the operator was left to clear by hand.
* **Reject** a triageable parked task that duplicates an older open task
  (same normalised title) — it would only redo work already queued.

Any other task created with ``requires_approval`` on purpose, and anything
outward-facing (deploy/release/external write), is never touched.

Decisions are rule-based on purpose: approving work must not hinge on a free-tier
LLM's judgement, and every decision is written to the task's execution log.
"""

from __future__ import annotations

import asyncio
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


def _is_trend_code_change(task: Task) -> bool:
    from agent.trend_scoping import TREND_OWNER_ID

    return task.task_type == "trend_scoping" and task.owner_id == TREND_OWNER_ID


def _triage_may_decide(task: Task) -> bool:
    """Whether this parked task is triage's to decide (else it waits for a human)."""
    if _is_outward_facing(task):
        return False
    if _was_auto_promoted(task):
        return True
    from packages.config import settings

    return settings.is_triage_approve_trends_enabled and _is_trend_code_change(task)


async def _open_titles(store: TaskStore) -> dict[str, str]:
    """Normalised title → task_id for tasks already queued to run."""
    pending = await store.list_pending(limit=_SCAN_LIMIT)
    return {_norm_title(t.title): t.task_id for t in pending if _norm_title(t.title)}


async def materialize_portfolio() -> int:
    """Turn the top committed portfolio initiatives into tasks. Never raises.

    The board is rebuilt from live signals in a worker thread — the build is
    synchronous and some signal collectors start their own event loop, which
    must not happen on the dispatcher's loop.
    """
    try:
        from agents.portfolio_api import _materialize_and_log, get_service

        svc = get_service()
        await asyncio.to_thread(svc.ensure_fresh)
        created = await _materialize_and_log(svc)
    except Exception:
        log.exception("Portfolio intake failed")
        return 0
    if created:
        log.info("Portfolio intake: queued %d initiative task(s)", len(created))
    return len(created)


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
            if not _triage_may_decide(task):
                result.left_for_human += 1
                continue
            if key and key in seen and seen[key] != task.task_id:
                workflow.approve_execution(
                    task, actor=TRIAGE_ACTOR, approved=False,
                    reason=f"duplicate of open task {seen[key]}",
                )
                result.rejected += 1
            else:
                workflow.approve_execution(task, actor=TRIAGE_ACTOR, approved=True)
                result.approved += 1
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
