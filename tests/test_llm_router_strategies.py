"""Routing strategies (ADR-008).

Strategies are pure ranking functions, so each one is tested by constructing a
candidate set whose correct order is unambiguous and asserting the strategy
finds it. Every strategy must also be total: given N candidates it returns all
N, because the tail of the list is the fallback chain.
"""
from __future__ import annotations

from packages.llm.config import HealthConfig, ModelConfig, ProviderConfig, RoutingConfig
from packages.llm.health import HealthTracker
from packages.llm.strategies import (
    STRATEGIES,
    Candidate,
    RoutingContext,
    get_strategy,
    reset,
    strategy_names,
)
from packages.llm.types import LLMRequest


def _candidate(pid, *, tier="free", priority=100, weight=1.0, concurrency=8,
               model_id=None, context=32768, cost=0.0, tools=True, speed="medium"):
    return Candidate(
        provider=ProviderConfig(id=pid, tier=tier, priority=priority, weight=weight,
                                max_concurrency=concurrency),
        model=ModelConfig(id=model_id or f"{pid}-model", provider=pid,
                          context_window=context, supports_tools=tools,
                          supports_json=True, supports_streaming=True,
                          input_cost_per_1m=cost, speed_tier=speed, priority=priority),
    )


def _context(candidates, *, tracker=None, routing=None, request=None, in_flight=None):
    return RoutingContext(
        request=request or LLMRequest(messages=[{"role": "user", "content": "hi"}]),
        health=tracker or HealthTracker(HealthConfig()),
        routing=routing or RoutingConfig(),
        in_flight=in_flight or {},
        window_sec=300.0,
    )


def test_every_strategy_is_registered_and_total():
    candidates = [_candidate("a"), _candidate("b"), _candidate("c")]
    ctx = _context(candidates)
    assert len(STRATEGIES) == 15
    for name in strategy_names():
        ordered = get_strategy(name)(list(candidates), ctx)
        assert len(ordered) == 3, f"{name} dropped candidates"
        assert {c.key for c in ordered} == {c.key for c in candidates}


def test_unknown_strategy_falls_back_to_adaptive():
    assert get_strategy("does-not-exist") is STRATEGIES["adaptive"]
    assert get_strategy(None) is STRATEGIES["adaptive"]
    # Hyphenated spellings are natural in YAML and must resolve.
    assert get_strategy("cost-optimized") is STRATEGIES["cost_optimized"]
    assert get_strategy("smart") is STRATEGIES["adaptive"]


def test_priority_uses_the_configured_order():
    candidates = [_candidate("c", priority=30), _candidate("a", priority=10),
                  _candidate("b", priority=20)]
    ordered = get_strategy("priority")(candidates, _context(candidates))
    assert [c.provider.id for c in ordered] == ["a", "b", "c"]


def test_round_robin_rotates_between_requests():
    reset()
    candidates = [_candidate("a", priority=1), _candidate("b", priority=2),
                  _candidate("c", priority=3)]
    ctx = _context(candidates)
    firsts = [get_strategy("round_robin")(list(candidates), ctx)[0].provider.id
              for _ in range(3)]
    assert firsts == ["a", "b", "c"]


def test_least_loaded_prefers_free_capacity():
    candidates = [_candidate("busy", concurrency=4), _candidate("idle", concurrency=4)]
    ctx = _context(candidates, in_flight={"busy": 4, "idle": 0})
    ordered = get_strategy("least_loaded")(candidates, ctx)
    assert ordered[0].provider.id == "idle"


def test_lowest_latency_prefers_the_fast_provider():
    tracker = HealthTracker(HealthConfig())
    for _ in range(5):
        tracker.record_success("slow", latency_ms=5000)
        tracker.record_success("fast", latency_ms=100)
    candidates = [_candidate("slow"), _candidate("fast")]
    ordered = get_strategy("lowest_latency")(candidates, _context(candidates, tracker=tracker))
    assert ordered[0].provider.id == "fast"


def test_lowest_latency_gives_an_unmeasured_provider_a_chance():
    """An incumbent must not starve a provider that has never been tried."""
    tracker = HealthTracker(HealthConfig())
    for _ in range(5):
        tracker.record_success("known", latency_ms=100)
    candidates = [_candidate("known"), _candidate("never-tried")]
    ordered = get_strategy("lowest_latency")(candidates, _context(candidates, tracker=tracker))
    assert ordered[0].provider.id == "never-tried"


def test_highest_success_rate_prefers_the_reliable_provider():
    tracker = HealthTracker(HealthConfig(failure_threshold=99, min_samples=99))
    for _ in range(9):
        tracker.record_success("good", latency_ms=10)
    tracker.record_success("flaky", latency_ms=10)
    for _ in range(9):
        tracker.record_failure("flaky", status=500)
    candidates = [_candidate("flaky"), _candidate("good")]
    ordered = get_strategy("highest_success_rate")(candidates, _context(candidates, tracker=tracker))
    assert ordered[0].provider.id == "good"


def test_cost_optimized_puts_free_first():
    candidates = [_candidate("paid", cost=15.0), _candidate("free", cost=0.0),
                  _candidate("cheap", cost=0.5)]
    ordered = get_strategy("cost_optimized")(candidates, _context(candidates))
    assert [c.provider.id for c in ordered] == ["free", "cheap", "paid"]


def test_context_length_optimized_picks_the_smallest_window_that_fits():
    request = LLMRequest(messages=[{"role": "user", "content": "x" * 40_000}], max_tokens=1000)
    candidates = [
        _candidate("huge", context=1_000_000),
        _candidate("small", context=4_096),
        _candidate("right", context=32_768),
    ]
    ordered = get_strategy("context_length_optimized")(
        candidates, _context(candidates, request=request)
    )
    # ~10k prompt tokens + 1k output: 32k fits with least waste; 4k cannot fit.
    assert ordered[0].provider.id == "right"
    assert ordered[-1].provider.id == "small"


def test_token_budget_optimized_avoids_the_rate_limited_provider():
    tracker = HealthTracker(HealthConfig(failure_threshold=99, min_samples=99))
    for _ in range(5):
        tracker.record_success("clear", latency_ms=10)
        tracker.record_failure("limited", status=429, counts_against_breaker=False)
    candidates = [_candidate("limited"), _candidate("clear")]
    ordered = get_strategy("token_budget_optimized")(
        candidates, _context(candidates, tracker=tracker)
    )
    assert ordered[0].provider.id == "clear"


def test_model_capability_puts_capable_models_first():
    request = LLMRequest(
        messages=[{"role": "user", "content": "hi"}],
        tools=[{"type": "function", "function": {"name": "f"}}],
    )
    candidates = [_candidate("no-tools", tools=False), _candidate("tools", tools=True)]
    ordered = get_strategy("model_capability")(candidates, _context(candidates, request=request))
    assert ordered[0].provider.id == "tools"


def test_provider_health_sinks_a_tripped_breaker():
    tracker = HealthTracker(HealthConfig(failure_threshold=2, open_duration_sec=60.0))
    for _ in range(2):
        tracker.record_failure("down", status=500)
    candidates = [_candidate("down"), _candidate("up")]
    ordered = get_strategy("provider_health")(candidates, _context(candidates, tracker=tracker))
    assert ordered[0].provider.id == "up"
    assert ordered[-1].provider.id == "down"


def test_fallback_chain_follows_the_configured_order():
    routing = RoutingConfig(fallback_chain=["third", "first"])
    candidates = [_candidate("first", priority=90), _candidate("second", priority=10),
                  _candidate("third", priority=95)]
    ordered = get_strategy("fallback_chain")(candidates, _context(candidates, routing=routing))
    # Chain order first, then anything unlisted by priority.
    assert [c.provider.id for c in ordered] == ["third", "first", "second"]


def test_automatic_failover_walks_the_tiers():
    routing = RoutingConfig(prefer_local=True)
    candidates = [
        _candidate("premium", tier="premium"),
        _candidate("free", tier="free"),
        _candidate("local", tier="local"),
        _candidate("cheap", tier="cheap"),
    ]
    ordered = get_strategy("automatic_failover")(candidates, _context(candidates, routing=routing))
    assert [c.provider.id for c in ordered] == ["local", "free", "cheap", "premium"]


def test_automatic_failover_never_drops_the_paid_tail():
    """Degradation means "paid last", not "paid never" — the tail is the safety net."""
    routing = RoutingConfig(prefer_local=True)
    candidates = [_candidate("premium", tier="premium"), _candidate("free", tier="free")]
    ordered = get_strategy("automatic_failover")(candidates, _context(candidates, routing=routing))
    assert {c.provider.id for c in ordered} == {"free", "premium"}


def test_adaptive_sinks_a_failing_provider_without_config_changes():
    tracker = HealthTracker(HealthConfig(failure_threshold=99, min_samples=99))
    for _ in range(10):
        tracker.record_success("healthy", latency_ms=200)
    for _ in range(10):
        tracker.record_failure("failing", status=500, counts_against_breaker=False)

    candidates = [_candidate("failing", priority=1), _candidate("healthy", priority=100)]
    ordered = get_strategy("adaptive")(candidates, _context(candidates, tracker=tracker))
    # Live health beats the configured priority — that is the whole point.
    assert ordered[0].provider.id == "healthy"


def test_adaptive_sends_a_tripped_breaker_to_the_very_back():
    tracker = HealthTracker(HealthConfig(failure_threshold=1, open_duration_sec=60.0))
    tracker.record_failure("down", status=500)
    candidates = [_candidate("down"), _candidate("a"), _candidate("b")]
    ordered = get_strategy("adaptive")(candidates, _context(candidates, tracker=tracker))
    assert ordered[-1].provider.id == "down"


def test_adaptive_honours_prefer_local():
    routing = RoutingConfig(prefer_local=True)
    candidates = [_candidate("cloud", tier="free"), _candidate("local", tier="local")]
    ordered = get_strategy("adaptive")(candidates, _context(candidates, routing=routing))
    assert ordered[0].provider.id == "local"


def test_weighted_favours_the_heavier_provider_over_many_draws():
    candidates = [_candidate("heavy", weight=10.0), _candidate("light", weight=1.0)]
    ctx = _context(candidates)
    wins = sum(
        1 for _ in range(300)
        if get_strategy("weighted")(list(candidates), ctx)[0].provider.id == "heavy"
    )
    assert wins > 200, f"weighted picked the heavy provider only {wins}/300 times"


def test_random_eventually_leads_with_each_candidate():
    candidates = [_candidate("a"), _candidate("b"), _candidate("c")]
    ctx = _context(candidates)
    seen = {get_strategy("random")(list(candidates), ctx)[0].provider.id for _ in range(80)}
    assert seen == {"a", "b", "c"}


# ── Regressions from the PR #1168 review ─────────────────────────────────────

def test_local_sits_behind_free_when_prefer_local_is_off():
    """The demotion was an integer no-op: local is rank 0, so nothing moved.

    A cold local model outranking a warm free cloud one contradicts both the
    docstring and the tier order in config/llm/providers.yaml.
    """
    routing = RoutingConfig(prefer_local=False)
    candidates = [
        _candidate("local", tier="local"),
        _candidate("free", tier="free"),
        _candidate("cheap", tier="cheap"),
    ]
    ordered = get_strategy("automatic_failover")(candidates, _context(candidates, routing=routing))
    assert [c.provider.id for c in ordered] == ["free", "local", "cheap"]


def test_unmetered_provider_has_the_most_headroom():
    """tokens_per_minute == 0 means unmetered, which must sort first."""
    candidates = [
        _candidate("metered"),
        _candidate("unmetered"),
    ]
    candidates[0].provider.tokens_per_minute = 10_000
    candidates[1].provider.tokens_per_minute = 0
    ordered = get_strategy("token_budget_optimized")(candidates, _context(candidates))
    assert ordered[0].provider.id == "unmetered"
