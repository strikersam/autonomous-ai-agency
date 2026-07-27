"""Adaptive traffic distribution across LLM providers.

The router (``packages/ai/router.py``) has always walked its provider list in
strict priority order: provider #1 absorbs *every* request until it fails, and
only then does traffic move to #2. On paid tiers that is exactly right. On the
free tiers this agency runs on (NVIDIA NIM, Cerebras, Groq) it is the single
biggest cause of 429 cascades — the second and third free keys sit idle while
the first one burns through its per-minute allowance.

This module adds the missing half: *spread* traffic across the providers that
are already healthy, instead of only *recovering* after one of them refuses.
The strategies are ports of the ones LiteLLM's ``Router`` exposes
(``litellm/router_strategy/``), adapted to this codebase's provider model:

``priority``          strict priority order — the historical behaviour, and
                      still the default, so nothing changes until an operator
                      opts in with ``LLM_ROUTING_STRATEGY``.
``weighted-shuffle``  weighted random pick by ``<PROVIDER>_WEIGHT``, falling
                      back to remaining RPM headroom, then to an equal share
                      (LiteLLM ``simple_shuffle``).
``least-busy``        fewest in-flight requests first (LiteLLM ``least_busy``).
``usage-based``       lowest fraction of its configured RPM/TPM budget spent
                      in the current window (LiteLLM ``lowest_tpm_rpm_v2``).
``latency-based``     lowest EWMA response latency, unsampled providers first
                      (LiteLLM ``lowest_latency``).

Two invariants keep this safe to switch on in production:

1. **Reordering never crosses an access tier.** The caller passes a
   ``group_key`` (the router passes the tier rank from ``provider_sort_key``)
   and distribution happens *within* each tier only. A shuffle can therefore
   never promote a paid commercial provider above a free one and start
   spending money.
2. **Nothing here can fail a request.** Every public entry point is
   exception-safe at the call site in the router; the worst case is that the
   list comes back in its original order.

The second contribution is the *pre-call budget check* (``over_budget``).
``packages/ai/rate_limiter.pace()`` already exists and *sleeps* when a
provider is at its configured RPM. Sleeping is the correct move when that
provider is the only one available; when a sibling is idle, skipping to the
sibling is strictly better. ``over_budget`` is what lets the router make that
choice — the same trick as LiteLLM's ``async_pre_call_check``, which raises
a synthetic rate-limit error so the caller falls through to another
deployment rather than spending a real request on a 429.

All state is in-process and best-effort: a sliding 60-second window of request
timestamps and token counts per provider, plus in-flight counts and an EWMA of
latency. Restarting the process resets it, which is fine — the window is a
minute long.
"""

from __future__ import annotations

import logging
import random
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

log = logging.getLogger("llm-traffic-director")

# Sliding window all usage accounting is done over. One minute, because every
# provider limit we care about (RPM/TPM) is quoted per minute.
_WINDOW_SECONDS: float = 60.0

# When a provider has no configured RPM cap we still want `usage-based` to
# rank it against its peers. Treating "unknown" as this many requests/min
# turns a raw count into a comparable 0..1 pressure score. It is a ranking
# aid only — never a limit, and never a reason to skip a provider.
_ASSUMED_RPM_WHEN_UNSET: float = 60.0

# Smoothing factor for the latency EWMA. 0.3 keeps roughly the last handful of
# calls dominant so a provider that just got slow is demoted quickly.
_EWMA_ALPHA: float = 0.3

# Scores are rounded to this many decimals before sorting so that
# near-identical providers count as tied and get the random tie-break rather
# than a stable sort that would send all of them back to the same provider.
_SCORE_PRECISION: int = 4

# Extra pressure added to a provider's usage score if it returned a 429 within
# the current window. Bigger than any real utilisation fraction, so a
# recently-rate-limited provider sorts behind every provider that isn't —
# without being excluded outright.
_RECENT_429_PENALTY: float = 1.0

STRATEGY_PRIORITY = "priority"
STRATEGY_WEIGHTED_SHUFFLE = "weighted-shuffle"
STRATEGY_LEAST_BUSY = "least-busy"
STRATEGY_USAGE_BASED = "usage-based"
STRATEGY_LATENCY_BASED = "latency-based"

KNOWN_STRATEGIES: frozenset[str] = frozenset(
    {
        STRATEGY_PRIORITY,
        STRATEGY_WEIGHTED_SHUFFLE,
        STRATEGY_LEAST_BUSY,
        STRATEGY_USAGE_BASED,
        STRATEGY_LATENCY_BASED,
    }
)

# Remember which unknown strategy names we already complained about, so a
# typo in the env var logs once per process instead of once per request.
_warned_strategies: set[str] = set()


def active_strategy() -> str:
    """Return the configured strategy name, falling back to ``priority``.

    An unrecognised ``LLM_ROUTING_STRATEGY`` must not silently become some
    other distribution — a typo would then change routing in a way the
    operator never asked for. Unknown names warn once and behave exactly like
    the historical strict-priority router.
    """
    from packages.ai.brain_config import routing_strategy

    name = routing_strategy()
    if name in KNOWN_STRATEGIES:
        return name
    if name not in _warned_strategies:
        _warned_strategies.add(name)
        log.warning(
            "traffic_director: unknown LLM_ROUTING_STRATEGY=%r — falling back to "
            "%r. Supported: %s",
            name,
            STRATEGY_PRIORITY,
            ", ".join(sorted(KNOWN_STRATEGIES)),
        )
    return STRATEGY_PRIORITY


def provider_id_of(provider: Any) -> str:
    """Extract a provider id from a ProviderConfig dataclass or a plain dict."""
    if isinstance(provider, dict):
        return str(provider.get("provider_id") or "")
    return str(getattr(provider, "provider_id", "") or "")


@dataclass
class _ProviderUsage:
    """Sliding-window usage counters for one provider."""

    # Monotonic timestamps of request starts inside the current window.
    request_times: deque[float] = field(default_factory=deque)
    # (timestamp, token_count) pairs inside the current window.
    token_events: deque[tuple[float, int]] = field(default_factory=deque)
    in_flight: int = 0
    ewma_latency_ms: float | None = None
    # Monotonic time of the most recent 429 from this provider (0.0 = never).
    rate_limited_at: float = 0.0
    # Lifetime counters — diagnostics only, never used for routing.
    total_requests: int = 0
    total_rate_limited: int = 0
    total_skipped: int = 0


class TrafficDirector:
    """In-process traffic distribution and budget accounting for providers."""

    def __init__(self) -> None:
        self._usage: dict[str, _ProviderUsage] = {}

    # ── state ──────────────────────────────────────────────────────────────

    def _get(self, provider_id: str) -> _ProviderUsage:
        usage = self._usage.get(provider_id)
        if usage is None:
            usage = _ProviderUsage()
            self._usage[provider_id] = usage
        return usage

    @staticmethod
    def _prune(usage: _ProviderUsage, now: float) -> None:
        """Drop request/token events that have fallen out of the window."""
        cutoff = now - _WINDOW_SECONDS
        while usage.request_times and usage.request_times[0] < cutoff:
            usage.request_times.popleft()
        while usage.token_events and usage.token_events[0][0] < cutoff:
            usage.token_events.popleft()

    def record_start(self, provider_id: str) -> None:
        """Count a request that is about to be sent to *provider_id*.

        Called immediately before the HTTP call so that concurrent callers see
        each other's requests: an in-flight request is already inside
        ``request_times``, which is what makes the RPM budget check correct
        under concurrency rather than only after responses come back.
        """
        now = time.monotonic()
        usage = self._get(provider_id)
        self._prune(usage, now)
        usage.request_times.append(now)
        usage.in_flight += 1
        usage.total_requests += 1

    def record_end(
        self,
        provider_id: str,
        *,
        latency_ms: int | None = None,
        tokens: int = 0,
        status_code: int | None = None,
    ) -> None:
        """Record the outcome of a request started with ``record_start``.

        Must be called exactly once per ``record_start`` (the router does this
        in a ``finally``), otherwise ``in_flight`` leaks upward and eventually
        pins the provider at its concurrency ceiling forever.
        """
        now = time.monotonic()
        usage = self._get(provider_id)
        self._prune(usage, now)
        usage.in_flight = max(0, usage.in_flight - 1)
        if tokens > 0:
            usage.token_events.append((now, tokens))
        if latency_ms is not None and latency_ms >= 0:
            if usage.ewma_latency_ms is None:
                usage.ewma_latency_ms = float(latency_ms)
            else:
                usage.ewma_latency_ms = (
                    _EWMA_ALPHA * latency_ms
                    + (1.0 - _EWMA_ALPHA) * usage.ewma_latency_ms
                )
        if status_code == 429:
            usage.rate_limited_at = now
            usage.total_rate_limited += 1

    # ── pre-call budget check ──────────────────────────────────────────────

    def over_budget(
        self, provider_id: str, *, estimated_tokens: int = 0
    ) -> str | None:
        """Return a reason string when *provider_id* has no budget left.

        Returns ``None`` when the provider is safe to call. The check is
        entirely driven by operator-configured ceilings — with none of
        ``<PROVIDER>_MAX_PARALLEL`` / ``_MAX_RPM`` / ``_MAX_TPM`` set this
        always returns ``None``, so an unconfigured deployment behaves exactly
        as it did before.

        The caller is expected to route to another provider on a non-None
        result, not to sleep; sleeping is what ``rate_limiter.pace()`` is for
        when there is nowhere else to go.
        """
        from packages.ai.brain_config import (
            provider_max_parallel,
            provider_max_rpm,
            provider_max_tpm,
        )

        usage = self._usage.get(provider_id)
        if usage is None:
            return None
        self._prune(usage, time.monotonic())

        max_parallel = provider_max_parallel(provider_id)
        if max_parallel is not None and usage.in_flight >= max_parallel:
            return f"max-parallel ({usage.in_flight}/{max_parallel})"

        max_rpm = provider_max_rpm(provider_id)
        used_rpm = len(usage.request_times)
        if max_rpm is not None and used_rpm >= max_rpm:
            return f"rpm ({used_rpm}/{max_rpm:g})"

        max_tpm = provider_max_tpm(provider_id)
        if max_tpm is not None:
            used_tpm = sum(count for _ts, count in usage.token_events)
            if used_tpm + max(0, estimated_tokens) >= max_tpm:
                return f"tpm ({used_tpm}/{max_tpm:g})"
        return None

    def record_skip(self, provider_id: str) -> None:
        """Count a request that was routed away from *provider_id* (diagnostics)."""
        self._get(provider_id).total_skipped += 1

    # ── ordering ───────────────────────────────────────────────────────────

    def order(
        self,
        providers: Sequence[Any],
        *,
        group_key: Callable[[Any], Any] | None = None,
    ) -> list[Any]:
        """Return *providers* reordered according to the active strategy.

        ``group_key`` partitions the list into runs that may be reordered
        internally but never against each other — the router passes the access
        tier so free providers keep sorting ahead of commercial ones no matter
        which strategy is active. Passing ``None`` allows reordering across the
        whole list, which is only appropriate when the caller has already
        established that every candidate is interchangeable.
        """
        strategy = active_strategy()
        if strategy == STRATEGY_PRIORITY or len(providers) < 2:
            return list(providers)

        groups: list[list[Any]] = []
        last_key: Any = object()  # sentinel that equals nothing
        for provider in providers:
            key = group_key(provider) if group_key is not None else None
            if groups and key == last_key:
                groups[-1].append(provider)
            else:
                groups.append([provider])
                last_key = key

        ordered: list[Any] = []
        for members in groups:
            ordered.extend(self._order_group(members, strategy))
        return ordered

    def _order_group(self, members: list[Any], strategy: str) -> list[Any]:
        """Reorder one interchangeable group of providers."""
        if len(members) < 2:
            return list(members)
        if strategy == STRATEGY_WEIGHTED_SHUFFLE:
            return self._weighted_shuffle(members)
        if strategy == STRATEGY_LEAST_BUSY:
            return self._sorted_by(
                members, lambda pid: float(self._get(pid).in_flight)
            )
        if strategy == STRATEGY_USAGE_BASED:
            return self._sorted_by(members, self._utilisation)
        if strategy == STRATEGY_LATENCY_BASED:
            return self._sorted_by(members, self._latency_score)
        return list(members)

    def _sorted_by(
        self, members: list[Any], score: Callable[[str], float]
    ) -> list[Any]:
        """Ascending sort by *score* with a random tie-break.

        The tie-break is the point: at cold start every provider scores 0, and
        a stable sort would hand the whole burst to the first one — precisely
        the pile-up this module exists to prevent.
        """
        return sorted(
            members,
            key=lambda p: (
                round(score(provider_id_of(p)), _SCORE_PRECISION),
                random.random(),  # nosec B311 - load spreading, not crypto
            ),
        )

    def _utilisation(self, provider_id: str) -> float:
        """Fraction of this provider's per-minute budget already spent.

        Uses the larger of the request and token fractions, because either one
        hitting 1.0 is enough to start collecting 429s. Providers with no
        configured RPM are scored against ``_ASSUMED_RPM_WHEN_UNSET`` so they
        still rank sensibly against their peers.
        """
        from packages.ai.brain_config import provider_max_rpm, provider_max_tpm

        usage = self._usage.get(provider_id)
        if usage is None:
            return 0.0
        now = time.monotonic()
        self._prune(usage, now)

        max_rpm = provider_max_rpm(provider_id) or _ASSUMED_RPM_WHEN_UNSET
        score = len(usage.request_times) / max_rpm

        max_tpm = provider_max_tpm(provider_id)
        if max_tpm:
            used_tpm = sum(count for _ts, count in usage.token_events)
            score = max(score, used_tpm / max_tpm)

        if usage.rate_limited_at and (now - usage.rate_limited_at) < _WINDOW_SECONDS:
            score += _RECENT_429_PENALTY
        return score

    def _latency_score(self, provider_id: str) -> float:
        """EWMA latency in ms; never-sampled providers sort first.

        Returning -1.0 for an unsampled provider is deliberate: without it a
        provider that has never been called has no latency to compare, would
        sort last forever, and could never earn a sample.
        """
        usage = self._usage.get(provider_id)
        if usage is None or usage.ewma_latency_ms is None:
            return -1.0
        return usage.ewma_latency_ms

    def _weighted_shuffle(self, members: list[Any]) -> list[Any]:
        """Weighted random permutation — heavier providers tend to come first.

        Weight precedence per provider: explicit ``<PROVIDER>_WEIGHT``, else
        remaining RPM headroom (so a provider that has already spent most of
        its minute is picked less often), else an equal share. Mirrors
        LiteLLM's ``simple_shuffle``, extended from "pick one" to "produce a
        full ordering" because this router needs a fallback sequence, not a
        single deployment.
        """
        remaining = list(members)
        weights = [self._weight_for(provider_id_of(p)) for p in remaining]
        ordered: list[Any] = []
        while remaining:
            total = sum(weights)
            if total <= 0:
                # Every candidate left has zero weight: fall back to a uniform
                # shuffle rather than dropping them, so they are still tried.
                random.shuffle(remaining)  # nosec B311 - load spreading
                ordered.extend(remaining)
                break
            index = random.choices(  # nosec B311 - load spreading, not crypto
                range(len(remaining)), weights=weights, k=1
            )[0]
            ordered.append(remaining.pop(index))
            weights.pop(index)
        return ordered

    def _weight_for(self, provider_id: str) -> float:
        """Selection weight for *provider_id* (see ``_weighted_shuffle``)."""
        from packages.ai.brain_config import provider_max_rpm, provider_weight

        explicit = provider_weight(provider_id)
        if explicit is not None:
            return explicit
        max_rpm = provider_max_rpm(provider_id)
        if max_rpm is None:
            return 1.0
        usage = self._usage.get(provider_id)
        used = 0
        if usage is not None:
            self._prune(usage, time.monotonic())
            used = len(usage.request_times)
        # Headroom, floored just above zero: a fully-spent provider should be
        # rare in the ordering, not absent from it — the budget check decides
        # whether it is actually skipped.
        return max(max_rpm - used, 0.01)

    # ── diagnostics ────────────────────────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        """Serializable view of current distribution state (for /api/metrics)."""
        from packages.ai.brain_config import (
            provider_max_parallel,
            provider_max_rpm,
            provider_max_tpm,
        )

        now = time.monotonic()
        providers: dict[str, Any] = {}
        for provider_id, usage in self._usage.items():
            self._prune(usage, now)
            providers[provider_id] = {
                "in_flight": usage.in_flight,
                "requests_in_window": len(usage.request_times),
                "tokens_in_window": sum(c for _ts, c in usage.token_events),
                "max_rpm": provider_max_rpm(provider_id),
                "max_tpm": provider_max_tpm(provider_id),
                "max_parallel": provider_max_parallel(provider_id),
                "utilisation": round(self._utilisation(provider_id), 3),
                "ewma_latency_ms": (
                    round(usage.ewma_latency_ms, 1)
                    if usage.ewma_latency_ms is not None
                    else None
                ),
                "seconds_since_429": (
                    round(now - usage.rate_limited_at, 1)
                    if usage.rate_limited_at
                    else None
                ),
                "total_requests": usage.total_requests,
                "total_rate_limited": usage.total_rate_limited,
                "total_skipped_over_budget": usage.total_skipped,
            }
        return {
            "strategy": active_strategy(),
            "window_seconds": _WINDOW_SECONDS,
            "providers": providers,
        }

    def reset(self) -> None:
        """Clear all counters (tests only)."""
        self._usage.clear()


_DIRECTOR = TrafficDirector()


def get_director() -> TrafficDirector:
    """Return the process-singleton TrafficDirector."""
    return _DIRECTOR


def reset() -> None:
    """Clear director state and the cached strategy warnings (tests only)."""
    _DIRECTOR.reset()
    _warned_strategies.clear()
