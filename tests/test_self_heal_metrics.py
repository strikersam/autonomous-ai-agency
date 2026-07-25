"""tests/test_self_heal_metrics.py — contract test for GET /api/metrics/self-heal.

The self-heal chain (agent/log_monitor.py -> agent/self_healing.py ->
agent/improvement_loop.py) runs continuously but previously had no API surface
beyond a boolean "running" flag in /api/autonomy/status. This endpoint feeds
the Dashboard's Self-Healing widget with real activity: capture counters and
recent healing events. It must never raise when the engines are not
bootstrapped (e.g. under a bare TestClient with no lifespan startup).
"""
from __future__ import annotations

import asyncio


def test_self_heal_stats_degrades_gracefully_when_engines_absent():
    from agent.log_monitor import get_log_monitor, set_log_monitor
    from agent.self_healing import get_self_healing_agent, set_self_healing_agent
    from backend.server import self_heal_stats

    prev_monitor, prev_healer = get_log_monitor(), get_self_healing_agent()
    set_log_monitor(None)
    set_self_healing_agent(None)
    try:
        body = asyncio.run(self_heal_stats(user={"sub": "test"}))

        assert body["log_monitor"] == {"attached": False, "tasks_created": 0, "active_cooldowns": 0}
        assert body["events"] == []
        assert body["active_count"] == 0
        assert body["resolved_count"] == 0
        assert body["awaiting_human_count"] == 0
    finally:
        set_log_monitor(prev_monitor)
        set_self_healing_agent(prev_healer)


def test_self_heal_stats_reports_engine_state_and_events():
    from agent.log_monitor import LogMonitor, get_log_monitor, set_log_monitor
    from agent.self_healing import SelfHealingAgent, get_self_healing_agent, set_self_healing_agent
    from backend.server import self_heal_stats

    prev_monitor, prev_healer = get_log_monitor(), get_self_healing_agent()
    monitor = LogMonitor()
    healer = SelfHealingAgent()
    set_log_monitor(monitor)
    set_self_healing_agent(healer)
    try:
        event = asyncio.run(healer.on_manual_report("Backend ERROR: boom", "trace...", severity="high"))
        healer.mark_fix_landed(event.signature)

        body = asyncio.run(self_heal_stats(user={"sub": "test"}))

        assert body["log_monitor"]["attached"] is False  # attach() not called in this test
        assert len(body["events"]) == 1
        event = body["events"][0]
        assert event["title"] == "Backend ERROR: boom"
        assert event["state"] == "verifying"
        assert body["active_count"] == 1
        assert body["resolved_count"] == 0
    finally:
        set_log_monitor(prev_monitor)
        set_self_healing_agent(prev_healer)


def test_self_heal_stats_sorts_events_newest_first():
    from agent.self_healing import SelfHealingAgent, get_self_healing_agent, set_self_healing_agent
    from backend.server import self_heal_stats

    prev_healer = get_self_healing_agent()
    healer = SelfHealingAgent()
    set_self_healing_agent(healer)
    try:
        first = asyncio.run(healer.on_manual_report("First", "d1", severity="low"))
        second = asyncio.run(healer.on_manual_report("Second", "d2", severity="low"))
        # Force distinct timestamps — both calls can land in the same wall-clock
        # second at _now()'s 1s resolution, which would make the sort order
        # depend on stability rather than the intended "newest first".
        first.created_at = "2026-07-24T10:00:00Z"
        second.created_at = "2026-07-24T10:00:01Z"

        body = asyncio.run(self_heal_stats(user={"sub": "test"}))

        titles = [e["title"] for e in body["events"]]
        assert titles == ["Second", "First"]
    finally:
        set_self_healing_agent(prev_healer)
