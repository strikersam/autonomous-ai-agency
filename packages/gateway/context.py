"""packages/gateway/context.py — per-request gateway call state.

The chat handlers call :func:`begin_call` once. The returned :class:`GatewayCall`
is also stored in a ``ContextVar`` so the existing ``_emit_safely`` hook (where
prompt/completion tokens are first known, for streaming and non-streaming
alike) can reach it through :func:`current_call` without new parameters.

The consumer id is the API key's id, or — for legacy keys that have none — a
sha256 digest of the key. The raw key is never kept.
"""

from __future__ import annotations

import hashlib
import logging
import time
from contextvars import ContextVar
from dataclasses import dataclass, field

from fastapi import HTTPException, Request

from packages.gateway import token_quota, usage_metrics
from packages.gateway.hygiene import get_request_id

log = logging.getLogger("qwen-proxy")


def consumer_id(raw_key: str, key_id: str | None) -> str:
    """Stable, non-reversible identity for the caller of a request."""
    if key_id:
        return str(key_id)
    if not raw_key:
        return "anonymous"
    return "sha256:" + hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:32]


def _raw_key(request: Request) -> str:
    """Mirror how ``verify_api_key`` reads the key; it has already validated it."""
    api_key = request.headers.get("x-api-key")
    if api_key:
        return api_key.strip()
    auth = request.headers.get("authorization") or ""
    return (auth[7:] if auth.startswith("Bearer ") else auth).strip()


@dataclass
class GatewayCall:
    """State for one proxied request."""

    consumer: str
    request_id: str
    started: float = field(default_factory=time.perf_counter)
    status: int = 200
    finished: bool = False

    def enforce_quota(self) -> None:
        """Raise 429 with ``Retry-After`` when this consumer has spent its tokens."""
        decision = token_quota.check(self.consumer)
        if decision.allowed:
            return
        log.warning("Token quota exceeded for consumer %s", self.consumer)
        raise HTTPException(
            status_code=429,
            detail="Token quota exceeded",
            headers={"Retry-After": str(decision.retry_after), **token_quota.rate_limit_headers(self.consumer)},
        )

    def finish(self, model: str, prompt_tokens: int, completion_tokens: int, outcome: str | None = None) -> None:
        """Record actual usage once; later calls are ignored. Never raises."""
        if self.finished:
            return
        self.finished = True
        try:
            token_quota.record(self.consumer, int(prompt_tokens) + int(completion_tokens))
            usage_metrics.record_call(
                consumer=self.consumer,
                model=model,
                prompt_tokens=int(prompt_tokens),
                completion_tokens=int(completion_tokens),
                latency_sec=time.perf_counter() - self.started,
                outcome=outcome or ("ok" if self.status < 400 else "error"),
            )
        except Exception as exc:
            log.warning("Gateway usage recording error: %s", exc)


_call_var: ContextVar[GatewayCall | None] = ContextVar("gateway_call", default=None)


def begin_call(request: Request, key_id: str | None) -> GatewayCall:
    """Start tracking this request and make it reachable via :func:`current_call`."""
    call = GatewayCall(consumer=consumer_id(_raw_key(request), key_id), request_id=get_request_id())
    _call_var.set(call)
    return call


def current_call() -> GatewayCall | None:
    """The active call, or ``None`` when the handler did not begin one."""
    return _call_var.get()


def finish_current(model: str, prompt_tokens: int, completion_tokens: int) -> None:
    """Record usage for the active call, if any (the ``_emit_safely`` hook)."""
    call = _call_var.get()
    if call is not None:
        call.finish(model, prompt_tokens, completion_tokens)
