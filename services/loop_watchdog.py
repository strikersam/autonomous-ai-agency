"""Name the code that froze the event loop.

Everything in the web process shares one event loop: requests, the health
check, background loops and agent tasks. One blocking call (a synchronous
database or network read, a large file copy) stops all of them. Render's health
check then times out after 5 seconds and the platform restarts the service,
killing whatever was running. That happened about 50 times in 37 hours with
memory and CPU well under their limits, and no log said what was blocking.

A daemon thread asks the loop to answer a no-op. When it has not answered within
the threshold, the thread logs the loop thread's current stack: the exact call
that is blocking. It cannot unblock the loop; it makes the next fix a matter of
reading one log line instead of guessing.
"""
from __future__ import annotations

import asyncio
import logging
import sys
import threading
import time
import traceback
from dataclasses import dataclass

log = logging.getLogger("qwen-proxy")

# Render kills the instance at 5s, so the report has to land well before that.
DEFAULT_THRESHOLD_S: float = 2.0
DEFAULT_INTERVAL_S: float = 0.5
_STACK_DEPTH: int = 25
_MAX_REPORTS: int = 20


@dataclass(frozen=True)
class StallReport:
    """One observed stall: when, for how long so far, and where the loop was."""

    at: float
    blocked_s: float
    stack: str


class LoopStallWatchdog:
    """Watch *loop* from another thread and report when it stops answering."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        *,
        threshold_s: float = DEFAULT_THRESHOLD_S,
        interval_s: float = DEFAULT_INTERVAL_S,
        max_reports: int = _MAX_REPORTS,
    ) -> None:
        self._loop = loop
        self._threshold_s = threshold_s
        self._interval_s = interval_s
        self._max_reports = max_reports
        self._loop_thread_id: int | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._reports: list[StallReport] = []
        self._lock = threading.Lock()

    def start(self) -> None:
        """Begin watching. Must be called from the loop's own thread. Idempotent."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._loop_thread_id = threading.get_ident()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="loop-stall-watchdog", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop watching and wait briefly for the thread to end."""
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=self._threshold_s + self._interval_s + 1.0)

    def recent(self) -> list[StallReport]:
        """The most recent stall reports, oldest first."""
        with self._lock:
            return list(self._reports)

    def _run(self) -> None:
        while not self._stop.is_set():
            answered = threading.Event()
            try:
                self._loop.call_soon_threadsafe(answered.set)
            except RuntimeError:
                return  # loop closed: nothing left to watch
            started = time.monotonic()
            if not answered.wait(self._threshold_s) and not self._stop.is_set():
                self._report(time.monotonic() - started)
                self._await_recovery(answered, started)
            self._stop.wait(self._interval_s)

    def _await_recovery(self, answered: threading.Event, started: float) -> None:
        """Wait for the loop to answer again, then log how long it was gone."""
        while not self._stop.is_set() and not answered.wait(self._interval_s):
            pass
        if not self._stop.is_set():
            log.warning("event loop responsive again after %.1fs", time.monotonic() - started)

    def _loop_stack(self) -> str:
        frame = sys._current_frames().get(self._loop_thread_id or -1)
        if frame is None:
            return "<loop thread stack unavailable>"
        return "".join(traceback.format_stack(frame, limit=_STACK_DEPTH))

    def _report(self, blocked_s: float) -> None:
        stack = self._loop_stack()
        with self._lock:
            self._reports.append(StallReport(at=time.time(), blocked_s=blocked_s, stack=stack))
            del self._reports[: -self._max_reports]
        log.warning(
            "event loop blocked for more than %.1fs; the loop thread is in:\n%s",
            blocked_s, stack,
        )


_watchdog: LoopStallWatchdog | None = None


def start_loop_watchdog() -> LoopStallWatchdog:
    """Start (once) the watchdog for the running loop. Call from a coroutine."""
    global _watchdog
    if _watchdog is None:
        _watchdog = LoopStallWatchdog(asyncio.get_running_loop())
    _watchdog.start()
    return _watchdog


def stop_loop_watchdog() -> None:
    """Stop and forget the shared watchdog."""
    global _watchdog
    if _watchdog is not None:
        _watchdog.stop()
        _watchdog = None
