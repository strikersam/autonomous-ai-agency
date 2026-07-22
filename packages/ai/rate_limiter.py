"""
Proactive rate-limit throttling from x-ratelimit-* response headers.

Providers such as Anthropic, Groq, and OpenAI return standard headers on
every response:

    x-ratelimit-limit-requests
    x-ratelimit-remaining-requests
    x-ratelimit-reset-requests    (delta like "1s" / "500ms", or ISO-8601)
    x-ratelimit-limit-tokens
    x-ratelimit-remaining-tokens
    x-ratelimit-reset-tokens

After each successful call ``update_from_response()`` captures these.
Before the next call ``pre_flight_check()`` checks whether remaining quota
has dropped below the configured threshold and, if so, sleeps until the
reset window.  This complements the existing reactive ``_parse_retry_after``
(which handles post-429 cooldown) with a proactive guard that avoids
hitting rate limits in the first place.

The singleton ``_TRACKER`` is the shared state; access it via ``get_tracker()``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

log = logging.getLogger("llm-rate-limiter")

# Fraction of limit at which we start holding: 5 % remaining → wait for reset.
_PREFLIGHT_THRESHOLD: float = 0.05
# Never block longer than this even if the reset time is far in the future.
_MAX_PREFLIGHT_WAIT_SECONDS: float = 60.0


@dataclass
class _ProviderQuota:
    remaining_requests: Optional[int] = None
    remaining_tokens: Optional[int] = None
    limit_requests: Optional[int] = None
    limit_tokens: Optional[int] = None
    # Monotonic deadlines for when each counter resets.
    reset_requests_at: float = 0.0
    reset_tokens_at: float = 0.0
    updated_at: float = field(default_factory=time.monotonic)


def _parse_reset_epoch(value: Optional[str]) -> float:
    """Convert a provider reset-time header value to a monotonic deadline.

    Supported formats:
    - "1s" / "1.5s"     — delta seconds
    - "500ms"           — delta milliseconds
    - ISO-8601 datetime — wall-clock absolute time
    Returns 0.0 on parse failure (treated as "no info available").
    """
    if not value:
        return 0.0
    try:
        if value.endswith("ms"):
            return time.monotonic() + float(value[:-2]) / 1000.0
        if value.endswith("s"):
            return time.monotonic() + float(value[:-1])
        # Attempt ISO-8601 wall-clock absolute.
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        now_wall = datetime.now(timezone.utc)
        delta = (dt - now_wall).total_seconds()
        return time.monotonic() + max(0.0, delta)
    except Exception:
        return 0.0


class RateLimitTracker:
    """In-memory tracker for per-provider rate-limit state."""

    def __init__(self) -> None:
        self._state: dict[str, _ProviderQuota] = {}

    def update_from_response(
        self, provider_id: str, response: httpx.Response
    ) -> None:
        """Parse x-ratelimit-* headers and update per-provider quota state.

        Safe to call on every response, including error responses — the headers
        are present on 200 and 429 alike, and we want to update state after a
        429 so ``pre_flight_check`` can calculate the correct wait time.
        """
        h = response.headers

        def _int(key: str) -> Optional[int]:
            v = h.get(key)
            return int(v) if v is not None else None

        q = self._state.setdefault(provider_id, _ProviderQuota())

        rem_req = _int("x-ratelimit-remaining-requests")
        lim_req = _int("x-ratelimit-limit-requests")
        if rem_req is not None:
            q.remaining_requests = rem_req
        if lim_req is not None:
            q.limit_requests = lim_req
        reset_req = _parse_reset_epoch(h.get("x-ratelimit-reset-requests"))
        if reset_req:
            q.reset_requests_at = reset_req

        rem_tok = _int("x-ratelimit-remaining-tokens")
        lim_tok = _int("x-ratelimit-limit-tokens")
        if rem_tok is not None:
            q.remaining_tokens = rem_tok
        if lim_tok is not None:
            q.limit_tokens = lim_tok
        reset_tok = _parse_reset_epoch(h.get("x-ratelimit-reset-tokens"))
        if reset_tok:
            q.reset_tokens_at = reset_tok

        q.updated_at = time.monotonic()

    async def pre_flight_check(self, provider_id: str) -> float:
        """Sleep if remaining quota for *provider_id* is critically low.

        Returns the number of seconds actually waited (0.0 if no throttle was
        needed).  Never blocks longer than ``_MAX_PREFLIGHT_WAIT_SECONDS``.

        The check is a no-op when:
        - No data has been collected for this provider yet.
        - Remaining quota is above the ``_PREFLIGHT_THRESHOLD`` fraction.
        - The reset deadline is already in the past.
        """
        q = self._state.get(provider_id)
        if q is None:
            return 0.0

        now = time.monotonic()
        wait = 0.0

        if (
            q.remaining_requests is not None
            and q.limit_requests
            and q.remaining_requests <= max(1, int(q.limit_requests * _PREFLIGHT_THRESHOLD))
            and q.reset_requests_at > now
        ):
            wait = max(wait, q.reset_requests_at - now + 0.1)

        if (
            q.remaining_tokens is not None
            and q.limit_tokens
            and q.remaining_tokens <= max(100, int(q.limit_tokens * _PREFLIGHT_THRESHOLD))
            and q.reset_tokens_at > now
        ):
            wait = max(wait, q.reset_tokens_at - now + 0.1)

        wait = min(wait, _MAX_PREFLIGHT_WAIT_SECONDS)
        if wait > 0:
            log.info(
                "rate_limiter: %s quota low (req=%s/%s tok=%s/%s) — "
                "waiting %.2fs for reset",
                provider_id,
                q.remaining_requests,
                q.limit_requests,
                q.remaining_tokens,
                q.limit_tokens,
                wait,
            )
            await asyncio.sleep(wait)

        return wait

    def get_stats(self) -> dict[str, object]:
        """Snapshot of all tracked provider quotas.  Safe to call from any context."""
        now = time.monotonic()
        out: dict[str, object] = {}
        for pid, q in self._state.items():
            out[pid] = {
                "remaining_requests": q.remaining_requests,
                "limit_requests": q.limit_requests,
                "reset_requests_in_s": (
                    max(0.0, round(q.reset_requests_at - now, 1))
                    if q.reset_requests_at
                    else None
                ),
                "remaining_tokens": q.remaining_tokens,
                "limit_tokens": q.limit_tokens,
                "reset_tokens_in_s": (
                    max(0.0, round(q.reset_tokens_at - now, 1))
                    if q.reset_tokens_at
                    else None
                ),
                "updated_s_ago": round(now - q.updated_at, 1),
            }
        return out

    def clear(self) -> None:
        """Reset all state (primarily for tests)."""
        self._state.clear()


_TRACKER = RateLimitTracker()


def get_tracker() -> RateLimitTracker:
    """Return the process-singleton RateLimitTracker."""
    return _TRACKER
