"""GET /api/tasks/counts — totals over the same set GET /api/tasks/ lists.

The list is paginated (50 by default), so the dashboard donut and board column
badges read their totals here. For admins the list spans every owner, so the
counts must too; they used to cover only the admin's own and system tasks.
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
def task_store(monkeypatch) -> TaskStore:
    store = TaskStore()
    set_task_store(store)
    monkeypatch.setattr(tasks_api, "_COUNTS_CACHE", {})
    return store


def _client(role: str, email: str) -> TestClient:
    app = FastAPI()

    @app.middleware("http")
    async def inject_user(request: Request, call_next):
        request.state.user = SimpleNamespace(email=email, role=role)
        return await call_next(request)

    app.include_router(task_router)
    return TestClient(app)


async def _seed(store: TaskStore) -> None:
    for i in range(60):  # more than one list page
        await store.create(Task(owner_id="other@x.com", title=f"o{i}", status=TaskStatus.DONE))
    await store.create(Task(owner_id="me@x.com", title="mine", status=TaskStatus.TODO))


@pytest.mark.asyncio
async def test_admin_counts_cover_every_owner_beyond_one_page(task_store):
    await _seed(task_store)
    counts = _client("admin", "admin@x.com").get("/api/tasks/counts").json()["counts"]
    assert counts == {"done": 60, "todo": 1}


@pytest.mark.asyncio
async def test_non_admin_counts_stay_scoped_to_own_tasks(task_store):
    await _seed(task_store)
    counts = _client("user", "me@x.com").get("/api/tasks/counts").json()["counts"]
    assert counts == {"todo": 1}


@pytest.mark.asyncio
async def test_gate_counts_are_uncapped_and_scoped(task_store):
    # /awaiting-approval lists at most 50; the counts must not stop there.
    for i in range(55):
        await task_store.create(Task(owner_id="system:trend-scoping", title=f"g{i}", requires_approval=True))
    await task_store.create(Task(owner_id="me@x.com", title="mine gated", requires_approval=True))
    await task_store.create(Task(owner_id="me@x.com", title="approved", requires_approval=True, execution_approved=True))

    admin = _client("admin", "admin@x.com").get("/api/tasks/counts").json()
    assert admin["awaiting_approval"] == {"todo": 56}
    user = _client("user", "me@x.com").get("/api/tasks/counts").json()
    assert user["awaiting_approval"] == {"todo": 1}
