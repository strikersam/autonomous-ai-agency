"""tasks/portfolio_intake.py — Portfolio initiative → Task materializer.

Converts committed portfolio initiatives into actionable tasks on the board,
idempotently. Mirrors the structure of tasks/issue_intake.py.

Key design decisions:
  - **One identity per initiative: its normalised title.** The board builder
    (``agents.portfolio_intelligence``) already de-duplicates signals by
    ``_norm_title``; the materializer keys tasks the same way. The previous key
    hashed ``source|title``, so when the winning signal for a title flipped
    between rebuilds (a bug-log row vs a GitHub issue, a trend's relevance) the
    same work got a second task.
  - **Matched against the task store by title, not only by source_id**, so
    tasks created under the old key — and a DONE task whose initiative signal
    is still open — are recognised instead of re-created.
  - **Task state flows back to the board.** Initiatives are rebuilt from
    signals as PROPOSED on every refresh; ``sync_initiative_status`` marks the
    ones whose task finished DONE (hidden from the queue) or in-flight
    IN_PROGRESS, so the portfolio queue actually drains.
  - **Duplicates are cleaned up**: open duplicates are closed WONT_DO and
    finished duplicates are deleted, keeping one task per initiative.
  - **Capped**: at most PORTFOLIO_MATERIALIZE_MAX tasks per pass.
  - **Flag-gated**: PORTFOLIO_MATERIALIZE_ENABLED (default true).
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any

from tasks.models import Task, TaskPriority, TaskStatus

log = logging.getLogger("qwen-proxy")

_TITLE_PREFIX = "[portfolio] "
_INDEX_SCAN_LIMIT = 5000
_ACTIVE = {
    TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.IN_REVIEW,
    TaskStatus.BLOCKED, TaskStatus.NEEDS_CLARIFICATION,
}
_DEDUPE_ACTOR = "system:portfolio_intake"


def _portfolio_materialize_enabled() -> bool:
    try:
        from packages.config import settings
        return settings.portfolio_materialize_enabled == "true"
    except Exception:
        return True  # fail-open


def portfolio_key(title: str) -> str:
    """Normalised identity of an initiative or portfolio task title."""
    from agents.portfolio_intelligence import _norm_title

    raw = (title or "").strip()
    if raw.lower().startswith(_TITLE_PREFIX):
        raw = raw[len(_TITLE_PREFIX):]
    return _norm_title(raw)


def portfolio_source_id(initiative: Any) -> str:
    """Stable id for a portfolio initiative, independent of which signal won."""
    key = portfolio_key(getattr(initiative, "title", "") or "")
    digest = hashlib.sha1(
        key.encode(),
        usedforsecurity=False,  # noqa: B324 — content fingerprint, not security
    ).hexdigest()[:16]
    return f"portfolio:{digest}"


def map_initiative_to_task(initiative: Any) -> Task:
    """Build a Task from a portfolio Initiative dataclass."""
    title = getattr(initiative, "title", "Portfolio initiative")
    description = getattr(initiative, "description", "") or ""
    horizon = getattr(initiative, "horizon", None)
    horizon_val = horizon.value if hasattr(horizon, "value") else str(horizon or "unscheduled")
    source = getattr(initiative, "source", "manual") or "manual"
    wsjf = _wsjf(initiative)

    prompt = (
        f"## Portfolio Initiative: {title}\n\n"
        f"**Horizon:** {horizon_val}\n"
        f"**Source:** {source}\n"
        f"**WSJF Score:** {wsjf:.2f}\n\n"
        f"**Description:**\n{description}\n\n"
        f"Implement this initiative. Break it down into concrete steps and execute."
    )

    return Task(
        owner_id="system",
        title=f"{_TITLE_PREFIX}{title[:80]}",
        description=f"Portfolio initiative: {title}",
        prompt=prompt[:4000],
        task_type="portfolio_initiative",
        priority=TaskPriority.HIGH if horizon_val == "now" else TaskPriority.MEDIUM,
        tags=["portfolio", horizon_val, source],
        source="portfolio",
        source_id=portfolio_source_id(initiative),
        pending_agent_run=True,
    )


def _wsjf(initiative: Any) -> float:
    w = getattr(initiative, "wsjf", 0.0)
    try:
        return float(w() if callable(w) else w)
    except Exception:
        return 0.0


def _status_value(s: Any) -> str:
    """Normalise a status to its string value (enum or raw string)."""
    return str(s.value) if hasattr(s, "value") else str(s)


async def portfolio_task_index(store: Any) -> dict[str, list[Task]]:
    """All portfolio tasks in the store, grouped by initiative key (oldest first)."""
    from tasks.store import _ts_to_float

    tasks = await store.list_all(limit=_INDEX_SCAN_LIMIT, include_log=False)
    index: dict[str, list[Task]] = {}
    for task in tasks:
        if task.source != "portfolio":
            continue
        key = portfolio_key(task.title)
        if key:
            index.setdefault(key, []).append(task)
    for group in index.values():
        group.sort(key=lambda t: _ts_to_float(t.created_at))
    return index


def _keeper(group: list[Task]) -> Task:
    """The one task to keep for an initiative: first DONE, else first active, else newest."""
    for status_set in ({TaskStatus.DONE}, _ACTIVE):
        for task in group:
            if task.status in status_set:
                return task
    return group[-1]


@dataclass
class DedupeResult:
    closed: int = 0
    deleted: int = 0


async def dedupe_portfolio_tasks(index: dict[str, list[Task]], store: Any) -> DedupeResult:
    """Keep one task per initiative: close open duplicates, delete finished ones.

    A duplicate that is mid-run (IN_PROGRESS) is left alone — it is closed on a
    later pass once it settles. Mutates *index* so each group holds only the
    keeper and anything still running.
    """
    from tasks.service import TaskWorkflowService

    workflow = TaskWorkflowService(store=store)
    result = DedupeResult()
    for key, group in index.items():
        if len(group) < 2:
            continue
        keep = _keeper(group)
        survivors = [keep]
        for task in group:
            if task.task_id == keep.task_id:
                continue
            try:
                if task.status in {TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.WONT_DO}:
                    await store.delete(task.task_id)
                    result.deleted += 1
                elif task.status is TaskStatus.IN_PROGRESS:
                    survivors.append(task)
                else:
                    full = await store.get(task.task_id) or task
                    workflow.transition(
                        full, TaskStatus.WONT_DO, actor=_DEDUPE_ACTOR,
                        message=f"Duplicate of portfolio task {keep.task_id}; closed.",
                    )
                    await store.update(full)
                    result.closed += 1
            except Exception:
                log.exception("portfolio dedupe: could not retire duplicate %s", task.task_id)
                survivors.append(task)
        index[key] = survivors
    if result.closed or result.deleted:
        log.info("portfolio dedupe: closed %d open and deleted %d finished duplicate task(s)",
                 result.closed, result.deleted)
    return result


def sync_initiative_status(portfolio: Any, index: dict[str, list[Task]]) -> int:
    """Reflect task state onto initiatives so the board queue drains. Returns changes.

    DONE task → initiative DONE (dropped from the queue); open task →
    IN_PROGRESS; only declined (WONT_DO) tasks → CANCELLED. FAILED-only
    initiatives stay as they are and are retried by :func:`retry_failed`.
    """
    from agents.portfolio import InitiativeStatus

    changed = 0
    for initiative in getattr(portfolio, "_initiatives", {}).values():
        group = index.get(portfolio_key(getattr(initiative, "title", "")))
        if not group:
            continue
        statuses = {t.status for t in group}
        if TaskStatus.DONE in statuses:
            new = InitiativeStatus.DONE
        elif statuses & _ACTIVE:
            new = InitiativeStatus.IN_PROGRESS
        elif statuses == {TaskStatus.WONT_DO}:
            new = InitiativeStatus.CANCELLED
        else:
            continue
        if _status_value(initiative.status) != new.value:
            initiative.status = new
            changed += 1
    return changed


async def retry_failed(index: dict[str, list[Task]], store: Any, *, max_retries: int) -> int:
    """Re-queue a portfolio initiative whose only task FAILED, up to *max_retries* times."""
    from tasks.service import TaskWorkflowService

    workflow = TaskWorkflowService(store=store)
    retried = 0
    for group in index.values():
        if {t.status for t in group} != {TaskStatus.FAILED}:
            continue
        task = group[-1]
        if task.auto_retry_count >= max_retries:
            continue
        full = await store.get(task.task_id)
        if full is None:
            continue
        try:
            workflow.transition(full, TaskStatus.TODO, actor=_DEDUPE_ACTOR,
                                message="Portfolio work is not finished — retrying.")
            full.auto_retry_count += 1
            await store.update(full)
            task.status = TaskStatus.TODO
            retried += 1
        except Exception:
            log.exception("portfolio retry: could not re-queue %s", task.task_id)
    return retried


async def materialize_committed(
    portfolio: Any,
    *,
    store: Any = None,
    cap: int | None = None,
) -> list[Task]:
    """Materialize committed portfolio initiatives into tasks.

    Cleans duplicates, syncs task state back onto the initiatives, retries
    failed ones, then queues the top-WSJF eligible initiatives (PROPOSED /
    APPROVED, not an open PR, no task yet). Returns the newly created tasks.
    """
    if not _portfolio_materialize_enabled():
        log.debug("portfolio_intake: materialize disabled (PORTFOLIO_MATERIALIZE_ENABLED=false)")
        return []

    from packages.config import settings
    if cap is None:
        cap = settings.portfolio_materialize_max
    if store is None:
        from tasks.store import get_task_store
        store = get_task_store()

    index = await portfolio_task_index(store)
    await dedupe_portfolio_tasks(index, store)
    await retry_failed(index, store, max_retries=settings.portfolio_retry_max)
    sync_initiative_status(portfolio, index)

    try:
        committed = portfolio.allocate_capacity(capacity=20).committed
    except Exception:
        committed = list(getattr(portfolio, "_initiatives", {}).values())

    from agents.portfolio import InitiativeStatus
    eligible_status = {InitiativeStatus.PROPOSED.value, InitiativeStatus.APPROVED.value}
    eligible = [
        i for i in committed
        if _status_value(i.status) in eligible_status
        and getattr(i, "source", "") != "pr"
        and portfolio_key(i.title) not in index
    ]
    eligible.sort(key=_wsjf, reverse=True)

    from tasks.service import TaskWorkflowService
    wf = TaskWorkflowService(store=store)
    created: list[Task] = []
    for initiative in eligible[:cap]:
        if await store.find_by_source_id(portfolio_source_id(initiative)) is not None:
            continue
        task = map_initiative_to_task(initiative)
        await wf.create_task(task, actor="system:portfolio_intake")
        created.append(task)
        index[portfolio_key(initiative.title)] = [task]
        initiative.status = InitiativeStatus.IN_PROGRESS
        log.info("portfolio_intake: created task %s for initiative '%s' (wsjf=%.2f)",
                 task.task_id, initiative.title[:40], _wsjf(initiative))

    if created:
        log.info("portfolio_intake: materialized %d task(s) from %d eligible initiative(s)",
                 len(created), len(eligible))
    return created


async def sync_board_status(portfolio: Any, *, store: Any = None) -> int:
    """Read-only: reflect task state onto the board without creating tasks."""
    if store is None:
        from tasks.store import get_task_store
        store = get_task_store()
    return sync_initiative_status(portfolio, await portfolio_task_index(store))
