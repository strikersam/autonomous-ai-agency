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

        import packages.scheduler.store as ss_mod
        ss_mod._store = sim_store

        sched = AgentScheduler()
        assert "hydrate-job" not in sched._jobs

        count = await sched.hydrate()
        assert count >= 1
        assert "hydrate-job" in sched._jobs
        restored = sched._jobs["hydrate-job"]
        assert restored.name == "hydrate test"

        ss_mod._store = _ss_backup

    async def test_count_empty(self, store):
        """count() returns 0 for an empty store."""
        c = await store.count()
        assert c == 0

    async def test_count_after_saves(self, store):
        """count() reflects the number of saved jobs."""
        from agent.scheduler import ScheduledJob
        for i in range(3):
            job = ScheduledJob(
                job_id=f"count-{i}",
                name=f"count job {i}",
                cron="0 0 * * *",
                instruction="ping",
                created_at="2026-01-01T00:00:00Z",
            )
            await store.save(job)
        c = await store.count()
        assert c == 3

    async def test_count_after_delete(self, store):
        """count() decreases after delete."""
        from agent.scheduler import ScheduledJob
        job = ScheduledJob(
            job_id="count-del",
            name="to delete",
            cron="0 0 * * *",
            instruction="ping",
            created_at="2026-01-01T00:00:00Z",
        )
        await store.save(job)
        assert await store.count() == 1
        await store.delete("count-del")
        assert await store.count() == 0

    async def test_delete_stale_keeps_recent(self, store):
        """delete_stale() keeps jobs updated recently."""
        from agent.scheduler import ScheduledJob
        job = ScheduledJob(
            job_id="recent-job",
            name="recent",
            cron="0 0 * * *",
            instruction="ping",
            created_at="2026-01-01T00:00:00Z",
        )
        await store.save(job)  # updated_at = now
        deleted = await store.delete_stale(retention_days=365)
        assert deleted == 0
        assert await store.count() == 1

    async def test_delete_stale_removes_old_jobs(self, store):
        """delete_stale() removes jobs with old updated_at."""
        import time
        from agent.scheduler import ScheduledJob

        # Save a job and then backdate its updated_at
        job = ScheduledJob(
            job_id="stale-job",
            name="stale",
            cron="0 0 * * *",
            instruction="ping",
            created_at="2026-01-01T00:00:00Z",
        )
        await store.save(job)

        # Force the updated_at timestamp to be 60 days in the past
        old_ts = time.time() - (60 * 86_400)
        if store._mem and "stale-job" in store._mem:
            store._mem["stale-job"]["updated_at"] = old_ts
        else:
            # Memory-store path: inject into the underlying _MemCollection
            col = await store._collection()
            if col is not None and hasattr(col, "_docs"):
                if "stale-job" in col._docs:
                    col._docs["stale-job"]["updated_at"] = old_ts

        # Save another fresh job for comparison
        job2 = ScheduledJob(
            job_id="fresh-job",
            name="fresh",
            cron="0 0 * * *",
            instruction="ping",
            created_at="2026-01-01T00:00:00Z",
        )
        await store.save(job2)

        # 30-day retention should remove the stale job only
        deleted = await store.delete_stale(retention_days=30)
        assert deleted >= 1
        assert await store.count() == 1
        docs = await store.load_all()
        ids = {d.get("job_id") for d in docs}
        assert "stale-job" not in ids
        assert "fresh-job" in ids

    async def test_delete_stale_default_retention_from_env(self, store, monkeypatch):
        """delete_stale() reads SCHEDULER_JOB_RETENTION_DAYS from env."""
        import time
        from agent.scheduler import ScheduledJob

        monkeypatch.setenv("SCHEDULER_JOB_RETENTION_DAYS", "7")

        job = ScheduledJob(
            job_id="env-stale",
            name="env stale",
            cron="0 0 * * *",
            instruction="ping",
            created_at="2026-01-01T00:00:00Z",
        )
        await store.save(job)

        old_ts = time.time() - (14 * 86_400)  # 14 days old
        if store._mem and "env-stale" in store._mem:
            store._mem["env-stale"]["updated_at"] = old_ts
        else:
            col = await store._collection()
            if col is not None and hasattr(col, "_docs") and "env-stale" in col._docs:
                col._docs["env-stale"]["updated_at"] = old_ts

        deleted = await store.delete_stale()  # uses env: 7 days
        assert deleted >= 1
        assert await store.count() == 0

    async def test_delete_stale_nothing_stale(self, store):
        """delete_stale() returns 0 when all jobs are recent."""
        from agent.scheduler import ScheduledJob
        job = ScheduledJob(
            job_id="fresh",
            name="fresh",
            cron="0 0 * * *",
            instruction="ping",
            created_at="2026-01-01T00:00:00Z",
        )
        await store.save(job)
        # 365-day retention — nothing is stale
        deleted = await store.delete_stale(retention_days=365)
        assert deleted == 0
        assert await store.count() == 1

    async def test_delete_stale_explicit_retention_overrides_env(self, store, monkeypatch):
        """Explicit retention_days arg takes precedence over env var."""
        import time
        from agent.scheduler import ScheduledJob

        monkeypatch.setenv("SCHEDULER_JOB_RETENTION_DAYS", "365")

        job = ScheduledJob(
            job_id="override-stale",
            name="override",
            cron="0 0 * * *",
            instruction="ping",
            created_at="2026-01-01T00:00:00Z",
        )
        await store.save(job)

        old_ts = time.time() - (14 * 86_400)  # 14 days old
        if store._mem and "override-stale" in store._mem:
            store._mem["override-stale"]["updated_at"] = old_ts
        else:
            col = await store._collection()
            if col is not None and hasattr(col, "_docs") and "override-stale" in col._docs:
                col._docs["override-stale"]["updated_at"] = old_ts

        # Explicit 7-day arg overrides the env's 365-day default
        deleted = await store.delete_stale(retention_days=7)
        assert deleted >= 1
        assert await store.count() == 0

    # ── _MemCollection.count_documents / delete_many ───────────────────────

    async def test_mem_collection_count_documents(self):
        """_MemCollection.count_documents returns doc count."""
        from services.scheduler_store import _MemCollection
        col = _MemCollection()
        assert await col.count_documents({}) == 0
        col._docs["a"] = {"job_id": "a", "name": "test"}
        col._docs["b"] = {"job_id": "b", "name": "test"}
        assert await col.count_documents({}) == 2

    async def test_mem_collection_delete_many(self):
        """_MemCollection.delete_many removes docs matching updated_at < cutoff."""
        import time
        from services.scheduler_store import _MemCollection
        col = _MemCollection()
        now = time.time()
        col._docs["old"] = {"job_id": "old", "updated_at": now - 100_000}
        col._docs["new"] = {"job_id": "new", "updated_at": now}
        result = await col.delete_many({"updated_at": {"$lt": now - 50_000}})
        assert result.deleted_count == 1
        assert "old" not in col._docs
        assert "new" in col._docs

    async def test_mem_delete_result_count(self):
        """_MemDeleteResult supports explicit count for batch deletes."""
        from services.scheduler_store import _MemDeleteResult
        r = _MemDeleteResult(True, count=7)
        assert r.deleted_count == 7
        r2 = _MemDeleteResult(False)
        assert r2.deleted_count == 0
        r3 = _MemDeleteResult(True)
        assert r3.deleted_count == 1
