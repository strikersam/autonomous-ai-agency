"""Tests for the CEO ledger, the supervised escalation loop, and the 24x7 sweeper.

These cover the behaviours that make "the CEO drives work to closure" a
checkable claim rather than an aspiration:
  - the ledger records goals, subtasks and every attempt, durably
  - a slop result is re-delegated one tier up instead of being accepted
  - escalation is bounded and terminates
  - the supervisor closes finished goals, re-drives stalled ones, and abandons
    the ones that spent their budget
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import patch

import pytest

from services.ceo_dispatcher import CEODispatcher, SpecialistTask, _harvest_changed_files
from services.ceo_ledger import (
    Attempt,
    CEOLedger,
    GoalRecord,
    SubtaskRecord,
    reset_ceo_ledger,
)
from services.ceo_micromanager import SubtaskPlan, Tier
from services.ceo_supervisor import (
    CEOSupervisor,
    SupervisorConfig,
    reset_ceo_supervisor,
)


@pytest.fixture
def ledger(monkeypatch, tmp_path):
    """A SQLite-backed ledger isolated to this test's tmp dir.

    The singleton is pinned to the same instance so the supervisor — which
    reaches for ``get_ceo_ledger()`` internally — sees this test's store and
    not a shared on-disk database.
    """
    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    monkeypatch.setenv("AGENCY_SQLITE_DB_PATH", str(tmp_path / "agency.db"))
    reset_ceo_ledger()
    store = CEOLedger(sqlite_path=str(tmp_path / "agency.db"))
    monkeypatch.setattr("services.ceo_ledger.get_ceo_ledger", lambda: store)
    yield store
    reset_ceo_ledger()


@pytest.fixture(autouse=True)
def _clean_supervisor():
    reset_ceo_supervisor()
    yield
    reset_ceo_supervisor()


def _goal(goal_id: str = "g-1", **kw) -> GoalRecord:
    base = dict(goal_id=goal_id, goal="Ship the health endpoint", request="Ship it")
    base.update(kw)
    return GoalRecord(**base)


# ── Ledger ────────────────────────────────────────────────────────────────────


def test_ledger_uses_sqlite_and_round_trips_a_goal(ledger):
    assert ledger.mode == "sqlite"
    goal = _goal()
    goal.subtasks = [SubtaskRecord(subtask_id="s1", title="Recon", role="scout")]
    ledger.upsert(goal)

    loaded = ledger.get("g-1")
    assert loaded is not None
    assert loaded.goal == "Ship the health endpoint"
    assert [s.subtask_id for s in loaded.subtasks] == ["s1"]


def test_ledger_survives_a_new_store_instance(ledger, monkeypatch, tmp_path):
    """Durability is the whole point — a redeploy must not lose open goals."""
    ledger.upsert(_goal("g-durable"))
    reopened = CEOLedger()
    assert reopened.get("g-durable") is not None


def test_ledger_records_attempt_history(ledger):
    goal = _goal()
    goal.subtasks = [SubtaskRecord(subtask_id="s1", title="Implement")]
    goal.subtasks[0].attempts.append(
        Attempt(tier="intern", started_at=time.time(), status="rejected")
    )
    goal.subtasks[0].attempts.append(
        Attempt(tier="junior", started_at=time.time(), status="accepted")
    )
    ledger.upsert(goal)

    loaded = ledger.get("g-1")
    assert [a.tier for a in loaded.subtasks[0].attempts] == ["intern", "junior"]
    assert loaded.subtasks[0].attempts_used == 2


def test_open_goals_excludes_closed_and_abandoned(ledger):
    ledger.upsert(_goal("open-1"))
    ledger.upsert(_goal("closed-1", state="closed"))
    ledger.upsert(_goal("abandoned-1", state="abandoned"))
    assert {g.goal_id for g in ledger.open_goals()} == {"open-1"}


def test_open_goals_puts_the_most_stalled_first(ledger):
    now = time.time()
    ledger.upsert(_goal("fresh", last_progress_at=now))
    ledger.upsert(_goal("stale", last_progress_at=now - 9000))
    assert [g.goal_id for g in ledger.open_goals()][0] == "stale"


def test_goal_progress_counts_done_subtasks(ledger):
    goal = _goal()
    goal.subtasks = [
        SubtaskRecord(subtask_id="s1", title="a", status="done"),
        SubtaskRecord(subtask_id="s2", title="b", status="running"),
    ]
    assert goal.progress() == (1, 2)


def test_ledger_stats_reports_state_breakdown(ledger):
    ledger.upsert(_goal("a"))
    ledger.upsert(_goal("b", state="closed"))
    stats = ledger.stats()
    assert stats["mode"] == "sqlite"
    assert stats["by_state"]["open"] == 1
    assert stats["by_state"]["closed"] == 1
    assert stats["open"] == 1


def test_ledger_degrades_to_memory_without_a_backend(monkeypatch):
    """A storage outage must never take the agency down."""
    monkeypatch.setenv("STORAGE_BACKEND", "mongo")
    monkeypatch.setenv("MONGO_URL", "mongodb://127.0.0.1:1")  # nothing listening
    monkeypatch.setenv("MONGO_SELECTION_TIMEOUT_MS", "50")
    store = CEOLedger(mongo_url="mongodb://127.0.0.1:1")
    assert store.mode == "memory"
    store.upsert(_goal("mem-1"))
    assert store.get("mem-1") is not None
    assert [g.goal_id for g in store.open_goals()] == ["mem-1"]


# ── changed-file harvesting ───────────────────────────────────────────────────


class _Result:
    def __init__(self, metadata=None, artifacts=None):
        if metadata is not None:
            self.metadata = metadata
        if artifacts is not None:
            self.artifacts = artifacts


def test_harvest_prefers_metadata_changed_files():
    files, reported = _harvest_changed_files(_Result(metadata={"changed_files": ["a.py"]}))
    assert files == ["a.py"]
    assert reported is True


def test_harvest_falls_back_to_string_artifacts():
    files, reported = _harvest_changed_files(_Result(artifacts=["a.py", "b.py"]))
    assert files == ["a.py", "b.py"]
    assert reported is True


def test_harvest_reads_dict_shaped_artifacts():
    files, reported = _harvest_changed_files(_Result(artifacts=[{"path": "a.py"}]))
    assert files == ["a.py"]
    assert reported is True


def test_harvest_reports_nothing_for_a_runtime_that_cannot_tell():
    """Distinguishing "changed nothing" from "cannot say" is what stops the
    quality gate rejecting every successful Hermes subtask."""
    files, reported = _harvest_changed_files(_Result())
    assert files == []
    assert reported is False


def test_harvest_distinguishes_explicit_empty_from_absent():
    files, reported = _harvest_changed_files(_Result(metadata={"changed_files": []}))
    assert files == []
    assert reported is True


# ── Supervised escalation ─────────────────────────────────────────────────────


class _RoutingDecision:
    def __init__(self, runtime_id: str) -> None:
        self.selected_runtime_id = runtime_id


class _TaskResult:
    def __init__(self, success=True, output="", error=None, metadata=None):
        self.success = success
        self.output = output
        self.error = error
        self.metadata = metadata or {}


class _ScriptedManager:
    """Returns a queued result per call, recording the specs it was given."""

    def __init__(self, results):
        self._results = list(results)
        self.calls = []
        self._started = True

    async def execute(self, spec):
        self.calls.append(spec)
        result = self._results.pop(0) if self._results else _TaskResult(
            success=True, output="fallback output that is long enough to pass",
            metadata={"changed_files": ["x.py", "tests/test_x.py"]},
        )
        if isinstance(result, Exception):
            raise result
        return result, _RoutingDecision(getattr(spec, "provider_preference", "internal_agent"))


def _task(tier=Tier.INTERN) -> SpecialistTask:
    plan = SubtaskPlan(
        subtask_id="s1",
        title="Add the health route",
        scope="Add a /health route.",
        outcome="GET /health returns 200.",
        tier=tier,
        writes_code=True,
    )
    return SpecialistTask(
        task_id="s1", instruction="brief", role="dev",
        runtime_id="internal_agent", tier=tier.value, plan=plan,
    )


@pytest.mark.asyncio
async def test_slop_result_is_escalated_and_the_retry_is_accepted(monkeypatch):
    """Claimed success with no file changes must be re-delegated, not accepted."""
    monkeypatch.setenv("CEO_MAX_ATTEMPTS_PER_SUBTASK", "3")
    mgr = _ScriptedManager([
        # Attempt 1 (intern): says it succeeded, changed nothing → slop.
        _TaskResult(success=True, output="All done, the route is now available.",
                    metadata={"changed_files": []}),
        # Attempt 2 (junior): real work with a test.
        _TaskResult(success=True, output="Added the /health route and a test for it.",
                    metadata={"changed_files": ["api.py", "tests/test_api.py"]}),
    ])
    ceo = CEODispatcher()
    st = _task(Tier.INTERN)
    entry = await ceo._run_supervised(mgr, st, sem=asyncio.Semaphore(2), results={})

    assert len(mgr.calls) == 2, "the slop result should have been re-delegated"
    assert entry["status"] == "ok"
    assert entry["quality"]["accepted"] is True
    # The retry ran one rung up the ladder.
    assert st.tier == Tier.JUNIOR.value
    assert entry["changed_files"] == ["api.py", "tests/test_api.py"]


@pytest.mark.asyncio
async def test_escalation_is_bounded_by_the_attempt_budget(monkeypatch):
    monkeypatch.setenv("CEO_MAX_ATTEMPTS_PER_SUBTASK", "2")
    slop = lambda: _TaskResult(  # noqa: E731 — terse factory keeps the script readable
        success=True, output="Everything is complete.", metadata={"changed_files": []}
    )
    mgr = _ScriptedManager([slop(), slop(), slop(), slop()])
    ceo = CEODispatcher()
    entry = await ceo._run_supervised(mgr, _task(Tier.INTERN), sem=asyncio.Semaphore(2), results={})

    assert len(mgr.calls) == 2, "budget of 2 must cap execution at 2 attempts"
    assert entry["status"] == "error"
    assert "quality gate" in entry["error"]


@pytest.mark.asyncio
async def test_escalation_terminates_at_the_top_tier(monkeypatch):
    """A subtask that starts at senior has nowhere to escalate to."""
    monkeypatch.setenv("CEO_MAX_ATTEMPTS_PER_SUBTASK", "4")
    mgr = _ScriptedManager([
        _TaskResult(success=True, output="Everything is complete.", metadata={"changed_files": []})
    ] * 4)
    ceo = CEODispatcher()
    entry = await ceo._run_supervised(mgr, _task(Tier.SENIOR), sem=asyncio.Semaphore(2), results={})

    assert len(mgr.calls) == 1
    assert entry["status"] == "error"


@pytest.mark.asyncio
async def test_escalation_can_be_disabled(monkeypatch):
    monkeypatch.setenv("CEO_ESCALATION_ENABLED", "false")
    mgr = _ScriptedManager([
        _TaskResult(success=True, output="Everything is complete.", metadata={"changed_files": []})
    ] * 3)
    ceo = CEODispatcher()
    entry = await ceo._run_supervised(mgr, _task(Tier.INTERN), sem=asyncio.Semaphore(2), results={})
    assert len(mgr.calls) == 1
    assert entry["status"] == "error"


@pytest.mark.asyncio
async def test_good_first_attempt_is_not_retried():
    mgr = _ScriptedManager([
        _TaskResult(success=True, output="Added the /health route and a regression test.",
                    metadata={"changed_files": ["api.py", "tests/test_api.py"]})
    ])
    ceo = CEODispatcher()
    entry = await ceo._run_supervised(mgr, _task(Tier.MIDLEVEL), sem=asyncio.Semaphore(2), results={})
    assert len(mgr.calls) == 1
    assert entry["quality"]["accepted"] is True


@pytest.mark.asyncio
async def test_legacy_task_without_a_plan_is_not_judged():
    """The low-complexity fast path has no plan, so there is nothing to gate on."""
    mgr = _ScriptedManager([_TaskResult(success=True, output="ok")])
    ceo = CEODispatcher()
    st = SpecialistTask(task_id="s1", instruction="do it", role="dev")
    entry = await ceo._run_supervised(mgr, st, sem=asyncio.Semaphore(2), results={})
    assert len(mgr.calls) == 1
    assert "quality" not in entry


@pytest.mark.asyncio
async def test_delegate_accepts_the_orchestrator_call_signature():
    """Regression guard for the TypeError that broke every medium/high EXECUTE.

    ``WorkflowOrchestrator._handle_execute`` passes ``goal`` and ``max_steps``.
    The dispatcher did not accept either, and the orchestrator re-raises
    unexpected exceptions, so the whole phase failed before any specialist ran.
    The existing test used an AsyncMock dispatcher, which accepts any keyword,
    so CI never saw it. This calls the real signature.
    """
    import inspect

    from services.ceo_dispatcher import CEODispatcher as RealCEO

    inspect.signature(RealCEO.delegate).bind(
        None,
        goal="Fix the bug",
        request="Fix the bug",
        complexity="medium",
        domain="testing",
        workspace_root="/tmp/wt",
        specialists=["s1"],
        max_steps=5,
    )


# ── Supervisor ────────────────────────────────────────────────────────────────


def _supervisor(**kw) -> CEOSupervisor:
    config = SupervisorConfig(**{"wake_runtimes": False, **kw})
    return CEOSupervisor(config=config)


@pytest.mark.asyncio
async def test_sweep_closes_a_goal_whose_subtasks_are_all_done(ledger):
    goal = _goal("done-1")
    goal.subtasks = [
        SubtaskRecord(subtask_id="s1", title="a", status="done"),
        SubtaskRecord(subtask_id="s2", title="b", status="done"),
    ]
    ledger.upsert(goal)

    report = await _supervisor().sweep()
    assert report.closed == 1
    assert ledger.get("done-1").state == "closed"


@pytest.mark.asyncio
async def test_sweep_leaves_a_goal_that_is_genuinely_in_flight(ledger):
    goal = _goal("busy-1", last_progress_at=time.time())
    goal.subtasks = [SubtaskRecord(subtask_id="s1", title="a", status="running")]
    ledger.upsert(goal)

    report = await _supervisor(stall_s=1800).sweep()
    assert report.in_flight == 1
    assert report.redriven == 0
    assert ledger.get("busy-1").state == "open"


@pytest.mark.asyncio
async def test_sweep_redrives_a_stalled_goal(ledger):
    goal = _goal("stalled-1", last_progress_at=time.time() - 5000)
    goal.subtasks = [SubtaskRecord(subtask_id="s1", title="a", status="running")]
    ledger.upsert(goal)

    driven = {}

    class _FakeCEO:
        async def delegate(self, request, **kwargs):
            driven["request"] = request
            driven["goal_id"] = kwargs.get("goal_id")
            return None

    with patch("services.ceo_dispatcher.get_ceo_dispatcher", return_value=_FakeCEO()):
        supervisor = _supervisor(stall_s=600)
        report = await supervisor.sweep()
        # The re-drive runs as a detached task; let it complete.
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    assert report.redriven == 1
    stored = ledger.get("stalled-1")
    assert stored.interventions == 1
    assert any("intervention #1" in n for n in stored.notes)
    # The re-drive reuses the existing ledger entry instead of opening a duplicate.
    assert driven["goal_id"] == "stalled-1"


@pytest.mark.asyncio
async def test_sweep_abandons_a_goal_that_spent_its_intervention_budget(ledger):
    goal = _goal("spent-1", last_progress_at=time.time() - 5000, interventions=3)
    goal.subtasks = [SubtaskRecord(subtask_id="s1", title="a", status="running")]
    ledger.upsert(goal)

    report = await _supervisor(stall_s=600, max_interventions=3).sweep()
    assert report.abandoned == 1
    stored = ledger.get("spent-1")
    assert stored.state == "abandoned"
    # Abandoned must never read as success.
    assert stored.verdict == "FAILED"
    assert any("intervention budget spent" in n for n in stored.notes)


@pytest.mark.asyncio
async def test_sweep_abandons_a_goal_past_the_age_limit(ledger):
    goal = _goal("old-1", created_at=time.time() - 100000, last_progress_at=time.time() - 100000)
    goal.subtasks = [SubtaskRecord(subtask_id="s1", title="a", status="running")]
    ledger.upsert(goal)

    report = await _supervisor(stall_s=600, max_goal_age_s=3600).sweep()
    assert report.abandoned == 1
    assert any("exceeded limit" in n for n in ledger.get("old-1").notes)


@pytest.mark.asyncio
async def test_sweep_caps_how_many_goals_it_redrives_at_once(ledger):
    for i in range(5):
        goal = _goal(f"stalled-{i}", last_progress_at=time.time() - 5000)
        goal.subtasks = [SubtaskRecord(subtask_id="s1", title="a", status="running")]
        ledger.upsert(goal)

    class _FakeCEO:
        async def delegate(self, request, **kwargs):
            return None

    with patch("services.ceo_dispatcher.get_ceo_dispatcher", return_value=_FakeCEO()):
        report = await _supervisor(stall_s=600, max_redrives_per_sweep=2).sweep()
        await asyncio.sleep(0)

    assert report.redriven == 2, "a single sweep must not stampede after an outage"
    assert report.scanned == 5


@pytest.mark.asyncio
async def test_sweep_does_not_redrive_a_goal_it_is_already_driving(ledger):
    goal = _goal("busy-2", last_progress_at=time.time() - 5000)
    goal.subtasks = [SubtaskRecord(subtask_id="s1", title="a", status="running")]
    ledger.upsert(goal)

    supervisor = _supervisor(stall_s=600)
    supervisor._driving.add("busy-2")
    report = await supervisor.sweep()

    assert report.redriven == 0
    assert report.in_flight == 1


@pytest.mark.asyncio
async def test_sweep_survives_a_ledger_outage(monkeypatch):
    """The supervisor keeps everything else alive, so it must be hard to kill."""
    def _boom():
        raise RuntimeError("ledger exploded")

    monkeypatch.setattr("services.ceo_ledger.get_ceo_ledger", _boom)
    report = await _supervisor().sweep()
    assert report.scanned == 0
    assert any("ledger unavailable" in e for e in report.errors)


@pytest.mark.asyncio
async def test_supervisor_status_reports_its_bounds():
    supervisor = _supervisor(interval_s=300, stall_s=900)
    await supervisor.sweep()
    status = supervisor.get_status()
    assert status["sweeps"] == 1
    assert status["config"]["interval_s"] == 300
    assert status["config"]["stall_s"] == 900
    assert status["last_report"] is not None


def test_supervisor_is_disabled_under_testing(monkeypatch):
    """Unit tests must never start a background sweeper."""
    from services.ceo_supervisor import supervisor_enabled

    monkeypatch.setenv("TESTING", "true")
    assert supervisor_enabled() is False
    monkeypatch.setenv("TESTING", "false")
    monkeypatch.setenv("CEO_SUPERVISOR_ENABLED", "true")
    assert supervisor_enabled() is True
    monkeypatch.setenv("CEO_SUPERVISOR_ENABLED", "false")
    assert supervisor_enabled() is False


def test_supervisor_config_clamps_hostile_env(monkeypatch):
    monkeypatch.setenv("CEO_SUPERVISOR_INTERVAL_S", "1")       # below floor
    monkeypatch.setenv("CEO_SUPERVISOR_MAX_INTERVENTIONS", "9999")
    monkeypatch.setenv("CEO_SUPERVISOR_STALL_S", "garbage")
    config = SupervisorConfig.from_env()
    assert config.interval_s == 30
    assert config.max_interventions == 10
    assert config.stall_s == 1800


@pytest.mark.asyncio
async def test_run_forever_keeps_going_after_a_failing_sweep(monkeypatch):
    """One bad sweep must not end the 24x7 loop."""
    supervisor = _supervisor(interval_s=30)
    calls = {"n": 0}

    async def _flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient")
        supervisor.stop()
        from services.ceo_supervisor import SweepReport
        return SweepReport()

    monkeypatch.setattr(supervisor, "sweep", _flaky)
    # Make the inter-sweep sleep instant so the test does not wait 30s. The real
    # sleep is captured first — referring to asyncio.sleep inside the
    # replacement would call the replacement.
    real_sleep = asyncio.sleep
    monkeypatch.setattr(
        "services.ceo_supervisor.asyncio.sleep", lambda _s: real_sleep(0)
    )

    await asyncio.wait_for(supervisor.run_forever(), timeout=5)
    assert calls["n"] >= 2, "the loop must survive the first failure and sweep again"
