"""backend/ceo_router.py — observability and manual control for the CEO.

Surfaces what the CEO is driving so an operator can answer the question the
dashboard could not previously answer: *is the agency actually finishing
anything, or does it just look busy?* The ledger holds the honest record —
every goal, every subtask, every attempt, and every quality verdict — and these
routes read it.

Routes (mounted on ``backend.server.app`` via ``build_ceo_router(get_current_user)``):

  GET  /api/ceo/status            → supervisor state + ledger aggregate counts
  GET  /api/ceo/goals             → recent goals, newest first (optional ?state=)
  GET  /api/ceo/goals/{goal_id}   → one goal with its full subtask history
  POST /api/ceo/sweep             → run one supervision sweep now (admin)
  POST /api/ceo/goals/{goal_id}/redrive → force a re-drive of one goal (admin)

The two POST routes are admin-only: both start real agent work, which costs
provider tokens, so they are not something any authenticated reader should be
able to trigger.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Query

log = logging.getLogger("ceo_router")


def _require_admin(user: dict) -> None:
    """Reject non-admin callers for routes that spend provider budget.

    Delegates to ``backend.company_api._is_admin`` — the backend app's single
    role-tag authority — rather than comparing the role string here, so this
    router cannot drift into a second, subtly different admin rule. (The
    ``_get_admin_identity_from_request`` helper belongs to ``proxy.py``, a
    different app with a different auth model; it is not importable here.)
    """
    from backend.company_api import _is_admin

    if not user or not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin role required")


def build_ceo_router(get_current_user: Callable[..., Any]) -> APIRouter:
    router = APIRouter(prefix="/api/ceo", tags=["ceo"])

    @router.get("/status")
    async def ceo_status(user: dict = Depends(get_current_user)) -> dict:
        """Supervisor state plus ledger aggregates."""
        from fastapi.concurrency import run_in_threadpool

        from services.ceo_ledger import get_ceo_ledger
        from services.ceo_micromanager import TIER_LADDER, get_config
        from services.ceo_supervisor import get_ceo_supervisor, supervisor_enabled

        config = get_config()
        # CEOLedger is deliberately synchronous (it is written from the
        # supervisor's background context too), so its SQLite/Mongo calls must
        # not run inline on the event loop.
        stats = await run_in_threadpool(get_ceo_ledger().stats)
        return {
            "supervisor": {
                "enabled": supervisor_enabled(),
                **get_ceo_supervisor().get_status(),
            },
            "ledger": stats,
            "micromanager": {
                "tier_ladder": [t.value for t in TIER_LADDER],
                "max_subtasks": config.max_subtasks,
                "max_attempts_per_subtask": config.max_attempts_per_subtask,
                "escalation_enabled": config.escalation_enabled,
                "llm_decomposition": config.llm_decomposition,
                "require_tests_for_code": config.require_tests_for_code,
            },
        }

    @router.get("/goals")
    async def list_goals(
        state: str | None = Query(default=None),
        limit: int = Query(default=25, ge=1, le=200),
        user: dict = Depends(get_current_user),
    ) -> dict:
        """Recent goals, newest first. ``?state=open`` returns only open ones."""
        from fastapi.concurrency import run_in_threadpool

        from services.ceo_ledger import get_ceo_ledger

        ledger = get_ceo_ledger()
        wanted = (state or "").strip().lower()
        if wanted == "open":
            goals = await run_in_threadpool(ledger.open_goals, limit=limit)
        elif wanted:
            # Filtering after a LIMIT silently under-reports: ?state=abandoned
            # could return nothing while abandoned goals sat just outside the
            # newest-N window. Over-fetch, filter, then slice.
            candidates = await run_in_threadpool(ledger.recent, limit=max(limit * 10, 200))
            goals = [g for g in candidates if g.state == wanted][:limit]
        else:
            goals = await run_in_threadpool(ledger.recent, limit=limit)
        # Subtask histories are large; the list view returns headline fields
        # only, and the detail route carries the attempts.
        summaries = []
        for g in goals:
            d = g.as_dict()
            d.pop("subtasks", None)
            d.pop("request", None)
            summaries.append(d)
        return {"goals": summaries, "count": len(summaries)}

    @router.get("/goals/{goal_id}")
    async def get_goal(goal_id: str, user: dict = Depends(get_current_user)) -> dict:
        """One goal with its full subtask and attempt history."""
        from fastapi.concurrency import run_in_threadpool

        from services.ceo_ledger import get_ceo_ledger

        goal = await run_in_threadpool(get_ceo_ledger().get, goal_id)
        if goal is None:
            raise HTTPException(status_code=404, detail="Goal not found")
        return goal.as_dict()

    @router.post("/sweep")
    async def run_sweep(user: dict = Depends(get_current_user)) -> dict:
        """Run one supervision sweep immediately instead of waiting for the cadence."""
        _require_admin(user)
        from services.ceo_supervisor import get_ceo_supervisor

        report = await get_ceo_supervisor().sweep()
        log.info("CEO sweep triggered manually: %s", report.as_dict())
        return report.as_dict()

    @router.post("/goals/{goal_id}/redrive")
    async def redrive_goal(goal_id: str, user: dict = Depends(get_current_user)) -> dict:
        """Force a re-drive of one goal, bypassing the stall threshold.

        The intervention budget still applies — a goal that has spent it is
        refused rather than re-driven, so the manual route cannot be used to
        loop a permanently broken goal.
        """
        _require_admin(user)
        from fastapi.concurrency import run_in_threadpool

        from services.ceo_ledger import get_ceo_ledger
        from services.ceo_supervisor import get_ceo_supervisor

        ledger = get_ceo_ledger()
        goal = await run_in_threadpool(ledger.get, goal_id)
        if goal is None:
            raise HTTPException(status_code=404, detail="Goal not found")
        supervisor = get_ceo_supervisor()
        # request_redrive keeps the budget check and the in-flight claim
        # together, so this route cannot bypass either by construction.
        if supervisor.is_driving(goal_id):
            raise HTTPException(status_code=409, detail="Goal is already being re-driven")
        if not supervisor.request_redrive(goal, ledger):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Goal has spent its intervention budget "
                    f"({goal.interventions}/{supervisor.config.max_interventions})"
                ),
            )
        return {"goal_id": goal_id, "interventions": goal.interventions, "status": "redriving"}

    return router
