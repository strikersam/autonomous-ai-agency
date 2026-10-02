"""Upstream retries: transient statuses, connect errors, Retry-After, budget, streams."""

from __future__ import annotations

import httpx
import pytest

from packages.gateway import upstream_retry
from packages.gateway.upstream_retry import post_with_retries
from packages.llm.config import RetryConfig
from tests.gateway_support import (  # noqa: F401
    OK_BODY,
    chat_body,
    clear_dependency_overrides,
    gateway_env,
    json_response,
    make_client,
)

ZERO_DELAY = RetryConfig(max_attempts=99, base_delay_sec=0.0, max_delay_sec=0.0, jitter=0.0, budget_sec=60.0)


def _sequence(*outcomes):
    """A responder that plays *outcomes* in order (an exception instance is raised)."""
    remaining = list(outcomes)

    def respond(request: httpx.Request) -> httpx.Response:
        outcome = remaining.pop(0) if len(remaining) > 1 else remaining[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return respond


@pytest.fixture
def transport(monkeypatch):
    """Route post_with_retries' AsyncClient through a MockTransport; returns (set_responder, calls)."""
    calls: list[httpx.Request] = []
    holder: dict = {}
    real = httpx.AsyncClient

    def factory(*args, **kwargs):
        def handler(request):
            calls.append(request)
            return holder["responder"](request)

        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)
    return (lambda responder: holder.update(responder=responder)), calls


async def test_zero_retries_is_exactly_one_attempt(transport):
    set_responder, calls = transport
    set_responder(_sequence(httpx.Response(503), json_response()))

    resp = await post_with_retries("http://up/v1", b"{}", {}, 0)

    assert resp.status_code == 503 and len(calls) == 1


@pytest.mark.parametrize("status", [429, 502, 503, 504])
async def test_transient_status_is_retried_until_success(transport, status):
    set_responder, calls = transport
    set_responder(_sequence(httpx.Response(status), httpx.Response(status), json_response()))

    resp = await post_with_retries("http://up/v1", b"{}", {}, 3, ZERO_DELAY)

    assert resp.status_code == 200 and len(calls) == 3


@pytest.mark.parametrize("status", [400, 401, 404, 500])
async def test_non_transient_status_is_returned_immediately(transport, status):
    set_responder, calls = transport
    set_responder(_sequence(httpx.Response(status)))

    resp = await post_with_retries("http://up/v1", b"{}", {}, 3, ZERO_DELAY)

    assert resp.status_code == status and len(calls) == 1


async def test_attempts_are_capped_and_last_response_is_returned(transport):
    set_responder, calls = transport
    set_responder(_sequence(httpx.Response(503)))

    resp = await post_with_retries("http://up/v1", b"{}", {}, 2, ZERO_DELAY)

    assert resp.status_code == 503 and len(calls) == 3  # 1 try + 2 retries


async def test_connect_error_is_retried_then_succeeds(transport):
    set_responder, calls = transport
    request = httpx.Request("POST", "http://up/v1")
    set_responder(_sequence(httpx.ConnectError("no", request=request), json_response()))

    resp = await post_with_retries("http://up/v1", b"{}", {}, 2, ZERO_DELAY)

    assert resp.status_code == 200 and len(calls) == 2


async def test_persistent_connect_error_is_reraised_unchanged(transport):
    set_responder, calls = transport
    request = httpx.Request("POST", "http://up/v1")
    set_responder(_sequence(httpx.ConnectError("no", request=request)))

    with pytest.raises(httpx.ConnectError):
        await post_with_retries("http://up/v1", b"{}", {}, 2, ZERO_DELAY)
    assert len(calls) == 3


async def test_read_timeout_is_not_retried(transport):
    set_responder, calls = transport
    request = httpx.Request("POST", "http://up/v1")
    set_responder(_sequence(httpx.ReadTimeout("slow", request=request)))

    with pytest.raises(httpx.ReadTimeout):
        await post_with_retries("http://up/v1", b"{}", {}, 3, ZERO_DELAY)
    assert len(calls) == 1, "the upstream may have started generating; do not replay"


async def test_retry_after_header_is_honoured(transport, monkeypatch):
    set_responder, _calls = transport
    set_responder(_sequence(httpx.Response(429, headers={"Retry-After": "7"}), json_response()))
    seen: list[float | None] = []

    async def fake_sleep(attempt, config, budget, *, retry_after=None):
        seen.append(retry_after)
        return True

    monkeypatch.setattr(upstream_retry, "sleep_before_retry", fake_sleep)
    resp = await post_with_retries("http://up/v1", b"{}", {}, 1, ZERO_DELAY)

    assert resp.status_code == 200 and seen == [7.0]


async def test_http_date_retry_after_falls_back_to_computed_backoff(transport, monkeypatch):
    set_responder, _calls = transport
    set_responder(
        _sequence(httpx.Response(503, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}), json_response())
    )
    seen: list[float | None] = []

    async def fake_sleep(attempt, config, budget, *, retry_after=None):
        seen.append(retry_after)
        return True

    monkeypatch.setattr(upstream_retry, "sleep_before_retry", fake_sleep)
    await post_with_retries("http://up/v1", b"{}", {}, 1, ZERO_DELAY)

    assert seen == [None]


async def test_unaffordable_wait_returns_the_response_instead_of_sleeping(transport):
    set_responder, calls = transport
    set_responder(_sequence(httpx.Response(429, headers={"Retry-After": "30"})))
    tight = RetryConfig(max_attempts=99, base_delay_sec=0.0, max_delay_sec=30.0, jitter=0.0, budget_sec=0.001)

    resp = await post_with_retries("http://up/v1", b"{}", {}, 3, tight)

    assert resp.status_code == 429 and len(calls) == 1


# ── wired into the proxy, ahead of the model-swap fallback ───────────────────


def test_proxy_is_unchanged_with_retries_off(gateway_env):
    client, upstream, _obs = make_client(gateway_env, _sequence(httpx.Response(503, json={"e": 1}), json_response()))

    resp = client.post("/v1/chat/completions", json=chat_body())

    assert resp.status_code == 503 and len(upstream.requests) == 1


def test_proxy_retries_the_same_model_before_giving_up(gateway_env):
    gateway_env.setenv("GATEWAY_UPSTREAM_RETRIES", "2")
    gateway_env.setattr(upstream_retry, "default_retry_config", lambda retries: ZERO_DELAY.__class__(
        max_attempts=retries + 1, base_delay_sec=0.0, max_delay_sec=0.0, jitter=0.0, budget_sec=60.0))
    client, upstream, _obs = make_client(
        gateway_env,
        _sequence(httpx.Response(503, json={"e": 1}), httpx.Response(429, json={"e": 2}), json_response()),
    )

    resp = client.post("/v1/chat/completions", json=chat_body())

    assert resp.status_code == 200 and resp.json() == OK_BODY
    assert len(upstream.requests) == 3
    assert {b["model"] for b in upstream.bodies()} == {"test-model"}


def test_proxy_connect_error_still_maps_to_503_after_retries(gateway_env):
    gateway_env.setenv("GATEWAY_UPSTREAM_RETRIES", "1")
    gateway_env.setattr(upstream_retry, "default_retry_config", lambda retries: ZERO_DELAY.__class__(
        max_attempts=retries + 1, base_delay_sec=0.0, max_delay_sec=0.0, jitter=0.0, budget_sec=60.0))

    def refuse(request):
        raise httpx.ConnectError("refused", request=request)

    client, upstream, _obs = make_client(gateway_env, refuse)

    resp = client.post("/v1/chat/completions", json=chat_body())

    assert resp.status_code == 503
    assert len(upstream.requests) == 2


def test_streams_are_never_retried(gateway_env):
    gateway_env.setenv("GATEWAY_UPSTREAM_RETRIES", "3")
    client, upstream, _obs = make_client(gateway_env, lambda _r: httpx.Response(503, content=b"down"))

    resp = client.post("/v1/chat/completions", json=chat_body(stream=True))

    assert resp.content == b"down"
    assert len(upstream.requests) == 1
