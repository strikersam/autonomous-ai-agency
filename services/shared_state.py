"""Shared-state abstraction — in-memory (default) and Redis backends.

Provides distributed locks, cooldowns, and rate-limit windows so the worker
process and web process can coordinate without a database.

Backends
--------
- **in-memory** (default): Fast, zero-config, single-process only.  Saved state
  is lost on restart.
- **Redis**: When ``REDIS_URL`` is set, all operations go through Redis.
  Survives restarts and works across processes.

Usage
-----
::

    from services.shared_state import claim, release, cooldown_set, cooldown_get

    if await claim(f"task:{task_id}", ttl=3600):
        try:
            ...
        finally:
            await release(f"task:{task_id}")

    await cooldown_set(f"provider:openai", ttl=30)
    is_cool = await cooldown_get(f"provider:openai")

Environment
-----------
  REDIS_URL    redis://... or rediss://... connection string (default: in-memory)
"""

from __future__ import annotations

import asyncio
import logging
import os
import time

log = logging.getLogger("qwen-proxy")

_REDIS_URL = os.environ.get("REDIS_URL", "").strip()
_REDIS_TTL_MAX = 7 * 24 * 3600  # 7 days — reasonable upper bound for any TTL


# ═══════════════════════════════════════════════════════════════════════════════
# In-memory backend
# ═══════════════════════════════════════════════════════════════════════════════

class _InMemoryBackend:
    """Single-process backend using asyncio.Lock + dicts with TTL timestamps."""

    def __init__(self) -> None:
        self._data: dict[str, float] = {}
        self._guard = asyncio.Lock()

    async def _cleanup(self, key: str) -> None:
        now = time.monotonic()
        if key in self._data and self._data[key] <= now:
            del self._data[key]

    async def claim(self, key: str, ttl: int) -> bool:
        async with self._guard:
            await self._cleanup(f"lock:{key}")
            full_key = f"lock:{key}"
            if full_key in self._data:
                return False
            self._data[full_key] = time.monotonic() + min(ttl, _REDIS_TTL_MAX)
            return True

    async def release(self, key: str) -> None:
        async with self._guard:
            self._data.pop(f"lock:{key}", None)

    async def cooldown_set(self, key: str, ttl: int) -> None:
        async with self._guard:
            full_key = f"cooldown:{key}"
            self._data[full_key] = time.monotonic() + min(ttl, _REDIS_TTL_MAX)

    async def cooldown_get(self, key: str) -> bool:
        async with self._guard:
            await self._cleanup(f"cooldown:{key}")
            full_key = f"cooldown:{key}"
            return full_key in self._data

    async def incr_window(self, key: str, window_s: int, _limit: int = 0) -> int:
        async with self._guard:
            full_key = f"window:{key}"
            now = time.monotonic()
            if full_key in self._data:
                count, until = self._data[full_key]  # type: ignore[assignment]
                if now >= until:
                    count = 0
                count = int(count) + 1
            else:
                count = 1
            self._data[full_key] = (
                count,
                now + min(window_s, _REDIS_TTL_MAX),
            )  # type: ignore[assignment]
            return count


# ═══════════════════════════════════════════════════════════════════════════════
# Redis backend
# ═══════════════════════════════════════════════════════════════════════════════

class _RedisBackend:
    """Redis-backed shared state using SET NX / DELETE / SETEX / INCR+EXPIRE."""

    def __init__(self) -> None:
        self._redis: object = None  # lazy init
        self._prefix = os.environ.get("REDIS_KEY_PREFIX", "llms:")

    async def _client(self):
        """Lazy-create the Redis client (imported on first use so a missing
        ``redis`` package doesn't crash the in-memory path)."""
        if self._redis is None:
            import redis.asyncio as _redis_mod

            self._redis = _redis_mod.from_url(_REDIS_URL)
        return self._redis

    async def claim(self, key: str, ttl: int) -> bool:
        client = await self._client()
        result = await client.set(
            f"{self._prefix}lock:{key}", "1", nx=True, ex=min(ttl, _REDIS_TTL_MAX)
        )
        return result is True

    async def release(self, key: str) -> None:
        client = await self._client()
        await client.delete(f"{self._prefix}lock:{key}")

    async def cooldown_set(self, key: str, ttl: int) -> None:
        client = await self._client()
        await client.setex(
            f"{self._prefix}cooldown:{key}", min(ttl, _REDIS_TTL_MAX), "1"
        )

    async def cooldown_get(self, key: str) -> bool:
        client = await self._client()
        return await client.exists(f"{self._prefix}cooldown:{key}") > 0

    async def incr_window(self, key: str, window_s: int, _limit: int = 0) -> int:
        client = await self._client()
        full_key = f"{self._prefix}window:{key}"
        count = await client.incr(full_key)
        if count == 1:
            await client.expire(full_key, min(window_s, _REDIS_TTL_MAX))
        return count


# ═══════════════════════════════════════════════════════════════════════════════
# Singleton dispatch
# ═══════════════════════════════════════════════════════════════════════════════

_backend: _InMemoryBackend | _RedisBackend | None = None


def _get_backend() -> _InMemoryBackend | _RedisBackend:
    global _backend
    if _backend is None:
        if _REDIS_URL:
            log.info("Shared-state backend: Redis at %s", _REDIS_URL)
            _backend = _RedisBackend()
        else:
            log.info("Shared-state backend: in-memory (no REDIS_URL set)")
            _backend = _InMemoryBackend()
    return _backend


def _reset_backend() -> None:
    """Reset the singleton (for tests)."""
    global _backend
    _backend = None


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════


async def claim(key: str, ttl: int) -> bool:
    """Try to acquire a named lock. Returns True if acquired, False if already held."""
    return await _get_backend().claim(key, ttl)


async def release(key: str) -> None:
    """Release a previously acquired lock."""
    await _get_backend().release(key)


async def cooldown_set(key: str, ttl: int) -> None:
    """Put a key on cooldown for *ttl* seconds."""
    await _get_backend().cooldown_set(key, ttl)


async def cooldown_get(key: str) -> bool:
    """Return True if *key* is still within its cooldown window."""
    return await _get_backend().cooldown_get(key)


async def incr_window(key: str, window_s: int, limit: int = 0) -> int:
    """Increment a rate-limit counter. Returns the current count within the window."""
    return await _get_backend().incr_window(key, window_s, limit)
