"""packages/llm/budget.py — token and cost accounting with spend alerts.

Tracks input tokens, output tokens, and USD cost broken down by agent,
workflow, provider, and model, aggregated per day and per month.

Budgets are advisory by default: crossing a threshold logs and emits an alert
event, but the request still runs. Set ``budget.enforce: true`` in
``routing.yaml`` to make a breach raise ``BudgetExceeded`` instead. Advisory is
the default deliberately — an autonomous agency that silently stops working at
month-end because of a misconfigured ceiling is a worse failure than an
overspend the operator can see coming from the 50% alert onward.

Counters are in-memory and per-process. That is the right scope for alerting
and dashboards; durable cross-restart accounting stays with
``packages/ai/cost_tracker.py``, which this module feeds.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from packages.llm.config import BudgetConfig, get_config
from packages.llm.types import BudgetExceeded, Usage

log = logging.getLogger("llm.budget")

# The platform is meant to run for weeks, so every unbounded dict here is a
# slow leak. Daily buckets are pruned to a rolling window and the free-form
# dimensions are capped; anything past the cap folds into "other" so the
# totals stay correct.
MAX_DAILY_BUCKETS = 62
MAX_MONTHLY_BUCKETS = 24
MAX_DIMENSION_KEYS = 500
_OTHER = "other"

AlertHandler = Callable[[dict[str, Any]], None]


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


@dataclass
class Counter:
    """Token and cost totals for one dimension value."""

    requests: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: float = 0.0
    errors: int = 0

    def add(self, usage: Usage, cost: float) -> None:
        self.requests += 1
        self.prompt_tokens += usage.prompt_tokens
        self.completion_tokens += usage.completion_tokens
        self.cached_tokens += usage.cached_tokens
        self.cost_usd += cost

    def as_dict(self) -> dict[str, Any]:
        return {
            "requests": self.requests,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cached_tokens": self.cached_tokens,
            "total_tokens": self.prompt_tokens + self.completion_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "errors": self.errors,
        }


@dataclass
class _Dimensions:
    agent: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    workflow: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    provider: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    model: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    daily: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    monthly: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))


class BudgetTracker:
    """Usage accounting plus threshold alerting."""

    def __init__(self, config: BudgetConfig | None = None) -> None:
        self._config = config or get_config().budget
        self._dims = _Dimensions()
        self._total = Counter()
        self._alerted: set[str] = set()
        self._alerts: list[dict[str, Any]] = []
        self._handlers: list[AlertHandler] = []
        self._lock = threading.Lock()

    @property
    def config(self) -> BudgetConfig:
        return self._config

    def on_alert(self, handler: AlertHandler) -> None:
        """Register a callback fired when a spend threshold is crossed."""
        self._handlers.append(handler)

    # ── Recording ───────────────────────────────────────────────────────────

    @staticmethod
    def _bounded_key(bucket: dict[str, Counter], key: str) -> str:
        """Fold a new key into "other" once the dimension is at its cap."""
        if key in bucket or len(bucket) < MAX_DIMENSION_KEYS:
            return key
        return _OTHER

    def _prune(self) -> None:
        """Drop period buckets older than the retention window."""
        for bucket, limit in ((self._dims.daily, MAX_DAILY_BUCKETS),
                              (self._dims.monthly, MAX_MONTHLY_BUCKETS)):
            while len(bucket) > limit:
                del bucket[min(bucket)]

    def record(
        self,
        *,
        usage: Usage,
        cost_usd: float,
        provider: str = "",
        model: str = "",
        agent: str = "",
        workflow: str = "",
    ) -> None:
        """Record one completed call across every dimension."""
        with self._lock:
            self._total.add(usage, cost_usd)
            for bucket, key in (
                (self._dims.agent, agent or "unattributed"),
                (self._dims.workflow, workflow or "unattributed"),
                (self._dims.provider, provider or "unknown"),
                (self._dims.model, model or "unknown"),
                (self._dims.daily, _today()),
                (self._dims.monthly, _month()),
            ):
                bucket[self._bounded_key(bucket, key)].add(usage, cost_usd)
            self._prune()

        self._check_thresholds()
        self._mirror_to_cost_tracker(usage, provider, model)

    def record_error(self, *, provider: str = "", agent: str = "") -> None:
        with self._lock:
            self._total.errors += 1
            self._dims.provider[provider or "unknown"].errors += 1
            self._dims.agent[agent or "unattributed"].errors += 1

    def _mirror_to_cost_tracker(self, usage: Usage, provider: str, model: str) -> None:
        """Feed the durable tracker so historical reporting stays one source."""
        try:
            from packages.ai import cost_tracker
        except Exception:  # pragma: no cover - defensive
            return
        try:
            cost_tracker.record_usage(
                provider_id=provider,
                model=model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
            )
        except Exception as exc:  # pragma: no cover - signature drift
            log.debug("llm.budget: cost_tracker mirror skipped (%s)", exc)

    # ── Enforcement ─────────────────────────────────────────────────────────

    def spend_today(self) -> float:
        with self._lock:
            return self._dims.daily[_today()].cost_usd

    def spend_this_month(self) -> float:
        with self._lock:
            return self._dims.monthly[_month()].cost_usd

    def check_affordable(self, estimated_cost_usd: float = 0.0) -> None:
        """Raise ``BudgetExceeded`` when enforcement is on and the cap is hit."""
        if not self._config.enforce:
            return
        if self._config.daily_usd:
            projected = self.spend_today() + estimated_cost_usd
            if projected > self._config.daily_usd:
                raise BudgetExceeded(
                    f"daily budget exceeded: ${projected:.4f} > "
                    f"${self._config.daily_usd:.2f}"
                )
        if self._config.monthly_usd:
            projected = self.spend_this_month() + estimated_cost_usd
            if projected > self._config.monthly_usd:
                raise BudgetExceeded(
                    f"monthly budget exceeded: ${projected:.4f} > "
                    f"${self._config.monthly_usd:.2f}"
                )

    def _check_thresholds(self) -> None:
        """Emit one alert per (period, threshold) crossing, never repeatedly."""
        for period, spend, cap in (
            ("daily", self.spend_today(), self._config.daily_usd),
            ("monthly", self.spend_this_month(), self._config.monthly_usd),
        ):
            if not cap:
                continue
            ratio = spend / cap
            for threshold in sorted(self._config.alert_at):
                if ratio < threshold:
                    continue
                token = f"{period}:{_today() if period == 'daily' else _month()}:{threshold}"
                if token in self._alerted:
                    continue
                self._alerted.add(token)
                self._emit({
                    "period": period,
                    "threshold": threshold,
                    "spend_usd": round(spend, 4),
                    "budget_usd": cap,
                    "ratio": round(ratio, 4),
                    "enforced": self._config.enforce,
                    "at": time.time(),
                })

    def _emit(self, alert: dict[str, Any]) -> None:
        self._alerts.append(alert)
        log.warning(
            "llm.budget: %s spend at %.0f%% of $%.2f ($%.4f used)",
            alert["period"], alert["ratio"] * 100, alert["budget_usd"],
            alert["spend_usd"],
        )
        for handler in self._handlers:
            try:
                handler(alert)
            except Exception as exc:  # pragma: no cover - handler is user code
                log.warning("llm.budget: alert handler failed (%s)", exc)

    # ── Reporting ───────────────────────────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total": self._total.as_dict(),
                "by_agent": {k: v.as_dict() for k, v in self._dims.agent.items()},
                "by_workflow": {k: v.as_dict() for k, v in self._dims.workflow.items()},
                "by_provider": {k: v.as_dict() for k, v in self._dims.provider.items()},
                "by_model": {k: v.as_dict() for k, v in self._dims.model.items()},
                "daily": {k: v.as_dict() for k, v in sorted(self._dims.daily.items())},
                "monthly": {k: v.as_dict() for k, v in sorted(self._dims.monthly.items())},
                "budget": {
                    "daily_usd": self._config.daily_usd,
                    "monthly_usd": self._config.monthly_usd,
                    "enforce": self._config.enforce,
                    "spend_today_usd": round(self._dims.daily[_today()].cost_usd, 6),
                    "spend_month_usd": round(self._dims.monthly[_month()].cost_usd, 6),
                },
                "alerts": list(self._alerts[-20:]),
            }

    def reset(self) -> None:
        with self._lock:
            self._dims = _Dimensions()
            self._total = Counter()
            self._alerted.clear()
            self._alerts.clear()


_tracker: BudgetTracker | None = None
_lock = threading.Lock()


def get_budget() -> BudgetTracker:
    """The process-wide budget tracker."""
    global _tracker
    if _tracker is None:
        with _lock:
            if _tracker is None:
                _tracker = BudgetTracker()
    return _tracker


def reset() -> None:
    """Test hook — clear all usage accounting."""
    global _tracker
    with _lock:
        _tracker = None
