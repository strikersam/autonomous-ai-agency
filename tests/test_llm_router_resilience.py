"""Circuit breaker, key rotation, and retry policy (ADR-008 §4, §5).

The property these tests exist to protect: a failure is attributed to the
*narrowest* scope that explains it. Marking a whole provider dead because one
key hit a rate limit, or because one model was decommissioned, is the exact
failure mode that took the platform down before (CLAUDE.md §7).
"""
from __future__ import annotations

import time

import pytest

from packages.llm import keys as llm_keys
from packages.llm.config import HealthConfig, RetryConfig
from packages.llm.health import BreakerState, HealthTracker
from packages.llm.providers.base import classify_error, retry_after_seconds
from packages.llm.retry import RetryBudget, compute_delay, is_retryable
from packages.llm.types import PermanentError, TransientError


@pytest.fixture
def tracker() -> HealthTracker:
    return HealthTracker(HealthConfig(
        failure_threshold=3,
        open_duration_sec=0.05,
        half_open_probes=1,
        backoff_multiplier=2.0,
        max_open_duration_sec=1.0,
        min_samples=100,      # keep the rate rule out of these cases
        window_sec=60.0,
    ))


# ── Error classification ────────────────────────────────────────────────────

@pytest.mark.parametrize("status,body,expected_type,expected_scope", [
    (429, "rate limit exceeded",        TransientError, "key"),
    (429, "insufficient_quota",         TransientError, "key"),
    (404, "model_not_found: gone",      TransientError, "model"),
    (400, "unknown model xyz",          TransientError, "model"),
    (410, "endpoint removed",           TransientError, "model"),
    (500, "internal error",             TransientError, "provider"),
    (502, "bad gateway",                TransientError, "provider"),
    (503, "unavailable",                TransientError, "provider"),
    (504, "gateway timeout",            TransientError, "provider"),
])
def test_transient_errors_carry_the_right_scope(status, body, expected_type, expected_scope):
    error = classify_error(status, body, provider_id="demo")
    assert isinstance(error, expected_type)
    assert error.scope == expected_scope


@pytest.mark.parametrize("status", [400, 401, 403, 405, 413, 422, 451])
def test_permanent_errors_are_never_retried(status):
    error = classify_error(status, "nope", provider_id="demo")
    assert isinstance(error, PermanentError)
    assert is_retryable(error, RetryConfig()) is False


def test_404_without_a_model_hint_is_permanent():
    """A 404 on the wrong URL is a config bug, not a missing model."""
    error = classify_error(404, "Not Found", provider_id="demo")
    assert isinstance(error, PermanentError)


def test_retry_after_header_parsing():
    assert retry_after_seconds({"retry-after": "12"}) == 12.0
    assert retry_after_seconds({"retry-after": "1.5s"}) == 1.5
    assert retry_after_seconds({"retry-after": "500ms"}) == 0.5
    assert retry_after_seconds({}) is None
    assert retry_after_seconds({"retry-after": "not-a-number"}) is None


# ── Circuit breaker ─────────────────────────────────────────────────────────

def test_breaker_opens_after_consecutive_failures(tracker):
    assert tracker.is_available("demo") is True
    for _ in range(3):
        tracker.record_failure("demo", status=500, error="boom")

    assert tracker.get("demo").state is BreakerState.OPEN
    assert tracker.is_available("demo") is False


def test_breaker_half_opens_then_closes_on_a_good_probe(tracker):
    for _ in range(3):
        tracker.record_failure("demo", status=500)
    time.sleep(0.06)

    assert tracker.is_available("demo") is True                  # transitions to half-open
    assert tracker.get("demo").state is BreakerState.HALF_OPEN
    assert tracker.acquire_probe("demo") is True
    assert tracker.acquire_probe("demo") is False, "only one probe may be in flight"

    tracker.record_success("demo", latency_ms=20)
    assert tracker.get("demo").state is BreakerState.CLOSED
    assert tracker.is_available("demo") is True


def test_failed_probe_reopens_with_a_longer_window(tracker):
    for _ in range(3):
        tracker.record_failure("demo", status=500)
    first_window = tracker.get("demo").open_until - tracker.get("demo").opened_at
    time.sleep(0.06)
    tracker.is_available("demo")                                  # -> half-open
    tracker.record_failure("demo", status=500)

    health = tracker.get("demo")
    assert health.state is BreakerState.OPEN
    assert health.trips == 2
    assert (health.open_until - health.opened_at) > first_window


def test_key_scoped_failures_do_not_open_the_breaker(tracker):
    """A 429 on one key says nothing about whether the provider is up."""
    for _ in range(10):
        tracker.record_failure("demo", status=429, counts_against_breaker=False)

    assert tracker.get("demo").state is BreakerState.CLOSED
    assert tracker.is_available("demo") is True
    assert tracker.get("demo").total_rate_limits == 10


def test_model_scoped_failures_do_not_open_the_breaker(tracker):
    """One decommissioned model must not take the whole provider out."""
    for _ in range(10):
        tracker.record_failure("demo", status=404, counts_against_breaker=False)

    assert tracker.get("demo").state is BreakerState.CLOSED


def test_rolling_failure_rate_trips_without_a_consecutive_streak():
    tracker = HealthTracker(HealthConfig(
        failure_threshold=99, failure_rate_threshold=0.5, min_samples=4,
        open_duration_sec=1.0, window_sec=60.0,
    ))
    for _ in range(3):
        tracker.record_success("demo", latency_ms=10)
        tracker.record_failure("demo", status=500)

    assert tracker.get("demo").state is BreakerState.OPEN


def test_health_metrics_are_computed_over_the_window(tracker):
    for latency in (100, 200, 300, 400):
        tracker.record_success("demo", latency_ms=latency)
    tracker.record_failure("demo", status=429, counts_against_breaker=False)

    health = tracker.get("demo")
    assert health.success_rate(60.0) == pytest.approx(0.8)
    assert health.avg_latency_ms(60.0) == pytest.approx(250.0)
    assert health.p95_latency_ms(60.0) == 400.0
    assert health.rate_limit_frequency(60.0) == pytest.approx(0.2)


def test_manual_override_takes_a_provider_out_and_back(tracker):
    tracker.force_open("demo", duration_sec=60.0)
    assert tracker.is_available("demo") is False
    tracker.force_close("demo")
    assert tracker.is_available("demo") is True


# ── Key rotation ────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clean_keys():
    llm_keys.reset()
    yield
    llm_keys.reset()


def test_keys_rotate_round_robin():
    ring = llm_keys.KeyRing()
    keys = ["k1", "k2", "k3"]
    picked = [ring.acquire("demo", keys)[0] for _ in range(6)]
    assert picked == ["k1", "k2", "k3", "k1", "k2", "k3"]


def test_rate_limited_key_is_skipped_not_the_provider():
    ring = llm_keys.KeyRing()
    keys = ["k1", "k2"]

    first, _index = ring.acquire("demo", keys)
    ring.record_rate_limit("demo", first, retry_after=60.0)

    # The next acquire must hand out the *other* key, not fail.
    second, _index = ring.acquire("demo", keys)
    assert second != first
    assert ring.all_cooling("demo", keys) is False


def test_all_keys_cooling_reports_none_available():
    ring = llm_keys.KeyRing()
    keys = ["k1", "k2"]
    for key in keys:
        ring.acquire("demo", keys)
        ring.record_rate_limit("demo", key, retry_after=60.0)

    assert ring.all_cooling("demo", keys) is True
    picked, index = ring.acquire("demo", keys)
    assert picked is None and index == -1


def test_repeated_limits_lengthen_the_cooldown():
    ring = llm_keys.KeyRing()
    first = ring.record_rate_limit("demo", "k1")
    second = ring.record_rate_limit("demo", "k1")
    assert second > first


def test_quota_exhaustion_cools_far_longer_than_a_burst():
    ring = llm_keys.KeyRing()
    burst = ring.record_rate_limit("demo", "k1")
    ring.record_success("demo", "k1")
    quota = ring.record_rate_limit("demo", "k2", quota_exhausted=True)
    assert quota > burst * 10


def test_no_keys_means_no_auth_not_exhausted():
    """A local Ollama has no key; that must not read as 'all keys spent'."""
    ring = llm_keys.KeyRing()
    key, index = ring.acquire("ollama", [])
    assert key == "" and index == 0


def test_snapshot_never_exposes_key_material():
    ring = llm_keys.KeyRing()
    ring.acquire("demo", ["super-secret-value"])
    ring.record_rate_limit("demo", "super-secret-value")

    rendered = repr(ring.snapshot())
    assert "super-secret-value" not in rendered
    assert len(ring.snapshot()["demo"][0]["digest"]) == 8


def test_resolve_keys_splits_and_dedupes(monkeypatch):
    monkeypatch.setenv("POOL_A", "one, two  three")
    monkeypatch.setenv("POOL_B", "three,four")
    assert llm_keys.resolve_keys(["POOL_A", "POOL_B"]) == ["one", "two", "three", "four"]


# ── Retry policy ────────────────────────────────────────────────────────────

def test_backoff_grows_and_is_capped():
    config = RetryConfig(base_delay_sec=1.0, multiplier=2.0, max_delay_sec=10.0, jitter=0.0)
    assert compute_delay(1, config) == 1.0
    assert compute_delay(2, config) == 2.0
    assert compute_delay(3, config) == 4.0
    assert compute_delay(9, config) == 10.0


def test_jitter_spreads_retries():
    """Without jitter every caller retries in the same millisecond."""
    config = RetryConfig(base_delay_sec=1.0, multiplier=2.0, max_delay_sec=10.0, jitter=0.3)
    samples = {compute_delay(2, config) for _ in range(40)}
    assert len(samples) > 1
    assert all(1.4 <= s <= 2.6 for s in samples)


def test_retry_after_overrides_the_computed_delay():
    config = RetryConfig(base_delay_sec=1.0, max_delay_sec=30.0, jitter=0.0)
    assert compute_delay(5, config, retry_after=3.0) == 3.0


def test_retry_after_is_clamped_to_max_delay():
    """A provider advertising an hour must not stall the whole request."""
    config = RetryConfig(max_delay_sec=30.0)
    assert compute_delay(1, config, retry_after=3600.0) == 30.0


def test_transport_errors_are_retryable():
    config = RetryConfig()
    assert is_retryable(ConnectionResetError("reset"), config) is True
    assert is_retryable(TimeoutError("timeout"), config) is True


def test_status_outside_the_retry_list_is_not_retried():
    config = RetryConfig(retry_statuses=[429, 503])
    assert is_retryable(TransientError("x", status=500), config) is False
    assert is_retryable(TransientError("x", status=429), config) is True


def test_budget_bounds_both_attempts_and_wall_clock():
    budget = RetryBudget(max_attempts=2, deadline_sec=60.0)
    assert budget.exhausted() is False
    budget.charge()
    budget.charge()
    assert budget.exhausted() is True
    assert "attempt budget" in budget.reason()

    timed = RetryBudget(max_attempts=99, deadline_sec=0.0)
    assert timed.exhausted() is True
    assert "time budget" in timed.reason()


def test_budget_refuses_a_wait_it_cannot_afford():
    budget = RetryBudget(max_attempts=9, deadline_sec=1.0)
    assert budget.can_wait(0.1) is True
    assert budget.can_wait(30.0) is False
