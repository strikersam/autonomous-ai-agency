"""packages/ai/rate_limiter.py — proactive per-provider request pacing.

``packages/ai/router.py`` already reacts well to rate limits after the fact:
exponential backoff on repeated 429s, ``Retry-After`` honored when a provider
sends one, per-model skip on 419, dead-model memory on 410. What's missing is
the proactive half — pacing requests to stay *under* a provider's limit
instead of always finding out by eating a 429 first. This module is that
missing half: a simple token-bucket limiter, one bucket per provider, that
the router can await before dispatching a request.

Deliberately does not hardcode any provider's "current" free-tier limit —
those numbers change over time and are provider-account-specific (shared
keys, org tiers, promotions), so a baked-in guess would be stale the moment
it shipped. Instead this is off by default (zero behavior change) and reads
each provider's real, current limit from an env var an operator sets after
checking that provider's own dashboard/docs — the only place that number is
actually current.

Usage::

    from packages.ai.rate_limiter import pace
    waited = await pace("cerebras")  # no-op unless CEREBRAS_MAX_RPM is set

Env vars: ``<PROVIDER_ID>_MAX_RPM`` (e.g. ``CEREBRAS_MAX_RPM=28``,
``GROQ_MAX_RPM=30``). Provider id is upper-cased as-is (matches
``provider.provider_id`` from ``packages/ai/router.py``).
"""
from __future__ import annotations

import asyncio
import logging
import os
import time

log = logging.getLogger("qwen-proxy")


class TokenBucket:
    """Rate limiter using virtual scheduling (GCRA-style): each caller
    atomically reserves the next available slot while holding the lock,
    then releases the lock and sleeps until its own slot — rather than
    computing a wait time and sleeping *outside* the lock.

    That ordering matters under concurrency: an earlier design recomputed
    "tokens available" from a shared counter, released the lock, then slept —
    so N callers arriving on a drained bucket all read roughly the same
    token count, all computed roughly the same wait, and all woke up and
    proceeded together. A drained bucket under concurrent load enforced
    nothing; it just added a uniform delay before a burst of N requests.
    Reserving a strictly increasing slot time under the lock instead spaces
    concurrent callers one interval apart, which is what "requests per
    minute" is supposed to mean.
    """

    def __init__(self, rate_per_min: float, capacity: float | None = None) -> None:
        self.rate_per_sec = max(rate_per_min, 0.001) / 60.0
        # Default burst allowance: ~10 seconds worth of tokens, floor of 1 so a
        # very low configured rate still allows at least one immediate request.
        self.capacity = capacity if capacity is not None else max(1.0, rate_per_min / 6.0)
        self._interval = 1.0 / self.rate_per_sec
        # The earliest time the next token becomes available. Seeded in the
        # past by a full burst window so the first `capacity` callers proceed
        # immediately (the intended burst allowance).
        self._next_slot = time.monotonic() - self.capacity * self._interval
        self._lock = asyncio.Lock()

    async def acquire(self, max_wait: float = 5.0) -> float:
        """Block until this caller's reserved slot arrives, or *max_wait* elapses.

        Returns seconds actually waited. Never waits longer than *max_wait* —
        if the bucket is badly drained, proceed anyway rather than stalling
        the caller indefinitely; the existing reactive 429 handling in
        router.py remains the safety net. A clamped wait means this caller's
        actual departure lags its reserved slot, which under-throttles
        slightly rather than blocking forever — the same tradeoff the
        max_wait cap already implies.
        """
        async with self._lock:
            now = time.monotonic()
            earliest = now - self.capacity * self._interval
            start = max(self._next_slot, earliest)
            my_slot = start + self._interval
            self._next_slot = my_slot
            wait = max(0.0, my_slot - now)
        wait = min(wait, max_wait)
        if wait > 0:
            await asyncio.sleep(wait)
        return wait


_buckets: dict[str, TokenBucket] = {}
_bucket_lock = asyncio.Lock()


def _configured_rpm(provider_id: str) -> float | None:
    raw = os.environ.get(f"{provider_id.upper()}_MAX_RPM")
    if not raw:
        return None
    try:
        rpm = float(raw)
    except ValueError:
        log.debug("rate_limiter: ignoring non-numeric %s_MAX_RPM=%r", provider_id.upper(), raw)
        return None
    return rpm if rpm > 0 else None


async def pace(provider_id: str, *, max_wait: float = 5.0) -> float:
    """Proactively pace a request to *provider_id*.

    No-op (returns 0.0 immediately) unless ``<PROVIDER_ID>_MAX_RPM`` is set —
    the default is zero behavior change. When set, blocks up to *max_wait*
    seconds so the request stream stays under the configured rate instead of
    bursting and relying on reactive 429 handling.
    """
    rpm = _configured_rpm(provider_id)
    if rpm is None:
        return 0.0
    async with _bucket_lock:
        bucket = _buckets.get(provider_id)
        if bucket is None or bucket.rate_per_sec != max(rpm, 0.001) / 60.0:
            bucket = TokenBucket(rpm)
            _buckets[provider_id] = bucket
    waited = await bucket.acquire(max_wait=max_wait)
    if waited > 0:
        log.debug("rate_limiter: paced %s for %.2fs (configured %s RPM)", provider_id, waited, rpm)
    return waited


def reset() -> None:
    """Clear all buckets (tests only)."""
    _buckets.clear()
