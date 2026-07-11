"""tasks/portfolio_intake.py — Portfolio initiative → Task materializer.

Converts committed portfolio initiatives into actionable tasks on the board,
idempotently. Mirrors the structure of tasks/issue_intake.py.

Key design decisions:
  - **Content-derived source_id**: initiative UUIDs regenerate on every
    portfolio rebuild, so we hash (source|title) for a stable key.
  - **Idempotent**: checks store.find_by_source_id() before creating.
  - **Capped**: at most 3 tasks per refresh (PORTFOLIO_MATERIALIZE_MAX).
  - **Flag-gated**: PORTFOLIO_MATERIALIZE_ENABLED (default true).
"""
from __future__ import annotations

import hashlib
import logging
import os
from typing import Any

from tasks.models import Task, TaskPriority

log = logging.getLogger("qwen-proxy")

# Cap: max tasks per refresh cycle
_PORTFOLIO_MATERIALIZE_MAX = int(os.environ.get("PORTFOLIO_MATERIALIZE_MAX", "3"))

# Flag: default ON (read from the canonical config module)
def _portfolio_materialize_enabled() -> bool:
    try:
        from packages.config import settings
        return settings.portfolio_materialize_enabled == "true"
    except Exception:
        return True  # fail-open


def portfolio_source_id(initiative: Any) -> str:
    """Content-derived stable id for a portfolio initiative.

    Initiative UUIDs regenerate on every rebuild, so we hash the
    source + title for a key that survives rebuilds.
    """
    source = getattr(initiative, "source", "manual") or "manual"
    title = (getattr(initiative, "title", "") or "").strip().lower()
    digest = hashlib.sha1(f"{source}|{title}".encode()).hexdigest()[:16]
    return f"portfolio:{digest}"


def map_initiative_to_task(initiative: Any) -> Task:
    """Build a Task from a portfolio Initiative dataclass."""
    title = getattr(initiative, "title", "Portfolio initiative")
    description = getattr(initiative, "description", "") or ""
    horizon = getattr(initiative, "horizon", None)
    horizon_val = horizon.value if hasattr(horizon, "value") else str(horizon or "unscheduled")
    source = getattr(initiative, "source", "manual") or "manual"
    wsjf = getattr(initiative, "wsjf", 0.0)
    if callable(wsjf):
        try:
            wsjf = wsjf()
        except Exception:
            wsjf = 0.0

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
        title=f"[portfolio] {title[:80]}",
        description=f"Portfolio initiative: {title}",
        prompt=prompt[:4000],
        task_type="portfolio_initiative",
        priority=TaskPriority.HIGH if horizon_val == "now" else TaskPriority.MEDIUM,
        tags=["portfolio", horizon_val, source],
        source="portfolio",
        source_id=portfolio_source_id(initiative),
        pending_agent_run=True,
    )


async def materialize_committed(
    portfolio: Any,
    *,
    store: Any = None,
    cap: int = _PORTFOLIO_MATERIALIZE_MAX,
) -> list[Task]:
    """Materialize committed portfolio initiatives into tasks.

    Takes initiatives from PortfolioManager.allocate_capacity() committed set
    with status in {PROPOSED, APPROVED} and source != "pr" (open PRs are
    already in-flight work), orders by WSJF desc, caps at `cap`, and checks
    store.find_by_source_id() before creating → fully idempotent.

    Returns the list of newly created tasks (empty if all already tracked).
    """
    if not _portfolio_materialize_enabled():
        log.debug("portfolio_intake: materialize disabled (PORTFOLIO_MATERIALIZE_ENABLED=false)")
        return []

    if store is None:
        from tasks.store import get_task_store
        store = get_task_store()

    # Get committed initiatives from the portfolio
    try:
        allocation = portfolio.allocate_capacity(capacity=20)
        committed = allocation.committed
    except Exception:
        # Fallback: use all initiatives directly
        committed = list(getattr(portfolio, "_initiatives", {}).values())

    # Filter: status in {PROPOSED, APPROVED}, source != "pr"
    # Tolerant of both InitiativeStatus enum values and plain strings —
    # tests pass strings, production passes enums. Compare by .value when
    # the status is an enum, by raw string otherwise.
    from agents.portfolio import InitiativeStatus
    _eligible_status_values = {
        InitiativeStatus.PROPOSED.value,
        InitiativeStatus.APPROVED.value,
    }

    def _status_value(s: Any) -> str:
        """Normalise a status to its string value (enum or raw string)."""
        if hasattr(s, "value"):
            return str(s.value)
        return str(s)

    eligible = [
        i for i in committed
        if _status_value(i.status) in _eligible_status_values
        and getattr(i, "source", "") != "pr"
    ]

    # Sort by WSJF descending
    def _wsjf(i):
        w = getattr(i, "wsjf", 0.0)
        return w() if callable(w) else w
    eligible.sort(key=_wsjf, reverse=True)

    # Cap
    eligible = eligible[:cap]

    # Create tasks (idempotent via source_id)
    from tasks.service import TaskWorkflowService
    wf = TaskWorkflowService(store=store)
    created: list[Task] = []

    for initiative in eligible:
        sid = portfolio_source_id(initiative)
        existing = await store.find_by_source_id(sid)
        if existing is not None:
            continue  # Already tracked

        task = map_initiative_to_task(initiative)
        await wf.create_task(task, actor="system:portfolio_intake")
        created.append(task)
        log.info("portfolio_intake: created task %s for initiative '%s' (wsjf=%.2f)",
                 task.task_id, initiative.title[:40], _wsjf(initiative))

    if created:
        log.info("portfolio_intake: materialized %d task(s) from %d eligible initiative(s)",
                 len(created), len(eligible))

    return created
