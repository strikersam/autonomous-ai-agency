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
    """Reject non-admin callers for routes that spend provider budget."""
    role = str((user or {}).get("role") or "").strip().lower()
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")


def build_ceo_router(get_current_user: Callable[..., Any]) -> APIRouter:
    router = APIRouter(prefix="/api/ceo", tags=["ceo"])

    @router.get("/status")
    async def ceo_status(user: dict = Depends(get_current_user)) -> dict:
        """Supervisor state plus ledger aggregates."""
        from services.ceo_ledger import get_ceo_ledger
        from services.ceo_micromanager import TIER_LADDER, get_config
        from services.ceo_supervisor import get_ceo_supervisor, supervisor_enabled

        config = get_config()
        return {
            "supervisor": {
                "enabled": supervisor_enabled(),
                **get_ceo_supervisor().get_status(),
            },
            "ledger": get_ceo_ledger().stats(),
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
        from services.ceo_ledger import get_ceo_ledger

        ledger = get_ceo_ledger()
        goals = (
            ledger.open_goals(limit=limit)
            if (state or "").strip().lower() == "open"
            else ledger.recent(limit=limit)
        )
        if state and state.strip().lower() != "open":
            goals = [g for g in goals if g.state == state.strip().lower()]
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
        from services.ceo_ledger import get_ceo_ledger

        goal = get_ceo_ledger().get(goal_id)
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
        from services.ceo_ledger import get_ceo_ledger
        from services.ceo_supervisor import get_ceo_supervisor

        ledger = get_ceo_ledger()
        goal = ledger.get(goal_id)
        if goal is None:
            raise HTTPException(status_code=404, detail="Goal not found")
        supervisor = get_ceo_supervisor()
        if goal.interventions >= supervisor.config.max_interventions:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Goal has spent its intervention budget "
                    f"({goal.interventions}/{supervisor.config.max_interventions})"
                ),
            )
        if goal_id in supervisor._driving:
            raise HTTPException(status_code=409, detail="Goal is already being re-driven")
        supervisor._spawn_redrive(ledger, goal)
        return {"goal_id": goal_id, "interventions": goal.interventions, "status": "redriving"}

    return router
