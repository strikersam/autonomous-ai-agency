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


# ── One-shot boot purge (PURGE_BACKLOG_ON_BOOT nonce) ────────────────────────

def _run_boot_purge(
    monkeypatch: pytest.MonkeyPatch,
    *,
    nonce_env: str | None,
    stored_nonce: str,
    core=None,
) -> tuple[int, list[str]]:
    """Drive _maybe_boot_purge with fakes; return (purged, marker_writes).

    ``core`` overrides the purge core (e.g. a raising or partial-failure
    fake); the default fake reports a clean summary and counts invocations.
    """
    import backend.server as srv
    import app_settings

    calls = {"purged": 0, "markers": []}

    async def _fake_core(**kwargs):
        calls["purged"] += 1
        return {"schedules": {"total": 0, "deleted": 0}, "tasks_deleted": {}}

    async def _fake_get(key, default=None):
        return stored_nonce

    async def _fake_set(key, value, updated_by="admin"):
        calls["markers"].append(value)

    monkeypatch.setattr(srv, "_purge_backlog_core", core or _fake_core)
    monkeypatch.setattr(app_settings, "get_setting", _fake_get)
    monkeypatch.setattr(app_settings, "set_setting", _fake_set)
    if nonce_env is None:
        monkeypatch.delenv("PURGE_BACKLOG_ON_BOOT", raising=False)
    else:
        monkeypatch.setenv("PURGE_BACKLOG_ON_BOOT", nonce_env)

    asyncio.run(srv._maybe_boot_purge())
    return calls["purged"], calls["markers"]


def test_boot_purge_runs_once_for_new_nonce(monkeypatch):
    purged, markers = _run_boot_purge(
        monkeypatch, nonce_env="purge-2026-07-03", stored_nonce=""
    )
    assert purged == 1
    assert markers == ["purge-2026-07-03"], "nonce must be stored after success"


def test_boot_purge_skips_already_executed_nonce(monkeypatch):
    purged, markers = _run_boot_purge(
        monkeypatch, nonce_env="purge-2026-07-03", stored_nonce="purge-2026-07-03"
    )
    assert purged == 0
    assert markers == []


def test_boot_purge_noop_without_env(monkeypatch):
    purged, markers = _run_boot_purge(monkeypatch, nonce_env=None, stored_nonce="")
    assert purged == 0
    assert markers == []


def test_boot_purge_failure_does_not_store_marker(monkeypatch):
    """A failed purge must NOT record the nonce — it retries next boot."""
    async def _boom(**kwargs):
        raise RuntimeError("store unavailable")

    _purged, markers = _run_boot_purge(
        monkeypatch, nonce_env="purge-x", stored_nonce="", core=_boom
    )
    assert markers == []


def test_boot_purge_partial_failure_does_not_store_marker(monkeypatch):
    """A PARTIAL purge (error markers inside the summary) must not record
    the nonce either — _purge_backlog_core degrades failures into the
    summary instead of raising, and persisting the marker for a partial
    purge would silently break the retry-next-boot contract."""
    async def _partial(**kwargs):
        return {
            "schedules": {"error": "mongo unavailable"},
            "tasks_deleted": {"blocked": 2},
        }

    _purged, markers = _run_boot_purge(
        monkeypatch, nonce_env="purge-y", stored_nonce="", core=_partial
    )
    assert markers == []


def test_boot_purge_task_drain_error_does_not_store_marker(monkeypatch):
    async def _partial(**kwargs):
        return {
            "schedules": {"total": 1, "deleted": 1},
            "tasks_deleted": {"blocked": 1, "todo_error": 0},
        }

    _purged, markers = _run_boot_purge(
        monkeypatch, nonce_env="purge-z", stored_nonce="", core=_partial
    )
    assert markers == []
