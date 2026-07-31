"""packages/llm/distributed.py — cross-instance coordination.

Two facilities that only matter once more than one process routes traffic:

``DistributedRateLimiter``  A shared token bucket. With three Render instances
                            each locally pacing at the provider's full RPM,
                            the provider sees 3x the limit and 429s everyone.
                            A shared bucket makes the pace correct in
                            aggregate.

``PersistentQueue``         Durable storage for queued work, so requests that
                            were pending when a process restarted are picked
                            up rather than lost.

Both degrade to correct single-instance behaviour when no Redis URL is
configured: the limiter falls back to a local bucket, the queue to memory.
That keeps development and CI free of infrastructure while production gets
the shared semantics.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("llm.distributed")

# How long to wait before retrying a failed Redis connection.
_RECONNECT_COOLDOWN_SEC = 30.0

# Atomic refill-and-consume. Kept in Lua so the read-modify-write cannot
# interleave between instances — the entire reason for using Redis here.
_TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local rate = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local requested = tonumber(ARGV[3])
-- Server clock, not the caller's: each instance passing its own
-- time.time() let a fast-running clock refill the shared bucket for
-- its own skew. Redis 7 replicates script effects, so TIME is fine.
local t = redis.call('TIME')
local now = tonumber(t[1]) + tonumber(t[2]) / 1000000

local bucket = redis.call('HMGET', key, 'tokens', 'updated')
local tokens = tonumber(bucket[1])
local updated = tonumber(bucket[2])

if tokens == nil then
  tokens = capacity
  updated = now
end

local elapsed = math.max(0, now - updated)
tokens = math.min(capacity, tokens + elapsed * rate)

local allowed = 0
if tokens >= requested then
  tokens = tokens - requested
  allowed = 1
end

redis.call('HSET', key, 'tokens', tokens, 'updated', now)
redis.call('EXPIRE', key, 3600)
return {allowed, tostring(tokens)}
"""


@dataclass
class _LocalBucket:
    """In-process token bucket — the fallback when Redis is absent."""

    rate_per_sec: float
    capacity: float
    tokens: float = 0.0
    updated: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        self.tokens = self.capacity

    def consume(self, amount: float = 1.0) -> tuple[bool, float]:
        now = time.monotonic()
        self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate_per_sec)
        self.updated = now
        if self.tokens >= amount:
            self.tokens -= amount
            return True, self.tokens
        return False, self.tokens


class DistributedRateLimiter:
    """Token bucket shared across instances when Redis is available."""

    def __init__(self, redis_url: str = "", *, namespace: str = "llm:rl") -> None:
        self._namespace = namespace
        self._redis_url = redis_url
        self._redis: Any = None
        self._script: Any = None
        self._local: dict[str, _LocalBucket] = {}
        self._lock = threading.Lock()
        # A retry deadline rather than a one-shot flag: a single failed ping
        # used to pin the process into local-only mode for its whole lifetime,
        # so shared pacing never came back after a brief Redis blip.
        self._next_connect_at = 0.0
        self._redis_unavailable = False   # permanent: the package is missing

    @property
    def distributed(self) -> bool:
        """True once a Redis connection has actually been established."""
        return self._redis is not None

    async def _ensure_redis(self) -> Any:
        if self._redis is not None or self._redis_unavailable or not self._redis_url:
            return self._redis
        if time.monotonic() < self._next_connect_at:
            return None
        self._next_connect_at = time.monotonic() + _RECONNECT_COOLDOWN_SEC
        try:
            import redis.asyncio as aioredis
        except ImportError:
            self._redis_unavailable = True   # never going to appear at runtime
            log.info("llm.distributed: redis package absent — pacing locally")
            return None
        try:
            client = aioredis.from_url(self._redis_url, decode_responses=True)
            await client.ping()
            self._redis = client
            self._script = client.register_script(_TOKEN_BUCKET_LUA)
            log.info("llm.distributed: shared rate limiting active")
        except Exception as exc:
            log.warning("llm.distributed: Redis unavailable (%s) — pacing locally", exc)
        return self._redis

    def _bucket(self, key: str, rate_per_sec: float, capacity: float) -> _LocalBucket:
        with self._lock:
            bucket = self._local.get(key)
            if bucket is None or bucket.rate_per_sec != rate_per_sec:
                bucket = _LocalBucket(rate_per_sec=rate_per_sec, capacity=capacity)
                self._local[key] = bucket
            return bucket

    async def acquire(
        self,
        provider_id: str,
        *,
        requests_per_minute: int,
        tokens: float = 1.0,
        max_wait_sec: float = 5.0,
    ) -> bool:
        """Consume capacity, waiting up to ``max_wait_sec``.

        Returns False when capacity never became available — the caller should
        try a different provider rather than block, which is what keeps a
        rate-limited provider from becoming a queue.
        """
        if requests_per_minute <= 0:
            return True

        rate_per_sec = requests_per_minute / 60.0
        capacity = float(max(1, requests_per_minute))
        key = f"{self._namespace}:{provider_id}"
        deadline = time.monotonic() + max_wait_sec

        while True:
            allowed = await self._try_consume(key, rate_per_sec, capacity, tokens)
            if allowed:
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            await asyncio.sleep(min(0.25, remaining))

    async def _try_consume(
        self, key: str, rate_per_sec: float, capacity: float, tokens: float
    ) -> bool:
        redis = await self._ensure_redis()
        if redis is not None and self._script is not None:
            try:
                allowed, _remaining = await self._script(
                    keys=[key], args=[rate_per_sec, capacity, tokens]
                )
                return bool(int(allowed))
            except Exception as exc:
                log.warning("llm.distributed: Redis consume failed (%s) — local fallback", exc)
                self._redis = None
        allowed, _remaining = self._bucket(key, rate_per_sec, capacity).consume(tokens)
        return allowed

    async def close(self) -> None:
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:  # pragma: no cover - best effort
                pass
            self._redis = None

    def reset(self) -> None:
        with self._lock:
            self._local.clear()
            self._next_connect_at = 0.0


@dataclass
class PersistedRequest:
    """One queued request durable across a restart."""

    id: str
    payload: dict[str, Any]
    priority: int
    enqueued_at: float
    attempts: int = 0
    agent: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "payload": self.payload,
            "priority": self.priority,
            "enqueued_at": self.enqueued_at,
            "attempts": self.attempts,
            "agent": self.agent,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PersistedRequest:
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex),
            payload=data.get("payload") or {},
            priority=int(data.get("priority") or 20),
            enqueued_at=float(data.get("enqueued_at") or time.time()),
            attempts=int(data.get("attempts") or 0),
            agent=str(data.get("agent") or ""),
        )


class PersistentQueue:
    """Durable pending-work store backed by Redis, with a memory fallback.

    Deliberately *not* a full job runner. It records what was accepted but not
    yet completed so a restart can replay it; execution stays with
    ``RequestQueue``, which owns concurrency. Keeping the two apart means a
    storage outage degrades durability without stopping traffic.
    """

    def __init__(self, redis_url: str = "", *, namespace: str = "llm:queue") -> None:
        self._namespace = namespace
        self._redis_url = redis_url
        self._redis: Any = None
        self._next_connect_at = 0.0
        self._redis_unavailable = False
        self._memory: dict[str, PersistedRequest] = {}
        self._lock = threading.Lock()

    async def _ensure_redis(self) -> Any:
        if self._redis is not None or self._redis_unavailable or not self._redis_url:
            return self._redis
        if time.monotonic() < self._next_connect_at:
            return None
        self._next_connect_at = time.monotonic() + _RECONNECT_COOLDOWN_SEC
        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(self._redis_url, decode_responses=True)
            await client.ping()
            self._redis = client
            log.info("llm.distributed: persistent queue active")
        except Exception as exc:
            log.info("llm.distributed: persistent queue in memory only (%s)", exc)
        return self._redis

    async def enqueue(self, request: PersistedRequest) -> str:
        redis = await self._ensure_redis()
        if redis is not None:
            try:
                await redis.hset(self._namespace, request.id, json.dumps(request.as_dict()))
                return request.id
            except Exception as exc:
                log.warning("llm.distributed: enqueue persist failed (%s)", exc)
        with self._lock:
            self._memory[request.id] = request
        return request.id

    async def complete(self, request_id: str) -> None:
        redis = await self._ensure_redis()
        if redis is not None:
            try:
                await redis.hdel(self._namespace, request_id)
            except Exception as exc:
                log.warning("llm.distributed: complete failed (%s)", exc)
        with self._lock:
            self._memory.pop(request_id, None)

    async def pending(self) -> list[PersistedRequest]:
        """Everything accepted but not completed — the restart replay set.

        Both stores are merged. `enqueue` falls back to memory when a Redis
        write fails, so returning only the Redis hash after recovery would
        silently drop accepted work from the replay set.
        """
        merged: dict[str, PersistedRequest] = {}
        with self._lock:
            merged.update(self._memory)
        redis = await self._ensure_redis()
        if redis is not None:
            try:
                entries = await redis.hgetall(self._namespace)
                for raw in entries.values():
                    record = PersistedRequest.from_dict(json.loads(raw))
                    merged[record.id] = record
            except Exception as exc:
                log.warning("llm.distributed: pending read failed (%s)", exc)
        return list(merged.values())

    async def depth(self) -> int:
        return len(await self.pending())

    def reset(self) -> None:
        with self._lock:
            self._memory.clear()
            self._next_connect_at = 0.0


_limiter: DistributedRateLimiter | None = None
_queue: PersistentQueue | None = None
_lock = threading.Lock()


def _redis_url() -> str:
    from packages.config import settings

    return getattr(settings, "redis_url", "") or ""


def get_limiter() -> DistributedRateLimiter:
    """The process-wide distributed rate limiter."""
    global _limiter
    if _limiter is None:
        with _lock:
            if _limiter is None:
                _limiter = DistributedRateLimiter(_redis_url())
    return _limiter


def get_persistent_queue() -> PersistentQueue:
    """The process-wide persistent queue."""
    global _queue
    if _queue is None:
        with _lock:
            if _queue is None:
                _queue = PersistentQueue(_redis_url())
    return _queue


def reset() -> None:
    """Test hook — drop both singletons."""
    global _limiter, _queue
    with _lock:
        _limiter = None
        _queue = None
