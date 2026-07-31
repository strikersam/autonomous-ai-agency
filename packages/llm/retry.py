"""packages/llm/retry.py — backoff policy.

Decides whether a failure is worth another attempt and how long to wait.
Two rules govern everything here:

* **Never retry a permanent error.** A 401 will still be a 401 in four
  seconds; retrying wastes the wall-clock budget that a genuinely transient
  failure could have used.
* **Always jitter.** Without it, every agent that hit the same 429 retries in
  the same millisecond and re-creates the burst that caused the limit.

``Retry-After`` from the provider always wins over the computed delay when
present — the provider knows its own window better than our exponent does.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass

import httpx

from packages.llm.config import RetryConfig
from packages.llm.types import LLMError, PermanentError, TransientError

log = logging.getLogger("llm.retry")


def is_retryable(error: BaseException, config: RetryConfig) -> bool:
    """Whether ``error`` justifies another attempt."""
    if isinstance(error, PermanentError):
        return False
    if isinstance(error, TransientError):
        return error.status is None or error.status in set(config.retry_statuses)
    if isinstance(error, LLMError):
        return False
    # Transport-level failures: timeouts, connection resets, DNS blips.
    #
    # httpx.TransportError is listed explicitly because httpx's hierarchy is
    # TransportError -> RequestError -> HTTPError -> Exception. It is NOT an
    # OSError and TimeoutException is NOT a TimeoutError, so the stdlib tuple
    # alone matches none of them — every connect timeout and connection reset
    # would be classified permanent and stop failover dead.
    return isinstance(error, (
        httpx.TransportError,
        asyncio.TimeoutError,
        ConnectionError,
        ConnectionResetError,
        TimeoutError,
        OSError,
    ))


def compute_delay(attempt: int, config: RetryConfig, *, retry_after: float | None = None) -> float:
    """Seconds to wait before attempt number ``attempt`` (1-based).

    ``retry_after`` is honoured verbatim when the config allows it, clamped to
    ``max_delay_sec`` so a provider advertising a 3600s window cannot stall the
    request past its own budget — the router moves to another provider instead.
    """
    if retry_after is not None and config.respect_retry_after and retry_after > 0:
        return min(float(retry_after), config.max_delay_sec)

    raw = config.base_delay_sec * (config.multiplier ** max(0, attempt - 1))
    capped = min(raw, config.max_delay_sec)
    if config.jitter <= 0:
        return capped
    spread = capped * config.jitter
    # nosec B311 — retry jitter desynchronises callers; it is not a security
    # decision and nothing derives a secret from it. A CSPRNG here would cost
    # entropy on every retry to no benefit.
    return max(0.0, capped + random.uniform(-spread, spread))  # nosec B311


@dataclass
class RetryBudget:
    """Wall-clock and attempt ceiling shared by every attempt in one request.

    Without a shared budget, a request that fails over across six providers
    with six retries each could block for twenty minutes. The budget makes the
    worst case bounded and predictable.
    """

    max_attempts: int
    deadline_sec: float
    _used: int = 0
    _started: float = 0.0

    def __post_init__(self) -> None:
        self._started = time.monotonic()

    def charge(self) -> None:
        self._used += 1

    @property
    def used(self) -> int:
        return self._used

    @property
    def elapsed_sec(self) -> float:
        return time.monotonic() - self._started

    @property
    def remaining_sec(self) -> float:
        return max(0.0, self.deadline_sec - self.elapsed_sec)

    def exhausted(self) -> bool:
        return self._used >= self.max_attempts or self.remaining_sec <= 0

    def can_wait(self, delay: float) -> bool:
        """Whether sleeping ``delay`` still leaves time for the attempt after it."""
        return delay < self.remaining_sec

    def reason(self) -> str:
        if self._used >= self.max_attempts:
            return f"attempt budget exhausted after {self._used} attempt(s)"
        return f"time budget exhausted after {self.elapsed_sec:.1f}s"


async def sleep_before_retry(
    attempt: int, config: RetryConfig, budget: RetryBudget, *, retry_after: float | None = None
) -> bool:
    """Wait the backoff interval. Returns False when the budget can't afford it."""
    delay = compute_delay(attempt, config, retry_after=retry_after)
    if not budget.can_wait(delay):
        return False
    if delay > 0:
        await asyncio.sleep(delay)
    return True
