"""packages/llm/gateway.py — the router's REST surface.

Two groups of routes:

**Gateway mode** (``/api/llm/v1/*``) exposes the routing layer as an
OpenAI-compatible API so other applications — an IDE, a script, another
service — get the same failover, key rotation, and caching this platform's
own agents get. Off by default; set ``LLM_GATEWAY_ENABLED=true``.

**Observability** (``/api/llm/*``) backs the dashboard and Prometheus. These
are always mounted, because a routing layer nobody can see is a routing layer
nobody can debug.

Authentication is the caller's concern: ``build_llm_router`` takes the
platform's ``get_current_user`` dependency and applies it to every mutating
route, matching the pattern in ``backend/admin_local_brain_router.py``.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

from packages.llm.budget import get_budget
from packages.llm.cache import get_cache
from packages.llm.compat import openai_body_from_response, request_from_openai_payload
from packages.llm.config import get_config, reload_config, router_enabled
from packages.llm.health import get_tracker
from packages.llm.metrics import get_metrics
from packages.llm.registry import get_registry
from packages.llm.router import get_router
from packages.llm.strategies import strategy_names
from packages.llm.types import (
    BudgetExceeded,
    LLMRequest,
    PermanentError,
    QueueFull,
    RouterExhausted,
)

log = logging.getLogger("llm.gateway")

_TRUTHY = {"1", "true", "yes", "on"}


def gateway_enabled() -> bool:
    """Whether the OpenAI-compatible passthrough routes accept traffic."""
    return os.environ.get("LLM_GATEWAY_ENABLED", "").strip().lower() in _TRUTHY


class ChatRequest(BaseModel):
    """OpenAI-compatible chat request, plus this router's extensions."""

    model: str | None = None
    messages: list[dict[str, Any]] = Field(default_factory=list)
    temperature: float = 0.3
    max_tokens: int = 4096
    stream: bool = False
    tools: list[dict[str, Any]] | None = None
    tool_choice: Any = None
    response_format: dict[str, Any] | None = None
    # Router extensions — all optional, all ignored by an OpenAI client.
    agent: str | None = None
    workflow: str | None = None
    strategy: str | None = None
    providers: list[str] | None = None
    allow_paid: bool | None = None
    pin_model: bool = False


class StrategyUpdate(BaseModel):
    strategy: str


class ProviderToggle(BaseModel):
    enabled: bool
    duration_sec: float = 300.0


def build_llm_router(
    get_current_user: Callable[..., Any] | None = None,
) -> APIRouter:
    """Build the ``/api/llm`` router.

    ``get_current_user`` is the platform's auth dependency. When omitted (in
    tests) the routes are unauthenticated.
    """
    router = APIRouter(prefix="/api/llm", tags=["llm-router"])
    guard = [Depends(get_current_user)] if get_current_user else []

    # ── Observability ───────────────────────────────────────────────────────

    @router.get("/status")
    async def status() -> dict[str, Any]:
        """Full routing state — providers, health, queue, cache, budget."""
        if not _available():
            return _disabled_status()
        return get_router().status()

    @router.get("/providers")
    async def providers() -> dict[str, Any]:
        """Providers ordered healthiest-first, for the dashboard."""
        if not _available():
            return {"providers": [], "enabled": False}
        state = get_router().status()
        ranked = sorted(
            state["providers"],
            key=lambda p: (
                0 if p.get("available") else 1,
                -float((p.get("health") or {}).get("success_rate", 1.0)),
                float((p.get("health") or {}).get("p95_latency_ms", 0.0)) or 1e9,
                p.get("priority", 100),
            ),
        )
        return {
            "providers": ranked,
            "enabled": True,
            "strategy": state["strategy"],
            "strategies": state["strategies"],
        }

    @router.get("/health")
    async def health() -> dict[str, Any]:
        """Circuit-breaker and rolling-health state per provider."""
        return {"providers": get_tracker().snapshot()}

    @router.post("/health/probe", dependencies=guard)
    async def probe(provider_id: str | None = None) -> dict[str, Any]:
        """Actively probe providers now instead of waiting for live traffic."""
        if not _available():
            raise HTTPException(503, "LLM router is not enabled")
        return {"results": await get_router().health_check(provider_id)}

    @router.get("/models")
    async def models() -> dict[str, Any]:
        """The model registry with full capability metadata."""
        return {"models": get_registry().snapshot()}

    @router.post("/models/discover", dependencies=guard)
    async def discover() -> dict[str, Any]:
        """Ask every provider what it serves and register anything new."""
        if not _available():
            raise HTTPException(503, "LLM router is not enabled")
        return {"discovered": await get_router().discover_models()}

    @router.get("/metrics", response_class=PlainTextResponse)
    async def metrics() -> str:
        """Prometheus exposition for scraping."""
        if _available():
            get_router()._refresh_gauges()  # noqa: SLF001 - gauges are router-owned
        return get_metrics().render()

    @router.get("/metrics.json")
    async def metrics_json() -> dict[str, Any]:
        """The same metrics as JSON, so the dashboard need not parse text."""
        return get_metrics().snapshot()

    @router.get("/usage")
    async def usage() -> dict[str, Any]:
        """Token and cost totals by agent, workflow, provider, model, and period."""
        return get_budget().snapshot()

    @router.get("/cache")
    async def cache_stats() -> dict[str, Any]:
        return get_cache().stats()

    @router.delete("/cache", dependencies=guard)
    async def cache_clear() -> dict[str, Any]:
        return {"cleared": get_cache().clear()}

    @router.get("/config")
    async def config() -> dict[str, Any]:
        """The effective configuration. Never includes key material."""
        cfg = get_config()
        return {
            "source_dir": cfg.source_dir,
            "router_enabled": router_enabled(),
            "gateway_enabled": gateway_enabled(),
            "strategy": cfg.routing.strategy,
            "available_strategies": strategy_names(),
            "prefer_local": cfg.routing.prefer_local,
            "allow_paid": cfg.routing.allow_paid,
            "fallback_chain": cfg.routing.fallback_chain,
            "retry": {
                "max_attempts": cfg.routing.retry.max_attempts,
                "base_delay_sec": cfg.routing.retry.base_delay_sec,
                "max_delay_sec": cfg.routing.retry.max_delay_sec,
                "jitter": cfg.routing.retry.jitter,
                "retry_statuses": cfg.routing.retry.retry_statuses,
                "budget_sec": cfg.routing.retry.budget_sec,
            },
            "queue": {
                "enabled": cfg.routing.queue_enabled,
                "max_depth": cfg.routing.queue_max_depth,
                "global_max_concurrency": cfg.routing.global_max_concurrency,
            },
            "health": {
                "failure_threshold": cfg.health.failure_threshold,
                "open_duration_sec": cfg.health.open_duration_sec,
                "half_open_probes": cfg.health.half_open_probes,
                "window_sec": cfg.health.window_sec,
            },
            "agents": sorted(cfg.routing.agents),
            "providers": [
                {
                    "id": p.id,
                    "kind": p.kind,
                    "tier": p.tier,
                    "enabled": p.enabled,
                    "priority": p.priority,
                    "key_env": p.key_env,          # names only, never values
                    "key_count": len(p.key_env),
                }
                for p in cfg.providers.values()
            ],
        }

    @router.post("/config/reload", dependencies=guard)
    async def config_reload() -> dict[str, Any]:
        """Re-read ``config/llm/*.yaml`` without restarting the process."""
        from packages.llm import router as router_module

        cfg = reload_config()
        router_module.reset()
        return {
            "reloaded": True,
            "providers": len(cfg.providers),
            "models": len(cfg.models),
            "strategy": cfg.routing.strategy,
        }

    @router.put("/config/strategy", dependencies=guard)
    async def set_strategy(body: StrategyUpdate) -> dict[str, Any]:
        """Switch the active routing strategy at runtime."""
        if body.strategy not in strategy_names():
            raise HTTPException(
                400, f"unknown strategy {body.strategy!r}; choose one of {strategy_names()}"
            )
        get_config().routing.strategy = body.strategy
        return {"strategy": body.strategy}

    @router.put("/providers/{provider_id}/enabled", dependencies=guard)
    async def toggle_provider(provider_id: str, body: ProviderToggle) -> dict[str, Any]:
        """Take a provider out of rotation, or put it back."""
        tracker = get_tracker()
        if body.enabled:
            tracker.force_close(provider_id)
        else:
            tracker.force_open(provider_id, body.duration_sec)
        return {"provider": provider_id, "enabled": body.enabled}

    # ── Gateway mode ────────────────────────────────────────────────────────

    @router.post("/v1/chat/completions")
    async def chat_completions(body: ChatRequest, request: Request) -> Any:
        """OpenAI-compatible completions, routed through ``LLMRouter``."""
        if not gateway_enabled():
            raise HTTPException(
                403, "Gateway mode is disabled. Set LLM_GATEWAY_ENABLED=true to enable it."
            )
        if not _available():
            raise HTTPException(503, "LLM router is not enabled")
        if not body.messages:
            raise HTTPException(400, "messages must not be empty")

        llm_request = request_from_openai_payload(
            body.model_dump(exclude_none=True),
            agent=body.agent or request.headers.get("x-agent", ""),
            workflow=body.workflow or request.headers.get("x-workflow", ""),
        )
        llm_request.strategy = body.strategy or request.headers.get("x-routing-strategy") or None
        llm_request.providers = body.providers
        llm_request.pin_model = body.pin_model
        if body.allow_paid is not None:
            llm_request.allow_paid = body.allow_paid

        if body.stream:
            return StreamingResponse(
                _stream_sse(llm_request), media_type="text/event-stream",
            )

        try:
            response = await get_router().chat(llm_request)
        except QueueFull as exc:
            raise HTTPException(429, str(exc)) from exc
        except BudgetExceeded as exc:
            raise HTTPException(402, str(exc)) from exc
        except PermanentError as exc:
            raise HTTPException(exc.status or 400, str(exc)) from exc
        except RouterExhausted as exc:
            raise HTTPException(503, str(exc)) from exc
        return openai_body_from_response(response)

    @router.get("/v1/models")
    async def list_models() -> dict[str, Any]:
        """OpenAI-compatible model list."""
        if not gateway_enabled():
            raise HTTPException(
                403, "Gateway mode is disabled. Set LLM_GATEWAY_ENABLED=true to enable it."
            )
        return {
            "object": "list",
            "data": [
                {
                    "id": model["id"],
                    "object": "model",
                    "owned_by": model["provider"],
                    "context_window": model["context_window"],
                }
                for model in get_registry().snapshot()
            ],
        }

    return router


async def _stream_sse(request: LLMRequest) -> Any:
    """Render router chunks as OpenAI-compatible SSE."""
    index = 0
    try:
        async for chunk in get_router().stream(request):
            payload = {
                "id": f"chatcmpl-stream-{index}",
                "object": "chat.completion.chunk",
                "model": chunk.model,
                "choices": [{
                    "index": 0,
                    "delta": ({"content": chunk.text} if chunk.text else {}),
                    "finish_reason": chunk.finish_reason,
                }],
            }
            if chunk.tool_call is not None:
                payload["choices"][0]["delta"]["tool_calls"] = [{
                    "index": chunk.tool_call.index,
                    "id": chunk.tool_call.id,
                    "type": "function",
                    "function": {
                        "name": chunk.tool_call.name,
                        "arguments": chunk.tool_call.arguments,
                    },
                }]
            index += 1
            yield f"data: {json.dumps(payload)}\n\n"
    except RouterExhausted as exc:
        yield f"data: {json.dumps({'error': {'message': str(exc), 'type': 'router_exhausted'}})}\n\n"
    except Exception as exc:  # pragma: no cover - transport failures
        log.warning("llm.gateway: stream failed (%s)", exc)
        yield f"data: {json.dumps({'error': {'message': str(exc)[:300]}})}\n\n"
    yield "data: [DONE]\n\n"


def _available() -> bool:
    """Whether the router can serve traffic at all."""
    if not router_enabled():
        return False
    try:
        return bool(get_router().providers)
    except Exception as exc:  # pragma: no cover - misconfiguration
        log.warning("llm.gateway: router unavailable (%s)", exc)
        return False


def _disabled_status() -> dict[str, Any]:
    """A shape-compatible status payload when the router is off.

    The dashboard renders this without special-casing: same keys, empty lists,
    plus the reason and the switch that turns it on.
    """
    cfg = get_config()
    return {
        "enabled": False,
        "reason": (
            "LLM_ROUTER_ENABLED is not set — the platform is using the legacy "
            "failover path. Set LLM_ROUTER_ENABLED=true to route through LLMRouter."
        ),
        "strategy": cfg.routing.strategy,
        "strategies": strategy_names(),
        "prefer_local": cfg.routing.prefer_local,
        "allow_paid": cfg.routing.allow_paid,
        "providers": [],
        "queue": {"depth": 0, "max_depth": cfg.routing.queue_max_depth},
        "bulkheads": {"limits": {}, "in_flight": {}, "rejected": {}},
        "dedupe": {"hits": 0, "misses": 0, "hit_rate": 0.0, "in_flight": 0},
        "cache": get_cache().stats(),
        "budget": get_budget().snapshot(),
        "config_dir": cfg.source_dir,
    }
