"""backend/render_router.py — Render platform view for operators and agents.

Exposes the read-only half of the Render MCP integration
(``packages/integrations/render_mcp.py``) over HTTP so the dashboard, the
Telegram bot, and any agent that reaches the API instead of importing Python
can all see the same production state: services, deploys, platform logs, and
metrics.

Every route is admin-only. Render deploy history and platform logs describe the
whole deployment — including other tenants' service names in a shared workspace
— so they are not per-user data and must not be readable by a signed-in
non-admin.

There is deliberately no write route here. Mutating Render tools stay reachable
only through ``RenderMCPClient`` with ``RENDER_MCP_ALLOW_WRITES`` on, so a
deploy or an env-var change is always a deliberate act rather than one HTTP
call away from any admin session.

Routes (mounted on ``backend.server.app`` via ``build_render_router(get_current_user)``):

  GET /api/render/health                    → MCP reachability + tool count
  GET /api/render/services                  → services in the workspace
  GET /api/render/services/{id}/deploys     → deploy history, newest first
  GET /api/render/services/{id}/logs        → platform logs (level/limit filters)
  GET /api/render/services/{id}/metrics     → performance metrics
  GET /api/render/ops/status                → ops-loop counters
  GET /api/render/ops/scan                  → run one scan now, report findings
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Query

log = logging.getLogger("render_router")

# Metric types the diagnostics endpoint defaults to. Chosen because these four
# are the ones that explain an unexplained restart, which is the question this
# endpoint exists to answer.
DEFAULT_METRICS: tuple[str, ...] = (
    "memory_usage", "memory_limit", "cpu_usage", "instance_count",
)


def _require_admin(user: dict[str, Any] | None) -> dict[str, Any]:
    """Reject anyone who is not the agency admin."""
    if not user or str(user.get("role") or "").strip().lower() != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin-only endpoint — Render platform state is deployment-wide, not per-user.",
        )
    return user


def _unavailable(exc: Exception) -> HTTPException:
    """Map an MCP transport failure onto 503 rather than a 500.

    The distinction matters to the dashboard: 503 means "Render is unreachable,
    retry", 500 would mean "this endpoint is broken".
    """
    return HTTPException(status_code=503, detail=f"Render MCP unavailable: {exc}")


def build_render_router(get_current_user: Callable[..., Any]) -> APIRouter:
    router = APIRouter(prefix="/api/render", tags=["render"])

    @router.get("/health")
    async def render_health(user: dict = Depends(get_current_user)) -> dict:
        """Report whether the agency can currently reach Render over MCP."""
        _require_admin(user)
        from packages.integrations.render_mcp import get_render_mcp
        return await get_render_mcp().health()

    @router.get("/services")
    async def render_services(
        include_previews: bool = Query(default=False),
        user: dict = Depends(get_current_user),
    ) -> dict:
        """List the services visible to the configured Render API key."""
        _require_admin(user)
        from agent.mcp_client import MCPUnavailableError
        from packages.integrations.render_mcp import get_render_mcp
        try:
            services = await get_render_mcp().list_services(include_previews=include_previews)
        except (MCPUnavailableError, RuntimeError) as exc:
            raise _unavailable(exc) from exc
        return {"services": services, "count": len(services)}

    @router.get("/services/{service_id}/deploys")
    async def render_deploys(
        service_id: str,
        limit: int = Query(default=20, ge=1, le=100),
        user: dict = Depends(get_current_user),
    ) -> dict:
        """Return deploy history for a service, newest first."""
        _require_admin(user)
        from agent.mcp_client import MCPUnavailableError
        from packages.integrations.render_mcp import get_render_mcp
        try:
            deploys = await get_render_mcp().list_deploys(service_id)
        except (MCPUnavailableError, RuntimeError) as exc:
            raise _unavailable(exc) from exc
        trimmed = deploys[:limit]
        return {
            "service_id": service_id,
            "deploys": [d.as_dict() for d in trimmed],
            "count": len(trimmed),
        }

    @router.get("/services/{service_id}/logs")
    async def render_logs(
        service_id: str,
        level: str | None = Query(default=None, description="Comma-separated severities"),
        limit: int = Query(default=50, ge=1, le=200),
        user: dict = Depends(get_current_user),
    ) -> dict:
        """Return platform logs for a service.

        These are Render's logs, not this process's — they include build
        output, edge request logs, and anything printed before the app booted.
        """
        _require_admin(user)
        from agent.mcp_client import MCPUnavailableError
        from packages.integrations.render_mcp import get_render_mcp
        levels = [p.strip() for p in (level or "").split(",") if p.strip()] or None
        try:
            entries = await get_render_mcp().list_logs(
                [service_id], level=levels, limit=limit
            )
        except (MCPUnavailableError, RuntimeError) as exc:
            raise _unavailable(exc) from exc
        return {"service_id": service_id, "logs": entries, "count": len(entries)}

    @router.get("/services/{service_id}/metrics")
    async def render_metrics(
        service_id: str,
        metrics: str | None = Query(default=None, description="Comma-separated metric types"),
        user: dict = Depends(get_current_user),
    ) -> dict:
        """Return performance metrics for a service."""
        _require_admin(user)
        from agent.mcp_client import MCPUnavailableError
        from packages.integrations.render_mcp import get_render_mcp
        wanted = [m.strip() for m in (metrics or "").split(",") if m.strip()]
        try:
            payload = await get_render_mcp().get_metrics(
                service_id, wanted or list(DEFAULT_METRICS)
            )
        except (MCPUnavailableError, RuntimeError) as exc:
            raise _unavailable(exc) from exc
        return {"service_id": service_id, "metrics": payload}

    @router.get("/ops/status")
    async def render_ops_status(user: dict = Depends(get_current_user)) -> dict:
        """Counters for the autonomous Render monitoring loop."""
        _require_admin(user)
        from services.render_ops import get_render_ops_monitor
        return get_render_ops_monitor().get_status()

    @router.get("/ops/scan")
    async def render_ops_scan(user: dict = Depends(get_current_user)) -> dict:
        """Run one scan immediately and report what it found.

        Read-only and does not file issues — it answers "what does Render think
        is wrong right now?" without waiting for the next tick or adding to the
        issue backlog. The loop's ``tick()`` is what files.
        """
        _require_admin(user)
        from services.render_ops import get_render_ops_monitor
        monitor = get_render_ops_monitor()
        findings = await monitor.scan()
        return {
            "findings": [f.as_dict() for f in findings],
            "count": len(findings),
            "status": monitor.get_status(),
        }

    return router
