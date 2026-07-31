"""packages/llm/queue.py — admission control, concurrency, and bulkheads.

Three separate mechanisms, deliberately not merged:

``RequestQueue``  A priority queue in front of the router. Bounds how much
                  work can be pending, so a burst produces backpressure
                  (``QueueFull``) instead of unbounded memory growth.

``Bulkhead``      One semaphore per provider. A provider that stops
                  responding can exhaust only its own slots — the outage is
                  contained instead of draining a shared pool and stalling
                  providers that are perfectly healthy (ADR-008 §5).

``Deduplicator``  Collapses concurrent identical requests onto one in-flight
                  call. Twelve agents asking the same question during a fan-out
                  cost one completion, not twelve.

All three are asyncio-native and hold no cross-process state; distributed
coordination lives in ``packages/llm/distributed.py``.
"""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import heapq
import json
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from packages.llm.types import Priority, QueueFull

log = logging.getLogger("llm.queue")

T = TypeVar("T")


# ── Bulkhead ─────────────────────────────────────────────────────────────────

class Bulkhead:
    """Per-provider concurrency isolation."""

    def __init__(self, default_limit: int = 8) -> None:
        self._default = max(1, default_limit)
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._limits: dict[str, int] = {}
        self._in_flight: dict[str, int] = {}
        self._rejected: dict[str, int] = {}
        self._lock = asyncio.Lock()

    def configure(self, provider_id: str, limit: int) -> None:
        """Set a provider's slot count. Safe to call before any traffic."""
        limit = max(1, limit)
        if provider_id in self._semaphores and self._limits.get(provider_id) == limit:
            return
        self._limits[provider_id] = limit
        self._semaphores[provider_id] = asyncio.Semaphore(limit)

    def _semaphore(self, provider_id: str) -> asyncio.Semaphore:
        semaphore = self._semaphores.get(provider_id)
        if semaphore is None:
            semaphore = asyncio.Semaphore(self._default)
            self._semaphores[provider_id] = semaphore
            self._limits[provider_id] = self._default
        return semaphore

    @contextlib.asynccontextmanager
    async def slot(self, provider_id: str, *, timeout: float = 30.0) -> AsyncIterator[bool]:
        """Hold one slot for the duration of the block.

        Yields ``False`` when no slot became free within ``timeout`` — the
        caller should move to a different provider rather than wait longer.
        That is the whole point of the bulkhead: a saturated provider redirects
        traffic instead of absorbing it.
        """
        semaphore = self._semaphore(provider_id)
        acquired = False
        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=timeout)
            acquired = True
        except (asyncio.TimeoutError, TimeoutError):
            self._rejected[provider_id] = self._rejected.get(provider_id, 0) + 1
            log.debug("llm.queue: bulkhead full for %s after %.1fs", provider_id, timeout)
            yield False
            return

        self._in_flight[provider_id] = self._in_flight.get(provider_id, 0) + 1
        try:
            yield True
        finally:
            self._in_flight[provider_id] = max(0, self._in_flight.get(provider_id, 1) - 1)
            if acquired:
                semaphore.release()

    def in_flight(self, provider_id: str | None = None) -> Any:
        if provider_id is None:
            return dict(self._in_flight)
        return self._in_flight.get(provider_id, 0)

    def snapshot(self) -> dict[str, Any]:
        return {
            "limits": dict(self._limits),
            "in_flight": dict(self._in_flight),
            "rejected": dict(self._rejected),
        }

    def reset(self) -> None:
        self._semaphores.clear()
        self._limits.clear()
        self._in_flight.clear()
        self._rejected.clear()


# ── Deduplication ────────────────────────────────────────────────────────────

def request_fingerprint(payload: dict[str, Any]) -> str:
    """Stable hash of the semantically significant parts of a request."""
    material = {
        "model": payload.get("model"),
        "messages": payload.get("messages"),
        "tools": payload.get("tools"),
        "temperature": payload.get("temperature"),
        "max_tokens": payload.get("max_tokens"),
        "response_format": payload.get("response_format"),
        # Same reason as the cache key: two requests with different provider
        # constraints must not collapse onto one in-flight call.
        "allow_paid": payload.get("allow_paid"),
        "providers": payload.get("providers"),
        "exclude_providers": payload.get("exclude_providers"),
    }
    encoded = json.dumps(material, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class Deduplicator(Generic[T]):
    """Collapse concurrent identical calls onto a single execution."""

    def __init__(self, window_sec: float = 30.0) -> None:
        self._window = window_sec
        self._in_flight: dict[str, asyncio.Future[T]] = {}
        self._started: dict[str, float] = {}
        self._hits = 0
        self._misses = 0
        self._lock = asyncio.Lock()

    async def run(self, fingerprint: str, factory: Callable[[], Awaitable[T]]) -> tuple[T, bool]:
        """Execute ``factory``, or await an identical call already running.

        Returns ``(result, was_deduplicated)``. Every waiter gets the same
        result object, so callers must not mutate it — the router copies
        before annotating.
        """
        async with self._lock:
            existing = self._in_flight.get(fingerprint)
            fresh = existing is not None and (
                time.monotonic() - self._started.get(fingerprint, 0.0) < self._window
            )
            if existing is not None and fresh and not existing.done():
                self._hits += 1
                future = existing
                joined = True
            else:
                future = asyncio.get_running_loop().create_future()
                self._in_flight[fingerprint] = future
                self._started[fingerprint] = time.monotonic()
                self._misses += 1
                joined = False

        if joined:
            return await future, True

        try:
            result = await factory()
        except BaseException as exc:
            async with self._lock:
                self._in_flight.pop(fingerprint, None)
                self._started.pop(fingerprint, None)
            if not future.done():
                future.set_exception(exc)
            # Waiters observe the exception through the future; make sure the
            # retrieval is not reported as "never retrieved" by asyncio.
            with contextlib.suppress(BaseException):
                future.exception()
            raise

        async with self._lock:
            self._in_flight.pop(fingerprint, None)
            self._started.pop(fingerprint, None)
        if not future.done():
            future.set_result(result)
        return result, False

    def stats(self) -> dict[str, Any]:
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 4) if total else 0.0,
            "in_flight": len(self._in_flight),
        }

    def reset(self) -> None:
        self._in_flight.clear()
        self._started.clear()
        self._hits = 0
        self._misses = 0


# ── Priority queue ───────────────────────────────────────────────────────────

@dataclass(order=True)
class _Waiter:
    """One job waiting for a concurrency slot, ordered by (priority, arrival)."""

    priority: int
    sequence: int
    event: asyncio.Event = field(compare=False, default_factory=asyncio.Event)


class RequestQueue:
    """Bounded priority queue with concurrency limits and backpressure.

    Admission is ordered by (priority, arrival): a CRITICAL request overtakes
    NORMAL work already waiting, and ties inside a band are strict FIFO so no
    job is starved by a steady trickle of same-priority arrivals.

    A plain ``asyncio.Semaphore`` cannot express this — it is FIFO over the
    order tasks happened to await it, so priority had no effect at all. Slots
    are therefore handed out explicitly from a heap of waiters.
    """

    def __init__(self, *, max_depth: int = 512, max_concurrency: int = 32) -> None:
        self._max_depth = max_depth
        self._max_concurrency = max_concurrency
        self._waiters: list[_Waiter] = []
        self._in_flight = 0
        self._depth = 0
        self._sequence = 0
        self._peak_depth = 0
        self._enqueued = 0
        self._rejected = 0
        self._completed = 0
        self._cancelled = 0
        self._timed_out = 0
        self._wait_total = 0.0
        self._lock = asyncio.Lock()

    @property
    def depth(self) -> int:
        return self._depth

    async def submit(
        self,
        job: Callable[[], Awaitable[T]],
        *,
        priority: Priority | int = Priority.NORMAL,
        timeout: float | None = None,
    ) -> T:
        """Run ``job`` under the queue's concurrency limit.

        Raises ``QueueFull`` immediately when the queue is at capacity — the
        backpressure signal. Raises ``asyncio.TimeoutError`` when ``timeout``
        elapses, counting the wait *and* the execution.
        """
        async with self._lock:
            if self._depth >= self._max_depth:
                self._rejected += 1
                raise QueueFull(
                    f"LLM request queue full ({self._depth}/{self._max_depth}) — "
                    "shed load or raise routing.queue_max_depth"
                )
            self._depth += 1
            self._sequence += 1
            self._enqueued += 1
            self._peak_depth = max(self._peak_depth, self._depth)

        waited_from = time.monotonic()
        priority_value = int(priority)
        try:
            if timeout is not None:
                return await asyncio.wait_for(
                    self._run(job, waited_from, priority_value), timeout=timeout
                )
            return await self._run(job, waited_from, priority_value)
        except (asyncio.TimeoutError, TimeoutError):
            self._timed_out += 1
            raise
        except asyncio.CancelledError:
            self._cancelled += 1
            raise
        finally:
            async with self._lock:
                self._depth = max(0, self._depth - 1)

    async def _acquire(self, priority: int) -> None:
        """Wait for a slot, yielding to higher-priority work already queued."""
        async with self._lock:
            if self._in_flight < self._max_concurrency and not self._waiters:
                self._in_flight += 1
                return
            self._sequence += 1
            waiter = _Waiter(priority=priority, sequence=self._sequence)
            heapq.heappush(self._waiters, waiter)
        try:
            await waiter.event.wait()
        except asyncio.CancelledError:
            async with self._lock:
                if waiter in self._waiters:
                    self._waiters.remove(waiter)
                    heapq.heapify(self._waiters)
                elif waiter.event.is_set():
                    # The slot was already granted — hand it straight on.
                    self._release_locked()
            raise

    def _release_locked(self) -> None:
        """Give the slot to the best waiting job, or return it to the pool."""
        if self._waiters:
            heapq.heappop(self._waiters).event.set()
        else:
            self._in_flight = max(0, self._in_flight - 1)

    async def _release(self) -> None:
        async with self._lock:
            self._release_locked()

    async def _run(
        self, job: Callable[[], Awaitable[T]], waited_from: float, priority: int
    ) -> T:
        await self._acquire(priority)
        try:
            self._wait_total += time.monotonic() - waited_from
            result = await job()
            self._completed += 1
            return result
        finally:
            await self._release()

    def stats(self) -> dict[str, Any]:
        return {
            "depth": self._depth,
            "peak_depth": self._peak_depth,
            "max_depth": self._max_depth,
            "max_concurrency": self._max_concurrency,
            "enqueued": self._enqueued,
            "completed": self._completed,
            "rejected": self._rejected,
            "cancelled": self._cancelled,
            "timed_out": self._timed_out,
            "avg_wait_ms": round(
                (self._wait_total / self._completed) * 1000, 1
            ) if self._completed else 0.0,
        }

    def reset(self) -> None:
        self._depth = 0
        self._sequence = 0
        self._peak_depth = 0
        self._enqueued = 0
        self._rejected = 0
        self._completed = 0
        self._cancelled = 0
        self._timed_out = 0
        self._wait_total = 0.0
        self._waiters.clear()
        self._in_flight = 0
