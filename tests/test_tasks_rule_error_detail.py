"""Task workflow rule violations must tell the user what rule they broke.

tasks/api.py answered every workflow ValueError with
``400 {"detail": "Internal server error"}`` — so moving a task from To Do
straight to Done in the task panel reported a server fault instead of the
disallowed transition. Rule messages now raise ``TaskRuleError`` and are
surfaced; any other ValueError still gets a generic detail (rule 27).
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

import tasks.service as tasks_service
from tasks.api import task_router
from tasks.models import Task
from tasks.store import TaskStore, set_task_store


@pytest.fixture()
def seeded() -> tuple[TestClient, str]:
    store = TaskStore()
    set_task_store(store)
    task = Task(owner_id="qa@example.com", title="probe")
    asyncio.run(store.create(task))

    app = FastAPI()

    @app.middleware("http")
    async def inject_user(request: Request, call_next):
        request.state.user = SimpleNamespace(email="qa@example.com", role="admin")
        return await call_next(request)

    app.include_router(task_router)
    return TestClient(app), task.task_id


def test_invalid_transition_names_the_transition(seeded) -> None:
    client, task_id = seeded
    resp = client.patch(f"/api/tasks/{task_id}", json={"status": "done"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Cannot transition task from todo to done"


def test_unrelated_value_error_stays_generic(seeded, monkeypatch) -> None:
    client, task_id = seeded

    def _boom(self, *args, **kwargs):
        raise ValueError("internal: /srv/secret/path.db is locked")

    monkeypatch.setattr(tasks_service.TaskWorkflowService, "transition", _boom)
    resp = client.patch(f"/api/tasks/{task_id}", json={"status": "in_progress"})
    assert resp.status_code == 400
    assert "secret" not in resp.text
    assert resp.json()["detail"] == "Invalid task request"
