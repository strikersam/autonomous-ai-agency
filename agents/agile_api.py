"""REST endpoints for agile sprint management.

Uses the process-wide AgileManager singleton from services/skill_bindings.py
so sprint state accumulates across requests.

NOTE: Sprint data is in-memory only — restarts reset sprint state.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

log = logging.getLogger("qwen-proxy")

agile_router = APIRouter(prefix="/api/agile", tags=["agile"])


def _get_mgr() -> Any:
    from services.skill_bindings import _get_agile_manager
    return _get_agile_manager()


async def _require_auth(request: Request) -> Any:
    user = getattr(request.state, "user", None)
    if user is not None:
        return user
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth[:7].lower() == "bearer " else request.headers.get("x-api-key", "").strip()
    if token:
        try:
            from tokens import verify_token
            payload = verify_token(token, token_type="access")  # nosec B106
            if payload:
                return payload
        except Exception:  # nosec B110
            pass
    raise HTTPException(status_code=401, detail="Not authenticated")


def _sprint_to_dict(sprint: Any) -> dict[str, Any]:
    from agents.agile_sprints import SprintStatus
    metrics = sprint.get_metrics()
    return {
        "sprint_id": sprint.sprint_id,
        "name": sprint.name,
        "goal": sprint.goal,
        "status": sprint.status.value,
        "start_date": sprint.start_date.isoformat() if sprint.start_date else None,
        "end_date": sprint.end_date.isoformat() if sprint.end_date else None,
        "story_count": sprint.story_count,
        "scope_added": sprint.scope_added,
        "metrics": {
            "total_points": metrics.total_points,
            "completed_points": metrics.completed_points,
            "health": metrics.health.value,
            "days_remaining": round(metrics.days_remaining, 1),
            "completion_percentage": round(metrics.completion_percentage, 1),
            "burndown_rate": round(metrics.burndown_rate, 2),
        },
    }


# ── Request schemas ─────────────────────────────────────────────────────────

class SprintCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    goal: str = Field(default="", max_length=1000)


class SprintStartRequest(BaseModel):
    duration_days: int = Field(default=14, ge=1, le=90)


# ── Endpoints ───────────────────────────────────────────────────────────────

@agile_router.get("/sprints")
async def list_sprints() -> dict[str, Any]:
    mgr = _get_mgr()
    sprints = list(mgr._sprints.values())
    return {"ok": True, "data": [_sprint_to_dict(s) for s in sprints]}


@agile_router.post("/sprints", status_code=201)
async def create_sprint(body: SprintCreateRequest, _user: Any = Depends(_require_auth)) -> dict[str, Any]:
    mgr = _get_mgr()
    sprint = mgr.create_sprint(name=body.name, goal=body.goal)
    return {"ok": True, "data": _sprint_to_dict(sprint)}


@agile_router.post("/sprints/{sprint_id}/start")
async def start_sprint(sprint_id: str, body: SprintStartRequest = SprintStartRequest(), _user: Any = Depends(_require_auth)) -> dict[str, Any]:
    mgr = _get_mgr()
    sprint = mgr.get_sprint(sprint_id)
    if sprint is None:
        raise HTTPException(status_code=404, detail="Sprint not found")
    try:
        sprint.start(duration_days=body.duration_days)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "data": _sprint_to_dict(sprint)}


@agile_router.post("/sprints/{sprint_id}/complete")
async def complete_sprint(sprint_id: str, _user: Any = Depends(_require_auth)) -> dict[str, Any]:
    mgr = _get_mgr()
    sprint = mgr.get_sprint(sprint_id)
    if sprint is None:
        raise HTTPException(status_code=404, detail="Sprint not found")
    try:
        metrics = sprint.complete()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "ok": True,
        "data": {
            "sprint": _sprint_to_dict(sprint),
            "metrics": {
                "total_points": metrics.total_points,
                "completed_points": metrics.completed_points,
                "completion_percentage": round(metrics.completion_percentage, 1),
            },
        },
    }


@agile_router.get("/velocity")
async def get_velocity() -> dict[str, Any]:
    from agents.agile_sprints import SprintStatus
    mgr = _get_mgr()
    predicted = mgr.predicted_velocity()
    history = []
    for sprint in mgr._sprints.values():
        if sprint.status == SprintStatus.COMPLETED and sprint._historical_velocity:
            history.append({
                "sprint_id": sprint.sprint_id,
                "name": sprint.name,
                "velocity": sprint._historical_velocity[-1],
            })
    return {
        "ok": True,
        "data": {
            "predicted_velocity": round(predicted, 1),
            "sprint_count": mgr.sprint_count,
            "history": history,
        },
    }
