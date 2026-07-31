"""packages/llm/strategies.py — candidate ordering.

A *candidate* is one (provider, model) pair. A *strategy* orders the candidate
list; the router then walks that order until something succeeds. Strategies
never perform I/O and never mutate state — they are pure ranking functions, so
they are trivially testable and cheap to run on every request.

Fifteen strategies ship. Fourteen map to the classic named policies; the
fifteenth, ``adaptive``, is this platform's default and blends live health,
latency, success rate, cost, and load into one score (ADR-008, adopted from
OmniRoute's multi-factor scoring).

Selecting one is configuration: ``routing.yaml``'s ``strategy`` key, the
``LLM_ROUTER_STRATEGY`` environment variable, a per-agent policy, or
``LLMRequest.strategy`` for a single call.
"""
from __future__ import annotations

import itertools
import logging
import random
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from packages.llm.config import ModelConfig, ProviderConfig, RoutingConfig
from packages.llm.health import HealthTracker
from packages.llm.types import LLMRequest

log = logging.getLogger("llm.strategies")


@dataclass
class Candidate:
    """One routable (provider, model) pair."""

    provider: ProviderConfig
    model: ModelConfig
    in_flight: int = 0

    @property
    def key(self) -> str:
        return f"{self.provider.id}/{self.model.id}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider.id,
            "model": self.model.id,
            "tier": self.provider.tier,
            "priority": self.provider.priority,
            "context_window": self.model.context_window,
            "cost_per_1m": self.model.input_cost_per_1m + self.model.output_cost_per_1m,
        }


@dataclass
class RoutingContext:
    """Everything a strategy may read when ranking."""

    request: LLMRequest
    health: HealthTracker
    routing: RoutingConfig
    in_flight: dict[str, int] = field(default_factory=dict)
    window_sec: float = 300.0

    def load_of(self, provider_id: str) -> int:
        return self.in_flight.get(provider_id, 0)

    def utilisation(self, candidate: Candidate) -> float:
        """In-flight requests as a fraction of the provider's bulkhead size."""
        capacity = max(1, candidate.provider.max_concurrency)
        return min(1.0, self.load_of(candidate.provider.id) / capacity)


Strategy = Callable[[list[Candidate], RoutingContext], list[Candidate]]

_round_robin_counters: dict[str, itertools.count] = {}
_counter_lock = threading.Lock()


def _counter(name: str) -> itertools.count:
    with _counter_lock:
        counter = _round_robin_counters.get(name)
        if counter is None:
            counter = itertools.count()
            _round_robin_counters[name] = counter
        return counter


# ── Individual strategies ────────────────────────────────────────────────────

def priority(candidates: list[Candidate], ctx: RoutingContext) -> list[Candidate]:
    """Static order: provider priority, then model priority. The predictable one."""
    return sorted(candidates, key=lambda c: (c.provider.priority, c.model.priority, c.key))


def round_robin(candidates: list[Candidate], ctx: RoutingContext) -> list[Candidate]:
    """Even distribution — rotate the starting point on every request."""
    if not candidates:
        return []
    ordered = priority(candidates, ctx)
    offset = next(_counter("round_robin")) % len(ordered)
    return ordered[offset:] + ordered[:offset]


def random_choice(candidates: list[Candidate], ctx: RoutingContext) -> list[Candidate]:
    """Uniform shuffle — spreads load without any shared counter."""
    shuffled = list(candidates)
    random.shuffle(shuffled)  # noqa: S311 - load spreading, not cryptography
    return shuffled


def least_loaded(candidates: list[Candidate], ctx: RoutingContext) -> list[Candidate]:
    """Prefer the provider with the most free bulkhead capacity."""
    return sorted(
        candidates,
        key=lambda c: (ctx.utilisation(c), c.provider.priority, c.key),
    )


def lowest_latency(candidates: list[Candidate], ctx: RoutingContext) -> list[Candidate]:
    """Prefer the fastest observed provider.

    Providers with no samples sort first: an unmeasured provider is given one
    chance to prove itself rather than being starved forever by an incumbent.
    """
    def score(candidate: Candidate) -> tuple[float, int, str]:
        health = ctx.health.get(candidate.provider.id)
        latency = health.p95_latency_ms(ctx.window_sec)
        return (latency if latency > 0 else -1.0, candidate.provider.priority, candidate.key)

    return sorted(candidates, key=score)


def highest_success_rate(candidates: list[Candidate], ctx: RoutingContext) -> list[Candidate]:
    """Prefer the provider that fails least often in the rolling window."""
    return sorted(
        candidates,
        key=lambda c: (
            -ctx.health.get(c.provider.id).success_rate(ctx.window_sec),
            c.provider.priority,
            c.key,
        ),
    )


def weighted(candidates: list[Candidate], ctx: RoutingContext) -> list[Candidate]:
    """Randomised order biased by each provider's configured weight.

    Uses the exponential-race method: draw a key of ``-ln(u)/weight`` per
    candidate and sort ascending. The result is a full ordering whose first
    element is chosen with probability proportional to weight — so the
    fallback tail stays usable instead of collapsing to a single pick.
    """
    import math

    def sort_key(candidate: Candidate) -> float:
        weight = max(1e-6, candidate.provider.weight)
        draw = max(1e-12, random.random())  # noqa: S311 - load spreading
        return -math.log(draw) / weight

    return sorted(candidates, key=sort_key)


def cost_optimized(candidates: list[Candidate], ctx: RoutingContext) -> list[Candidate]:
    """Cheapest first — free models before any paid one."""
    return sorted(
        candidates,
        key=lambda c: (
            c.model.input_cost_per_1m + c.model.output_cost_per_1m,
            c.provider.priority,
            c.key,
        ),
    )


def context_length_optimized(candidates: list[Candidate], ctx: RoutingContext) -> list[Candidate]:
    """Prefer the smallest context window that still fits the prompt.

    Reserving the 1M-token model for prompts that need it keeps it available
    when something actually overflows, and large-context models are usually
    slower and dearer per token.
    """
    needed = ctx.request.approx_prompt_tokens() + ctx.request.max_tokens

    def score(candidate: Candidate) -> tuple[int, int, str]:
        window = candidate.model.context_window
        fits = 0 if window >= needed else 1
        headroom = window - needed if fits == 0 else -window
        return (fits, headroom, candidate.key)

    return sorted(candidates, key=score)


def token_budget_optimized(candidates: list[Candidate], ctx: RoutingContext) -> list[Candidate]:
    """Prefer providers with token-per-minute headroom left in the window.

    A provider that is 429ing frequently has no headroom whatever its
    configured limit claims, so observed rate-limit frequency is the primary
    signal and the configured TPM is the tie-break.
    """
    def score(candidate: Candidate) -> tuple[float, float, str]:
        health = ctx.health.get(candidate.provider.id)
        pressure = health.rate_limit_frequency(ctx.window_sec)
        tpm = candidate.provider.tokens_per_minute or candidate.model.max_tokens_per_minute
        headroom = -float(tpm) if tpm else 0.0
        return (pressure, headroom, candidate.key)

    return sorted(candidates, key=score)


def model_capability(candidates: list[Candidate], ctx: RoutingContext) -> list[Candidate]:
    """Prefer the model that most closely matches what the request needs.

    Exact capability matches sort first; a model with extra unneeded
    capabilities sorts behind one that fits, because over-capable models are
    normally the expensive ones.
    """
    request = ctx.request
    needs_tools = request.requires_tools()
    needs_json = request.requires_json()
    needs_images = request.requires_vision()

    def score(candidate: Candidate) -> tuple[int, int, int, str]:
        model = candidate.model
        missing = 0
        if needs_tools and not (model.supports_tools or model.supports_function_calling):
            missing += 1
        if needs_json and not model.supports_json:
            missing += 1
        if needs_images and not model.supports_images:
            missing += 1
        if request.stream and not model.supports_streaming:
            missing += 1
        surplus = sum((
            1 if (model.supports_images and not needs_images) else 0,
            1 if (model.supports_reasoning and not needs_tools) else 0,
        ))
        return (missing, surplus, model.priority, candidate.key)

    return sorted(candidates, key=score)


def provider_health(candidates: list[Candidate], ctx: RoutingContext) -> list[Candidate]:
    """Order strictly by breaker state, then failure rate."""
    def score(candidate: Candidate) -> tuple[int, float, int, str]:
        health = ctx.health.get(candidate.provider.id)
        available = 0 if ctx.health.is_available(candidate.provider.id) else 1
        return (available, health.failure_rate(ctx.window_sec),
                candidate.provider.priority, candidate.key)

    return sorted(candidates, key=score)


def fallback_chain(candidates: list[Candidate], ctx: RoutingContext) -> list[Candidate]:
    """Follow the explicit chain in ``routing.yaml``, then everything else.

    The chain lists provider ids in order. Anything not named keeps its
    priority order behind the chain, so an incomplete chain degrades to
    ``priority`` rather than dropping providers.
    """
    chain = ctx.routing.fallback_chain or []
    rank = {pid: index for index, pid in enumerate(chain)}
    return sorted(
        candidates,
        key=lambda c: (rank.get(c.provider.id, len(chain)), c.provider.priority, c.key),
    )


def automatic_failover(candidates: list[Candidate], ctx: RoutingContext) -> list[Candidate]:
    """Tiered degradation: local → free → cheap → premium.

    Paid tiers are appended, never skipped: when every free option is
    exhausted the request still completes if the operator opted into paid.
    This is the graceful-degradation path from ADR-008.
    """
    tier_rank = {"local": 0, "free": 1, "cheap": 2, "premium": 3}
    prefer_local = ctx.routing.prefer_local

    def score(candidate: Candidate) -> tuple[int, int, int, str]:
        tier = tier_rank.get(candidate.provider.tier, 2)
        if not prefer_local and candidate.provider.tier == "local":
            # Without prefer_local, a cold local model shouldn't outrank a warm
            # free cloud one — sit it just behind the free tier.
            tier = 1 if tier_rank.get("free", 1) < tier else tier
        healthy = 0 if ctx.health.is_available(candidate.provider.id) else 1
        return (healthy, tier, candidate.provider.priority, candidate.key)

    return sorted(candidates, key=score)


def adaptive(candidates: list[Candidate], ctx: RoutingContext) -> list[Candidate]:
    """Multi-factor live scoring — the default.

    Blends five signals into one score, lower being better:

        success rate      (weight 3.0)  historical reliability dominates
        rate-limit rate   (weight 2.0)  a provider that 429s is nearly useless
        load              (weight 1.5)  spread work across free capacity
        latency           (weight 1.0)  normalised against a 10s reference
        cost              (weight 0.5)  a tie-break, not a driver

    Unlike a static priority list this reacts within one rolling window: a
    provider that starts failing sinks without anyone editing YAML, and climbs
    back as soon as it recovers.
    """
    prefer_local = ctx.routing.prefer_local

    def score(candidate: Candidate) -> tuple[float, str]:
        health = ctx.health.get(candidate.provider.id)
        window = ctx.window_sec

        failure = 1.0 - health.success_rate(window)
        limited = health.rate_limit_frequency(window)
        load = ctx.utilisation(candidate)
        latency = min(1.0, health.p95_latency_ms(window) / 10_000.0)
        cost = min(1.0, (candidate.model.input_cost_per_1m + candidate.model.output_cost_per_1m) / 100.0)

        total = (
            3.0 * failure
            + 2.0 * limited
            + 1.5 * load
            + 1.0 * latency
            + 0.5 * cost
        )
        # A tripped breaker is not merely a bad score — it goes last.
        if not ctx.health.is_available(candidate.provider.id):
            total += 100.0
        if prefer_local and candidate.provider.tier == "local":
            total -= 1.0
        # Nudge by configured priority so ties resolve the way the operator expects.
        total += candidate.provider.priority / 10_000.0
        return (total, candidate.key)

    return sorted(candidates, key=score)


STRATEGIES: dict[str, Strategy] = {
    "round_robin": round_robin,
    "least_loaded": least_loaded,
    "lowest_latency": lowest_latency,
    "highest_success_rate": highest_success_rate,
    "random": random_choice,
    "weighted": weighted,
    "priority": priority,
    "cost_optimized": cost_optimized,
    "context_length_optimized": context_length_optimized,
    "token_budget_optimized": token_budget_optimized,
    "model_capability": model_capability,
    "provider_health": provider_health,
    "fallback_chain": fallback_chain,
    "automatic_failover": automatic_failover,
    "adaptive": adaptive,
}

# Accept the hyphenated spellings people naturally write in YAML.
_ALIASES = {name.replace("_", "-"): name for name in STRATEGIES}
_ALIASES.update({
    "failover": "automatic_failover",
    "cost": "cost_optimized",
    "latency": "lowest_latency",
    "health": "provider_health",
    "capability": "model_capability",
    "smart": "adaptive",
    "auto": "adaptive",
})


def get_strategy(name: str | None) -> Strategy:
    """Look up a strategy by name, falling back to ``adaptive``."""
    key = (name or "adaptive").strip().lower()
    key = _ALIASES.get(key, key)
    strategy = STRATEGIES.get(key)
    if strategy is None:
        log.warning("llm.strategies: unknown strategy %r — using 'adaptive'", name)
        return adaptive
    return strategy


def strategy_names() -> list[str]:
    """Every selectable strategy name, for the dashboard and docs."""
    return sorted(STRATEGIES)


def reset() -> None:
    """Test hook — restart the round-robin counters."""
    with _counter_lock:
        _round_robin_counters.clear()
