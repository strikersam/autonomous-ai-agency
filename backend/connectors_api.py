"""backend/connectors_api.py — the connector catalogue API (`/api/connectors/*`).

Surfaces ``packages.integrations.connector_registry`` over HTTP so the dashboard
(and, later, workflow steps and agents) can discover connectors and run the
webhook action. Admin-only: a connector reaches out to arbitrary URLs, so it is
deployment-wide platform state, not a per-user feature (rules 8 & 10).

Mounted on ``backend.server.app`` via ``build_connectors_router(get_current_user)``,
following the same builder pattern as ``backend/render_router.py``.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from packages.integrations import connector_registry

log = logging.getLogger("qwen-proxy")


def _require_admin(user: dict[str, Any] | None) -> dict[str, Any]:
    """Reject anyone who is not the agency admin."""
    if not user or str(user.get("role") or "").strip().lower() != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin-only endpoint — connectors reach external services deployment-wide.",
        )
    return user


class WebhookSendRequest(BaseModel):
    """Body for ``POST /api/connectors/webhook/send`` (rule 11 — no raw dict in)."""

    url: str = Field(..., min_length=1, max_length=2048, description="Public HTTPS target URL")
    event: str | None = Field(default=None, max_length=200, description="Event name label")
    payload: dict[str, Any] | None = Field(default=None, description="JSON body to deliver")


def build_connectors_router(get_current_user: Callable[..., Any]) -> APIRouter:
    router = APIRouter(prefix="/api/connectors", tags=["connectors"])

    @router.get("/")
    async def list_connectors(user: dict = Depends(get_current_user)) -> dict:
        """Return the connector catalogue (metadata only, no secrets)."""
        _require_admin(user)
        connectors = connector_registry.list_connectors()
        return {"connectors": connectors, "count": len(connectors)}

    @router.post("/webhook/send")
    async def webhook_send(
        body: WebhookSendRequest,
        user: dict = Depends(get_current_user),
    ) -> dict:
        """Execute the webhook connector: POST a JSON event to a public URL.

        The URL clears the SSRF guard inside ``send_webhook`` (rule 14) before
        the first request; a non-public target returns ``ok: false`` with the
        reason rather than reaching out.
        """
        _require_admin(user)
        result = await connector_registry.send_webhook(
            body.url, body.payload, event=body.event
        )
        return result

    return router
