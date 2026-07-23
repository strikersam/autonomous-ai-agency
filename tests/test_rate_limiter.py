"""Tests for packages/ai/rate_limiter.py — proactive x-ratelimit-* throttling
(header-driven layer) and operator-configured per-provider pacing (token-bucket
layer)."""

from __future__ import annotations

import asyncio
import time
from typing import Iterator

import httpx
import pytest

from packages.ai import rate_limiter as rl
from packages.ai.rate_limiter import RateLimitTracker, _parse_reset_epoch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _response(headers: dict[str, str], status: int = 200) -> httpx.Response:
    return httpx.Response(status, json={}, headers=headers)


# ---------------------------------------------------------------------------
# _parse_reset_epoch
# ---------------------------------------------------------------------------

class TestParseResetEpoch:
    def test_delta_seconds(self) -> None:
        before = time.monotonic()
        epoch = _parse_reset_epoch("2s")
        after = time.monotonic()
        assert before + 2.0 <= epoch <= after + 2.1

    def test_delta_milliseconds(self) -> None:
        before = time.monotonic()
        epoch = _parse_reset_epoch("500ms")
        after = time.monotonic()
        assert before + 0.5 <= epoch <= after + 0.6

    def test_fractional_seconds(self) -> None:
        before = time.monotonic()
        epoch = _parse_reset_epoch("1.5s")
        assert epoch > before + 1.0

    def test_iso_8601_future(self) -> None:
        from datetime import datetime, timedelta, timezone
        future = datetime.now(timezone.utc) + timedelta(seconds=10)
        epoch = _parse_reset_epoch(future.isoformat())
        now = time.monotonic()
        # Should be ~10s in the future (±1s tolerance for slow CI)
        assert now + 8 < epoch < now + 12

    def test_empty_string_returns_zero(self) -> None:
        assert _parse_reset_epoch("") == 0.0

    def test_none_returns_zero(self) -> None:
        assert _parse_reset_epoch(None) == 0.0

    def test_garbage_returns_zero(self) -> None:
        assert _parse_reset_epoch("not-a-time") == 0.0


# ---------------------------------------------------------------------------
# RateLimitTracker.update_from_response
# ---------------------------------------------------------------------------

class TestUpdateFromResponse:
    def setup_method(self) -> None:
        self.tracker = RateLimitTracker()

    def test_parses_request_quota(self) -> None:
        resp = _response({
            "x-ratelimit-limit-requests": "100",
            "x-ratelimit-remaining-requests": "42",
            "x-ratelimit-reset-requests": "1s",
        })
        self.tracker.update_from_response("groq", resp)
        stats = self.tracker.get_stats()
        assert stats["groq"]["limit_requests"] == 100
        assert stats["groq"]["remaining_requests"] == 42

    def test_parses_token_quota(self) -> None:
        resp = _response({
            "x-ratelimit-limit-tokens": "50000",
            "x-ratelimit-remaining-tokens": "1000",
            "x-ratelimit-reset-tokens": "500ms",
        })
        self.tracker.update_from_response("anthropic", resp)
        stats = self.tracker.get_stats()
        assert stats["anthropic"]["limit_tokens"] == 50000
        assert stats["anthropic"]["remaining_tokens"] == 1000

    def test_missing_headers_ignored(self) -> None:
        resp = _response({})
        self.tracker.update_from_response("nvidia", resp)
        stats = self.tracker.get_stats()
        assert stats["nvidia"]["remaining_requests"] is None
        assert stats["nvidia"]["remaining_tokens"] is None

    def test_partial_headers_preserved(self) -> None:
        # First response gives requests quota.
        self.tracker.update_from_response(
            "groq",
            _response({"x-ratelimit-remaining-requests": "5", "x-ratelimit-limit-requests": "100"}),
        )
        # Second response gives only token quota.
        self.tracker.update_from_response(
            "groq",
            _response({"x-ratelimit-remaining-tokens": "200", "x-ratelimit-limit-tokens": "5000"}),
        )
        stats = self.tracker.get_stats()
        # Both fields should be present after two partial updates.
        assert stats["groq"]["remaining_requests"] == 5
        assert stats["groq"]["remaining_tokens"] == 200

    def test_multiple_providers_tracked_independently(self) -> None:
        self.tracker.update_from_response(
            "groq", _response({"x-ratelimit-remaining-requests": "10", "x-ratelimit-limit-requests": "100"})
        )
        self.tracker.update_from_response(
            "anthropic", _response({"x-ratelimit-remaining-requests": "80", "x-ratelimit-limit-requests": "1000"})
        )
        stats = self.tracker.get_stats()
        assert stats["groq"]["remaining_requests"] == 10
        assert stats["anthropic"]["remaining_requests"] == 80

    def test_called_on_429_response(self) -> None:
        resp = _response(
            {"x-ratelimit-remaining-requests": "0", "x-ratelimit-limit-requests": "60",
             "x-ratelimit-reset-requests": "1s"},
            status=429,
        )
        self.tracker.update_from_response("groq", resp)
        stats = self.tracker.get_stats()
        assert stats["groq"]["remaining_requests"] == 0


# ---------------------------------------------------------------------------
# RateLimitTracker.pre_flight_check
# ---------------------------------------------------------------------------

class TestPreFlightCheck:
    def setup_method(self) -> None:
        self.tracker = RateLimitTracker()

    @pytest.mark.asyncio
    async def test_noop_when_no_data(self) -> None:
        waited = await self.tracker.pre_flight_check("unknown-provider")
        assert waited == 0.0

    @pytest.mark.asyncio
    async def test_noop_when_healthy_quota(self) -> None:
        self.tracker.update_from_response(
            "groq",
            _response({
                "x-ratelimit-limit-requests": "100",
                "x-ratelimit-remaining-requests": "90",
                "x-ratelimit-reset-requests": "1s",
            }),
        )
        waited = await self.tracker.pre_flight_check("groq")
        assert waited == 0.0

    @pytest.mark.asyncio
    async def test_noop_when_reset_already_passed(self) -> None:
        # Even if remaining is 0, if the reset time has already passed, no wait.
        q = self.tracker._state.setdefault("groq", __import__("packages.ai.rate_limiter", fromlist=["_ProviderQuota"])._ProviderQuota())
        q.remaining_requests = 0
        q.limit_requests = 100
        q.reset_requests_at = time.monotonic() - 1.0  # already passed
        waited = await self.tracker.pre_flight_check("groq")
        assert waited == 0.0

    @pytest.mark.asyncio
    async def test_waits_when_requests_critically_low(self) -> None:
        # remaining=1, limit=100, threshold=5% → 5 → 1 < 5 → should wait
        self.tracker.update_from_response(
            "groq",
            _response({
                "x-ratelimit-limit-requests": "100",
                "x-ratelimit-remaining-requests": "1",
                "x-ratelimit-reset-requests": "0.05s",  # 50ms reset
            }),
        )
        t0 = time.monotonic()
        waited = await self.tracker.pre_flight_check("groq")
        elapsed = time.monotonic() - t0
        assert waited > 0.0
        assert elapsed >= 0.04  # actually slept

    @pytest.mark.asyncio
    async def test_waits_when_tokens_critically_low(self) -> None:
        # remaining_tokens=50, limit=5000, threshold=5% → 250 → 50 < 250 → wait
        self.tracker.update_from_response(
            "anthropic",
            _response({
                "x-ratelimit-limit-tokens": "5000",
                "x-ratelimit-remaining-tokens": "50",
                "x-ratelimit-reset-tokens": "0.05s",
            }),
        )
        t0 = time.monotonic()
        waited = await self.tracker.pre_flight_check("anthropic")
        elapsed = time.monotonic() - t0
        assert waited > 0.0
        assert elapsed >= 0.04

    @pytest.mark.asyncio
    async def test_caps_wait_at_max(self) -> None:
        from packages.ai import rate_limiter as rl_mod
        original_max = rl_mod._MAX_PREFLIGHT_WAIT_SECONDS
        rl_mod._MAX_PREFLIGHT_WAIT_SECONDS = 0.05  # tiny cap for the test
        try:
            self.tracker.update_from_response(
                "groq",
                _response({
                    "x-ratelimit-limit-requests": "100",
                    "x-ratelimit-remaining-requests": "0",
                    "x-ratelimit-reset-requests": "60s",  # far future
                }),
            )
            waited = await self.tracker.pre_flight_check("groq")
            assert waited <= 0.06
        finally:
            rl_mod._MAX_PREFLIGHT_WAIT_SECONDS = original_max


# ---------------------------------------------------------------------------
# RateLimitTracker.get_stats
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_empty_returns_empty(self) -> None:
        tracker = RateLimitTracker()
        assert tracker.get_stats() == {}

    def test_reset_in_s_is_nonnegative(self) -> None:
        tracker = RateLimitTracker()
        tracker.update_from_response(
            "groq",
            _response({
                "x-ratelimit-limit-requests": "60",
                "x-ratelimit-remaining-requests": "30",
                "x-ratelimit-reset-requests": "1s",
            }),
        )
        stats = tracker.get_stats()
        assert stats["groq"]["reset_requests_in_s"] >= 0

    def test_updated_s_ago_is_recent(self) -> None:
        tracker = RateLimitTracker()
        tracker.update_from_response("groq", _response({"x-ratelimit-remaining-requests": "5"}))
        assert tracker.get_stats()["groq"]["updated_s_ago"] < 1.0


# ---------------------------------------------------------------------------
# RateLimitTracker.clear
# ---------------------------------------------------------------------------

class TestClear:
    def test_clear_resets_all_state(self) -> None:
        tracker = RateLimitTracker()
        tracker.update_from_response("groq", _response({"x-ratelimit-remaining-requests": "5"}))
        tracker.clear()
        assert tracker.get_stats() == {}


# ---------------------------------------------------------------------------
# Layer 2: TokenBucket / pace() — operator-configured per-provider pacing
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_buckets() -> Iterator[None]:
    rl.reset()
    yield
    rl.reset()


def test_pace_is_noop_without_env_var(monkeypatch):
    monkeypatch.delenv("TESTPROV_MAX_RPM", raising=False)
    waited = asyncio.run(rl.pace("testprov"))
    assert waited == 0.0


def test_pace_noop_for_non_numeric_env_var(monkeypatch):
    monkeypatch.setenv("TESTPROV_MAX_RPM", "not-a-number")
    waited = asyncio.run(rl.pace("testprov"))
    assert waited == 0.0


def test_pace_noop_for_zero_or_negative_rpm(monkeypatch):
    monkeypatch.setenv("TESTPROV_MAX_RPM", "0")
    assert asyncio.run(rl.pace("testprov")) == 0.0
    monkeypatch.setenv("TESTPROV_MAX_RPM", "-5")
    assert asyncio.run(rl.pace("testprov")) == 0.0


def test_pace_noop_for_non_finite_rpm(monkeypatch):
    """Regression: float("inf") used to parse successfully and pass the
    rpm > 0 check, producing a zero pacing interval (i.e. silently NO
    pacing at all) instead of being rejected like other invalid input."""
    monkeypatch.setenv("TESTPROV_MAX_RPM", "inf")
    assert asyncio.run(rl.pace("testprov")) == 0.0
    monkeypatch.setenv("TESTPROV_MAX_RPM", "nan")
    assert asyncio.run(rl.pace("testprov")) == 0.0


def test_token_bucket_allows_burst_up_to_capacity():
    bucket = rl.TokenBucket(rate_per_min=60, capacity=3)
    waits = [asyncio.run(bucket.acquire()) for _ in range(3)]
    assert waits == [0.0, 0.0, 0.0]


def test_token_bucket_blocks_when_drained():
    bucket = rl.TokenBucket(rate_per_min=60, capacity=1)  # 1 token/sec, capacity 1
    first = asyncio.run(bucket.acquire())
    assert first == 0.0
    second = asyncio.run(bucket.acquire(max_wait=2.0))
    assert second > 0.0  # had to wait for a refill


def test_token_bucket_never_waits_past_max_wait():
    bucket = rl.TokenBucket(rate_per_min=1, capacity=1)  # very slow refill
    asyncio.run(bucket.acquire())  # drain the initial token
    start = time.monotonic()
    waited = asyncio.run(bucket.acquire(max_wait=0.2))
    elapsed = time.monotonic() - start
    assert waited <= 0.2 + 0.05
    assert elapsed <= 0.3


def test_pace_paces_configured_provider(monkeypatch):
    monkeypatch.setenv("TESTPROV_MAX_RPM", "60")  # 1/sec, capacity ~10 by default
    async def burn_bucket() -> None:
        for _ in range(11):
            await rl.pace("testprov", max_wait=0.05)
    asyncio.run(burn_bucket())
    # 11th+ request should have needed to wait (bucket capacity ~10)
    waited = asyncio.run(rl.pace("testprov", max_wait=0.05))
    assert waited > 0.0


def test_pace_reconfigures_bucket_when_rpm_env_changes(monkeypatch):
    monkeypatch.setenv("TESTPROV_MAX_RPM", "60")
    asyncio.run(rl.pace("testprov"))
    assert "testprov" in rl._buckets
    old_rate = rl._buckets["testprov"].rate_per_sec

    monkeypatch.setenv("TESTPROV_MAX_RPM", "120")
    asyncio.run(rl.pace("testprov"))
    assert rl._buckets["testprov"].rate_per_sec != old_rate


def test_pace_never_raises_on_bad_input(monkeypatch):
    monkeypatch.setenv("TESTPROV_MAX_RPM", "60")
    # Should not raise even with an empty provider id.
    asyncio.run(rl.pace(""))


def test_token_bucket_serializes_concurrent_waiters_instead_of_bursting():
    """Regression: concurrent callers on a drained bucket used to all compute
    roughly the same wait, release the lock, sleep in parallel, and proceed
    together — a burst of N, not N properly spaced requests. Reservations
    must be staggered by one interval each, made atomically under the lock."""
    bucket = rl.TokenBucket(rate_per_min=60, capacity=1)  # 1 token/sec, no burst beyond 1

    async def drain_then_race() -> list[float]:
        await bucket.acquire()  # consume the single burst token
        # 4 more callers arrive concurrently on a now-empty bucket.
        return await asyncio.gather(*(bucket.acquire(max_wait=10.0) for _ in range(4)))

    start = time.monotonic()
    waits = asyncio.run(drain_then_race())
    elapsed = time.monotonic() - start

    # Each of the 4 queued callers must have been staggered ~1 interval (1s)
    # apart from the others, not all woken at roughly the same time.
    waits_sorted = sorted(waits)
    for i in range(len(waits_sorted) - 1):
        gap = waits_sorted[i + 1] - waits_sorted[i]
        assert 0.7 < gap < 1.3, f"waiters were not staggered by ~1 interval: {waits_sorted}"
    # 4 callers spaced 1s apart means the last one waits ~4s, not ~1s.
    assert elapsed > 3.0


def test_token_bucket_reservations_are_monotonically_increasing():
    """Each acquire() under contention must reserve a strictly later slot
    than the previous one — the core invariant the concurrency fix relies on."""
    bucket = rl.TokenBucket(rate_per_min=600, capacity=1)

    async def many_acquires() -> list[float]:
        return await asyncio.gather(*(bucket.acquire(max_wait=10.0) for _ in range(5)))

    waits = asyncio.run(many_acquires())
    assert len(set(round(w, 3) for w in waits)) == len(waits), (
        f"expected distinct wait times, got {waits}"
    )
