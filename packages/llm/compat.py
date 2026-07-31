"""packages/llm/compat.py — backwards-compatible bridges to the legacy call paths.

Existing callers keep their exact signatures and return types. When
``LLM_ROUTER_ENABLED`` is falsey (the default) nothing here runs and the legacy
implementations execute unchanged — the Golden Rule requires that an
untouched deployment behave identically. When it is enabled, these adapters
translate to and from ``LLMRouter`` so the same callers gain every resilience
feature without a code change (ADR-008 §8).

Rollback is one environment variable, not a revert.
"""
from __future__ import annotations

import logging
from typing import Any

from packages.llm.config import router_enabled
from packages.llm.router import get_router
from packages.llm.types import (
    BudgetExceeded,
    LLMRequest,
    LLMResponse,
    PermanentError,
    Priority,
    QueueFull,
    RouterExhausted,
)

log = logging.getLogger("llm.compat")


def request_from_openai_payload(
    payload: dict[str, Any], *, agent: str = "", workflow: str = ""
) -> LLMRequest:
    """Translate an OpenAI-shaped chat payload into an ``LLMRequest``.

    Unknown keys are preserved in ``extra`` and forwarded to the provider, so a
    caller passing a vendor-specific parameter today keeps passing it.
    """
    # `n`, `stop`, and `top_p` are deliberately NOT listed: LLMRequest has no
    # fields for them, so listing them here would strip them from `extra` and
    # they would never reach the provider — silently changing sampling
    # behaviour for a routed call.
    known = {
        "model", "messages", "temperature", "max_tokens", "stream", "tools",
        "tool_choice", "response_format",
    }
    extra = {k: v for k, v in payload.items() if k not in known}

    return LLMRequest(
        messages=list(payload.get("messages") or []),
        model=str(payload.get("model") or "") or None,
        temperature=float(payload.get("temperature", 0.3) or 0.0),
        max_tokens=int(payload.get("max_tokens") or 4096),
        stream=bool(payload.get("stream")),
        tools=payload.get("tools"),
        tool_choice=payload.get("tool_choice"),
        response_format=payload.get("response_format"),
        agent=agent or None,
        workflow=workflow or None,
        extra=extra,
    )


def openai_body_from_response(response: LLMResponse) -> dict[str, Any]:
    """Render an ``LLMResponse`` as an OpenAI chat-completions body.

    Used by the gateway and by any caller that expects the raw dict shape the
    proxy has always returned.
    """
    message: dict[str, Any] = {"role": "assistant", "content": response.text}
    if response.tool_calls:
        message["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": call.arguments},
            }
            for call in response.tool_calls
        ]
    return {
        "id": f"chatcmpl-{int(response.created_at * 1000)}",
        "object": "chat.completion",
        "created": int(response.created_at),
        "model": response.model,
        "choices": [{
            "index": 0,
            "message": message,
            "finish_reason": response.finish_reason or "stop",
        }],
        "usage": response.usage.as_dict(),
        "x_router": {
            "provider": response.provider,
            "attempts": [a.as_dict() for a in response.attempts],
            "fallbacks": response.fallback_count,
            "cached": response.cached,
            "cost_usd": response.cost_usd,
            "latency_ms": response.latency_ms,
        },
    }


async def failover_chat_completion_via_router(
    payload: dict[str, Any], *, timeout_sec: float = 120.0
) -> Any:
    """Router-backed implementation of ``packages.ai.failover_client``'s entry point.

    Returns a ``FailoverResult`` so callers — ``agent/loop.py`` chief among
    them — cannot tell which implementation ran. ``RouterExhausted`` is
    re-raised as ``BrainFailoverExhausted`` for the same reason.
    """
    from packages.ai.failover_client import BrainFailoverExhausted, FailoverResult

    request = request_from_openai_payload(payload)
    request.timeout_sec = timeout_sec
    request.priority = Priority.HIGH

    try:
        response = await get_router().chat(request)
    except RouterExhausted as exc:
        attempted = {attempt.provider for attempt in exc.attempts}
        failures = [
            f"{attempt.provider}: {attempt.error}"
            for attempt in exc.attempts
            if attempt.error
        ]
        raise BrainFailoverExhausted(exc.reason, attempted, failures) from exc
    except (QueueFull, BudgetExceeded, PermanentError) as exc:
        # Callers such as agent/loop.py catch BrainFailoverExhausted and
        # nothing else. Letting a router-specific exception escape would break
        # them the moment the flag is enabled — exactly what the compatibility
        # contract exists to prevent.
        raise BrainFailoverExhausted(str(exc), set(), [str(exc)]) from exc

    return FailoverResult(
        text=response.text,
        model=response.model,
        provider_id=response.provider,
        prompt_tokens=response.usage.prompt_tokens,
        completion_tokens=response.usage.completion_tokens,
        latency_ms=response.latency_ms,
        attempts=[f"{a.provider}/{a.model}" for a in response.attempts],
    )


def should_use_router() -> bool:
    """Whether the compat bridges should delegate to ``LLMRouter``.

    Reads the flag on every call rather than caching it, so an operator can
    flip it at runtime through the admin API without a restart.
    """
    return router_enabled()
