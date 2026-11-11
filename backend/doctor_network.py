"""Connectivity-only doctor: per-provider reachability, nothing else.

``GET /api/doctor/network`` probes each provider in the failover chain with the
router's own ``ProviderRouter.health_check`` (rule 2: no direct provider calls
here) and reports reachable / unreachable plus latency. It runs none of the full
doctor report's storage, GitHub or agency checks, so it answers "can this deploy
reach NVIDIA → TokenIn → Cerebras → Groq → Ollama?" in one round trip.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

log = logging.getLogger("qwen-proxy")

# One slow provider must not hold the whole report past this.
_PROBE_TIMEOUT_S = 12.0


class ProviderReachability(BaseModel):
    """Reachability of one provider in the failover chain."""

    provider_id: str
    type: str
    priority: int
    reachable: bool
    latency_ms: int


class NetworkDoctorReport(BaseModel):
    """Connectivity-only doctor report."""

    ready: bool
    reachable: int
    total: int
    providers: list[ProviderReachability] = []
    run_at: str


def _default_router() -> Any:
    from packages.ai.router import ProviderRouter

    return ProviderRouter.from_env()


async def _probe(router: Any, provider: Any) -> ProviderReachability:
    started = time.monotonic()
    try:
        ok = await asyncio.wait_for(router.health_check(provider), _PROBE_TIMEOUT_S)
    except Exception:  # timeout or a probe error both mean "not reachable"
        ok = False
    return ProviderReachability(
        provider_id=str(provider.provider_id),
        type=str(provider.type),
        priority=int(provider.priority),
        reachable=bool(ok),
        latency_ms=int((time.monotonic() - started) * 1000),
    )


async def build_network_report(router: Any) -> NetworkDoctorReport:
    """Probe every provider in *router* concurrently and summarise."""
    providers = list(getattr(router, "providers", []) or [])
    results = await asyncio.gather(*(_probe(router, p) for p in providers))
    reachable = sum(1 for r in results if r.reachable)
    return NetworkDoctorReport(
        ready=reachable > 0,
        reachable=reachable,
        total=len(results),
        providers=sorted(results, key=lambda r: r.priority),
        run_at=datetime.now(timezone.utc).isoformat(),
    )


def build_doctor_network_router(
    get_current_user: Callable[..., Awaitable[dict]],
    router_factory: Callable[[], Any] = _default_router,
) -> APIRouter:
    """Return the authenticated ``/api/doctor/network`` router."""
    api = APIRouter()

    @api.get("/api/doctor/network", response_model=NetworkDoctorReport)
    async def doctor_network(
        user: dict = Depends(get_current_user),
    ) -> NetworkDoctorReport:
        """Per-provider reachability only (no storage/GitHub/agency checks)."""
        try:
            return await build_network_report(router_factory())
        except Exception:
            log.exception("Network doctor failed")
            raise HTTPException(status_code=500, detail="Network check failed")

    return api
