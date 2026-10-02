"""packages/gateway/token_quota.py — per-consumer tokens-per-minute / tokens-per-day quota.

Request-count limits (``RATE_LIMIT_RPM``) say nothing about cost: one request
can carry 200 tokens or 200 000. This quota counts the tokens the upstream
reports and refuses further requests from a consumer once a window is spent.

Semantics worth knowing:

* Fixed windows (UTC minute, UTC day). Tokens are only known after the
  response, so the check is "already at or over the limit" — one request can
  overshoot the window it started in; the next one is refused.
* A consumer is a key id, or a sha256 digest of the key for legacy keys. The
  raw key is never stored (see :func:`packages.gateway.context.consumer_id`).
* Memory is bounded: least-recently-seen consumers are evicted past
  ``MAX_CONSUMERS``, which resets their counters rather than growing forever.
* Both limits at 0 (the default) makes every function here a no-op.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass

from packages.gateway import config

MAX_CONSUMERS = 10_000
_MINUTE = 60
_DAY = 86_400


@dataclass
class _Usage:
    minute_window: int = 0
    minute_used: int = 0
    day_window: int = 0
    day_used: int = 0


@dataclass(frozen=True)
class QuotaDecision:
    """Outcome of :func:`check`; ``retry_after`` is whole seconds when refused."""

    allowed: bool
    retry_after: int = 0


_lock = threading.Lock()
_usage: OrderedDict[str, _Usage] = OrderedDict()


def _now() -> float:
    return time.time()


def reset() -> None:
    """Forget every consumer (test hook)."""
    with _lock:
        _usage.clear()


def _rolled(consumer: str, now: float) -> _Usage:
    """The consumer's counters with expired windows zeroed. Caller holds the lock."""
    entry = _usage.get(consumer)
    if entry is None:
        entry = _usage[consumer] = _Usage()
        while len(_usage) > MAX_CONSUMERS:
            _usage.popitem(last=False)
    else:
        _usage.move_to_end(consumer)
    minute, day = int(now // _MINUTE), int(now // _DAY)
    if entry.minute_window != minute:
        entry.minute_window, entry.minute_used = minute, 0
    if entry.day_window != day:
        entry.day_window, entry.day_used = day, 0
    return entry


def check(consumer: str) -> QuotaDecision:
    """Whether *consumer* may start another request right now."""
    per_minute, per_day = config.tokens_per_minute(), config.tokens_per_day()
    if not per_minute and not per_day:
        return QuotaDecision(True)
    now = _now()
    with _lock:
        entry = _rolled(consumer, now)
        waits: list[int] = []
        if per_minute and entry.minute_used >= per_minute:
            waits.append(int((entry.minute_window + 1) * _MINUTE - now) + 1)
        if per_day and entry.day_used >= per_day:
            waits.append(int((entry.day_window + 1) * _DAY - now) + 1)
    return QuotaDecision(False, max(waits)) if waits else QuotaDecision(True)


def record(consumer: str, tokens: int) -> None:
    """Add *tokens* actually consumed to both windows."""
    if tokens <= 0 or not (config.tokens_per_minute() or config.tokens_per_day()):
        return
    with _lock:
        entry = _rolled(consumer, _now())
        entry.minute_used += tokens
        entry.day_used += tokens


def rate_limit_headers(consumer: str) -> dict[str, str]:
    """``X-RateLimit-*-Tokens`` for the window with the least headroom, or ``{}``."""
    per_minute, per_day = config.tokens_per_minute(), config.tokens_per_day()
    if not per_minute and not per_day:
        return {}
    with _lock:
        entry = _rolled(consumer, _now())
        candidates = []
        if per_minute:
            candidates.append((max(0, per_minute - entry.minute_used), per_minute))
        if per_day:
            candidates.append((max(0, per_day - entry.day_used), per_day))
    remaining, limit = min(candidates)
    return {
        "X-RateLimit-Limit-Tokens": str(limit),
        "X-RateLimit-Remaining-Tokens": str(remaining),
    }
