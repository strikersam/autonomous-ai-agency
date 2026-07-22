"""Tests for packages/ai/rate_limiter.py — proactive per-provider request pacing."""
from __future__ import annotations

import asyncio
import time

import pytest

from packages.ai import rate_limiter as rl


@pytest.fixture(autouse=True)
def _reset_buckets():
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
    async def burn_bucket():
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
