"""GET /api/tasks/awaiting-approval — dashboard surface for the pre-execution gate.

The Telegram gate notification told operators to approve "via the dashboard",
but no dashboard endpoint listed parked tasks: system-owned gated tasks (e.g.
trend scoping's ``system:trend-scoping``) were invisible on the paginated
board. This endpoint returns every task parked at the gate for admins, and
only the caller's own for non-admins.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

import tasks.api as tasks_api
from tasks.api import task_router
from tasks.models import Task, TaskStatus
from tasks.store import TaskStore, set_task_store


@pytest.fixture()
def task_store() -> TaskStore:
    store = TaskStore()
    set_task_store(store)
    return store


def _client(role: str, email: str) -> TestClient:
    app = FastAPI()

    @app.middleware("http")
    async def inject_user(request: Request, call_next):
        request.state.user = SimpleNamespace(email=email, role=role)
        return await call_next(request)

    app.include_router(task_router)
    return TestClient(app)


async def _seed(store: TaskStore) -> Task:
    parked = Task(
        owner_id="system:trend-scoping",
        title="trend Digital Pantheon",
        requires_approval=True,
        pending_agent_run=False,  # parked by the dispatcher's gate
    )
    await store.create(parked)
    # Already approved — must not appear.
    await store.create(Task(
        owner_id="system:trend-scoping", title="approved trend",
        requires_approval=True, execution_approved=True,
    ))
    # Rejected → BLOCKED — must not appear.
    await store.create(Task(
        owner_id="system:trend-scoping", title="rejected trend",
        requires_approval=True, status=TaskStatus.BLOCKED,
        blocked_reason="Execution rejected",
    ))
    # Ordinary task — must not appear.
    await store.create(Task(owner_id="o@x.com", title="routine"))
    return parked


@pytest.mark.asyncio
async def test_admin_sees_system_owned_gated_tasks(task_store):
    parked = await _seed(task_store)

    resp = _client("admin", "admin@example.com").get("/api/tasks/awaiting-approval")

    assert resp.status_code == 200
    tasks = resp.json()["tasks"]
    assert [t["task_id"] for t in tasks] == [parked.task_id]
    assert all("execution_log" not in t for t in tasks)


@pytest.mark.asyncio
async def test_non_admin_sees_only_own_gated_tasks(task_store):
    await _seed(task_store)
    mine = Task(owner_id="o@x.com", title="my gated deploy", requires_approval=True)
    await task_store.create(mine)

    resp = _client("user", "o@x.com").get("/api/tasks/awaiting-approval")

    assert resp.status_code == 200
    assert [t["task_id"] for t in resp.json()["tasks"]] == [mine.task_id]


@pytest.mark.asyncio
async def test_approving_removes_task_from_awaiting_list(task_store, monkeypatch):
    parked = await _seed(task_store)
    # Don't spin up the real execution coordinator from the background task.
    monkeypatch.setattr(tasks_api, "_queue_task_execution", lambda *a, **k: None)
    client = _client("admin", "admin@example.com")

    resp = client.post(f"/api/tasks/{parked.task_id}/approve-execution", json={"approve": True})

    assert resp.status_code == 200
    assert resp.json()["task"]["execution_approved"] is True
    assert client.get("/api/tasks/awaiting-approval").json()["tasks"] == []


@pytest.mark.asyncio
async def test_rejecting_removes_task_from_awaiting_list(task_store):
    parked = await _seed(task_store)
    client = _client("admin", "admin@example.com")

    resp = client.post(
        f"/api/tasks/{parked.task_id}/approve-execution",
        json={"approve": False, "reason": "not now"},
    )

    assert resp.status_code == 200
    assert resp.json()["task"]["status"] == "wont_do"  # human decline, not a failure
    assert client.get("/api/tasks/awaiting-approval").json()["tasks"] == []


@pytest.mark.asyncio
async def test_retry_blocked_requeues_all_blocked(task_store, monkeypatch):
    monkeypatch.setattr(tasks_api, "_queue_task_execution", lambda *a, **k: None)
    for i in range(3):
        await task_store.create(Task(
            owner_id="o@x.com", title=f"blocked {i}", status=TaskStatus.BLOCKED,
            blocked_reason="No runtime available", pending_agent_run=False,
        ))
    # A non-blocked task must be left alone.
    await task_store.create(Task(owner_id="o@x.com", title="done", status=TaskStatus.DONE))

    resp = _client("user", "o@x.com").post("/api/tasks/retry-blocked")

    assert resp.status_code == 200
    assert resp.json()["retried"] == 3
    remaining_blocked = [t for t in await task_store.list_for_user("o@x.com")
                         if t.status is TaskStatus.BLOCKED]
    assert remaining_blocked == []


@pytest.mark.asyncio
async def test_comment_reengages_task_for_the_agent(task_store, monkeypatch):
    # A top-level comment on ANY status re-opens + re-queues the task so the
    # agent reads and acts on it — including on a terminal task.
    queued: list[str] = []
    monkeypatch.setattr(tasks_api, "_queue_task_execution",
                        lambda bg, req, tid: queued.append(tid))
    done = Task(owner_id="o@x.com", title="finished thing", status=TaskStatus.DONE)
    await task_store.create(done)
    client = _client("user", "o@x.com")

    resp = client.post(f"/api/tasks/{done.task_id}/comments", json={"body": "actually, also handle X"})

    assert resp.status_code == 201
    body = resp.json()
    assert body["queued"] is True
    assert body["task"]["status"] in ("in_progress", "todo")
    assert body["task"]["pending_agent_run"] is True
    assert queued == [done.task_id]


@pytest.mark.asyncio
async def test_threaded_reply_does_not_reengage(task_store, monkeypatch):
    queued: list[str] = []
    monkeypatch.setattr(tasks_api, "_queue_task_execution",
                        lambda bg, req, tid: queued.append(tid))
    done = Task(owner_id="o@x.com", title="finished", status=TaskStatus.DONE)
    from tasks.models import TaskComment
    parent = TaskComment(author="o@x.com", body="root")
    done.comments.append(parent)
    await task_store.create(done)
    client = _client("user", "o@x.com")

    resp = client.post(f"/api/tasks/{done.task_id}/comments",
                       json={"body": "just discussing", "reply_to": parent.comment_id})

    assert resp.status_code == 201
    assert resp.json()["queued"] is False
    assert queued == []                       # a reply is discussion, no re-run
    assert (await task_store.get(done.task_id)).status is TaskStatus.DONE
