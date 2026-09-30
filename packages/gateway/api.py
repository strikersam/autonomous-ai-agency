"""packages/gateway/api.py — gateway HTTP surface.

``GET /gateway/metrics`` serves the shared Prometheus registry as text. It is
authenticated with the proxy's ``verify_api_key`` dependency, which lives in
``proxy.py``; that module imports this one, so the dependency is injected by
:func:`build_router` rather than imported here.
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from packages.gateway import config
from packages.llm.metrics import get_metrics

PROMETHEUS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


def build_router(auth_dependency: Callable[..., Any]) -> APIRouter:
    """Build the gateway router, guarded by *auth_dependency*."""
    router = APIRouter()

    @router.get("/gateway/metrics", response_class=PlainTextResponse)
    async def gateway_metrics(_auth: Any = Depends(auth_dependency)) -> PlainTextResponse:
        """Prometheus text exposition of proxy usage (404 unless the toggle is on)."""
        if not config.usage_metrics_enabled():
            raise HTTPException(status_code=404, detail="Not found")
        return PlainTextResponse(get_metrics().render(), media_type=PROMETHEUS_CONTENT_TYPE)

    return router
