"""tests/test_schedule_persistence.py — #505 schedules survive restart.

Regression for: "Scheduler store is ephemeral — all schedules wiped on redeploy."
A fresh AgentScheduler attached to the same durable store must rehydrate every
job (cron, instruction, enabled state, run_count) — proving cadences survive a
process restart.
"""
from __future__ import annotations

import asyncio
import gc
import warnings

from agent.scheduler import AgentScheduler, ScheduledJob
from agent.schedule_store import ScheduleStore


class _FakePersistence:
    """In-memory stand-in for ScheduleStore (no Mongo needed in tests)."""

    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}

    def load_all(self) -> list[dict]:
        return list(self.docs.values())

    def upsert(self, doc: dict) -> None:
        self.docs[doc["job_id"]] = dict(doc)

    def remove(self, job_id: str) -> None:
        self.docs.pop(job_id, None)


def test_schedules_persist_and_rehydrate_across_restart() -> None:
    store = _FakePersistence()

    # --- process 1: create cadences ---
    s1 = AgentScheduler(persistence=store)
    j1 = s1.create(name="daily-security", cron="0 3 * * *", instruction="run security scan")
    s1.create(name="health-30m", cron="*/30 * * * *", instruction="health check")
    assert len(store.docs) == 2  # persisted on create

    # --- simulate redeploy: brand-new scheduler, same durable store ---
    s2 = AgentScheduler()
    assert s2.list() == []  # starts empty (the bug: stayed empty forever)
    n = s2.attach_persistence(store)

    assert n == 2
    names = {j.name for j in s2.list()}
    assert names == {"daily-security", "health-30m"}
    rehydrated = s2.get(j1.job_id)
    assert rehydrated is not None
    assert rehydrated.cron == "0 3 * * *"
    assert rehydrated.instruction == "run security scan"
    assert rehydrated.enabled is True


def test_delete_and_toggle_are_persisted() -> None:
    store = _FakePersistence()
    s = AgentScheduler(persistence=store)
    job = s.create(name="x", cron="0 9 * * *", instruction="do x")

    s.toggle(job.job_id, enabled=False)
    assert store.docs[job.job_id]["enabled"] is False

    s.delete(job.job_id)
    assert job.job_id not in store.docs

    # A restart sees neither a ghost nor the deleted job.
    s2 = AgentScheduler()
    s2.attach_persistence(store)
    assert s2.list() == []


def test_disabled_job_rehydrates_and_can_be_re_enabled() -> None:
    """A disabled job must be registered (paused) on rehydrate so a later
    toggle(enabled=True) can resume it instead of silently failing on a missing
    APScheduler job. Regression for CodeRabbit review on #525."""
    store = _FakePersistence()
    s1 = AgentScheduler(persistence=store)
    job = s1.create(name="paused-cadence", cron="0 2 * * *", instruction="nightly")
    s1.toggle(job.job_id, enabled=False)
    assert store.docs[job.job_id]["enabled"] is False

    # Restart: rehydrate, then re-enable. Must not raise and must end enabled.
    s2 = AgentScheduler()
    s2.attach_persistence(store)
    rehydrated = s2.get(job.job_id)
    assert rehydrated is not None and rehydrated.enabled is False
    s2.toggle(job.job_id, enabled=True)
    assert s2.get(job.job_id).enabled is True
    assert store.docs[job.job_id]["enabled"] is True


def test_scheduled_job_roundtrips_through_dict() -> None:
    j = ScheduledJob(
        job_id="job_abc", name="n", cron="* * * * *", instruction="i",
        created_at="2026-01-01T00:00:00Z", run_count=5, enabled=False, tags=["a"],
    )
    again = ScheduledJob.from_dict(j.as_dict())
    assert again.job_id == "job_abc"
    assert again.run_count == 5
    assert again.enabled is False
    assert again.tags == ["a"]


def _seed(store: "_FakePersistence", **jobs: str) -> None:
    """Populate the store directly so hydration tests don't depend on the
    timing of create()'s fire-and-forget persist tasks under a running loop."""
    for name, cron in jobs.items():
        store.upsert(
            ScheduledJob(
                job_id="job_" + name, name=name, cron=cron,
                instruction=name, created_at="2026-01-01T00:00:00Z",
            ).as_dict()
        )


async def test_attach_persistence_async_rehydrates_on_event_loop() -> None:
    """Regression for the production startup path: services/background.py runs
    inside the async FastAPI lifespan. The sync attach_persistence() would call
    asyncio.run() on the live loop — raising and silently skipping hydration.
    attach_persistence_async() awaits hydration and returns the real count."""
    store = _FakePersistence()
    _seed(store, cadence_a="0 3 * * *", cadence_b="*/15 * * * *")

    s2 = AgentScheduler()
    n = await s2.attach_persistence_async(store)
    assert n == 2
    assert {j.name for j in s2.list()} == {"cadence_a", "cadence_b"}


async def test_sync_rehydrate_on_running_loop_does_not_leak() -> None:
    """The sync attach_persistence()/rehydrate() must stay safe even if called
    from within a running loop: it schedules hydration as a task and returns 0
    instead of constructing a coroutine for asyncio.run() that would leak."""
    store = _FakePersistence()
    _seed(store, cadence="0 9 * * *")

    s2 = AgentScheduler()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        n = s2.attach_persistence(store)  # called from this async test's loop
        assert n == 0  # cannot block on a running loop; hydration deferred
        await asyncio.sleep(0)  # let the scheduled hydrate() task run
        gc.collect()
    leaked = [
        w for w in caught
        if issubclass(w.category, RuntimeWarning) and "never awaited" in str(w.message)
    ]
    assert not leaked, f"leaked coroutines: {[str(w.message) for w in leaked]}"
    assert {j.name for j in s2.list()} == {"cadence"}


def test_store_falls_back_to_memory_without_mongo() -> None:
    # No Mongo in the test sandbox → store must degrade to a working backend
    # (sqlite when STORAGE_BACKEND=sqlite, or in-memory as the Mongo fallback),
    # not crash. Either way the round-trip must work.
    store = ScheduleStore()
    assert store.mode in ("mongo", "memory", "sqlite")
    store.upsert({"job_id": "j1", "name": "n", "cron": "* * * * *"})
    assert any(d["job_id"] == "j1" for d in store.load_all())
    store.remove("j1")
    assert all(d["job_id"] != "j1" for d in store.load_all())
