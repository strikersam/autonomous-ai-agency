"""tests/test_scheduler_store.py — Tests for durable scheduler store (#505)."""
from __future__ import annotations

import pytest


class TestSchedulerStore:
    """Save, load, delete, and hydration of scheduled jobs."""

    @pytest.fixture
    def store(self):
        from services.scheduler_store import (
            SchedulerStore,
            _MemDB,
            _store as _ss_singleton,
        )
        _backup = _ss_singleton
        s = SchedulerStore()
        # Force memory backend — inject _MemDB directly so _ensure_db()
        # skips the `from backend.server import get_db` import chain which
        # can trigger event-loop-closed errors in CI.
        s._db = _MemDB()
        import services.scheduler_store as mod
        mod._store = s
        yield s
        mod._store = _backup

    async def test_save_and_load(self, store):
        from agent.scheduler import ScheduledJob
        job = ScheduledJob(
            job_id="job-1",
            name="test job",
            cron="0 9 * * 1",
            instruction="Run weekly lint",
            created_at="2026-01-01T00:00:00Z",
        )
        await store.save(job)
        docs = await store.load_all()
        assert len(docs) >= 1
        found = next((d for d in docs if d.get("job_id") == "job-1"), None)
        assert found is not None
        assert found.get("name") == "test job"

    async def test_delete(self, store):
        from agent.scheduler import ScheduledJob
        job = ScheduledJob(
            job_id="job-del",
            name="delete me",
            cron="0 0 * * *",
            instruction="gone soon",
            created_at="2026-01-01T00:00:00Z",
        )
        await store.save(job)
        deleted = await store.delete("job-del")
        assert deleted is True

        docs = await store.load_all()
        ids = {d.get("job_id") for d in docs}
        assert "job-del" not in ids

    async def test_delete_nonexistent(self, store):
        deleted = await store.delete("no-such-job")
        assert deleted is False

    async def test_empty_load(self, store):
        docs = await store.load_all()
        assert isinstance(docs, list)

    async def test_agent_scheduler_hydrate(self):
        """AgentScheduler.hydrate() loads jobs from the store."""
        from agent.scheduler import AgentScheduler, ScheduledJob
        from services.scheduler_store import (
            SchedulerStore,
            _store as _ss_singleton,
        )
        _ss_backup = _ss_singleton

        # Set up a store with a persisted job
        sim_store = SchedulerStore()
        # Force memory backend to skip get_db() import chain in CI.
        from services.scheduler_store import _MemDB
        sim_store._db = _MemDB()
        sim_job = ScheduledJob(
            job_id="hydrate-job",
            name="hydrate test",
            cron="0 6 * * *",
            instruction="Morning check",
            created_at="2026-06-10T00:00:00Z",
        )
        await sim_store.save(sim_job)

        import services.scheduler_store as ss_mod
        ss_mod._store = sim_store

        sched = AgentScheduler()
        assert "hydrate-job" not in sched._jobs

        count = await sched.hydrate()
        assert count >= 1
        assert "hydrate-job" in sched._jobs
        restored = sched._jobs["hydrate-job"]
        assert restored.name == "hydrate test"

        ss_mod._store = _ss_backup
