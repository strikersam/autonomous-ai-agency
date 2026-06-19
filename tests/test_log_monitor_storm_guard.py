"""Tests for the LogMonitor self-heal storm guard.

A system that is already erroring (slow brain timing out, provider outage) must
not let the log-driven self-heal loop create a flood of fix tasks that saturate
the dispatcher and make everything slower. Two defences:
  - operational/transient errors are skipped (not auto-fixable code bugs),
  - a global hourly cap bounds total auto-created fix tasks.
"""
from __future__ import annotations

import agent.log_monitor as lm


def _fresh_monitor():
    # A bare LogMonitor (not attached); _on_log_error increments _task_count only
    # when it would actually dispatch a fix task. No healer is set, so dispatch
    # short-circuits — we assert on _task_count.
    return lm.LogMonitor()


def test_operational_errors_are_skipped():
    m = _fresh_monitor()
    for msg in (
        "Task task_abc Execution timed out after 150s",
        "Runtime '*' unavailable: All runtimes failed and policy prevents paid escalation",
        "blocked after 10 failed dispatch attempts",
        "No module named brain_policy",
        "HTTP 503 Service Unavailable from provider",
        "httpx.ReadTimeout: read timeout",
    ):
        m._on_log_error("agency.orchestrator", "ERROR", msg)
    assert m._task_count == 0  # none of these are auto-fixable code bugs


def test_real_code_error_creates_a_task():
    m = _fresh_monitor()
    m._on_log_error("agency.orchestrator", "ERROR",
                    "AttributeError: 'NoneType' object has no attribute 'plan'")
    assert m._task_count == 1


def test_hourly_cap_suppresses_storm(monkeypatch):
    monkeypatch.setattr(lm, "MAX_TASKS_PER_HOUR", 3)
    m = _fresh_monitor()
    # 10 DISTINCT real errors (distinct signatures bypass the per-sig cooldown)
    for i in range(10):
        m._on_log_error("agency.orchestrator", "ERROR", f"ValueError: bad value number {i}")
    assert m._task_count == 3  # capped


def test_cap_zero_disables_cap(monkeypatch):
    monkeypatch.setattr(lm, "MAX_TASKS_PER_HOUR", 0)
    m = _fresh_monitor()
    for i in range(7):
        m._on_log_error("agency.orchestrator", "ERROR", f"KeyError: missing key {i}")
    assert m._task_count == 7  # uncapped
