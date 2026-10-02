"""Per-consumer token quota: windows, eviction, 429 + Retry-After, headers."""

from __future__ import annotations

import hashlib

import pytest

from packages.gateway import token_quota
from packages.gateway.context import consumer_id
from tests.gateway_support import (  # noqa: F401
    OK_BODY,
    chat_body,
    clear_dependency_overrides,
    gateway_env,
    make_client,
)

T0 = 1_700_000_040.0  # exactly on a UTC minute boundary


@pytest.fixture
def clock(gateway_env):
    state = {"now": T0}
    gateway_env.setattr(token_quota, "_now", lambda: state["now"])
    return state


def test_everything_is_a_noop_when_limits_are_zero(clock):
    token_quota.record("c1", 10**9)
    assert token_quota.check("c1").allowed
    assert token_quota.rate_limit_headers("c1") == {}
    assert token_quota._usage == {}


def test_minute_window_blocks_then_resets(clock, gateway_env):
    gateway_env.setenv("GATEWAY_TOKENS_PER_MINUTE", "100")
    token_quota.record("c1", 60)
    assert token_quota.check("c1").allowed
    token_quota.record("c1", 40)
    decision = token_quota.check("c1")
    assert not decision.allowed
    assert 1 <= decision.retry_after <= 61
    assert token_quota.check("other").allowed

    clock["now"] = T0 + 61
    assert token_quota.check("c1").allowed


def test_day_window_gives_a_long_retry_after(clock, gateway_env):
    gateway_env.setenv("GATEWAY_TOKENS_PER_DAY", "1000")
    token_quota.record("c1", 1000)
    decision = token_quota.check("c1")
    assert not decision.allowed
    assert decision.retry_after > 60
    clock["now"] = T0 + 86_400
    assert token_quota.check("c1").allowed


def test_rate_limit_headers_report_the_tightest_window(clock, gateway_env):
    gateway_env.setenv("GATEWAY_TOKENS_PER_MINUTE", "100")
    gateway_env.setenv("GATEWAY_TOKENS_PER_DAY", "150")
    token_quota.record("c1", 90)
    assert token_quota.rate_limit_headers("c1") == {
        "X-RateLimit-Limit-Tokens": "100",
        "X-RateLimit-Remaining-Tokens": "10",
    }
    clock["now"] = T0 + 120  # minute rolled, day did not: the day is now the tighter one
    assert token_quota.rate_limit_headers("c1") == {
        "X-RateLimit-Limit-Tokens": "150",
        "X-RateLimit-Remaining-Tokens": "60",
    }


def test_memory_is_bounded_by_lru_eviction(clock, gateway_env):
    gateway_env.setenv("GATEWAY_TOKENS_PER_MINUTE", "10")
    gateway_env.setattr(token_quota, "MAX_CONSUMERS", 3)
    for name in ("a", "b", "c"):
        token_quota.record(name, 10)
    token_quota.check("a")  # touch: b is now the least recently used
    token_quota.record("d", 10)
    assert len(token_quota._usage) == 3
    assert "b" not in token_quota._usage
    assert not token_quota.check("a").allowed


def test_consumer_is_key_id_or_a_digest_never_the_raw_key():
    assert consumer_id("secret-key-value", "kid_1") == "kid_1"
    legacy = consumer_id("secret-key-value", None)
    assert legacy == "sha256:" + hashlib.sha256(b"secret-key-value").hexdigest()[:32]
    assert "secret-key-value" not in legacy
    assert consumer_id("", None) == "anonymous"


def test_handler_records_usage_and_exposes_headers(clock, gateway_env):
    gateway_env.setenv("GATEWAY_TOKENS_PER_MINUTE", "100")
    client, _upstream, _obs = make_client(gateway_env)

    first = client.post("/v1/chat/completions", json=chat_body())

    assert first.status_code == 200
    assert first.headers["X-RateLimit-Limit-Tokens"] == "100"
    assert first.headers["X-RateLimit-Remaining-Tokens"] == str(100 - OK_BODY["usage"]["total_tokens"])


def test_handler_refuses_over_quota_with_429_and_retry_after(clock, gateway_env):
    gateway_env.setenv("GATEWAY_TOKENS_PER_MINUTE", "10")
    client, upstream, _obs = make_client(gateway_env)

    assert client.post("/v1/chat/completions", json=chat_body()).status_code == 200  # spends 12 tokens
    blocked = client.post("/v1/chat/completions", json=chat_body())

    assert blocked.status_code == 429
    assert blocked.json() == {"detail": "Token quota exceeded"}
    assert int(blocked.headers["Retry-After"]) >= 1
    assert blocked.headers["X-RateLimit-Remaining-Tokens"] == "0"
    assert len(upstream.requests) == 1, "a refused request must not reach the upstream"


def test_quota_is_per_consumer(clock, gateway_env):
    gateway_env.setenv("GATEWAY_TOKENS_PER_MINUTE", "10")
    client_a, _u, _o = make_client(gateway_env, key_id="kid_a")
    assert client_a.post("/v1/chat/completions", json=chat_body()).status_code == 200
    assert client_a.post("/v1/chat/completions", json=chat_body()).status_code == 429

    client_b, _u, _o = make_client(gateway_env, key_id="kid_b")
    assert client_b.post("/v1/chat/completions", json=chat_body()).status_code == 200


def test_legacy_key_without_id_is_tracked_by_digest(clock, gateway_env):
    gateway_env.setenv("GATEWAY_TOKENS_PER_MINUTE", "10")
    client, _u, _o = make_client(gateway_env, key_id=None)
    headers = {"Authorization": "Bearer legacy-key-123"}

    assert client.post("/v1/chat/completions", json=chat_body(), headers=headers).status_code == 200
    assert client.post("/v1/chat/completions", json=chat_body(), headers=headers).status_code == 429
    assert list(token_quota._usage) == [consumer_id("legacy-key-123", None)]
    assert all("legacy-key-123" not in name for name in token_quota._usage)


def test_no_quota_headers_or_blocking_by_default(gateway_env):
    client, _u, _o = make_client(gateway_env)
    for _ in range(3):
        resp = client.post("/v1/chat/completions", json=chat_body())
        assert resp.status_code == 200
        assert "X-RateLimit-Limit-Tokens" not in resp.headers


def test_anthropic_messages_enforce_the_same_quota(clock, gateway_env):
    gateway_env.setenv("GATEWAY_TOKENS_PER_MINUTE", "10")
    client, upstream, _obs = make_client(gateway_env)
    body = {"model": "test-model", "max_tokens": 16, "messages": [{"role": "user", "content": "hi"}]}

    first = client.post("/v1/messages", json=body)
    assert first.status_code == 200, first.text
    assert first.headers["X-RateLimit-Limit-Tokens"] == "10"
    second = client.post("/v1/messages", json=body)
    assert second.status_code == 429
    assert "Retry-After" in second.headers
    assert len(upstream.requests) == 1
