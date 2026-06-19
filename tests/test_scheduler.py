"""Tests for agent/scheduler.py — Scheduled Agent Jobs."""
import gc
import warnings

import pytest

from agent.scheduler import AgentScheduler, ScheduledJob


class _FakePersistence:
    """In-memory ScheduleStore stand-in (sync upsert/remove/load_all)."""

    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}

    def load_all(self) -> list[dict]:
        return list(self.docs.values())

    def upsert(self, doc: dict) -> None:
        self.docs[doc["job_id"]] = dict(doc)

    def remove(self, job_id: str) -> None:
        self.docs.pop(job_id, None)


def test_sync_ops_do_not_leak_unawaited_coroutines():
    """Regression: create/toggle/trigger/delete from a sync caller (no running
    event loop) must not construct persistence coroutines that are never
    awaited. The old try-create_task/except-RuntimeError pattern built the
    coroutine before scheduling, leaking it and emitting a RuntimeWarning."""
    store = _FakePersistence()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        sched = AgentScheduler(persistence=store)
        job = sched.create(name="x", cron="* * * * *", instruction="x")
        sched.toggle(job.job_id, enabled=False)
        sched.trigger(job.job_id)
        sched.delete(job.job_id)
        sched.shutdown()
        # Orphaned coroutines warn on finalization; force it to surface now.
        gc.collect()
    leaked = [
        w for w in caught
        if issubclass(w.category, RuntimeWarning) and "never awaited" in str(w.message)
    ]
    assert not leaked, f"leaked coroutines: {[str(w.message) for w in leaked]}"
    # Behaviour preserved: sync path still persisted create+toggle, then removed.
    assert job.job_id not in store.docs


def test_create_job():
    sched = AgentScheduler()
    job = sched.create(name="lint", cron="0 9 * * 1", instruction="Run lint")
    assert job.name == "lint"
    assert job.cron == "0 9 * * 1"
    assert job.run_count == 0
    assert job.enabled is True
    sched.shutdown()


def test_list_jobs():
    sched = AgentScheduler()
    sched.create(name="a", cron="* * * * *", instruction="A")
    sched.create(name="b", cron="* * * * *", instruction="B")
    jobs = sched.list()
    names = [j.name for j in jobs]
    assert "a" in names
    assert "b" in names
    sched.shutdown()


def test_get_job():
    sched = AgentScheduler()
    job = sched.create(name="c", cron="* * * * *", instruction="C")
    fetched = sched.get(job.job_id)
    assert fetched is not None
    assert fetched.job_id == job.job_id
    sched.shutdown()


def test_delete_job():
    sched = AgentScheduler()
    job = sched.create(name="del", cron="* * * * *", instruction="Del")
    deleted = sched.delete(job.job_id)
    assert deleted is True
    assert sched.get(job.job_id) is None
    sched.shutdown()


def test_delete_nonexistent():
    sched = AgentScheduler()
    assert sched.delete("nope") is False
    sched.shutdown()


def test_trigger_fires_callback():
    fired: list[ScheduledJob] = []
    sched = AgentScheduler(on_fire=fired.append)
    job = sched.create(name="fire", cron="0 0 1 1 *", instruction="Fire me")
    sched.trigger(job.job_id)
    assert len(fired) == 1
    assert fired[0].job_id == job.job_id
    assert fired[0].run_count == 1
    sched.shutdown()


def test_trigger_unknown_raises():
    sched = AgentScheduler()
    with pytest.raises(KeyError):
        sched.trigger("unknown_job")
    sched.shutdown()


def test_trigger_increments_run_count():
    sched = AgentScheduler()
    job = sched.create(name="cnt", cron="* * * * *", instruction="Count")
    sched.trigger(job.job_id)
    sched.trigger(job.job_id)
    assert sched.get(job.job_id).run_count == 2
    sched.shutdown()


def test_as_dict():
    sched = AgentScheduler()
    job = sched.create(name="d", cron="* * * * *", instruction="D")
    d = job.as_dict()
    assert "job_id" in d
    assert "cron" in d
    assert "enabled" in d
    sched.shutdown()
