"""Tests for autonomous-loop bootstrap (services/background._start_autonomy_loops).

These engines (self-heal, log-monitor, improvement-loop, trend-watcher) existed
but were never started in production — their singletons stayed ``None`` so the
autonomous loops silently never ran. This guards that the bootstrap actually
wires them, is env-gated, and is idempotent.
"""
from __future__ import annotations

import asyncio
import contextlib

import pytest

import agent.self_healing as sh
import agent.log_monitor as lm
import agent.improvement_loop as il
import agent.trend_watcher as tw
import services.background as bg
from services.background import _start_autonomy_loops


class _FakeScheduler:
    def __init__(self):
        self.created = []

    def create(self, **kwargs):
        self.created.append(kwargs)
        return kwargs


@pytest.fixture(autouse=True)
def _reset_singletons_and_threads(monkeypatch):
    # Replace thread/handler-spawning entrypoints with no-ops so the test is fast
    # and leaves no global logging handler or background threads behind.
    monkeypatch.setattr(sh.SelfHealingAgent, "start", lambda self: None)
    monkeypatch.setattr(il.ImprovementLoop, "start", lambda self: None)
    monkeypatch.setattr(lm.LogMonitor, "attach", lambda self: None)
    # Reset all singletons + the trend-poller handle before and after.
    sh.set_self_healing_agent(None)  # type: ignore[arg-type]
    lm.set_log_monitor(None)  # type: ignore[arg-type]
    il.set_improvement_loop(None)  # type: ignore[arg-type]
    tw.set_trend_watcher(None)  # type: ignore[arg-type]
    bg._trend_watch_task = None
    bg._ephemeral_reaper_task = None
    yield
    sh.set_self_healing_agent(None)  # type: ignore[arg-type]
    lm.set_log_monitor(None)  # type: ignore[arg-type]
    il.set_improvement_loop(None)  # type: ignore[arg-type]
    tw.set_trend_watcher(None)  # type: ignore[arg-type]
    bg._trend_watch_task = None
    bg._ephemeral_reaper_task = None


def test_bootstrap_starts_all_loops_by_default(monkeypatch):
    for var in (
        "AGENCY_IMPROVEMENT_ENABLED", "AGENCY_SELF_HEAL_ENABLED",
        "AGENCY_LOG_MONITOR_ENABLED", "AGENCY_TREND_WATCH_ENABLED",
    ):
        monkeypatch.delenv(var, raising=False)  # default = on

    sched = _FakeScheduler()
    tasks = _start_autonomy_loops(sched)

    assert sh.get_self_healing_agent() is not None
    assert lm.get_log_monitor() is not None
    assert il.get_improvement_loop() is not None
    assert tw.get_trend_watcher() is not None
    # ImprovementLoop must be wired to the scheduler's create() (the self-heal sink)
    assert il.get_improvement_loop()._on_task == sched.create
    # No running event loop in this sync test → trend poller is skipped, not crashed
    assert tasks == []


def test_bootstrap_respects_env_gates(monkeypatch):
    monkeypatch.setenv("AGENCY_SELF_HEAL_ENABLED", "false")
    monkeypatch.setenv("AGENCY_LOG_MONITOR_ENABLED", "0")
    monkeypatch.setenv("AGENCY_IMPROVEMENT_ENABLED", "off")
    monkeypatch.setenv("AGENCY_TREND_WATCH_ENABLED", "no")

    _start_autonomy_loops(_FakeScheduler())

    assert sh.get_self_healing_agent() is None
    assert lm.get_log_monitor() is None
    assert il.get_improvement_loop() is None
    assert tw.get_trend_watcher() is None


def test_bootstrap_is_idempotent(monkeypatch):
    for var in (
        "AGENCY_IMPROVEMENT_ENABLED", "AGENCY_SELF_HEAL_ENABLED",
        "AGENCY_LOG_MONITOR_ENABLED", "AGENCY_TREND_WATCH_ENABLED",
    ):
        monkeypatch.delenv(var, raising=False)
    sched = _FakeScheduler()
    _start_autonomy_loops(sched)
    first_healer = sh.get_self_healing_agent()
    first_loop = il.get_improvement_loop()
    _start_autonomy_loops(sched)  # second call must not replace existing singletons
    assert sh.get_self_healing_agent() is first_healer
    assert il.get_improvement_loop() is first_loop


async def test_bootstrap_is_idempotent_with_running_loop(monkeypatch):
    """Under a running event loop, repeated bootstrap must not spawn duplicate
    poller tasks (a duplicate would double trend fetch + fan-out, or double the
    ephemeral-company reaper sweeps)."""
    for var in (
        "AGENCY_IMPROVEMENT_ENABLED", "AGENCY_SELF_HEAL_ENABLED",
        "AGENCY_LOG_MONITOR_ENABLED", "AGENCY_TREND_WATCH_ENABLED",
        "EPHEMERAL_COMPANY_REAPER_ENABLED",
    ):
        monkeypatch.delenv(var, raising=False)
    sched = _FakeScheduler()
    first = _start_autonomy_loops(sched)
    second = _start_autonomy_loops(sched)
    # Two daemon pollers are scheduled on first boot: the trend poller and the
    # ephemeral-company reaper.
    assert len(first) == 2
    assert second == []             # second call schedules none (idempotent)
    for t in first:
        t.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await t
