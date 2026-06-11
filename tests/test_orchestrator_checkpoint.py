"""tests/test_orchestrator_checkpoint.py — Tests for durable checkpointing (#522)."""
from __future__ import annotations

import pytest


class TestOrchestratorCheckpointStore:
    """Save, load, list, delete, and restore operations."""

    @pytest.fixture
    def store(self):
        from services.orchestrator_checkpoint import (
            OrchestratorCheckpointStore,
            _store as _cp_singleton,
        )
        _backup = _cp_singleton
        cp = OrchestratorCheckpointStore()
        # Use in-memory fallback
        from services.orchestrator_checkpoint import _NoopDB as _ModNoopDB
        cp._store = _ModNoopDB()
        import services.orchestrator_checkpoint as mod
        mod._store = cp
        yield cp
        mod._store = _backup

    async def test_save_and_load(self, store):
        from services.workflow_orchestrator import WorkflowRun
        run = WorkflowRun(run_id="test-run-1")
        run.status = "running"
        run.current_phase = "classify"

        await store.save(run)
        doc = await store.load("test-run-1")
        assert doc is not None
        assert doc["run_id"] == "test-run-1"
        snap = doc.get("snapshot", {})
        assert snap.get("status") == "running"

    async def test_list_in_flight(self, store):
        from services.workflow_orchestrator import WorkflowRun

        running = WorkflowRun(run_id="r1")
        running.status = "running"
        await store.save(running)

        done = WorkflowRun(run_id="r2")
        done.status = "done"
        await store.save(done)

        docs = await store.list_in_flight()
        ids = {d["run_id"] for d in docs}
        assert "r1" in ids
        assert "r2" not in ids  # done is terminal

    async def test_delete(self, store):
        from services.workflow_orchestrator import WorkflowRun
        run = WorkflowRun(run_id="del-me")
        await store.save(run)
        await store.delete("del-me")
        doc = await store.load("del-me")
        assert doc is None

    async def test_restore_in_flight_runs(self, store):
        from services.workflow_orchestrator import WorkflowRun

        for i in range(3):
            run = WorkflowRun(run_id=f"r{i}")
            run.status = "queued" if i < 2 else "done"
            await store.save(run)

        docs = await store.restore_in_flight_runs()
        ids = {d["run_id"] for d in docs}
        assert len(ids) >= 2  # r0, r1 are in-flight
        assert "r2" not in ids  # done

    async def test_nonexistent_load(self, store):
        doc = await store.load("no-such-run")
        assert doc is None



