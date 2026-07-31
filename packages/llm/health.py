"""packages/llm/health.py — provider health tracking and circuit breaking.

Two collaborating pieces:

``HealthTracker`` keeps a rolling window of outcomes per provider — latency,
success rate, 429 frequency, timeout frequency — which the adaptive and
lowest-latency strategies score against.

``CircuitBreaker`` decides admission. It has the usual three states, with the
half-open state admitting a bounded number of probes so a recovering provider
is tested with one request rather than the full firehose:

    CLOSED    ──(failure threshold)──▶  OPEN
    OPEN      ──(open duration)─────▶  HALF_OPEN
    HALF_OPEN ──(probe succeeds)────▶  CLOSED
    HALF_OPEN ──(probe fails)───────▶  OPEN  (with a longer duration)

Repeated trips lengthen the open duration geometrically up to a ceiling, so a
provider that is genuinely down stops being probed every minute forever, while
one that blipped recovers quickly.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from packages.llm.config import HealthConfig, get_config

log = logging.getLogger("llm.health")


class BreakerState(str, Enum):
    CLOSED = "closed"        # normal operation
    OPEN = "open"            # refusing traffic
    HALF_OPEN = "half_open"  # admitting probes


@dataclass
class _Outcome:
    at: float
    ok: bool
    latency_ms: int
    status: int | None = None
    timeout: bool = False
    # False for key- and model-scoped failures. Those still count toward the
    # reported success rate an operator sees, but must be excluded from the
    # breaker's rate rule — otherwise a key exhausting its quota with 429s
    # raises the windowed failure rate until the next provider-scoped failure
    # trips the breaker for the whole provider, which is precisely the
    # escalation ADR-008 §4 exists to prevent.
    counts_against_breaker: bool = True


@dataclass
class ProviderHealth:
    """Rolling health for one provider."""

    provider_id: str
    state: BreakerState = BreakerState.CLOSED
    consecutive_failures: int = 0
    trips: int = 0
    opened_at: float = 0.0
    open_until: float = 0.0
    probes_in_flight: int = 0
    probes_allowed: int = 0
    # Set by force_open: an in-flight request completing after an admin
    # takes a provider out of rotation must not put it straight back.
    manual_hold: bool = False
    total_requests: int = 0
    total_failures: int = 0
    total_rate_limits: int = 0
    total_timeouts: int = 0
    last_error: str = ""
    last_success_at: float = 0.0
    outcomes: deque[_Outcome] = field(default_factory=lambda: deque(maxlen=256))

    # ── Derived metrics ─────────────────────────────────────────────────────

    def _window(self, window_sec: float) -> list[_Outcome]:
        cutoff = time.monotonic() - window_sec
        return [o for o in self.outcomes if o.at >= cutoff]

    def success_rate(self, window_sec: float = 300.0) -> float:
        recent = self._window(window_sec)
        if not recent:
            return 1.0
        return sum(1 for o in recent if o.ok) / len(recent)

    def failure_rate(self, window_sec: float = 300.0) -> float:
        return 1.0 - self.success_rate(window_sec)

    def avg_latency_ms(self, window_sec: float = 300.0) -> float:
        recent = [o for o in self._window(window_sec) if o.ok]
        if not recent:
            return 0.0
        return sum(o.latency_ms for o in recent) / len(recent)

    def p95_latency_ms(self, window_sec: float = 300.0) -> float:
        recent = sorted(o.latency_ms for o in self._window(window_sec) if o.ok)
        if not recent:
            return 0.0
        index = min(len(recent) - 1, int(len(recent) * 0.95))
        return float(recent[index])

    def rate_limit_frequency(self, window_sec: float = 300.0) -> float:
        recent = self._window(window_sec)
        if not recent:
            return 0.0
        return sum(1 for o in recent if o.status == 429) / len(recent)

    def timeout_frequency(self, window_sec: float = 300.0) -> float:
        recent = self._window(window_sec)
        if not recent:
            return 0.0
        return sum(1 for o in recent if o.timeout) / len(recent)

    def as_dict(self, window_sec: float = 300.0) -> dict[str, Any]:
        return {
            "provider": self.provider_id,
            "state": self.state.value,
            "available": self.state is not BreakerState.OPEN,
            "consecutive_failures": self.consecutive_failures,
            "trips": self.trips,
            "open_for_sec": round(max(0.0, self.open_until - time.monotonic()), 1),
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "total_rate_limits": self.total_rate_limits,
            "total_timeouts": self.total_timeouts,
            "success_rate": round(self.success_rate(window_sec), 4),
            "failure_rate": round(self.failure_rate(window_sec), 4),
            "avg_latency_ms": round(self.avg_latency_ms(window_sec), 1),
            "p95_latency_ms": round(self.p95_latency_ms(window_sec), 1),
            "rate_limit_frequency": round(self.rate_limit_frequency(window_sec), 4),
            "timeout_frequency": round(self.timeout_frequency(window_sec), 4),
            "last_error": self.last_error,
            "last_success_age_sec": (
                round(time.time() - self.last_success_at, 1) if self.last_success_at else None
            ),
        }


class HealthTracker:
    """Health and circuit-breaker state for every provider."""

    def __init__(self, config: HealthConfig | None = None) -> None:
        self._config = config or get_config().health
        self._health: dict[str, ProviderHealth] = {}
        self._lock = threading.Lock()

    @property
    def config(self) -> HealthConfig:
        return self._config

    def _get(self, provider_id: str) -> ProviderHealth:
        health = self._health.get(provider_id)
        if health is None:
            health = ProviderHealth(provider_id=provider_id)
            self._health[provider_id] = health
        return health

    def get(self, provider_id: str) -> ProviderHealth:
        with self._lock:
            return self._get(provider_id)

    # ── Admission ───────────────────────────────────────────────────────────

    def is_available(self, provider_id: str) -> bool:
        """Whether the breaker will admit a request right now.

        Transitions OPEN → HALF_OPEN when the open duration has elapsed, so
        recovery needs no background timer.
        """
        with self._lock:
            health = self._get(provider_id)
            if health.state is BreakerState.CLOSED:
                return True
            now = time.monotonic()
            if health.state is BreakerState.OPEN:
                if now < health.open_until:
                    return False
                health.state = BreakerState.HALF_OPEN
                health.probes_allowed = max(1, self._config.half_open_probes)
                health.probes_in_flight = 0
                log.info("llm.health: %s breaker half-open — probing", provider_id)
            return health.probes_in_flight < health.probes_allowed

    def acquire_probe(self, provider_id: str) -> bool:
        """Claim a half-open probe slot. Returns False when none are free."""
        with self._lock:
            health = self._get(provider_id)
            if health.state is not BreakerState.HALF_OPEN:
                return True
            if health.probes_in_flight >= health.probes_allowed:
                return False
            health.probes_in_flight += 1
            return True

    def release_probe(self, provider_id: str) -> None:
        """Hand a half-open probe permit back when nothing was actually tried.

        A candidate can be skipped after the permit is claimed — every key
        cooling, the bulkhead full, rate-limit pacing giving up. Without this
        the permit leaks and the provider can never be probed again, so it
        stays out of rotation until the process restarts.
        """
        with self._lock:
            health = self._get(provider_id)
            if health.state is BreakerState.HALF_OPEN:
                health.probes_in_flight = max(0, health.probes_in_flight - 1)

    # ── Recording outcomes ──────────────────────────────────────────────────

    def record_success(self, provider_id: str, *, latency_ms: int = 0) -> None:
        with self._lock:
            health = self._get(provider_id)
            health.total_requests += 1
            health.consecutive_failures = 0
            health.last_success_at = time.time()
            health.last_error = ""
            health.outcomes.append(_Outcome(time.monotonic(), True, latency_ms))
            if health.manual_hold and time.monotonic() < health.open_until:
                return
            health.manual_hold = False
            if health.state is not BreakerState.CLOSED:
                log.info("llm.health: %s breaker closed after successful probe", provider_id)
                health.state = BreakerState.CLOSED
                health.trips = 0
                health.probes_in_flight = 0
                health.open_until = 0.0

    def record_failure(
        self,
        provider_id: str,
        *,
        status: int | None = None,
        latency_ms: int = 0,
        error: str = "",
        timeout: bool = False,
        counts_against_breaker: bool = True,
    ) -> None:
        """Record a failed attempt and trip the breaker if thresholds are crossed.

        ``counts_against_breaker=False`` is used for key- and model-scoped
        failures: a 429 on one key or a decommissioned model says nothing about
        whether the provider itself is up, so it must not open the breaker
        (ADR-008 §4).
        """
        with self._lock:
            health = self._get(provider_id)
            health.total_requests += 1
            health.total_failures += 1
            if status == 429:
                health.total_rate_limits += 1
            if timeout:
                health.total_timeouts += 1
            health.last_error = (error or f"HTTP {status}")[:200]
            health.outcomes.append(
                _Outcome(
                    time.monotonic(), False, latency_ms, status=status, timeout=timeout,
                    counts_against_breaker=counts_against_breaker,
                )
            )

            if not counts_against_breaker:
                return

            health.consecutive_failures += 1
            if health.state is BreakerState.HALF_OPEN:
                self._trip(health, "probe failed")
                return
            if self._should_trip(health):
                self._trip(health, f"{health.consecutive_failures} consecutive failures")

    def _should_trip(self, health: ProviderHealth) -> bool:
        if health.consecutive_failures >= self._config.failure_threshold:
            return True
        # Successes count, but only breaker-eligible failures do. A provider
        # whose keys are rate-limited is not itself unwell.
        window = [
            o for o in health._window(self._config.window_sec)
            if o.ok or o.counts_against_breaker
        ]
        if len(window) >= self._config.min_samples:
            failures = sum(1 for o in window if not o.ok)
            if failures / len(window) >= self._config.failure_rate_threshold:
                return True
        return False

    def _trip(self, health: ProviderHealth, reason: str) -> None:
        health.trips += 1
        health.state = BreakerState.OPEN
        health.opened_at = time.monotonic()
        duration = min(
            self._config.open_duration_sec
            * (self._config.backoff_multiplier ** (health.trips - 1)),
            self._config.max_open_duration_sec,
        )
        health.open_until = health.opened_at + duration
        health.probes_in_flight = 0
        log.warning(
            "llm.health: %s breaker OPEN for %.0fs (trip #%d — %s)",
            health.provider_id, duration, health.trips, reason,
        )

    # ── Manual control ──────────────────────────────────────────────────────

    def force_open(self, provider_id: str, duration_sec: float = 300.0) -> None:
        """Take a provider out of rotation by hand (admin action)."""
        with self._lock:
            health = self._get(provider_id)
            health.state = BreakerState.OPEN
            health.opened_at = time.monotonic()
            health.open_until = health.opened_at + duration_sec
            health.manual_hold = True
            health.last_error = "manually disabled"

    def force_close(self, provider_id: str) -> None:
        """Restore a provider immediately (admin action)."""
        with self._lock:
            health = self._get(provider_id)
            health.state = BreakerState.CLOSED
            health.consecutive_failures = 0
            health.trips = 0
            health.open_until = 0.0
            health.manual_hold = False
            health.last_error = ""

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [h.as_dict(self._config.window_sec) for h in self._health.values()]

    def available_providers(self, provider_ids: list[str]) -> list[str]:
        return [pid for pid in provider_ids if self.is_available(pid)]

    def reset(self) -> None:
        with self._lock:
            self._health.clear()


_tracker: HealthTracker | None = None
_lock = threading.Lock()


def get_tracker() -> HealthTracker:
    """The process-wide health tracker."""
    global _tracker
    if _tracker is None:
        with _lock:
            if _tracker is None:
                _tracker = HealthTracker()
    return _tracker


def reset() -> None:
    """Test hook — clear all health state."""
    global _tracker
    with _lock:
        _tracker = None
