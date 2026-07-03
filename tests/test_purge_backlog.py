"""tests/test_purge_backlog.py — 2026-07-03 crash-loop remediation.

Covers:
- POST /api/admin/maintenance/purge-backlog (auth, admin gate, task drain,
  scheduler purge wiring)
- AgentScheduler.purge_all() (store + in-memory wipe)
- Tick requeue hardening: one task per tick, retry counter preserved,
  poisoned tasks (retry cap reached) never requeued.

Task-store interactions use a FakeTaskStore (monkeypatched via
``tasks.store.get_task_store``) so the tests are hermetic and immune to the
motor/aiosqlite event-loop binding between asyncio.run() and the TestClient
loop.
"""
from __future__ import annotations

import asyncio
import os

import pytest

from tasks.models import Task, TaskStatus


class FakeTaskStore:
    """Minimal in-memory stand-in for tasks.store.TaskStore."""

    def __init__(self, tasks: list[Task]) -> None:
        self.tasks: dict[str, Task] = {t.task_id: t for t in tasks}

    async def list_all(self, *, status=None, limit=100, offset=0):
        rows = [t for t in self.tasks.values() if status is None or t.status == status]
        return rows[offset: offset + limit]

    async def list_blocked(self, *, limit=50):
        return [t for t in self.tasks.values() if t.status == TaskStatus.BLOCKED][:limit]

    async def list_pending(self, *, limit=50):
        return []

    async def get(self, task_id, owner_id=None):
        return self.tasks.get(task_id)

    async def delete(self, task_id, owner_id=None):
        return self.tasks.pop(task_id, None) is not None

    async def update(self, task):
        self.tasks[task.task_id] = task
        return task


@pytest.fixture()
def auth_headers(client):
    """Auth headers for the seeded admin user (same pattern as test_agile_api)."""
    from backend.server import ADMIN_EMAIL

    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    resp = client.post(
        "/api/auth/login", json={"email": ADMIN_EMAIL, "password": admin_password}
    )
    if resp.status_code == 200:
        token = resp.json().get("access_token") or resp.json().get("token")
        if token:
            return {"Authorization": f"Bearer {token}"}
    return {}


# ── Endpoint ──────────────────────────────────────────────────────────────────

def test_purge_backlog_requires_auth(client):
    resp = client.post("/api/admin/maintenance/purge-backlog", json={})
    assert resp.status_code == 401


def test_purge_backlog_deletes_blocked_and_queued_tasks(client, auth_headers, monkeypatch):
    if not auth_headers:
        pytest.skip("admin login unavailable")

    import backend.server as srv
    import tasks.store as task_store_mod

    async def _fake_scheduler_purge():
        return {"total": 3, "deleted": 3}

    monkeypatch.setattr(srv.SCHEDULER, "purge_all", _fake_scheduler_purge)

    fake = FakeTaskStore([
        Task(owner_id="purge-test", title="poisoned blocked", status=TaskStatus.BLOCKED),
        Task(owner_id="purge-test", title="poisoned todo", status=TaskStatus.TODO),
        Task(owner_id="purge-test", title="stranded", status=TaskStatus.IN_PROGRESS),
        Task(owner_id="purge-test", title="finished — must survive", status=TaskStatus.DONE),
    ])
    monkeypatch.setattr(task_store_mod, "get_task_store", lambda: fake)

    resp = client.post(
        "/api/admin/maintenance/purge-backlog", json={}, headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["schedules"] == {"total": 3, "deleted": 3}
    assert body["tasks_deleted"] == {"blocked": 1, "todo": 1, "in_progress": 1}
    # DONE task untouched
    assert [t.status for t in fake.tasks.values()] == [TaskStatus.DONE]


def test_purge_backlog_flags_can_disable_sections(client, auth_headers, monkeypatch):
    if not auth_headers:
        pytest.skip("admin login unavailable")

    import backend.server as srv
    import tasks.store as task_store_mod

    async def _boom():  # must never be called when schedules=false
        raise AssertionError("scheduler purge should not run")

    monkeypatch.setattr(srv.SCHEDULER, "purge_all", _boom)
    monkeypatch.setattr(task_store_mod, "get_task_store", lambda: FakeTaskStore([]))
    resp = client.post(
        "/api/admin/maintenance/purge-backlog",
        json={"schedules": False, "blocked": False, "queued": False, "stranded": False},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert "schedules" not in resp.json()
    assert resp.json()["tasks_deleted"] == {}


# ── Scheduler.purge_all ───────────────────────────────────────────────────────

def test_scheduler_purge_all_wipes_store_and_memory():
    from packages.scheduler.scheduler import AgentScheduler

    sched = AgentScheduler()

    async def _scenario():
        job = sched.create(
            name="doomed-schedule", cron="0 0 * * *", instruction="noop"
        )
        assert job is not None
        summary = await sched.purge_all()
        return summary

    summary = asyncio.run(_scenario())
    assert set(summary) == {"total", "deleted"}
    assert sched.list() == []


# ── Tick requeue hardening ────────────────────────────────────────────────────

def test_tick_requeue_caps_at_one_and_preserves_retry_count(client, monkeypatch):
    """The per-minute tick must requeue at most ONE blocked task, keep its
    auto_retry_count (the old reset-to-zero defeated the dispatcher\'s retry
    cap), and never touch tasks that already burned through their retries."""
    import tasks.store as task_store_mod

    fresh = [
        Task(owner_id="tick-test", title=f"blocked {i}",
             status=TaskStatus.BLOCKED, auto_retry_count=2)
        for i in range(3)
    ]
    poisoned = Task(owner_id="tick-test", title="poisoned",
                    status=TaskStatus.BLOCKED, auto_retry_count=99)
    fake = FakeTaskStore(fresh + [poisoned])
    monkeypatch.setattr(task_store_mod, "get_task_store", lambda: fake)

    resp = client.get("/api/autonomy/tick")
    assert resp.status_code == 200
    assert resp.json().get("requeued", 0) <= 1

    requeued = [t for t in fake.tasks.values()
                if t.owner_id == "tick-test" and t.status == TaskStatus.TODO]
    assert len(requeued) == 1
    assert requeued[0].auto_retry_count == 2, "retry counter must be preserved"
    assert fake.tasks[poisoned.task_id].status == TaskStatus.BLOCKED, \
        "poisoned task must stay BLOCKED"
