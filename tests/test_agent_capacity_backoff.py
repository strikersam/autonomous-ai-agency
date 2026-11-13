"""Regression: a rate-limited brain must be waited out, not retried instantly.

Production (2026-11-12) showed tasks failing with "All brain providers
exhausted" / "nvidia HTTP 429: rate limited". The agent retried tool selection
after 0.5s, inside the provider's 20s+ cooldown, so every retry failed, three
failed steps tripped the halter and the task was lost. Planning had no retry.
"""
from __future__ import annotations

import pytest

from agent import capacity_backoff as cb
from packages.ai.failover_client import BrainFailoverExhausted


@pytest.mark.parametrize(
    "exc",
    [
        BrainFailoverExhausted("all candidates failed"),
        RuntimeError("All 1 brain provider attempt(s) failed: nvidia: nvidia HTTP 429: rate limited"),
        RuntimeError("All brain providers exhausted. Last error: all candidates failed"),
        RuntimeError("All configured LLM providers failed (nvidia/x: 429)"),
        RuntimeError("groq HTTP 429: rate limited (quota exhausted)"),
    ],
)
def test_capacity_errors_are_recognised(exc: BaseException) -> None:
    assert cb.is_capacity_error(exc)


def test_capacity_error_found_through_exception_chain() -> None:
    try:
        try:
            raise BrainFailoverExhausted("all candidates failed")
        except BrainFailoverExhausted as inner:
            raise ValueError("wrapped") from inner
    except ValueError as outer:
        assert cb.is_capacity_error(outer)


@pytest.mark.parametrize(
    "exc",
    [ValueError("model returned invalid JSON"), KeyError("tool"), RuntimeError("bad plan output")],
)
def test_other_errors_are_not_capacity_errors(exc: BaseException) -> None:
    assert not cb.is_capacity_error(exc)


def test_unrelated_error_raised_while_handling_a_429_is_not_capacity() -> None:
    try:
        try:
            raise RuntimeError("nvidia HTTP 429: rate limited")
        except RuntimeError:
            raise ValueError("unrelated defect")
    except ValueError as outer:
        assert not cb.is_capacity_error(outer)


def test_backoff_grows_and_is_capped() -> None:
    waits = [cb.capacity_backoff_s(n) for n in (1, 2, 3, 4, 10)]
    assert waits[0] >= 15, "first wait must outlast a single-429 provider cooldown"
    assert waits[0] < waits[1] < waits[2]
    assert max(waits) <= cb.MAX_BACKOFF_S
    assert waits[-1] == cb.MAX_BACKOFF_S


@pytest.fixture()
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    recorded: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        recorded.append(seconds)

    monkeypatch.setattr(cb, "_sleep", fake_sleep)
    return recorded


async def test_retry_waits_out_capacity_errors_then_succeeds(sleeps: list[float]) -> None:
    calls = {"n": 0}

    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] <= 2:
            raise BrainFailoverExhausted("all candidates failed")
        return "plan"

    assert await cb.call_with_capacity_retry(flaky, what="planning") == "plan"
    assert calls["n"] == 3
    assert sleeps == [cb.capacity_backoff_s(1), cb.capacity_backoff_s(2)]


async def test_retry_does_not_touch_non_capacity_errors(sleeps: list[float]) -> None:
    async def broken() -> str:
        raise ValueError("model returned invalid JSON")

    with pytest.raises(ValueError):
        await cb.call_with_capacity_retry(broken, what="planning")
    assert sleeps == []


async def test_retry_is_bounded(sleeps: list[float]) -> None:
    calls = {"n": 0}

    async def always_limited() -> str:
        calls["n"] += 1
        raise BrainFailoverExhausted("all candidates failed")

    with pytest.raises(BrainFailoverExhausted):
        await cb.call_with_capacity_retry(always_limited, what="planning")
    assert calls["n"] == cb.MAX_CAPACITY_RETRIES + 1
    assert len(sleeps) == cb.MAX_CAPACITY_RETRIES


def test_agent_loop_uses_capacity_backoff() -> None:
    """The loop must route both failure sites through the helper."""
    from pathlib import Path

    src = Path(cb.__file__).with_name("loop.py").read_text(encoding="utf-8")
    assert "call_with_capacity_retry(" in src, "planning must wait out a rate-limited brain"
    assert "retry_delay_s(" in src, "tool selection must not retry inside a provider cooldown"


def test_json_parse_failure_quoting_capacity_words_is_not_capacity() -> None:
    exc = ValueError(
        "Model did not return a JSON object after 4 attempts; last raw output "
        "(truncated to 200 chars): 'I hit a rate limit so I cannot answer'"
    )
    assert not cb.is_capacity_error(exc)


def test_no_provider_configured_is_not_capacity() -> None:
    exc = BrainFailoverExhausted("no providers configured — set at least one provider API key")
    assert not cb.is_capacity_error(exc)
    try:
        try:
            raise exc
        except BrainFailoverExhausted as inner:
            raise RuntimeError("planning: no providers configured") from inner
    except RuntimeError as outer:
        assert not cb.is_capacity_error(outer)


def test_nothing_attempted_is_capacity_only_when_a_provider_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exc = BrainFailoverExhausted("ignored")  # default text depends on arguments
    real = RuntimeError("All brain providers exhausted \u2014 none configured or all in cooldown.")
    monkeypatch.setattr(cb, "_no_provider_configured", lambda: True)
    assert not cb.is_capacity_error(real)
    monkeypatch.setattr(cb, "_no_provider_configured", lambda: False)
    assert cb.is_capacity_error(real)
    assert isinstance(exc, RuntimeError)


def test_no_provider_configured_reads_the_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    import services.brain_failover as bf

    monkeypatch.setattr(bf, "brain_availability_summary", lambda: {"total": 0})
    assert cb._no_provider_configured() is True
    monkeypatch.setattr(bf, "brain_availability_summary", lambda: {"total": 2, "usable": 0})
    assert cb._no_provider_configured() is False
