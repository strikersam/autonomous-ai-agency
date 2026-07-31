"""packages/llm/metrics.py — Prometheus metrics without the client library.

The exposition format is a few lines of text, and this repo's constitution
asks for no unnecessary dependencies, so the collectors and the renderer live
here. Everything is a counter, a gauge, or a histogram with fixed buckets —
enough for the alerting rules a routing layer actually needs.

Exposed at ``GET /api/llm/metrics`` (see ``packages/llm/gateway.py``).
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Iterable

# Latency buckets in seconds. Tuned for LLM calls: sub-second is a cache hit or
# a tiny local model, and anything past a minute is a long generation.
LATENCY_BUCKETS: tuple[float, ...] = (
    0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0, 60.0, 120.0,
)

Labels = tuple[tuple[str, str], ...]

# Ceiling on distinct label combinations per metric family. Some label values
# are caller-controlled — the gateway accepts an `x-agent` header, and error
# text feeds `reason` — so an unbounded dict here is a memory leak that grows
# for as long as the process lives. Past the cap, series fold into
# {overflow="true"} rather than being dropped, so totals stay correct.
MAX_SERIES_PER_METRIC = 2000
_OVERFLOW: Labels = (("overflow", "true"),)


def sanitize_label(value: str, *, limit: int = 64) -> str:
    """Clamp a caller-supplied label value to something bounded and printable."""
    cleaned = "".join(c for c in str(value)[:limit] if c.isprintable())
    return cleaned.strip()


def _labels(**kwargs: str) -> Labels:
    """Build a label tuple, keeping empty values.

    Dropping an empty label would give one metric family two different label
    sets — `llm_requests_total` with and without `agent` — and Prometheus
    silently splits `sum by (agent)` across them.
    """
    return tuple(sorted((k, str(v)) for k, v in kwargs.items()))


def _render_labels(labels: Labels) -> str:
    if not labels:
        return ""
    inner = ",".join(f'{key}="{_escape(value)}"' for key, value in labels)
    return "{" + inner + "}"


def _escape(value: str) -> str:
    """Escape a label value per the exposition format.

    Newlines matter: `status` and `reason` carry provider error text, and an
    unescaped line feed produces an unparseable exposition line.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _render_value(value: float) -> str:
    """Render a sample without the six-significant-digit loss of ``:g``.

    `llm_tokens_total` passes counts that cross a million quickly; `:g` turns
    1234567 into 1.23457e+06, so the counter Prometheus records is wrong and
    every rate() over it is wrong too.
    """
    if value == int(value) and abs(value) < 2 ** 53:
        return str(int(value))
    return repr(value)


@dataclass
class _Counter:
    help_text: str
    values: dict[Labels, float] = field(default_factory=dict)

    def inc(self, labels: Labels, amount: float = 1.0) -> None:
        if labels not in self.values and len(self.values) >= MAX_SERIES_PER_METRIC:
            labels = _OVERFLOW
        self.values[labels] = self.values.get(labels, 0.0) + amount


@dataclass
class _Gauge:
    help_text: str
    values: dict[Labels, float] = field(default_factory=dict)

    def set(self, labels: Labels, value: float) -> None:
        if labels not in self.values and len(self.values) >= MAX_SERIES_PER_METRIC:
            return
        self.values[labels] = value


@dataclass
class _Histogram:
    help_text: str
    buckets: tuple[float, ...] = LATENCY_BUCKETS
    counts: dict[Labels, list[int]] = field(default_factory=dict)
    sums: dict[Labels, float] = field(default_factory=dict)
    totals: dict[Labels, int] = field(default_factory=dict)

    def observe(self, labels: Labels, value: float) -> None:
        if labels not in self.counts and len(self.counts) >= MAX_SERIES_PER_METRIC:
            labels = _OVERFLOW
        counts = self.counts.setdefault(labels, [0] * len(self.buckets))
        for index, upper in enumerate(self.buckets):
            if value <= upper:
                counts[index] += 1
        self.sums[labels] = self.sums.get(labels, 0.0) + value
        self.totals[labels] = self.totals.get(labels, 0) + 1


class MetricsRegistry:
    """All router metrics, renderable as Prometheus text."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started = time.time()

        self.requests = _Counter("Total LLM requests routed, by outcome.")
        self.retries = _Counter("Retry attempts, by provider and reason.")
        self.rate_limits = _Counter("HTTP 429 responses, by provider.")
        self.failures = _Counter("Failed attempts, by provider and status class.")
        self.fallbacks = _Counter("Requests that fell back to another provider.")
        self.tokens = _Counter("Tokens consumed, by provider, model, and direction.")
        self.cost = _Counter("Cost in USD, by provider and model.")
        self.cache_events = _Counter("Cache lookups, by layer and result.")
        self.prompt_cache_tokens = _Counter(
            "Prompt-cache token events, by provider, model, and direction "
            "(write=cache_creation_input_tokens, read=cache_read_input_tokens)."
        )
        self.breaker_trips = _Counter("Circuit breaker trips, by provider.")
        self.key_rotations = _Counter("API key rotations, by provider and reason.")

        self.queue_depth = _Gauge("Current LLM request queue depth.")
        self.in_flight = _Gauge("In-flight requests, by provider.")
        self.breaker_state = _Gauge("Circuit breaker state (0 closed, 1 half-open, 2 open).")
        self.provider_success_rate = _Gauge("Rolling provider success rate.")
        self.cache_hit_rate = _Gauge("Cache hit rate, by layer.")
        self.budget_ratio = _Gauge("Spend as a fraction of budget, by period.")

        self.latency = _Histogram("LLM request latency in seconds, by provider.")

    # ── Recording helpers ───────────────────────────────────────────────────

    def record_request(
        self,
        *,
        provider: str,
        model: str,
        outcome: str,
        latency_sec: float,
        agent: str = "",
        fallbacks: int = 0,
    ) -> None:
        with self._lock:
            self.requests.inc(_labels(provider=provider, model=model,
                                      outcome=outcome,
                                      agent=sanitize_label(agent)))
            self.latency.observe(_labels(provider=provider), latency_sec)
            if fallbacks:
                self.fallbacks.inc(_labels(provider=provider), fallbacks)

    def record_failure(self, *, provider: str, status: str, scope: str = "provider") -> None:
        with self._lock:
            self.failures.inc(_labels(provider=provider, status=status, scope=scope))
            if status == "429":
                self.rate_limits.inc(_labels(provider=provider))

    def record_retry(self, *, provider: str, reason: str) -> None:
        with self._lock:
            self.retries.inc(_labels(provider=provider, reason=reason))

    def record_tokens(
        self,
        *,
        provider: str,
        model: str,
        prompt: int,
        completion: int,
        cost_usd: float,
        cache_read: int = 0,
        cache_creation: int = 0,
    ) -> None:
        with self._lock:
            self.tokens.inc(_labels(provider=provider, model=model, direction="input"), prompt)
            self.tokens.inc(_labels(provider=provider, model=model, direction="output"), completion)
            if cost_usd:
                self.cost.inc(_labels(provider=provider, model=model), cost_usd)
            if cache_read:
                self.prompt_cache_tokens.inc(
                    _labels(provider=provider, model=model, direction="read"), cache_read
                )
            if cache_creation:
                self.prompt_cache_tokens.inc(
                    _labels(provider=provider, model=model, direction="write"), cache_creation
                )

    def record_cache(self, *, layer: str, hit: bool) -> None:
        with self._lock:
            self.cache_events.inc(_labels(layer=layer, result="hit" if hit else "miss"))

    def record_breaker_trip(self, *, provider: str) -> None:
        with self._lock:
            self.breaker_trips.inc(_labels(provider=provider))

    def record_key_rotation(self, *, provider: str, reason: str) -> None:
        with self._lock:
            self.key_rotations.inc(_labels(provider=provider, reason=reason))

    def set_queue_depth(self, depth: int) -> None:
        with self._lock:
            self.queue_depth.set((), float(depth))

    def set_in_flight(self, mapping: dict[str, int]) -> None:
        with self._lock:
            for provider, count in mapping.items():
                self.in_flight.set(_labels(provider=provider), float(count))

    def set_breaker_state(self, provider: str, state: str) -> None:
        value = {"closed": 0.0, "half_open": 1.0, "open": 2.0}.get(state, 0.0)
        with self._lock:
            self.breaker_state.set(_labels(provider=provider), value)

    def set_success_rate(self, provider: str, rate: float) -> None:
        with self._lock:
            self.provider_success_rate.set(_labels(provider=provider), rate)

    def set_cache_hit_rate(self, layer: str, rate: float) -> None:
        with self._lock:
            self.cache_hit_rate.set(_labels(layer=layer), rate)

    def set_budget_ratio(self, period: str, ratio: float) -> None:
        with self._lock:
            self.budget_ratio.set(_labels(period=period), ratio)

    # ── Rendering ───────────────────────────────────────────────────────────

    def render(self) -> str:
        """Prometheus text exposition (version 0.0.4)."""
        lines: list[str] = []
        with self._lock:
            for name, counter in self._counters():
                if not counter.values:
                    continue
                lines.append(f"# HELP {name} {counter.help_text}")
                lines.append(f"# TYPE {name} counter")
                for labels, value in sorted(counter.values.items()):
                    lines.append(f"{name}{_render_labels(labels)} {_render_value(value)}")
            for name, gauge in self._gauges():
                if not gauge.values:
                    continue
                lines.append(f"# HELP {name} {gauge.help_text}")
                lines.append(f"# TYPE {name} gauge")
                for labels, value in sorted(gauge.values.items()):
                    lines.append(f"{name}{_render_labels(labels)} {_render_value(value)}")
            lines.extend(self._render_histogram("llm_request_duration_seconds", self.latency))
            lines.append("# HELP llm_router_uptime_seconds Seconds since the router started.")
            lines.append("# TYPE llm_router_uptime_seconds gauge")
            lines.append(f"llm_router_uptime_seconds {_render_value(time.time() - self._started)}")
        return "\n".join(lines) + "\n"

    def _counters(self) -> Iterable[tuple[str, _Counter]]:
        return (
            ("llm_requests_total", self.requests),
            ("llm_retries_total", self.retries),
            ("llm_rate_limits_total", self.rate_limits),
            ("llm_failures_total", self.failures),
            ("llm_fallbacks_total", self.fallbacks),
            ("llm_tokens_total", self.tokens),
            ("llm_cost_usd_total", self.cost),
            ("llm_cache_events_total", self.cache_events),
            ("llm_prompt_cache_tokens_total", self.prompt_cache_tokens),
            ("llm_breaker_trips_total", self.breaker_trips),
            ("llm_key_rotations_total", self.key_rotations),
        )

    def _gauges(self) -> Iterable[tuple[str, _Gauge]]:
        return (
            ("llm_queue_depth", self.queue_depth),
            ("llm_in_flight_requests", self.in_flight),
            ("llm_circuit_breaker_state", self.breaker_state),
            ("llm_provider_success_rate", self.provider_success_rate),
            ("llm_cache_hit_rate", self.cache_hit_rate),
            ("llm_budget_ratio", self.budget_ratio),
        )

    @staticmethod
    def _render_histogram(name: str, histogram: _Histogram) -> list[str]:
        if not histogram.totals:
            return []
        lines = [
            f"# HELP {name} {histogram.help_text}",
            f"# TYPE {name} histogram",
        ]
        for labels, counts in sorted(histogram.counts.items()):
            for upper, count in zip(histogram.buckets, counts):
                bucket_labels = (*labels, ("le", str(upper)))
                lines.append(f"{name}_bucket{_render_labels(bucket_labels)} {count}")
            total = histogram.totals.get(labels, 0)
            lines.append(f"{name}_bucket{_render_labels((*labels, ('le', '+Inf')))} {total}")
            lines.append(f"{name}_sum{_render_labels(labels)} {_render_value(histogram.sums.get(labels, 0.0))}")
            lines.append(f"{name}_count{_render_labels(labels)} {total}")
        return lines

    def snapshot(self) -> dict[str, Any]:
        """JSON view for the dashboard, which shouldn't parse exposition text."""
        with self._lock:
            return {
                "counters": {
                    name: {
                        "|".join(f"{k}={v}" for k, v in labels) or "_": value
                        for labels, value in counter.values.items()
                    }
                    for name, counter in self._counters()
                    if counter.values
                },
                "gauges": {
                    name: {
                        "|".join(f"{k}={v}" for k, v in labels) or "_": value
                        for labels, value in gauge.values.items()
                    }
                    for name, gauge in self._gauges()
                    if gauge.values
                },
                "uptime_sec": round(time.time() - self._started, 1),
            }

    def reset(self) -> None:
        with self._lock:
            for _name, counter in self._counters():
                counter.values.clear()
            for _name, gauge in self._gauges():
                gauge.values.clear()
            self.latency.counts.clear()
            self.latency.sums.clear()
            self.latency.totals.clear()


_registry: MetricsRegistry | None = None
_lock = threading.Lock()


def get_metrics() -> MetricsRegistry:
    """The process-wide metrics registry."""
    global _registry
    if _registry is None:
        with _lock:
            if _registry is None:
                _registry = MetricsRegistry()
    return _registry


def reset() -> None:
    """Test hook — clear all metrics."""
    global _registry
    with _lock:
        _registry = None
