"""Tests for the shared-state abstraction (in-memory and Redis/fakeredis backends)."""

from __future__ import annotations

import asyncio
import os

import pytest

from services.shared_state import (
    _reset_backend,
    claim,
    cooldown_get,
    cooldown_set,
    incr_window,
    release,
)


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    """Reset the shared-state singleton before every test."""
    _reset_backend()
    # Ensure Redis URL is unset so tests default to in-memory
    if "REDIS_URL" in os.environ:
        del os.environ["REDIS_URL"]


# ═══════════════════════════════════════════════════════════════════════════════
# In-memory backend tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestInMemoryClaim:
    async def test_claim_returns_true_first_time(self) -> None:
        result = await claim("test-key", ttl=60)
        assert result is True

    async def test_claim_returns_false_while_held(self) -> None:
        await claim("test-key", ttl=60)
        result = await claim("test-key", ttl=60)
        assert result is False

    async def test_release_allows_reclaim(self) -> None:
        await claim("test-key", ttl=60)
        await release("test-key")
        result = await claim("test-key", ttl=60)
        assert result is True

    async def test_release_idempotent(self) -> None:
        await release("nonexistent")
        result = await claim("nonexistent", ttl=60)
        assert result is True

    async def test_ttl_expiry_releases_claim(self) -> None:
        await claim("test-key", ttl=1)
        await asyncio.sleep(1.1)
        result = await claim("test-key", ttl=60)
        assert result is True


class TestInMemoryCooldown:
    async def test_cooldown_set_then_get(self) -> None:
        await cooldown_set("provider:test", ttl=60)
        assert await cooldown_get("provider:test") is True

    async def test_cooldown_get_returns_false_when_not_set(self) -> None:
        assert await cooldown_get("provider:nonexistent") is False

    async def test_cooldown_get_returns_false_after_expiry(self) -> None:
        await cooldown_set("provider:test", ttl=1)
        await asyncio.sleep(1.1)
        assert await cooldown_get("provider:test") is False


class TestInMemoryIncrWindow:
    async def test_incr_window_starts_at_one(self) -> None:
        count = await incr_window("rate:test", window_s=60)
        assert count == 1

    async def test_incr_window_increments(self) -> None:
        await incr_window("rate:test", window_s=60)
        count = await incr_window("rate:test", window_s=60)
        assert count == 2

    async def test_incr_window_resets_after_window(self) -> None:
        await incr_window("rate:test", window_s=1)
        await incr_window("rate:test", window_s=1)
        await asyncio.sleep(1.1)
        count = await incr_window("rate:test", window_s=1)
        assert count == 1


class TestInMemoryKeyIsolation:
    async def test_different_keys_dont_interfere(self) -> None:
        await claim("task:a", ttl=60)
        result = await claim("task:b", ttl=60)
        assert result is True

    async def test_cooldown_separate_from_lock(self) -> None:
        await cooldown_set("provider:x", ttl=60)
        result = await claim("provider:x", ttl=60)
        assert result is True  # cooldown and lock are separate key spaces


# ═══════════════════════════════════════════════════════════════════════════════
# Redis backend tests (fakeredis)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def _redis_backend(monkeypatch):
    """Configure the shared_state module to use fakeredis for the test."""
    import fakeredis.aioredis as _fakeredis_mod

    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(
        "redis.asyncio.from_url",
        staticmethod(lambda url, **kw: _fakeredis_mod.FakeRedis()),
    )
    _reset_backend()


class TestRedisClaim:
    async def test_claim_returns_true_first_time(self, _redis_backend: None) -> None:
        result = await claim("test-key", ttl=60)
        assert result is True

    async def test_claim_returns_false_while_held(self, _redis_backend: None) -> None:
        await claim("test-key", ttl=60)
        result = await claim("test-key", ttl=60)
        assert result is False

    async def test_release_allows_reclaim(self, _redis_backend: None) -> None:
        await claim("test-key", ttl=60)
        await release("test-key")
        result = await claim("test-key", ttl=60)
        assert result is True


class TestRedisCooldown:
    async def test_cooldown_set_then_get(self, _redis_backend: None) -> None:
        await cooldown_set("provider:test", ttl=60)
        assert await cooldown_get("provider:test") is True

    async def test_cooldown_get_returns_false_when_not_set(self, _redis_backend: None) -> None:
        assert await cooldown_get("provider:nonexistent") is False


class TestRedisIncrWindow:
    async def test_incr_window_starts_at_one(self, _redis_backend: None) -> None:
        count = await incr_window("rate:test", window_s=60)
        assert count == 1

    async def test_incr_window_increments(self, _redis_backend: None) -> None:
        await incr_window("rate:test", window_s=60)
        count = await incr_window("rate:test", window_s=60)
        assert count == 2
