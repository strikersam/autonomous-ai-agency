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


async def test_a_failing_report_does_not_end_the_watch(monkeypatch: pytest.MonkeyPatch) -> None:
    watchdog = lw.LoopStallWatchdog(asyncio.get_running_loop(), threshold_s=0.05, interval_s=0.01)

    def boom(blocked_s: float) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(watchdog, "_report", boom)
    watchdog.start()
    try:
        await asyncio.sleep(0.02)
        _blocking_call_under_test(0.2)
        await asyncio.sleep(0.1)
        assert watchdog._thread is not None and watchdog._thread.is_alive()
    finally:
        watchdog.stop()


# ── The stack names the application frame, even under a deep library call ─────

import traceback  # noqa: E402


def _frame(path: str, line: int, name: str) -> traceback.FrameSummary:
    return traceback.FrameSummary(path, line, name, line="call()")


_LIB = "/usr/local/lib/python3.13/site-packages/pymongo/pool.py"


def test_the_application_frame_survives_a_deep_library_stack() -> None:
    """The 2026-11-14 stall: 40 pymongo frames above one application frame."""
    frames = [_frame("/app/services/ceo_ledger.py", 329, "_init_mongo")]
    frames += [_frame(_LIB, i, f"lib_{i}") for i in range(40)]
    text = lw.format_loop_stack(traceback.StackSummary.from_list(frames))
    assert text.splitlines()[0] == (
        "innermost application frame: /app/services/ceo_ledger.py:329 in _init_mongo")
    outer_marker, inner_marker = "(outer application frames;", "(innermost frames)"
    assert outer_marker in text and inner_marker in text, "both sections must be present"
    outer_section = text.split(outer_marker, 1)[1].split(inner_marker, 1)[0]
    assert "ceo_ledger.py" in outer_section, "the outer app frame must be kept in its own section"
    assert "lib_39" in text, "the innermost library frames are still shown"


def test_the_innermost_application_frame_is_the_deepest_one() -> None:
    frames = [
        _frame("/app/a.py", 1, "outer"),
        _frame("/app/b.py", 2, "inner"),
        _frame(_LIB, 3, "lib"),
    ]
    text = lw.format_loop_stack(traceback.StackSummary.from_list(frames))
    assert text.splitlines()[0].endswith("/app/b.py:2 in inner")


def test_a_shallow_stack_is_not_annotated_with_omissions() -> None:
    frames = [_frame("/app/a.py", 1, "f"), _frame(_LIB, 2, "g")]
    text = lw.format_loop_stack(traceback.StackSummary.from_list(frames))
    assert "omitted" not in text and "(innermost frames)" not in text


def test_a_stack_with_no_application_frame_still_formats() -> None:
    frames = [_frame("/usr/local/lib/python3.13/asyncio/runners.py", 1, "run")]
    text = lw.format_loop_stack(traceback.StackSummary.from_list(frames))
    assert "innermost application frame" not in text
    assert "runners.py" in text


async def test_a_real_stall_report_leads_with_the_application_frame() -> None:
    watchdog = lw.LoopStallWatchdog(asyncio.get_running_loop(), threshold_s=0.1, interval_s=0.02)
    watchdog.start()
    try:
        await asyncio.sleep(0.05)
        _blocking_call_under_test(0.5)
        await asyncio.sleep(0.2)
    finally:
        watchdog.stop()
    reports = watchdog.recent()
    assert reports
    assert reports[0].stack.splitlines()[0].startswith("innermost application frame:")
    assert "_blocking_call_under_test" in reports[0].stack.splitlines()[0]


# ── Other threads are listed, and console-script shims are not "application" ──

def test_a_console_script_shim_is_not_an_application_frame() -> None:
    frames = [_frame("/usr/local/bin/uvicorn", 6, "<module>"),
              _frame("/usr/local/lib/python3.13/site-packages/uvicorn/main.py", 448, "main")]
    text = lw.format_loop_stack(traceback.StackSummary.from_list(frames))
    assert "innermost application frame" not in text


def test_other_threads_are_listed_with_their_application_frame() -> None:
    stacks = {
        1: traceback.StackSummary.from_list([_frame("/app/main.py", 1, "main")]),
        2: traceback.StackSummary.from_list([
            _frame("/app/agent/improvement_loop.py", 88, "_scan"), _frame(_LIB, 3, "read")]),
    }
    text = lw.format_other_threads(stacks, skip={1})
    assert "other threads:" in text
    assert "/app/agent/improvement_loop.py:88 in _scan (innermost: read)" in text
    assert "/app/main.py" not in text, "the skipped (loop) thread is not repeated"


def test_no_other_threads_adds_nothing_and_the_count_is_capped() -> None:
    assert lw.format_other_threads({1: traceback.StackSummary.from_list([_frame("/app/a.py", 1, "f")])}, {1}) == ""
    many = {i: traceback.StackSummary.from_list([_frame("/app/a.py", i, "f")]) for i in range(40)}
    text = lw.format_other_threads(many, skip=set())
    assert text.count("  thread ") == lw._OTHER_THREADS_SHOWN and "more threads" in text
