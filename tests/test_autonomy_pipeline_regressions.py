"""Regression tests for the autonomy pipeline bugs that blocked the agency
from being "fully autonomous" (https://github.com/strikersam/autonomous-ai-agency).

Each bug is documented inline with the failure mode it prevents.

  BUG-1  ScheduledJob has no ``status`` attribute — ``company_agency.py`` touched it
         in three places, raising AttributeError and aborting schedule creation
         for every onboarded company.

  BUG-2  ScheduleStore was Mongo-only — with ``STORAGE_BACKEND=sqlite`` (the
         README's zero-dependency default) the store fell back to in-memory
         and lost every cadence on restart.

  BUG-3  APScheduler fires jobs from a background thread with no event loop.
         ``_fire`` fell back to ``asyncio.run(coro)`` which created a fresh
         loop that couldn't see Motor/aiosqlite clients bound to the FastAPI
         main loop → "Future attached to a different loop" and the agency's
         24x7 cadences silently never produced any work.
"""
from __future__ import annotations

import asyncio
import os
import threading
import time

import pytest

# NOTE: do NOT set STORAGE_BACKEND at module level — it would pollute every
# other test in the session (test_schedule_store_create_index_options.py
# stubs pymongo and expects ScheduleStore to take the Mongo path). Each test
# below uses monkeypatch.setenv() to scope STORAGE_BACKEND=sqlite to itself.
os.environ.setdefault("ADMIN_PASSWORD", "test123")
os.environ.setdefault("SELF_BOOTSTRAP_ENABLED", "false")
os.environ.setdefault("AGENCY_CEO_ENABLED", "false")
os.environ.setdefault("AGENCY_IMPROVEMENT_ENABLED", "false")
os.environ.setdefault("AGENCY_SELF_HEAL_ENABLED", "false")
os.environ.setdefault("AGENCY_LOG_MONITOR_ENABLED", "false")
os.environ.setdefault("AGENCY_TREND_WATCH_ENABLED", "false")


# ── BUG-1: ScheduledJob.status AttributeError ────────────────────────────────

def test_scheduled_job_has_no_status_attribute():
    """The dataclass exposes ``enabled`` (bool) only — code that read
    ``.status`` raised AttributeError and aborted schedule creation.
    This test pins the dataclass shape so the regression can't return.
    """
    from agent.scheduler import ScheduledJob

    job = ScheduledJob(
        job_id="job_test",
        name="test",
        cron="* * * * *",
        instruction="x",
        created_at="2026-01-01T00:00:00Z",
    )
    assert job.enabled is True
    with pytest.raises(AttributeError):
        _ = job.status  # noqa: B018 — intentional: pin the missing attr
    # The label callers actually want is synthesised from ``enabled``:
    assert job.as_dict()["status"] == "active"
    job.enabled = False
    assert job.as_dict()["status"] == "paused"


@pytest.mark.asyncio
async def test_company_agency_activate_creates_all_schedules(tmp_path, monkeypatch):
    """End-to-end: activate_company() on a fresh company creates all 6
    COMPANY_SCHEDULES without raising AttributeError on the dedup branch
    or the create branch.

    Pre-fix: every schedule creation raised
    ``AttributeError: 'ScheduledJob' object has no attribute 'status'``
    and the agency status came back as ``failed``.
    """
    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    monkeypatch.setenv("AGENCY_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AGENCY_SQLITE_DB_PATH", str(tmp_path / "agency.db"))

    from agent.scheduler import AgentScheduler
    from services.company_agency import CompanyAgencyService
    from models.company_graph import Company

    # Use a fresh scheduler so we don't disturb the global singleton state
    # (which the rest of the test session depends on).
    sched = AgentScheduler()
    svc = CompanyAgencyService()
    svc._scheduler = sched  # inject the isolated scheduler

    try:
        # Build a minimal in-memory company + specialist list — we only need
        # the activate path's schedule-creation loop, not the full store
        # round-trip (which would require a real Mongo/SQLite-backed
        # CompanyGraphStore and slow the test down).
        company = Company(
            id="co_regression",
            name="Regression Co",
            domain="regression.test",
            owner_id="test",
            onboarding_status="complete",
        )

        # Stub the store so activate_company() can read the company and
        # list its specialists (empty — we don't need any for schedule
        # creation, which is what we're regression-testing).
        class _StubStore:
            async def get_company(self, cid):
                return company

            async def list_specialists(self, cid):
                return []

            async def update_specialist(self, s):
                return s

        svc._specialist_service = None  # force lazy init skip
        # The activate_company code does:
        #     from services.company_graph_store import get_company_graph_store
        #     store = get_company_graph_store()
        # Patch the import target so our stub is returned.
        import services.company_graph_store as cgs_mod
        monkeypatch.setattr(cgs_mod, "get_company_graph_store", lambda: _StubStore())

        result = await svc.activate_company(
            company_id="co_regression",
            start_runtimes=False,  # don't try to start docker containers
            create_schedules=True,
        )

        # The bug caused ``status="failed"`` and zero schedules.
        assert result["status"] == "active", result
        assert len(result["schedules_created"]) == 6, (
            f"expected 6 schedules, got {len(result['schedules_created'])}: "
            f"{result}"
        )
        # Idempotency: re-activating hits the dedup branch (the original
        # crash site for ``existing_job.status``).
        result2 = await svc.activate_company(
            company_id="co_regression",
            start_runtimes=False,
            create_schedules=True,
        )
        assert result2["status"] == "active", result2
        assert all(
            s.get("note") == "already_exists" for s in result2["schedules_created"]
        ), "re-activation should hit the dedup branch, not create duplicates"
    finally:
        sched.shutdown()


# ── BUG-2: ScheduleStore SQLite backend ──────────────────────────────────────

def test_schedule_store_works_with_sqlite_backend(tmp_path, monkeypatch):
    """The README's zero-dependency deploy uses ``STORAGE_BACKEND=sqlite``.
    Pre-fix: ScheduleStore was Mongo-only and silently fell back to in-memory
    for SQLite deploys, so every company cadence was lost on restart.
    """
    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    monkeypatch.setenv("AGENCY_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AGENCY_SQLITE_DB_PATH", str(tmp_path / "agency.db"))

    from agent.schedule_store import ScheduleStore

    store = ScheduleStore()
    assert store.mode == "sqlite", (
        f"expected sqlite backend, got {store.mode} — ScheduleStore is "
        "supposed to honour STORAGE_BACKEND=sqlite"
    )

    # Round-trip: upsert → load_all → remove
    store.upsert({
        "job_id": "job_abc",
        "name": "test-schedule",
        "cron": "*/30 * * * *",
        "instruction": "do something",
    })
    loaded = store.load_all()
    assert any(d["job_id"] == "job_abc" for d in loaded), loaded

    store.remove("job_abc")
    loaded_after = store.load_all()
    assert not any(d["job_id"] == "job_abc" for d in loaded_after), (
        "remove() didn't delete the doc"
    )


def test_schedule_store_sqlite_survives_restart(tmp_path, monkeypatch):
    """The whole point of durable persistence is that schedules survive a
    process restart. Re-open the store from the same DB file and verify
    the previously-written job is rehydrated.
    """
    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    monkeypatch.setenv("AGENCY_DATA_DIR", str(tmp_path))
    db_path = str(tmp_path / "agency.db")
    monkeypatch.setenv("AGENCY_SQLITE_DB_PATH", db_path)

    from agent.schedule_store import ScheduleStore

    store1 = ScheduleStore()
    store1.upsert({
        "job_id": "job_persisted",
        "name": "survive-restart",
        "cron": "0 9 * * *",
        "instruction": "daily check",
    })

    # Simulate a restart by dropping the in-memory state and re-opening.
    store2 = ScheduleStore()
    loaded = store2.load_all()
    assert any(d["job_id"] == "job_persisted" for d in loaded), (
        "schedule did not survive simulated restart — SQLite persistence is broken"
    )


# ── BUG-3: APScheduler thread fires on_fire coroutine on the main loop ──────

def test_scheduler_attach_main_loop_and_fire_from_thread(tmp_path, monkeypatch):
    """APScheduler fires jobs from a background thread with no event loop.
    Pre-fix: ``_fire`` did ``asyncio.run(coro)`` which created a fresh loop
    that couldn't see Motor/aiosqlite clients bound to the main loop →
    "Future attached to a different loop".

    Post-fix: ``attach_main_loop(loop)`` captures the FastAPI main loop and
    ``_fire`` uses ``asyncio.run_coroutine_threadsafe(coro, main_loop)`` so
    the coroutine runs on the same loop that owns the DB clients.
    """
    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    monkeypatch.setenv("AGENCY_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AGENCY_SQLITE_DB_PATH", str(tmp_path / "agency.db"))

    from agent.scheduler import AgentScheduler

    # Shared state mutated by the on_fire coroutine. The coroutine records
    # which loop it ran on so we can assert it was the main loop, not a
    # fresh APScheduler-thread loop.
    fired: dict = {}
    main_loop = asyncio.new_event_loop()

    async def on_fire(job):
        # This coroutine touches the captured main loop — if it runs on a
        # different loop (the pre-fix bug), this assignment is the only
        # observable side effect that survives.
        fired["loop"] = asyncio.get_running_loop()
        fired["job_id"] = job.job_id

    sched = AgentScheduler(on_fire=on_fire)
    sched.attach_main_loop(main_loop)
    try:
        job = sched.create(name="thread-fire", cron="* * * * *", instruction="x")

        # Fire from a background thread — simulates APScheduler's worker.
        def fire_from_thread():
            # No running loop here, just like APScheduler's thread.
            sched._fire(job.job_id)

        t = threading.Thread(target=fire_from_thread)
        t.start()
        t.join()

        # Pump the main loop until the on_fire coroutine completes.
        # ``run_coroutine_threadsafe`` schedules the coroutine on the main
        # loop; we need to actually run that loop so the coroutine executes.
        deadline = time.time() + 5.0
        while "loop" not in fired and time.time() < deadline:
            main_loop.run_until_complete(asyncio.sleep(0.05))

        assert "loop" in fired, (
            "on_fire coroutine never ran — _fire didn't dispatch it onto the main loop"
        )
        assert fired["loop"] is main_loop, (
            "on_fire ran on a different loop — the APScheduler-thread bug is back. "
            f"main={main_loop}, actual={fired['loop']}"
        )
        assert fired["job_id"] == job.job_id
    finally:
        sched.shutdown()
        main_loop.close()
