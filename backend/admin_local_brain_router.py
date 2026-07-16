"""backend/admin_local_brain_router.py — admin-session proxy for the local-brain toggle.

Mirrors the surface of ``backend.local_brain_router`` (``GET /state`` +
``POST /toggle``) but gates on the admin's real session cookie instead of
``SERVICE_TOKEN``. The SERVICE_TOKEN endpoints stay live because
``scripts/local_controller.py`` (running on the operator's machine) posts
heartbeats with that token — the browser must never see it.

Why a separate router and not a simpler rewrite of the SERVICE_TOKEN route:

- The toggle is operator-only. ``SERVICE_TOKEN`` is a 32-byte machine secret
  that powers a single capability ("flip this one bool") while admin-session
  auth already exists for everything else, with proper RBAC + 401/403
  semantics. Splitting them keeps the trust boundaries honest — a leaked
  ``SERVICE_TOKEN`` cannot read task data, alter the brain config, or hit
  any ``/admin/*`` route.
- Admin-session auth works through the Cloudflare Worker without CORS
  faff because same-origin cookies cross automatically. ``SERVICE_TOKEN``
  would have to round-trip the secret through the browser, which fails the
  ``risky-module-review`` for ``backend/local_brain_router.py``.

Routes (mounted on ``backend.server.app`` via ``build_admin_local_brain_router(get_current_user)``):

  GET  /admin/api/local-brain/state   → admin UI; same body shape as SERVICE_TOKEN route
  POST /admin/api/local-brain/toggle  → admin UI; body same as SERVICE_TOKEN route

Both routes return ``LocalBrainStore.get_state()`` / ``set_desired()`` output
verbatim — ``frontend/src/v5/components/LocalBrainToggleCard.jsx`` already
expects this shape.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

log = logging.getLogger("admin_local_brain_router")

_VALID_DESIRED = frozenset({"on", "off"})


class ToggleBody(BaseModel):
    desired_state: str = Field(..., description='"on" or "off"')
    desired_provider: str | None = Field(default=None, max_length=64)
    machine_id: str | None = Field(default=None, max_length=80)
    actor: str | None = Field(default=None, max_length=200)


_store_singleton: LocalBrainStore | None = None


def _store():
    global _store_singleton
    if _store_singleton is None:
        from backend.local_brain_store import LocalBrainStore
        _store_singleton = LocalBrainStore()
    return _store_singleton


def _require_admin(user: dict[str, Any] | None) -> dict[str, Any]:
    if not user or str(user.get("role") or "").strip().lower() != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin-only endpoint — sign in as the agency admin to flip the local-brain toggle.",
        )
    return user


def build_admin_local_brain_router(get_current_user_dep: Callable[..., Any]) -> APIRouter:
    """Construct a ready-to-mount APIRouter with the auth dependency baked in.

    The include_router site in ``backend/server.py`` calls this with the
    production ``get_current_user`` dependency. Tests pass a fake async dep
    via FastAPI's ``dependency_overrides`` keyed on this very callable.
    """
    r = APIRouter(prefix="/admin/api/local-brain", tags=["admin-local-brain"])

    @r.get("/state")
    async def get_admin_local_brain_state(
        user: dict[str, Any] = Depends(get_current_user_dep),
    ) -> dict[str, Any]:
        _require_admin(user)
        log.info(
            "admin_local_brain: GET /state actor=%s",
            user.get("email") or "unknown",
        )
        return _store().get_state()

    @r.post("/toggle")
    async def post_admin_local_brain_toggle(
        payload: ToggleBody,
        user: dict[str, Any] = Depends(get_current_user_dep),
    ) -> dict[str, Any]:
        _require_admin(user)
        state = (payload.desired_state or "").strip().lower()
        if state not in _VALID_DESIRED:
            raise HTTPException(
                status_code=422,
                detail="desired_state must be 'on' or 'off'",
            )
        provider = (
            (payload.desired_provider or "").strip()
            or ("colibri" if state == "on" else "auto")
        )
        actor_str = (
            payload.actor
            or user.get("email")
            or "admin"
        )[:200]
        log.info(
            "admin_local_brain: POST /toggle state=%s provider=%s machine_id=%s actor=%s",
            state, provider, payload.machine_id, actor_str,
        )
        return _store().set_desired(
            state=state,
            provider=provider,
            actor=actor_str,
            machine_id=payload.machine_id,
        )

    return r
