"""Tests for the public brain-availability diagnosis and the supervisor's use of it.

The behaviour under test is the one that made a real incident opaque: every
provider switched off or cooling down leaves the failover chain empty, tasks
fail with the generic "No runtime available", and nothing on an unauthenticated
surface says why. These pin the diagnosis, the secret-safety of exposing it, and
the supervisor's refusal to burn intervention budget during an outage.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from services.ceo_supervisor import CEOSupervisor, SupervisorConfig


class _P:
    """Minimal provider stand-in matching what the summary reads."""

    def __init__(self, pid, tier="free", healthy=True, default_model="m"):
        self.id = pid
        self.name = pid
        self.tier = tier
        self.is_healthy = healthy
        self.default_model = default_model
        self.failure_count = 0
        self.total_calls = 0
        self.total_failures = 0
        self.avg_latency_ms = 0.0
        self.last_error = "sk-live-SHOULD-NEVER-LEAK"


def _patch_providers(monkeypatch, providers, off=None):
    import services.brain_failover as bf

    monkeypatch.setattr(bf, "disabled_providers", lambda force=False: dict(off or {}))
    monkeypatch.setattr(bf, "state_is_durable", lambda: True)
    monkeypatch.setattr(
        bf, "get_failover_manager",
        lambda: type("M", (), {"get_providers": staticmethod(lambda: providers)})(),
    )


# ── The summary ───────────────────────────────────────────────────────────────


def test_all_healthy_reports_every_provider_usable(monkeypatch):
    from services.brain_failover import brain_availability_summary

    _patch_providers(monkeypatch, [_P("groq"), _P("cerebras")])
    s = brain_availability_summary()
    assert (s["total"], s["usable"]) == (2, 0 + 2)
    assert s["disabled"] == [] and s["cooling"] == []


def test_disabled_and_cooling_are_reported_separately(monkeypatch):
    """The remedies differ: one needs a human, the other recovers itself."""
    from services.brain_failover import brain_availability_summary

    _patch_providers(
        monkeypatch,
        [_P("groq"), _P("cerebras", healthy=False), _P("nvidia")],
        off={"groq": "auto: 402 out of credit"},
    )
    s = brain_availability_summary()
    assert s["usable"] == 1
    assert [d["id"] for d in s["disabled"]] == ["groq"]
    assert s["cooling"] == ["cerebras"]
    assert s["disabled"][0]["auto"] is True


def test_empty_chain_is_the_blocked_task_condition(monkeypatch):
    from services.brain_failover import brain_availability_summary

    _patch_providers(
        monkeypatch,
        [_P("groq"), _P("nvidia", healthy=False)],
        off={"groq": "auto: 401 invalid or expired api key"},
    )
    s = brain_availability_summary()
    assert s["usable"] == 0, "zero usable is what empties the failover chain"


def test_summary_never_leaks_secrets(monkeypatch):
    """This is served unauthenticated — no keys, no raw provider error text."""
    from services.brain_failover import brain_availability_summary

    _patch_providers(monkeypatch, [_P("groq")], off={"groq": "auto: 401 invalid key"})
    blob = repr(brain_availability_summary())
    assert "SHOULD-NEVER-LEAK" not in blob, "raw last_error must not be exposed"
    assert "sk-" not in blob


def test_summary_never_raises(monkeypatch):
    import services.brain_failover as bf

    monkeypatch.setattr(bf, "disabled_providers", lambda force=False: {})
    def _boom():
        raise RuntimeError("registry down")
    monkeypatch.setattr(bf, "get_failover_manager", _boom)
    s = bf.brain_availability_summary()
    assert s["usable"] == 0 and "error" in s


# ── The public endpoint ───────────────────────────────────────────────────────


def _doctor(client) -> dict:
    r = client.get("/api/doctor/public")
    assert r.status_code == 200
    return {c["id"]: c for c in r.json()["checks"]}


def test_public_doctor_fails_loudly_when_no_provider_is_usable(client, monkeypatch):
    _patch_providers(
        monkeypatch,
        [_P("groq")],
        off={"groq": "auto: 402 out of credit/quota"},
    )
    check = _doctor(client)["brain_providers"]
    assert check["status"] == "fail"
    assert "0/1" in check["detail"]
    assert "groq" in check["detail"]
    # The remedy has to be in the response, or the operator still has to guess.
    assert check["explanation"]


def test_public_doctor_passes_when_a_provider_is_usable(client, monkeypatch):
    _patch_providers(monkeypatch, [_P("groq")])
    check = _doctor(client)["brain_providers"]
    assert check["status"] == "pass"
    assert "1/1" in check["detail"]


def test_public_doctor_warns_on_partial_capacity(client, monkeypatch):
    _patch_providers(monkeypatch, [_P("groq"), _P("nvidia", healthy=False)])
    check = _doctor(client)["brain_providers"]
    assert check["status"] == "warn"
    assert "nvidia" in check["detail"]


def test_public_doctor_flags_missing_configuration(client, monkeypatch):
    _patch_providers(monkeypatch, [])
    check = _doctor(client)["brain_providers"]
    assert check["status"] == "fail"
    assert "No brain providers configured" in check["detail"]


def test_public_doctor_response_carries_no_secrets(client, monkeypatch):
    _patch_providers(monkeypatch, [_P("groq")], off={"groq": "auto: 401 invalid key"})
    body = client.get("/api/doctor/public").text
    assert "SHOULD-NEVER-LEAK" not in body and "sk-" not in body


# ── The supervisor ────────────────────────────────────────────────────────────


def _sup(**kw) -> CEOSupervisor:
    return CEOSupervisor(config=SupervisorConfig(**{"wake_runtimes": False, **kw}))


def test_supervisor_sees_the_brain_as_down(monkeypatch):
    monkeypatch.setattr(
        "services.brain_failover.brain_availability_summary",
        lambda: {"total": 2, "usable": 0, "disabled": [], "cooling": ["a", "b"]},
    )
    assert _sup()._brain_available() is False


def test_supervisor_fails_open_when_the_check_errors(monkeypatch):
    """Wrongly pausing every goal is worse than one wasted re-drive."""
    def _boom():
        raise RuntimeError("nope")
    monkeypatch.setattr("services.brain_failover.brain_availability_summary", _boom)
    assert _sup()._brain_available() is True


@pytest.mark.asyncio
async def test_a_brain_outage_pauses_instead_of_abandoning(monkeypatch, tmp_path):
    """The core fix: an outage must not burn the backlog's intervention budget."""
    import time

    from services.ceo_ledger import CEOLedger, GoalRecord, SubtaskRecord, reset_ceo_ledger

    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    reset_ceo_ledger()
    ledger = CEOLedger(sqlite_path=str(tmp_path / "a.db"))
    monkeypatch.setattr("services.ceo_ledger.get_ceo_ledger", lambda: ledger)

    stalled = GoalRecord(goal_id="stalled", goal="g", request="r",
                         last_progress_at=time.time() - 9999)
    stalled.subtasks = [SubtaskRecord(subtask_id="s1", title="a", status="running")]
    ledger.upsert(stalled)

    spent = GoalRecord(goal_id="spent", goal="g", request="r", interventions=99,
                       last_progress_at=time.time() - 9999)
    spent.subtasks = [SubtaskRecord(subtask_id="s1", title="a", status="running")]
    ledger.upsert(spent)

    monkeypatch.setattr(
        "services.brain_failover.brain_availability_summary",
        lambda: {"total": 1, "usable": 0, "disabled": [], "cooling": ["groq"]},
    )
    report = await _sup(stall_s=600).sweep()

    assert report.brain_unavailable is True
    assert report.paused == 2
    assert report.redriven == 0
    assert report.abandoned == 0, "an outage must never abandon a goal"
    # Nothing was spent, so the goals are still recoverable when the brain returns.
    assert ledger.get("stalled").interventions == 0
    assert ledger.get("stalled").state == "open"
    assert ledger.get("spent").state == "open"
    reset_ceo_ledger()


@pytest.mark.asyncio
async def test_finished_goals_still_close_during_an_outage(monkeypatch, tmp_path):
    """Closing needs no brain, so it must not be suspended with the rest."""
    from services.ceo_ledger import CEOLedger, GoalRecord, SubtaskRecord, reset_ceo_ledger

    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    reset_ceo_ledger()
    ledger = CEOLedger(sqlite_path=str(tmp_path / "b.db"))
    monkeypatch.setattr("services.ceo_ledger.get_ceo_ledger", lambda: ledger)

    done = GoalRecord(goal_id="done", goal="g", request="r")
    done.subtasks = [SubtaskRecord(subtask_id="s1", title="a", status="done")]
    ledger.upsert(done)

    monkeypatch.setattr(
        "services.brain_failover.brain_availability_summary",
        lambda: {"total": 1, "usable": 0, "disabled": [], "cooling": ["groq"]},
    )
    report = await _sup(stall_s=600).sweep()
    assert report.closed == 1
    assert ledger.get("done").state == "closed"
    reset_ceo_ledger()
