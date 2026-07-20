"""Tests for packages/ai/response_cache.py — LRU+TTL in-memory LLM response cache."""
from __future__ import annotations

import asyncio
import time
import pytest

import packages.ai.response_cache as rc


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_cache(monkeypatch):
    """Reset cache state between tests to avoid cross-test pollution."""
    monkeypatch.setattr(rc, "_CACHE_ENABLED", True)
    monkeypatch.setattr(rc, "_CACHE_TTL_SEC", 3600.0)
    monkeypatch.setattr(rc, "_CACHE_MAX_SIZE", 256)
    rc._cache.clear()
    rc._hits = 0
    rc._misses = 0
    yield
    rc._cache.clear()
    rc._hits = 0
    rc._misses = 0


# ── Helpers ───────────────────────────────────────────────────────────────────


def _payload(
    model: str = "test-model",
    messages: list | None = None,
    temperature: float = 0.0,
    stream: bool = False,
    max_tokens: int = 100,
) -> dict:
    return {
        "model": model,
        "messages": messages or [{"role": "user", "content": "hello"}],
        "temperature": temperature,
        "stream": stream,
        "max_tokens": max_tokens,
    }


def _body(content: str = "world", model: str = "test-model") -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
    }


# ── is_cacheable ──────────────────────────────────────────────────────────────


def test_cacheable_temperature_zero():
    assert rc.is_cacheable(_payload(temperature=0.0)) is True


def test_not_cacheable_temperature_positive():
    assert rc.is_cacheable(_payload(temperature=0.7)) is False


def test_not_cacheable_streaming():
    assert rc.is_cacheable(_payload(stream=True)) is False


def test_not_cacheable_when_disabled(monkeypatch):
    monkeypatch.setattr(rc, "_CACHE_ENABLED", False)
    assert rc.is_cacheable(_payload()) is False


def test_cacheable_integer_zero_temperature():
    assert rc.is_cacheable(_payload(temperature=0)) is True


def test_not_cacheable_tiny_positive_temperature():
    assert rc.is_cacheable(_payload(temperature=0.01)) is False


def test_not_cacheable_when_temperature_omitted():
    """Omitted temperature must not be cached — providers default to non-zero."""
    payload = {
        "model": "test-model",
        "messages": [{"role": "user", "content": "hello"}],
    }
    assert rc.is_cacheable(payload) is False


# ── get_cached / put_cached round-trip ───────────────────────────────────────


@pytest.mark.asyncio
async def test_cache_miss_on_empty_cache():
    result = await rc.get_cached(_payload())
    assert result is None


@pytest.mark.asyncio
async def test_put_then_get():
    p = _payload()
    body = _body()
    await rc.put_cached(p, body)
    result = await rc.get_cached(p)
    assert result == body


@pytest.mark.asyncio
async def test_cache_miss_different_model():
    await rc.put_cached(_payload(model="model-a"), _body(model="model-a"))
    result = await rc.get_cached(_payload(model="model-b"))
    assert result is None


@pytest.mark.asyncio
async def test_cache_miss_different_messages():
    await rc.put_cached(_payload(messages=[{"role": "user", "content": "hi"}]), _body())
    result = await rc.get_cached(_payload(messages=[{"role": "user", "content": "bye"}]))
    assert result is None


@pytest.mark.asyncio
async def test_not_stored_for_stream():
    p = _payload(stream=True)
    await rc.put_cached(p, _body())
    result = await rc.get_cached(p)
    assert result is None


@pytest.mark.asyncio
async def test_not_stored_for_positive_temperature():
    p = _payload(temperature=0.5)
    await rc.put_cached(p, _body())
    result = await rc.get_cached(p)
    assert result is None


# ── TTL expiry ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_expired_entry_returns_none(monkeypatch):
    monkeypatch.setattr(rc, "_CACHE_TTL_SEC", 0.01)
    p = _payload()
    await rc.put_cached(p, _body())
    await asyncio.sleep(0.05)
    result = await rc.get_cached(p)
    assert result is None


# ── LRU eviction ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lru_eviction_when_over_max_size(monkeypatch):
    monkeypatch.setattr(rc, "_CACHE_MAX_SIZE", 3)
    for i in range(4):
        await rc.put_cached(
            _payload(messages=[{"role": "user", "content": f"msg-{i}"}]),
            _body(content=f"resp-{i}"),
        )
    assert len(rc._cache) <= 3


@pytest.mark.asyncio
async def test_lru_evicts_least_recently_used(monkeypatch):
    monkeypatch.setattr(rc, "_CACHE_MAX_SIZE", 2)
    p0 = _payload(messages=[{"role": "user", "content": "first"}])
    p1 = _payload(messages=[{"role": "user", "content": "second"}])
    p2 = _payload(messages=[{"role": "user", "content": "third"}])

    await rc.put_cached(p0, _body(content="r0"))
    await rc.put_cached(p1, _body(content="r1"))
    # Access p0 to make it recently used
    await rc.get_cached(p0)
    # Adding p2 should evict p1 (LRU), not p0
    await rc.put_cached(p2, _body(content="r2"))

    assert await rc.get_cached(p0) is not None, "p0 should still be cached (recently accessed)"
    assert await rc.get_cached(p1) is None, "p1 should have been evicted (LRU)"
    assert await rc.get_cached(p2) is not None


# ── cache_stats ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cache_stats_empty():
    stats = await rc.cache_stats()
    assert stats["size"] == 0
    assert stats["hits"] == 0
    assert stats["misses"] == 0
    assert stats["hit_rate_pct"] == 0.0
    assert stats["enabled"] is True


@pytest.mark.asyncio
async def test_cache_stats_after_put_and_get():
    p = _payload()
    await rc.put_cached(p, _body())
    await rc.get_cached(p)  # hit
    await rc.get_cached(_payload(model="other"))  # miss

    stats = await rc.cache_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["hit_rate_pct"] == 50.0
    assert stats["live_entries"] == 1


# ── clear_cache ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_clear_cache_removes_all_entries():
    for i in range(5):
        await rc.put_cached(
            _payload(messages=[{"role": "user", "content": f"m{i}"}]),
            _body(),
        )
    count = await rc.clear_cache()
    assert count == 5
    assert len(rc._cache) == 0


@pytest.mark.asyncio
async def test_clear_cache_returns_zero_on_empty():
    count = await rc.clear_cache()
    assert count == 0


# ── tools exclusion ───────────────────────────────────────────────────────────


def test_not_cacheable_when_tools_present():
    """Requests with tool definitions must never be cached — tool calls depend on live state."""
    payload = {
        "model": "test-model",
        "messages": [{"role": "user", "content": "what's the weather?"}],
        "temperature": 0.0,
        "tools": [{"type": "function", "function": {"name": "get_weather", "parameters": {}}}],
    }
    assert rc.is_cacheable(payload) is False


@pytest.mark.asyncio
async def test_tools_payload_not_stored():
    """put_cached must silently skip tool-use payloads."""
    payload = {
        "model": "test-model",
        "messages": [{"role": "user", "content": "search"}],
        "temperature": 0.0,
        "tools": [{"type": "function", "function": {"name": "search", "parameters": {}}}],
    }
    await rc.put_cached(payload, _body())
    result = await rc.get_cached(payload)
    assert result is None


# ── response_format in cache key ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_different_response_format_is_cache_miss():
    """A JSON-mode request must not receive a plain-text cached response."""
    plain_payload = _payload()
    json_payload = dict(_payload(), response_format={"type": "json_object"})

    await rc.put_cached(plain_payload, _body(content='{"ok": true}'))

    # The json_object request must miss even though model/messages/temp match
    result = await rc.get_cached(json_payload)
    assert result is None


@pytest.mark.asyncio
async def test_same_response_format_is_cache_hit():
    """Two JSON-mode requests with identical params should share the cache."""
    json_payload = dict(_payload(), response_format={"type": "json_object"})
    body = _body(content='{"answer": 42}')

    await rc.put_cached(json_payload, body)
    result = await rc.get_cached(json_payload)
    assert result == body
