"""backend/spec_router.py — review/approve persisted plan specifications.

Surfaces the spec artifacts written by ``services/spec_store.py`` (one per
agent plan) so an operator can read the plan the agency intends to execute
and approve or reject it before implementation when
``AGENT_SPEC_APPROVAL_REQUIRED=true``.

Routes (mounted on ``backend.server.app`` via ``build_spec_router(get_current_user)``):

  GET  /api/specs                 → list specs, newest first (optional ?status=)
  GET  /api/specs/{spec_id}       → one spec incl. markdown
  POST /api/specs/{spec_id}/approve
  POST /api/specs/{spec_id}/reject
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Query

log = logging.getLogger("spec_router")


def build_spec_router(get_current_user: Callable[..., Any]) -> APIRouter:
    router = APIRouter(prefix="/api/specs", tags=["specs"])

    @router.get("")
    async def list_spec_artifacts(
        status: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
        user: dict = Depends(get_current_user),
    ) -> dict:
        from services.spec_store import list_specs
        specs = await list_specs(status=status, limit=limit)
        for spec in specs:
            spec.pop("_id", None)
        return {"specs": specs, "count": len(specs)}

    @router.get("/{spec_id}")
    async def get_spec_artifact(spec_id: str, user: dict = Depends(get_current_user)) -> dict:
        from services.spec_store import get_spec
        spec = await get_spec(spec_id)
        if spec is None:
            raise HTTPException(status_code=404, detail="Spec not found")
        spec.pop("_id", None)
        return spec

    async def _decide(spec_id: str, status: str, user: dict) -> dict:
        from services.spec_store import set_spec_status
        decided_by = str(user.get("email") or user.get("id") or "operator")
        spec = await set_spec_status(spec_id, status, decided_by=decided_by)
        if spec is None:
            raise HTTPException(status_code=404, detail="Spec not found")
        spec.pop("_id", None)
        # Never log the operator's email/id (AGENTS.md logging rule) — the
        # actor is already durably recorded on the spec doc itself
        # (`decided_by`), retrievable via GET /api/specs/{spec_id} by an
        # authorized caller, which is the right audit surface for identity.
        log.info("Spec %s decided: %s", spec_id, status)
        return spec

    @router.post("/{spec_id}/approve")
    async def approve_spec(spec_id: str, user: dict = Depends(get_current_user)) -> dict:
        return await _decide(spec_id, "approved", user)

    @router.post("/{spec_id}/reject")
    async def reject_spec(spec_id: str, user: dict = Depends(get_current_user)) -> dict:
        return await _decide(spec_id, "rejected", user)

    return router
