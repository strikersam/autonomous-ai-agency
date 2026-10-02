"""Proxy-path exact-match response cache."""

from __future__ import annotations

import pytest

from packages.ai import response_cache
from tests.gateway_support import (  # noqa: F401
    OK_BODY,
    chat_body,
    clear_dependency_overrides,
    gateway_env,
    json_response,
    make_client,
)


@pytest.fixture(autouse=True)
async def _fresh_cache():
    await response_cache.clear_cache()
    yield
    await response_cache.clear_cache()


def _post(client, **extra):
    return client.post("/v1/chat/completions", json=chat_body(temperature=0, **extra))


def test_off_by_default_even_for_deterministic_requests(gateway_env):
    client, upstream, _obs = make_client(gateway_env)

    first, second = _post(client), _post(client)

    assert "X-Cache" not in first.headers and "X-Cache" not in second.headers
    assert len(upstream.requests) == 2


def test_miss_then_hit_serves_from_memory(gateway_env):
    gateway_env.setenv("GATEWAY_PROXY_CACHE_ENABLED", "true")
    client, upstream, observations = make_client(gateway_env)

    first = _post(client)
    second = _post(client)

    assert first.headers["X-Cache"] == "MISS" and second.headers["X-Cache"] == "HIT"
    assert first.json() == second.json() == OK_BODY
    assert len(upstream.requests) == 1
    assert len(observations) == 1, "a cache hit spends no upstream tokens and is not re-observed"
    assert second.headers["X-Routing-Model"] == "test-model"


def test_non_deterministic_and_streaming_and_tool_requests_bypass(gateway_env):
    gateway_env.setenv("GATEWAY_PROXY_CACHE_ENABLED", "true")
    client, upstream, _obs = make_client(gateway_env)

    for _ in range(2):
        no_temp = client.post("/v1/chat/completions", json=chat_body())
        warm = client.post("/v1/chat/completions", json=chat_body(temperature=0.7))
        tools = client.post("/v1/chat/completions", json=chat_body(temperature=0, tools=[{"type": "function"}]))
        for resp in (no_temp, warm, tools):
            assert "X-Cache" not in resp.headers
    assert len(upstream.requests) == 6


def test_cache_is_keyed_by_consumer(gateway_env):
    gateway_env.setenv("GATEWAY_PROXY_CACHE_ENABLED", "true")
    client_a, upstream, _o = make_client(gateway_env, key_id="kid_a")
    assert _post(client_a).headers["X-Cache"] == "MISS"
    assert _post(client_a).headers["X-Cache"] == "HIT"

    client_b, upstream_b, _o = make_client(gateway_env, key_id="kid_b")
    assert _post(client_b).headers["X-Cache"] == "MISS", "another key must not receive kid_a's completion"
    assert len(upstream_b.requests) == 1


def test_different_prompts_do_not_collide(gateway_env):
    gateway_env.setenv("GATEWAY_PROXY_CACHE_ENABLED", "true")
    client, upstream, _obs = make_client(gateway_env)

    a = client.post("/v1/chat/completions", json=chat_body("one", temperature=0))
    b = client.post("/v1/chat/completions", json=chat_body("two", temperature=0))

    assert a.headers["X-Cache"] == b.headers["X-Cache"] == "MISS"
    assert len(upstream.requests) == 2


def test_error_responses_are_not_cached(gateway_env):
    gateway_env.setenv("GATEWAY_PROXY_CACHE_ENABLED", "true")
    client, upstream, _obs = make_client(gateway_env, lambda _r: json_response(400, {"error": "bad"}))

    _post(client)
    again = _post(client)

    assert again.headers["X-Cache"] == "MISS"
    assert len(upstream.requests) == 2


def test_response_cache_flag_alone_does_not_enable_it(gateway_env):
    # RESPONSE_CACHE_ENABLED defaults on for the ProviderRouter; the gateway has its own opt-in.
    client, upstream, _obs = make_client(gateway_env)
    _post(client)
    _post(client)
    assert len(upstream.requests) == 2


def test_toggle_can_be_flipped_live(gateway_env):
    client, upstream, _obs = make_client(gateway_env)
    _post(client)
    gateway_env.setenv("GATEWAY_PROXY_CACHE_ENABLED", "true")
    assert _post(client).headers["X-Cache"] == "MISS"
    assert _post(client).headers["X-Cache"] == "HIT"
    gateway_env.setenv("GATEWAY_PROXY_CACHE_ENABLED", "false")
    assert "X-Cache" not in _post(client).headers
