"""tests/test_schedule_persistence.py — #505 schedules survive restart.

Regression for: "Scheduler store is ephemeral — all schedules wiped on redeploy."
A fresh AgentScheduler attached to the same durable store must rehydrate every
job (cron, instruction, enabled state, run_count) — proving cadences survive a
process restart.
"""
from __future__ import annotations

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


def test_store_falls_back_to_memory_without_mongo() -> None:
    # No Mongo in the test sandbox → store must degrade to in-memory, not crash.
    store = ScheduleStore()
    assert store.mode in ("mongo", "memory")
    store.upsert({"job_id": "j1", "name": "n", "cron": "* * * * *"})
    assert any(d["job_id"] == "j1" for d in store.load_all())
    store.remove("j1")
    assert all(d["job_id"] != "j1" for d in store.load_all())
