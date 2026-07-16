"""backend/local_brain_router.py — 3 endpoints for the cross-machine GLM toggle.

Routes:
  GET  /api/local-brain/state     → admin UI; returns desired+heartbeat
  POST /api/local-brain/toggle    → admin UI; updates desired_state (on/off)
  POST /api/local-brain/heartbeat → local daemon; updates last heartbeat

All three are gated on the existing SERVICE_TOKEN via ``require_service_token``.
The dependency is intentionally tight-scoped: a leaked token can only flip
the toggle on/off or spoof heartbeats — it cannot read task data, alter
agent prompts, or hit /admin/api/policy/brain. See service_token.py for the
inline risky-module-review.

Body shapes:

  POST /api/local-brain/toggle body:
    {
      "desired_state":    "on" | "off",       (required)
      "desired_provider": "colibri" | "auto", (optional; inferred from state if absent)
      "machine_id":       "<uuid>" | null,    (optional; pins the operator's machine)
      "actor":            "<string>"          (optional; written to desired_updated_by)
    }
    response: 200 + the full /api/local-brain/state document

  POST /api/local-brain/heartbeat body:
    {
      "machine_id":       "<uuid>",                  (required; identifies the local box)
      "status":           "ok"|"starting"|...",      (required)
      "port_state":       "listening"|"dead"|...,    (required)
      "v1_models":        [{"id": "glm-5.2", ...}],  (optional; from llama-server /v1/models)
      "models_has_glm52": bool,                      (optional; convenience flag — same as
                                                      any(m.get("id")=="glm-5.2" for m in v1_models))
      "error":            "<string>"                 (optional; last failure message)
    }
    response: 200 + the full /api/local-brain/state document

The router is mounted on ``backend.server.app`` as a single include line so
this file stays small and the server-side blast radius is one line.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from packages.auth.service_token import require_service_token
from backend.local_brain_store import LocalBrainStore

log = logging.getLogger("local_brain_router")

router = APIRouter(prefix="/api/local-brain", tags=["local-brain"])

# Singleton store so the admin UI + daemon see the same row across
# endpoint calls within a process. Threading: sqlite is fine for the
# single-row read/write pattern; we don't add a global lock.
_store_singleton: LocalBrainStore | None = None


def _store() -> LocalBrainStore:
    global _store_singleton
    if _store_singleton is None:
        _store_singleton = LocalBrainStore()
    return _store_singleton




class ToggleBody(BaseModel):
    desired_state: str = Field(..., description='"on" or "off"')
    desired_provider: str | None = Field(default=None)
    machine_id: str | None = Field(default=None, max_length=80)
    actor: str | None = Field(default=None, max_length=200)


class HeartbeatBody(BaseModel):
    machine_id: str = Field(..., min_length=1, max_length=80)
    status: str = Field(..., min_length=1, max_length=32)
    port_state: str = Field(default="unknown", min_length=1, max_length=32)
    v1_models: list[dict[str, Any]] | None = Field(default=None)
    models_has_glm52: bool = Field(default=False)
    error: str | None = Field(default=None, max_length=500)


def _validate_state(value: str) -> str:
    v = (value or "").strip().lower()
    if v not in {"on", "off"}:
        raise HTTPException(
            status_code=422,
            detail=f"desired_state must be 'on' or 'off' (got {value!r})",
        )
    return v


@router.get("/state")
async def get_local_brain_state(
    request: Request,
    _: dict[str, str] = Depends(require_service_token),
) -> dict[str, Any]:
    """Return the desired + last-reported state. Admin UI uses this on mount."""
    log.info("local_brain: GET /state")
    return _store().get_state()


@router.post("/toggle")
async def post_local_brain_toggle(
    payload: ToggleBody,
    _: dict[str, str] = Depends(require_service_token),
) -> dict[str, Any]:
    """Flip the operator's intent (on/off) + persist."""
    state = _validate_state(payload.desired_state)
    provider = (
        payload.desired_provider
        or ("colibri" if state == "on" else "auto")
    ).strip()
    if provider not in {"colibri", "auto"}:
        provider = "colibri" if state == "on" else "auto"
    actor_str = (payload.actor or "service:local_daemon")[:200]
    log.info(
        "local_brain: POST /toggle state=%s provider=%s machine_id=%s actor=%s",
        state, provider, payload.machine_id, actor_str,
    )
    new_state = _store().set_desired(
        state=state,
        provider=provider,
        actor=actor_str,
        machine_id=payload.machine_id,
    )
    return new_state


@router.post("/heartbeat")
async def post_local_brain_heartbeat(
    payload: HeartbeatBody,
    _: dict[str, str] = Depends(require_service_token),
) -> dict[str, Any]:
    """Local daemon posts a heartbeat every poll interval."""
    log.info(
        "local_brain: POST /heartbeat machine=%s status=%s port=%s has_glm52=%s",
        payload.machine_id, payload.status, payload.port_state,
        payload.models_has_glm52,
    )
    return _store().record_heartbeat(
        machine_id=payload.machine_id,
        status=payload.status,
        port_state=payload.port_state,
        v1_models=payload.v1_models,
        models_has_glm52=payload.models_has_glm52,
        error=payload.error,
    )
