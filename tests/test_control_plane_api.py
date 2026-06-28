"""tests/test_control_plane_api.py — Tests for Control Plane API endpoints.

Covers the new /api/schedules/* and /api/routing/* routes added as part of
the Control Plane implementation (Stage 2: runtime adapter system).
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from agent.scheduler import AgentScheduler, set_scheduler, get_scheduler, ScheduledJob
from schedules.api import schedules_router

from fastapi import FastAPI
from fastapi.testclient import TestClient


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def scheduler():
    sched = AgentScheduler()
    set_scheduler(sched)
    return sched


@pytest.fixture
def schedules_client(scheduler):
    app = FastAPI()
    app.include_router(schedules_router)
    return TestClient(app)


@pytest.fixture
def mock_runtime_manager():
    mgr = MagicMock()
    mgr.get_policy.return_value = {
        "never_use_paid_providers": True,
        "require_approval_before_paid_escalation": True,
        "max_paid_escalations_per_day": 0,
        "preferred_runtime_id": "hermes",
        "fallback_runtime_ids": [],
        "task_type_runtime_overrides": {},
    }
    mgr.get_decision_log.return_value = []
    return mgr


# ── Scheduler singleton ───────────────────────────────────────────────────────

def test_get_scheduler_raises_before_set():
    # V2.0 Phase 4: scheduler moved to packages.scheduler.scheduler.
    # The agent.scheduler shim re-exports symbols but module-level writes
    # don't propagate to the real singleton.
    import packages.scheduler.scheduler as sched_mod
    orig = sched_mod._scheduler_instance
    sched_mod._scheduler_instance = None
    with pytest.raises(RuntimeError, match="Scheduler not initialised"):
        get_scheduler()
    sched_mod._scheduler_instance = orig


def test_set_and_get_scheduler():
    sched = AgentScheduler()
    set_scheduler(sched)
    assert get_scheduler() is sched


# ── Scheduler toggle ──────────────────────────────────────────────────────────

def test_toggle_disables_job(scheduler):
    job = scheduler.create(name="test-job", cron="0 9 * * *", instruction="ping")
    assert job.enabled is True
    toggled = scheduler.toggle(job.job_id, enabled=False)
    assert toggled.enabled is False


def test_toggle_re_enables_job(scheduler):
    job = scheduler.create(name="test-job2", cron="0 9 * * *", instruction="ping")
    scheduler.toggle(job.job_id, enabled=False)
    toggled = scheduler.toggle(job.job_id, enabled=True)
    assert toggled.enabled is True


def test_toggle_missing_job_raises(scheduler):
    with pytest.raises(KeyError):
        scheduler.toggle("nonexistent-id", enabled=False)


# ── /api/schedules endpoints ──────────────────────────────────────────────────

def test_list_schedules_empty(schedules_client):
    resp = schedules_client.get("/api/schedules/")
    assert resp.status_code == 200
    assert resp.json()["schedules"] == []


def test_create_schedule(schedules_client):
    payload = {
        "name": "Daily lint",
        "cron": "0 9 * * *",
        "instruction": "Run lint",
        "approval_gate": False,
    }
    resp = schedules_client.post("/api/schedules/", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Daily lint"
    assert data["cron"] == "0 9 * * *"
    assert "job_id" in data


def test_list_schedules_after_create(schedules_client):
    schedules_client.post("/api/schedules/", json={
        "name": "Job A", "cron": "0 9 * * *", "instruction": "do A"
    })
    resp = schedules_client.get("/api/schedules/")
    assert resp.status_code == 200
    assert len(resp.json()["schedules"]) >= 1


def test_get_schedule(schedules_client):
    create_resp = schedules_client.post("/api/schedules/", json={
        "name": "Single", "cron": "0 9 * * *", "instruction": "do single"
    })
    job_id = create_resp.json()["job_id"]
    resp = schedules_client.get(f"/api/schedules/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["job_id"] == job_id


def test_get_schedule_not_found(schedules_client):
    resp = schedules_client.get("/api/schedules/nonexistent")
    assert resp.status_code == 404


def test_toggle_schedule_paused(schedules_client):
    create_resp = schedules_client.post("/api/schedules/", json={
        "name": "Toggleable", "cron": "0 9 * * *", "instruction": "toggle me"
    })
    job_id = create_resp.json()["job_id"]
    resp = schedules_client.patch(f"/api/schedules/{job_id}", json={"status": "paused"})
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False


def test_toggle_schedule_active(schedules_client):
    create_resp = schedules_client.post("/api/schedules/", json={
        "name": "ReActivate", "cron": "0 9 * * *", "instruction": "reactivate"
    })
    job_id = create_resp.json()["job_id"]
    schedules_client.patch(f"/api/schedules/{job_id}", json={"status": "paused"})
    resp = schedules_client.patch(f"/api/schedules/{job_id}", json={"status": "active"})
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True


def test_toggle_schedule_not_found(schedules_client):
    resp = schedules_client.patch("/api/schedules/bad-id", json={"status": "paused"})
    assert resp.status_code == 404


def test_run_schedule_now(schedules_client, scheduler):
    fired = []
    scheduler.set_on_fire(lambda job: fired.append(job.job_id))
    create_resp = schedules_client.post("/api/schedules/", json={
        "name": "Runnable", "cron": "0 9 * * *", "instruction": "run now"
    })
    job_id = create_resp.json()["job_id"]
    resp = schedules_client.post(f"/api/schedules/{job_id}/run")
    assert resp.status_code == 200
    assert resp.json()["status"] == "triggered"
    assert job_id in fired


def test_run_schedule_not_found(schedules_client):
    resp = schedules_client.post("/api/schedules/ghost/run")
    assert resp.status_code == 404


def test_delete_schedule(schedules_client):
    create_resp = schedules_client.post("/api/schedules/", json={
        "name": "Delete me", "cron": "0 9 * * *", "instruction": "bye"
    })
    job_id = create_resp.json()["job_id"]
    resp = schedules_client.delete(f"/api/schedules/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    # Confirm it's gone
    assert schedules_client.get(f"/api/schedules/{job_id}").status_code == 404


def test_schedule_runs_history(schedules_client):
    create_resp = schedules_client.post("/api/schedules/", json={
        "name": "History test", "cron": "0 9 * * *", "instruction": "count me"
    })
    job_id = create_resp.json()["job_id"]
    schedules_client.post(f"/api/schedules/{job_id}/run")
    resp = schedules_client.get(f"/api/schedules/{job_id}/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["schedule_id"] == job_id
    assert data["run_count"] >= 1


# ── hydrate() stale run-once job filtering (#844) ──────────────────────────

class _FakeStore:
    """In-memory store stub for hydrate() tests — isolates from real DB."""

    def __init__(self):
        self._docs: dict[str, dict] = {}

    def load_all(self) -> list[dict]:
        return list(self._docs.values())

    def upsert(self, doc: dict) -> None:
        jid = doc.get("job_id")
        if jid:
            self._docs[jid] = doc

    def remove(self, job_id: str) -> None:
        self._docs.pop(job_id, None)


def test_hydrate_skips_stale_run_once_jobs():
    """Stale run-once jobs (run_count > 0) must be skipped during hydration."""
    sched = AgentScheduler()
    store = _FakeStore()
    sched._store = store
    stale_doc = {
        "job_id": "job_stale_abc",
        "name": "agency: stale one-off",
        "cron": "* * * * *",
        "instruction": "already fired",
        "description": "[dev] Fix test",
        "tags": ["agency", "run-once", "priority-3"],
        "run_count": 1,
        "last_run": "2026-01-01T00:00:00Z",
        "enabled": True,
        "created_at": "2026-01-01T00:00:00Z",
    }
    store.upsert(stale_doc)

    import asyncio
    count = asyncio.run(sched.hydrate())

    assert count == 0, "stale run-once job must not be rehydrated"
    assert "job_stale_abc" not in sched._jobs
    # Also verify the stale job was cleaned from the store
    remaining = store.load_all()
    assert not any(d["job_id"] == "job_stale_abc" for d in remaining), \
        "stale run-once job must be removed from the store"


def test_hydrate_rehydrates_unfired_run_once_jobs():
    """Unfired run-once jobs (run_count == 0) must be rehydrated."""
    sched = AgentScheduler()
    store = _FakeStore()
    sched._store = store
    fresh_doc = {
        "job_id": "job_fresh_def",
        "name": "agency: fresh one-off",
        "cron": "* * * * *",
        "instruction": "not yet fired",
        "description": "[scout] Check trends",
        "tags": ["agency", "run-once", "priority-5"],
        "run_count": 0,
        "last_run": None,
        "enabled": True,
        "created_at": "2026-01-01T00:00:00Z",
    }
    store.upsert(fresh_doc)

    import asyncio
    count = asyncio.run(sched.hydrate())

    assert count == 1, "unfired run-once job must be rehydrated"
    assert "job_fresh_def" in sched._jobs
    job = sched._jobs["job_fresh_def"]
    assert job.name == "agency: fresh one-off"
    assert "run-once" in job.tags


def test_hydrate_skips_duplicate_by_job_id():
    """Jobs already in memory must not be rehydrated (dedup by job_id)."""
    sched = AgentScheduler()
    store = _FakeStore()
    sched._store = store

    existing = sched.create(
        name="already-present",
        cron="0 * * * *",
        instruction="existing",
    )
    store.upsert({
        "job_id": existing.job_id,
        "name": "already-present-duplicate",
        "cron": "0 * * * *",
        "instruction": "duplicate",
        "tags": [],
        "run_count": 0,
        "enabled": True,
        "created_at": "2026-01-01T00:00:00Z",
    })

    import asyncio
    count = asyncio.run(sched.hydrate())

    assert count == 0, "duplicate by job_id must not be re-added"
    assert sched._jobs[existing.job_id].name == "already-present"


def test_hydrate_with_no_store_returns_zero():
    """hydrate() with no store must return 0."""
    sched = AgentScheduler()
    sched._store = None
    # Stub _ensure_store so it doesn't lazily import a real store
    async def noop_store():
        pass
    sched._ensure_store = noop_store
    import asyncio
    count = asyncio.run(sched.hydrate())
    assert count == 0, "no store must return 0"

