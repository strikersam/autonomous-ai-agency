"""Fixtures of the reliability suite."""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from packages.runs.store import RunStore, set_run_store
from tasks import store as task_store_mod
from tasks.store import TaskStore

ALICE = {"_id": "alice", "email": "alice@example.com", "role": "user"}
BOB = {"_id": "bob", "email": "bob@example.com", "role": "user"}


@pytest.fixture
def api(monkeypatch):
    """A TestClient on the real app with an in memory run store, a task store and a switchable user."""
    from backend.server import app, get_current_user

    runs, tasks = RunStore(), TaskStore()
    set_run_store(runs)
    monkeypatch.setattr(task_store_mod, "_global_store", tasks)
    holder = {"user": ALICE}

    def _user():
        if holder["user"] is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return holder["user"]

    app.dependency_overrides[get_current_user] = _user
    client = TestClient(app, raise_server_exceptions=False)
    client.holder, client.runs, client.tasks = holder, runs, tasks
    yield client
    app.dependency_overrides.clear()
    set_run_store(None)
