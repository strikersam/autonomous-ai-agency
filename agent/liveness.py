"""Two-signal liveness: a job is alive only when its process exists AND its output is fresh.

A live process can be wedged and a fresh output file can be residue from a previous run,
so either signal alone misreports. Pure helpers: callers pass the pid and the timestamp of
the last output/heartbeat, so this module does no file I/O and reads no environment.
"""

from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class Liveness:
    """Verdict of ``check_liveness``: ``alive`` plus the failing signal in ``reason``."""

    alive: bool
    reason: str


def pid_alive(pid: int) -> bool:
    """True when ``pid`` names an existing process (signal 0 sends nothing)."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True  # the process exists but belongs to another user
    except (OSError, OverflowError):
        return False  # no such process, or a pid the OS rejects
    return True


def check_liveness(
    pid: int,
    last_output_at: float | None,
    max_age_s: float,
    now: float | None = None,
) -> Liveness:
    """Return ``Liveness`` for a job; ``last_output_at`` is epoch seconds, None if never."""
    now = time.time() if now is None else now
    if not pid_alive(pid):
        return Liveness(False, f"signal 1 FAIL: pid {pid} is not alive")
    if last_output_at is None:
        return Liveness(False, "signal 2 FAIL: no output recorded")
    age = now - last_output_at
    if not math.isfinite(age) or age < 0:  # NaN, infinite or future timestamp: not trustworthy
        return Liveness(False, "signal 2 FAIL: output timestamp is invalid or in the future")
    if age > max_age_s:
        return Liveness(False, f"signal 2 FAIL: output is {int(age)}s old (max {int(max_age_s)}s)")
    return Liveness(True, f"alive: pid {pid} running, output {int(age)}s old")
