"""Recurring operational failures must diagnose and file themselves.

The gap these tests pin: for an entire debugging session the platform produced
`Execution timed out after 600s` and `blocked after 5 failed dispatch attempts`
every few minutes for hours, and *nothing inside the system reacted*. Those
strings match `agent/log_monitor.py::_OPERATIONAL_PATTERNS`, so the handler
returned before doing anything, and a human had to read the dashboard and paste
logs by hand.

Two independent defects had to hold for that to happen, and both are pinned
below: the operational branch dropped the record entirely, and signatures were
built from the raw message — so every distinct `task_<hex>` hashed differently
and no repetition was ever visible even in principle.
"""
from __future__ import annotations

import asyncio
import logging

import pytest

from agent import operational_incidents as ops
from agent.operational_incidents import (
    OperationalIncidentTracker,
    normalise,
    signature_for,
    summarise_phases,
)

# Verbatim from the production task-error dashboard.
TIMEOUT_A = "Task task_c7022c0bd20258b3 Execution timed out after 600s"
TIMEOUT_B = "Task task_e2d70c78bf8c35b2 Execution timed out after 600s"
TIMEOUT_C = "Task task_66a1069f228a64d7 Execution timed out after 600s"
TIMEOUT_D = "Task task_4579077ef6659ea0 Execution timed out after 600s"
BLOCKED = (
    "Task task_39a904debc750344 blocked after 5 failed dispatch attempts "
    "(No runtime available): Runtime '*' unavailable: All runtimes failed and "
    "policy prevents paid escalation."
)


@pytest.fixture
def tracker(monkeypatch) -> OperationalIncidentTracker:
    """A tracker whose filing step is captured instead of hitting the network."""
    monkeypatch.setattr(ops, "INCIDENT_THRESHOLD", 3)
    monkeypatch.setattr(ops, "WINDOW_SECONDS", 1800)
    monkeypatch.setattr(ops, "COOLDOWN_SECONDS", 21600)
    monkeypatch.setattr(ops, "MAX_INCIDENTS_PER_HOUR", 3)
    return OperationalIncidentTracker()


@pytest.fixture
def filed(monkeypatch) -> list[ops.OperationalIncident]:
    """Capture incidents at the point they would be diagnosed and filed."""
    captured: list[ops.OperationalIncident] = []

    async def _capture(incident: ops.OperationalIncident) -> None:
        captured.append(incident)

    monkeypatch.setattr(ops, "_diagnose_and_file", _capture)
    # Run the scheduled coroutine inline so the assertion does not race it.
    monkeypatch.setattr(ops, "_schedule", lambda coro: asyncio.run(coro))
    return captured


# ── signature normalisation ──────────────────────────────────────────────────


def test_the_same_failure_on_different_tasks_shares_one_signature():
    """The defect that made the threshold unreachable.

    `agent/log_monitor.py::_sig` keys on `message[:120]` verbatim, so these two
    lines — the same failure mode on two different tasks — hash differently and
    each looks like a first occurrence forever. No amount of repetition would
    ever accumulate into a pattern.
    """
    assert signature_for("qwen-agent", TIMEOUT_A) == signature_for("qwen-agent", TIMEOUT_B)


def test_normalisation_collapses_ids_and_numbers_but_keeps_the_failure_mode():
    assert normalise(TIMEOUT_A) == "Task task_<id> Execution timed out after <n>s"


def test_genuinely_different_failures_keep_different_signatures():
    """Normalisation must not over-collapse — a timeout and a dispatch failure
    are different problems and must not share an incident."""
    assert signature_for("qwen-agent", TIMEOUT_A) != signature_for("qwen-agent", BLOCKED)


def test_the_same_message_from_different_loggers_is_a_different_signature():
    assert signature_for("qwen-agent", TIMEOUT_A) != signature_for("tasks", TIMEOUT_A)


# ── threshold behaviour ──────────────────────────────────────────────────────


def test_a_single_occurrence_files_nothing(tracker, filed):
    """One timeout is a bad minute, not an incident. Filing here is exactly the
    storm the log-monitor filter exists to prevent."""
    assert tracker.record("qwen-agent", TIMEOUT_A) is False
    assert filed == []


def test_recurrence_past_the_threshold_files_one_incident(tracker, filed):
    """The reported scenario, end to end: four real timeouts, one incident."""
    results = [
        tracker.record("qwen-agent", msg)
        for msg in (TIMEOUT_A, TIMEOUT_B, TIMEOUT_C, TIMEOUT_D)
    ]

    assert results == [False, False, True, False], (
        "should file exactly once, on crossing the threshold — not before, and "
        "not again on every later occurrence"
    )
    assert len(filed) == 1
    incident = filed[0]
    assert incident.count == 3
    assert "timed out" in incident.normalised
    # The sample carries the occurrence that crossed the threshold — the
    # freshest example of the failure, not the stalest.
    assert incident.sample == TIMEOUT_C


def test_occurrences_outside_the_window_do_not_count(tracker, filed, monkeypatch):
    """Two timeouts an hour apart are not a pattern."""
    monkeypatch.setattr(ops, "WINDOW_SECONDS", 60)
    clock = {"now": 1000.0}
    # Patch the module's own `_now` indirection rather than `time.monotonic`:
    # the latter is the shared standard-library module object, and freezing it
    # would leak the frozen clock into every other thread in the process.
    monkeypatch.setattr(ops, "_now", lambda: clock["now"])

    tracker.record("qwen-agent", TIMEOUT_A)
    tracker.record("qwen-agent", TIMEOUT_B)
    clock["now"] += 3600.0  # both fall out of the window
    assert tracker.record("qwen-agent", TIMEOUT_C) is False
    assert filed == []


def test_cooldown_suppresses_a_second_filing_for_the_same_signature(tracker, filed):
    for msg in (TIMEOUT_A, TIMEOUT_B, TIMEOUT_C):
        tracker.record("qwen-agent", msg)
    assert len(filed) == 1

    for msg in (TIMEOUT_A, TIMEOUT_B, TIMEOUT_C, TIMEOUT_D):
        tracker.record("qwen-agent", msg)
    assert len(filed) == 1, "same failure inside the cooldown must not re-file"


def test_the_hourly_cap_bounds_a_multi_failure_storm(tracker, filed, monkeypatch):
    """Even many *distinct* failure modes cannot produce unbounded incidents.

    The modes are worded differently rather than numbered: digits normalise to
    `<n>`, so `mode 1` and `mode 2` would collapse into one signature and this
    would silently stop testing the cap at all.
    """
    monkeypatch.setattr(ops, "MAX_INCIDENTS_PER_HOUR", 2)

    for mode in ("connection refused", "rate limited", "bad gateway",
                 "read timeout", "service unavailable"):
        for _ in range(3):
            tracker.record("qwen-agent", f"Upstream failure: {mode}")

    assert len(filed) == 2, "the hourly cap is a hard ceiling across signatures"


def test_record_never_raises_into_the_logging_path(tracker, monkeypatch):
    """`record` runs inside a logging.Handler — it must swallow everything."""
    def _boom(*_args, **_kwargs):
        raise RuntimeError("signature failure")

    monkeypatch.setattr(ops, "signature_for", _boom)
    assert tracker.record("qwen-agent", TIMEOUT_A) is False


# ── phase-marker analysis ────────────────────────────────────────────────────


def test_an_unfinished_phase_is_identified_as_the_stuck_call():
    """`_timed_phase` (#1218) brackets each call; a start with no end is the hang."""
    messages = [
        "phase_start planning session_id='s1'",
        "phase_end planning session_id='s1' elapsed_s=2.0",
        "phase_start execute_step step_id=1",
        "phase_start tool_dispatch step_id=1 tool='fetch_url'",
        # no phase_end for tool_dispatch — this is the stall
    ]
    summary = summarise_phases(messages)

    assert summary["likely_stuck_phase"] == "tool_dispatch"
    assert summary["unfinished"] == {"execute_step": 1, "tool_dispatch": 1}
    assert "planning" not in summary["unfinished"]


def test_the_innermost_unfinished_phase_wins_not_the_outer_wrapper():
    """Phases nest, so a stuck inner call leaves its wrapper unfinished too.

    Ranking by occurrence count ties at 1 and names `execute_step` — the
    symptom. The stall is the innermost phase, which is the one that started
    last.
    """
    messages = [
        "phase_start execute_step step_id=1",
        "phase_start tool_selection step_id=1 remaining=15",
        "phase_end tool_selection step_id=1 remaining=15 elapsed_s=3.0",
        "phase_start tool_dispatch step_id=1 tool='fetch_url'",
    ]
    summary = summarise_phases(messages)

    assert summary["unfinished"] == {"execute_step": 1, "tool_dispatch": 1}
    assert summary["likely_stuck_phase"] == "tool_dispatch"


def test_balanced_phases_report_no_stuck_call():
    messages = [
        "phase_start planning session_id='s1'",
        "phase_end planning session_id='s1' elapsed_s=1.0",
    ]
    assert summarise_phases(messages)["likely_stuck_phase"] is None


def test_phase_summary_tolerates_unrelated_log_lines():
    assert summarise_phases(["HTTP Request: GET /health 200", ""])["unfinished"] == {}


# ── evidence gathering degrades instead of failing ───────────────────────────


def test_evidence_reports_unavailable_when_render_is_not_configured(monkeypatch):
    """No RENDER_API_KEY must still file the incident — the recurrence itself is
    the finding; the Render window is an enrichment."""
    from packages.config import settings

    monkeypatch.setattr(
        type(settings), "is_render_mcp_configured", property(lambda _self: False)
    )
    evidence = asyncio.run(ops.gather_render_evidence())

    assert evidence["available"] is False
    assert "not configured" in evidence["reason"]


def test_incident_body_names_the_stuck_phase_when_evidence_has_one():
    incident = ops.OperationalIncident(
        signature="abc123",
        logger_name="qwen-agent",
        normalised="Task task_<id> Execution timed out after <n>s",
        sample=TIMEOUT_A,
        count=4,
        window_seconds=1800,
        first_seen="2026-08-04T15:00:00+00:00",
        last_seen="2026-08-04T15:25:00+00:00",
        evidence={
            "available": True,
            "line_count": 42,
            "window_minutes": 20,
            "excerpt": "phase_start tool_dispatch tool='fetch_url'",
            "phases": {
                "started": {"tool_dispatch": 3},
                "finished": {"tool_dispatch": 1},
                "unfinished": {"tool_dispatch": 2},
                "likely_stuck_phase": "tool_dispatch",
            },
        },
    )
    body = ops._format_incident(incident)

    # Render's marker-counting view is a cross-check, reported as such.
    assert "Render logs additionally show `tool_dispatch`" in body
    assert "recurred **4 times**" in body
    assert "Render logs" in body


# ── in-process phase tracking (needs no Render, no sidecar, no API key) ──────


@pytest.fixture(autouse=True)
def _clean_phases():
    """Phase state is module-global — keep tests from leaking into each other."""
    ops.reset_phase_tracking()
    yield
    ops.reset_phase_tracking()


def test_an_open_phase_is_reported_as_the_stall_with_its_real_duration():
    """Tracked as it happens, so the duration is measured rather than inferred."""
    ops.note_phase_start("tool_dispatch", "tool='fetch_url'")
    report = ops.open_phase_report()

    assert report["likely_stuck_phase"] == "tool_dispatch"
    assert report["stuck_for_s"] is not None
    assert report["open"][0]["context"] == "tool='fetch_url'"


def test_a_phase_that_completed_is_no_longer_reported():
    ops.note_phase_start("planning", "s1")
    ops.note_phase_end("planning", "s1")

    report = ops.open_phase_report()
    assert report["likely_stuck_phase"] is None
    assert report["open"] == []


def test_the_innermost_open_phase_is_named_not_its_wrapper():
    """`execute_step` wraps `tool_dispatch`; a stuck inner call leaves both open,
    and the inner one is the cause."""
    ops.note_phase_start("execute_step", "step_id=1")
    ops.note_phase_start("tool_dispatch", "tool='fetch_url'")

    assert ops.open_phase_report()["likely_stuck_phase"] == "tool_dispatch"


def test_open_phase_tracking_is_bounded(monkeypatch):
    """A missed end marker must not let the map grow without limit."""
    monkeypatch.setattr(ops, "_MAX_OPEN_PHASES", 5)
    for n in range(50):
        ops.note_phase_start("leaky", f"ctx={n}")

    assert len(ops.open_phase_report()["open"]) <= 5


def test_phase_helpers_never_raise_into_the_agent_loop(monkeypatch):
    """They are called from inside the run loop; a failure must not break it."""
    monkeypatch.setattr(ops, "_now", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    ops.note_phase_start("planning", "s1")  # must not raise
    ops.note_phase_end("planning", "s1")


def test_the_agent_loops_timed_phase_feeds_the_tracker():
    """End-to-end through the real `_timed_phase`, which is what production runs."""
    from agent.loop import _timed_phase

    seen: dict = {}

    async def _run():
        async with _timed_phase("tool_dispatch", tool="fetch_url"):
            seen.update(ops.open_phase_report())

    asyncio.run(_run())

    assert seen["likely_stuck_phase"] == "tool_dispatch", (
        "a phase in flight must be visible to the incident tracker"
    )
    assert ops.open_phase_report()["likely_stuck_phase"] is None, (
        "and must be cleared once the phase completes"
    )


def test_the_incident_body_leads_with_the_in_process_phase():
    """The in-process view is authoritative — it needs no external service."""
    incident = ops.OperationalIncident(
        signature="abc", logger_name="qwen-agent", normalised="x", sample="x",
        count=4, window_seconds=1800, first_seen="t0", last_seen="t1",
        evidence={
            "phases_in_process": {
                "open": [{"phase": "tool_dispatch", "context": "tool='fetch_url'",
                          "open_for_s": 412.0}],
                "likely_stuck_phase": "tool_dispatch",
                "stuck_for_s": 412.0,
            },
            "available": False,
            "reason": "log fetch failed: connection refused",
        },
    )
    body = ops._format_incident(incident)

    assert "Stuck phase: `tool_dispatch`" in body
    assert "412.0s" in body
    # And the unreachable-Render case must point at the likely cause.
    assert "agency-render-mcp" in body
    assert "render_ops.py" in body


def test_incident_body_says_so_when_render_evidence_is_missing():
    incident = ops.OperationalIncident(
        signature="abc123", logger_name="qwen-agent", normalised="x", sample="x",
        count=4, window_seconds=1800, first_seen="t0", last_seen="t1",
        evidence={"available": False, "reason": "RENDER_API_KEY not configured"},
    )
    body = ops._format_incident(incident)

    assert "Render platform logs unavailable" in body
    assert "RENDER_API_KEY not configured" in body


# ── wiring: the log monitor must route operational errors here ───────────────


def test_log_monitor_routes_operational_errors_to_the_tracker(monkeypatch):
    """The regression that let this whole class of failure go unnoticed.

    The operational branch must still create no fix task, but it must no longer
    drop the record on the floor.
    """
    from agent.log_monitor import LogMonitor

    recorded: list[tuple[str, str]] = []
    monkeypatch.setattr(
        ops, "record_operational_error",
        lambda logger_name, message: recorded.append((logger_name, message)) or True,
    )

    dispatched: list[str] = []
    monkeypatch.setattr(
        "agent.log_monitor._dispatch_async",
        lambda title, description, signature=None: dispatched.append(title),
    )

    LogMonitor()._on_log_error("tasks", "ERROR", TIMEOUT_A)

    assert recorded == [("tasks", TIMEOUT_A)], "operational error must be counted"
    assert dispatched == [], "operational error must still create no code-fix task"


def test_log_monitor_still_creates_fix_tasks_for_real_code_errors(monkeypatch):
    """The existing behaviour must be untouched for genuine code defects."""
    from agent.log_monitor import LogMonitor

    monkeypatch.setattr(ops, "record_operational_error", lambda *a, **k: True)
    dispatched: list[str] = []
    monkeypatch.setattr(
        "agent.log_monitor._dispatch_async",
        lambda title, description, signature=None: dispatched.append(title),
    )
    monkeypatch.setattr("agent.log_monitor._note_recurrence", lambda sig: None)

    LogMonitor()._on_log_error(
        "backend.server", "ERROR", "AttributeError: 'NoneType' has no attribute 'id'"
    )

    assert len(dispatched) == 1
    assert "AttributeError" in dispatched[0]


def test_tracker_stats_expose_the_bounds(tracker):
    stats = tracker.get_stats()
    assert stats["threshold"] == 3
    assert stats["incidents_filed"] == 0
    assert "window_seconds" in stats


# ── a failed filing must not suppress the signature for hours ────────────────


def test_a_failed_filing_releases_the_cooldown_so_the_next_recurrence_retries(
    tracker, monkeypatch
):
    """Admission is granted synchronously; the filing happens later and can fail.

    The practical case is process startup, where the ImprovementLoop is not yet
    running. Without the rollback, one failed attempt would silence the
    signature for the whole 6h cooldown — precisely the "no signal at all"
    behaviour this module exists to remove.
    """
    monkeypatch.setattr(ops, "_file_incident", lambda incident: False)
    monkeypatch.setattr(ops, "_schedule", lambda coro: asyncio.run(coro))
    monkeypatch.setattr(
        ops, "get_operational_incident_tracker", lambda: tracker
    )

    async def _no_evidence() -> dict:
        return {"available": False, "reason": "test"}

    monkeypatch.setattr(ops, "gather_render_evidence", _no_evidence)

    for msg in (TIMEOUT_A, TIMEOUT_B, TIMEOUT_C):
        tracker.record("qwen-agent", msg)

    stats = tracker.get_stats()
    assert stats["incidents_attempted"] == 1
    assert stats["incidents_filed"] == 0, "a failed filing must not be counted as filed"
    assert stats["active_cooldowns"] == 0, "the cooldown must have been released"


def test_a_successful_filing_is_counted_and_holds_its_cooldown(tracker, monkeypatch):
    monkeypatch.setattr(ops, "_file_incident", lambda incident: True)
    monkeypatch.setattr(ops, "_schedule", lambda coro: asyncio.run(coro))
    monkeypatch.setattr(ops, "get_operational_incident_tracker", lambda: tracker)

    async def _no_evidence() -> dict:
        return {"available": False, "reason": "test"}

    monkeypatch.setattr(ops, "gather_render_evidence", _no_evidence)

    for msg in (TIMEOUT_A, TIMEOUT_B, TIMEOUT_C):
        tracker.record("qwen-agent", msg)

    stats = tracker.get_stats()
    assert stats["incidents_attempted"] == 1
    assert stats["incidents_filed"] == 1
    assert stats["active_cooldowns"] == 1


# ── unbounded growth ─────────────────────────────────────────────────────────


def test_signatures_that_go_quiet_are_evicted(tracker, filed, monkeypatch):
    """The process is long-lived and every matching ERROR adds a signature.

    Without eviction the maps only grow, and `tracked_signatures` reports a
    cumulative total rather than what is actually active.
    """
    monkeypatch.setattr(ops, "WINDOW_SECONDS", 60)
    monkeypatch.setattr(ops, "COOLDOWN_SECONDS", 60)
    clock = {"now": 1000.0}
    monkeypatch.setattr(ops, "_now", lambda: clock["now"])

    for n in ("alpha", "beta", "gamma"):
        tracker.record("qwen-agent", f"Upstream failure: {n} connection refused")
    assert tracker.get_stats()["tracked_signatures"] == 3

    clock["now"] += 3600.0  # everything ages out of both window and cooldown
    tracker.record("qwen-agent", "Upstream failure: delta connection refused")

    assert tracker.get_stats()["tracked_signatures"] == 1, (
        "stale signatures must be evicted, leaving only the active one"
    )


def test_eviction_never_drops_a_signature_still_inside_its_cooldown(
    tracker, filed, monkeypatch
):
    """Dropping a cooling signature would release its cooldown early and let the
    same failure re-file immediately."""
    monkeypatch.setattr(ops, "WINDOW_SECONDS", 60)
    monkeypatch.setattr(ops, "COOLDOWN_SECONDS", 86400)
    clock = {"now": 1000.0}
    monkeypatch.setattr(ops, "_now", lambda: clock["now"])

    for msg in (TIMEOUT_A, TIMEOUT_B, TIMEOUT_C):
        tracker.record("qwen-agent", msg)
    assert len(filed) == 1

    clock["now"] += 600.0  # past the window, still deep inside the cooldown
    tracker.record("qwen-agent", "Upstream failure: unrelated connection refused")

    assert tracker.get_stats()["active_cooldowns"] == 1, (
        "a cooling signature must survive eviction"
    )


# ── redaction ────────────────────────────────────────────────────────────────


def test_a_credential_in_the_failure_message_never_reaches_the_issue_body():
    """This repo already leaked a live MongoDB password into a log line once
    (2026-08-01). Incident bodies copy failure text verbatim into an issue, so
    everything failure-derived is scrubbed first."""
    leaky = (
        "Connection failed: mongodb+srv://dbuser:" + "sup3rs3cret"
        + "@cluster0.example.mongodb.net/app timed out"
    )
    assert "sup3rs3cret" not in ops.scrub(leaky)


def test_scrub_keeps_the_non_secret_context_readable():
    """Redaction that destroyed the whole message would defeat the diagnosis."""
    scrubbed = ops.scrub(
        "Connection failed: mongodb+srv://u:p@cluster0.example.mongodb.net/app"
    )
    assert "cluster0.example.mongodb.net" in scrubbed


def test_the_incident_title_is_scrubbed_not_only_the_body(tracker, filed):
    """`normalised` feeds the issue *title*, which is always displayed."""
    leaky = "Auth failed for mongodb+srv://dbuser:hunter2@db.example.net timed out"
    for _ in range(3):
        tracker.record("qwen-agent", leaky)

    assert len(filed) == 1
    assert "hunter2" not in filed[0].title
    assert "hunter2" not in filed[0].normalised
    assert "hunter2" not in filed[0].sample


def test_scrub_fails_closed_when_a_redaction_helper_is_missing(monkeypatch):
    """Better to withhold the value than to pass it through unmasked."""
    import builtins

    real_import = builtins.__import__

    def _no_redact(name, *args, **kwargs):
        if "redact" in name or "rbac" in name:
            raise ImportError("unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_redact)
    assert ops.scrub("mongodb://u:p@host") == "<redaction unavailable — value withheld>"


# ── scheduled diagnosis must not be garbage-collected mid-flight ─────────────


def test_a_scheduled_diagnosis_is_held_until_it_completes():
    """`loop.create_task` is only weakly referenced by the loop, so without a
    strong reference the GC can reclaim the diagnosis before it runs."""
    started = asyncio.Event()

    async def _work() -> None:
        started.set()

    async def _drive() -> None:
        ops._schedule(_work())
        assert ops._pending, "the in-flight task must be strongly referenced"
        await asyncio.sleep(0)
        await started.wait()

    asyncio.run(_drive())
    assert ops._pending == set(), "the reference must be released on completion"
