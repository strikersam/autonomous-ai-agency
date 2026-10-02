"""Shared, hermetic harness for the AI gateway hardening tests.

Drives the real ``proxy.app`` with authentication stubbed, the router replaced
by a fixed decision, and the upstream LLM replaced by an ``httpx.MockTransport``
so no test touches the network or sleeps.
"""

from __future__ import annotations

import json
from typing import Any, Callable

import httpx
import pytest
from fastapi.testclient import TestClient

import chat_handlers
import proxy
from handlers import anthropic_compat
from packages.gateway import (
    prompt_policy,
    token_quota,
    usage_metrics,
)
from packages.llm import metrics as llm_metrics
from router import RoutingDecision

_REAL_ASYNC_CLIENT = httpx.AsyncClient  # captured before any test patches it

GATEWAY_ENV = (
    "GATEWAY_MAX_REQUEST_BYTES",
    "GATEWAY_SECURITY_HEADERS_ENABLED",
    "GATEWAY_TOKENS_PER_MINUTE",
    "GATEWAY_TOKENS_PER_DAY",
    "GATEWAY_PROMPT_POLICY_ENABLED",
    "GATEWAY_PROMPT_POLICY_FILE",
    "GATEWAY_SANITIZER_MODE",
    "GATEWAY_USAGE_METRICS_ENABLED",
    "GATEWAY_UPSTREAM_RETRIES",
    "GATEWAY_PROXY_CACHE_ENABLED",
)

OK_BODY = {
    "id": "chatcmpl-1",
    "object": "chat.completion",
    "model": "test-model",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "hello"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 7, "completion_tokens": 5, "total_tokens": 12},
}


def json_response(status: int = 200, body: dict[str, Any] | None = None, **kwargs: Any) -> httpx.Response:
    return httpx.Response(status, json=OK_BODY if body is None else body, **kwargs)


class _StubRouter:
    def route(self, **_kwargs: Any) -> RoutingDecision:
        return RoutingDecision(
            resolved_model="test-model",
            requested_model="test-model",
            mode="auto",
            routing_reason="test",
            task_category="general",
            selection_source="passthrough",
            fallback_chain=[],
        )


class Upstream:
    """Records every request the proxy sends upstream and answers via *responder*."""

    def __init__(self, responder: Callable[[httpx.Request], httpx.Response]) -> None:
        self.responder = responder
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.responder(request)

    def bodies(self) -> list[dict[str, Any]]:
        return [json.loads(r.content) for r in self.requests]


@pytest.fixture
def gateway_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Every gateway switch unset (its default) and all gateway state cleared."""
    for name in GATEWAY_ENV:
        monkeypatch.delenv(name, raising=False)
    token_quota.reset()
    usage_metrics.reset()
    prompt_policy.reset()
    llm_metrics.reset()
    return monkeypatch


def make_client(
    monkeypatch: pytest.MonkeyPatch,
    responder: Callable[[httpx.Request], httpx.Response] | None = None,
    *,
    key_id: str | None = "kid_a",
    key: str = "test-key",
) -> tuple[TestClient, Upstream, list[dict[str, Any]]]:
    """A client for the real proxy app plus the upstream recorder and Langfuse recorder."""
    upstream = Upstream(responder or (lambda _r: json_response()))
    real_client = _REAL_ASYNC_CLIENT

    def mocked_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = httpx.MockTransport(upstream)
        return real_client(*args, **kwargs)

    observations: list[dict[str, Any]] = []
    monkeypatch.setattr(httpx, "AsyncClient", mocked_client)
    for module in (chat_handlers, anthropic_compat):
        monkeypatch.setattr(module, "get_router", lambda: _StubRouter())
        monkeypatch.setattr(module, "emit_chat_observation", lambda **kw: observations.append(kw))
    proxy.app.dependency_overrides[proxy.verify_api_key] = lambda: proxy.AuthContext(
        key=key, email="t@example.com", department="eng", key_id=key_id, source="store"
    )
    return TestClient(proxy.app), upstream, observations


def chat_body(text: str = "hi", **extra: Any) -> dict[str, Any]:
    return {"model": "test-model", "messages": [{"role": "user", "content": text}], **extra}


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    proxy.app.dependency_overrides.clear()
