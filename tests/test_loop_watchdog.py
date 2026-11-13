"""The stall watchdog names the code that froze the event loop.

Production (2026-11-11 to 13) failed Render's 5-second health check about 50
times in 37 hours with memory and CPU far below their limits: something blocked
the event loop, and nothing recorded what. Each failure restarted the service
and killed the tasks running in it.
"""
from __future__ import annotations

import asyncio
import time

import pytest

from services import loop_watchdog as lw


def _blocking_call_under_test(seconds: float) -> None:
    time.sleep(seconds)  # deliberate: the defect the watchdog exists to catch


async def test_a_blocked_loop_is_reported_with_the_blocking_frame() -> None:
    watchdog = lw.LoopStallWatchdog(asyncio.get_running_loop(), threshold_s=0.1, interval_s=0.02)
    watchdog.start()
    try:
        await asyncio.sleep(0.05)
        _blocking_call_under_test(0.5)
        await asyncio.sleep(0.2)
    finally:
        watchdog.stop()
    reports = watchdog.recent()
    assert reports, "a 0.5s block over a 0.1s threshold must be reported"
    assert "_blocking_call_under_test" in reports[0].stack
    assert reports[0].blocked_s >= 0.1


async def test_a_responsive_loop_is_not_reported() -> None:
    watchdog = lw.LoopStallWatchdog(asyncio.get_running_loop(), threshold_s=0.3, interval_s=0.02)
    watchdog.start()
    try:
        for _ in range(10):
            await asyncio.sleep(0.02)
    finally:
        watchdog.stop()
    assert watchdog.recent() == []


async def test_reports_are_bounded() -> None:
    watchdog = lw.LoopStallWatchdog(
        asyncio.get_running_loop(), threshold_s=0.02, interval_s=0.005, max_reports=2,
    )
    watchdog.start()
    try:
        for _ in range(4):
            await asyncio.sleep(0.02)
            _blocking_call_under_test(0.08)
        await asyncio.sleep(0.05)
    finally:
        watchdog.stop()
    assert 1 <= len(watchdog.recent()) <= 2


async def test_stall_is_logged_as_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    watchdog = lw.LoopStallWatchdog(asyncio.get_running_loop(), threshold_s=0.05, interval_s=0.01)
    watchdog.start()
    try:
        with caplog.at_level("WARNING", logger="qwen-proxy"):
            await asyncio.sleep(0.03)
            _blocking_call_under_test(0.3)
            await asyncio.sleep(0.15)
    finally:
        watchdog.stop()
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "event loop blocked" in text
    assert "_blocking_call_under_test" in text


async def test_start_is_idempotent_and_stop_ends_the_thread() -> None:
    watchdog = lw.LoopStallWatchdog(asyncio.get_running_loop(), threshold_s=0.2, interval_s=0.01)
    watchdog.start()
    first = watchdog._thread
    watchdog.start()
    assert watchdog._thread is first
    watchdog.stop()
    assert first is not None and not first.is_alive()


async def test_module_level_start_returns_one_shared_watchdog() -> None:
    lw.stop_loop_watchdog()
    a = lw.start_loop_watchdog()
    b = lw.start_loop_watchdog()
    try:
        assert a is b
    finally:
        lw.stop_loop_watchdog()


def test_server_and_worker_start_the_watchdog() -> None:
    from pathlib import Path

    root = Path(lw.__file__).parents[1]
    assert "start_loop_watchdog()" in root.joinpath("backend", "server.py").read_text(encoding="utf-8")
    assert "start_loop_watchdog()" in root.joinpath("worker_main.py").read_text(encoding="utf-8")
