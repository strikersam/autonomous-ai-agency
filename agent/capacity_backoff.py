"""Wait out a rate-limited brain instead of retrying inside its cooldown.

A 429 cools a provider for 20s or more (``packages/ai/router.py``). Retrying an
LLM call sooner than that cannot succeed, so a short burst of rate limiting used
to fail every retry, then the step, then the task. These helpers recognise a
capacity failure and space the retries so the next attempt lands after the
cooldown.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

log = logging.getLogger("qwen-proxy")

T = TypeVar("T")

BASE_BACKOFF_S: float = 20.0
MAX_BACKOFF_S: float = 90.0
MAX_CAPACITY_RETRIES: int = 2
_NON_CAPACITY_DELAY_S: float = 0.5

_CAPACITY_MARKERS = (
    "all brain providers exhausted",
    "brain provider attempt(s) failed",
    "all configured llm providers failed",
    "all candidates failed",
    "http 429",
    "rate limit",
    "too many requests",
    "quota exhausted",
)

# Failures that mention capacity words but cannot be fixed by waiting: a reply
# that was not JSON (its text is the model's own), and no provider configured.
_NOT_CAPACITY_MARKERS = (
    "model did not return a json object",
    "no providers configured",
    "set at least one provider api key",
)

# The failover's own text for "nothing was attempted" covers two opposite cases.
_NOTHING_ATTEMPTED = "none configured or all in cooldown"

_sleep = asyncio.sleep


def _no_provider_configured() -> bool:
    """True when the brain registry has no provider at all, so waiting cannot help."""
    try:
        from services.brain_failover import brain_availability_summary
        return int(brain_availability_summary().get("total", 0) or 0) == 0
    except Exception:  # noqa: BLE001 - unknown registry state: assume a cooldown
        return False


def is_capacity_error(exc: BaseException | None) -> bool:
    """True if *exc*, or anything it was raised from, is a provider-capacity failure."""
    seen: set[int] = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        text = str(exc).lower()
        if any(marker in text for marker in _NOT_CAPACITY_MARKERS):
            return False
        if _NOTHING_ATTEMPTED in text and _no_provider_configured():
            return False
        if type(exc).__name__ == "BrainFailoverExhausted":
            return True
        if any(marker in text for marker in _CAPACITY_MARKERS):
            return True
        # Follow explicit causes only: __context__ is whatever happened to be
        # in flight, and an unrelated earlier 429 must not relabel a real defect.
        exc = exc.__cause__
    return False


def capacity_backoff_s(attempt: int) -> float:
    """Seconds to wait before retry number *attempt* (1-based), doubling up to the cap."""
    return min(BASE_BACKOFF_S * (2 ** max(attempt - 1, 0)), MAX_BACKOFF_S)


def retry_delay_s(exc: BaseException, attempt: int) -> float:
    """Delay before a retry: a cooldown-length wait for capacity errors, brief otherwise."""
    return capacity_backoff_s(attempt) if is_capacity_error(exc) else _NON_CAPACITY_DELAY_S


async def call_with_capacity_retry(fn: Callable[[], Awaitable[T]], *, what: str) -> T:
    """Await ``fn()``, retrying only capacity failures, each after a growing wait.

    Any other exception propagates at once. After ``MAX_CAPACITY_RETRIES`` waits
    the capacity error itself propagates, so a real outage still surfaces.
    """
    attempt = 0
    while True:
        try:
            return await fn()
        except Exception as exc:
            attempt += 1
            if attempt > MAX_CAPACITY_RETRIES or not is_capacity_error(exc):
                raise
            wait = capacity_backoff_s(attempt)
            log.warning(
                "%s: brain capacity error, waiting %.0fs before retry %d/%d: %s",
                what, wait, attempt, MAX_CAPACITY_RETRIES, exc,
            )
            await _sleep(wait)
