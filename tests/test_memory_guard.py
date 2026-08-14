"""tests/test_memory_guard.py — the RSS guard must be safe and total.

The guard exists to protect a memory-constrained process, so its own failure
modes matter more than its happy path: it must never raise, must degrade when
``malloc_trim`` is unavailable (non-glibc), and must honour its enable flag.
"""
from __future__ import annotations

import asyncio

import pytest

from services import memory_guard


def test_enabled_by_default(monkeypatch):
    monkeypatch.delenv("MEMORY_GUARD_ENABLED", raising=False)
    assert memory_guard.memory_guard_enabled() is True


@pytest.mark.parametrize("value,expected", [
    ("false", False), ("0", False), ("no", False), ("off", False),
    ("true", True), ("1", True), ("yes", True),
])
def test_enable_flag_parsing(monkeypatch, value, expected):
    monkeypatch.setenv("MEMORY_GUARD_ENABLED", value)
    assert memory_guard.memory_guard_enabled() is expected


def test_trim_now_returns_int_and_never_raises():
    # On glibc this actually trims; elsewhere it just does the gc sweep. Either
    # way it must return an int and not raise.
    result = memory_guard.trim_now()
    assert isinstance(result, int)


def test_trim_now_survives_a_broken_trim():
    # A malloc_trim that raises must be swallowed, not propagated.
    def _boom(_n: int) -> int:
        raise RuntimeError("simulated libc failure")

    assert memory_guard.trim_now(trim=_boom) >= 0


@pytest.mark.parametrize("raw,expected_floor", [
    ("0", True), ("-5", True), ("1", True), ("10", True),  # too-small → floored
    ("not-an-int", True), ("", True),                       # invalid → default then floored
])
def test_interval_is_floored_never_busy_loops(monkeypatch, raw, expected_floor):
    # A 0/negative/invalid interval must never yield a sub-minimum sleep, which
    # would turn the guard into a CPU-burning busy-wait.
    monkeypatch.setenv("MEMORY_GUARD_INTERVAL_SEC", raw)
    assert memory_guard._resolve_interval_sec() >= memory_guard._MIN_INTERVAL_SEC


def test_interval_honours_a_valid_large_value(monkeypatch):
    monkeypatch.setenv("MEMORY_GUARD_INTERVAL_SEC", "600")
    assert memory_guard._resolve_interval_sec() == 600


def test_load_malloc_trim_is_callable_or_none():
    trim = memory_guard._load_malloc_trim()
    assert trim is None or callable(trim)


@pytest.mark.asyncio
async def test_loop_cancels_cleanly(monkeypatch):
    # Make the interval tiny so the loop parks on sleep immediately, then cancel.
    monkeypatch.setattr(memory_guard, "_INTERVAL_SEC", 0)
    task = asyncio.create_task(memory_guard.memory_guard_loop())
    await asyncio.sleep(0)  # let it start and hit the first await
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
