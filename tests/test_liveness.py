from __future__ import annotations

import os
import subprocess
import sys

from agent.liveness import check_liveness, pid_alive


def test_alive_needs_both_signals() -> None:
    v = check_liveness(os.getpid(), 990.0, 30.0, now=1000.0)
    assert v.alive and "alive" in v.reason


def test_stale_output_with_live_process_is_dead() -> None:
    v = check_liveness(os.getpid(), 100.0, 30.0, now=1000.0)
    assert not v.alive and v.reason.startswith("signal 2 FAIL")


def test_missing_output_is_dead() -> None:
    v = check_liveness(os.getpid(), None, 30.0, now=1000.0)
    assert not v.alive and "no output" in v.reason


def test_fresh_output_with_dead_process_is_dead() -> None:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    v = check_liveness(proc.pid, 999.0, 30.0, now=1000.0)
    assert not v.alive and v.reason.startswith("signal 1 FAIL")


def test_non_positive_pid_is_not_alive() -> None:
    assert not pid_alive(0) and not pid_alive(-5)


def test_nan_or_future_timestamp_is_dead() -> None:
    assert not check_liveness(os.getpid(), float("nan"), 30.0, now=1000.0).alive
    assert not check_liveness(os.getpid(), 2000.0, 30.0, now=1000.0).alive


def test_huge_pid_does_not_raise() -> None:
    assert not pid_alive(2**70)


def test_infinite_timestamp_is_dead_without_raising() -> None:
    for ts in (float("-inf"), float("inf")):
        v = check_liveness(os.getpid(), ts, 30.0, now=1000.0)
        assert not v.alive and v.reason.startswith("signal 2 FAIL")
