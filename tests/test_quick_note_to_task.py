"""Quick-notes must become real Tasks so agents pick them up.

Previously a quick-note was only filed as a GitHub issue or parked in a local
queue processed by a `claude` CLI absent in production — so notes "stayed there
forever". Submitting a note now also creates a Task routed through the working
dispatcher.
"""

from __future__ import annotations

import os

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test-secret-for-tests-only")
os.environ.setdefault("ADMIN_EMAIL", "admin@test.local")
os.environ.setdefault("ADMIN_PASSWORD", "TestPassword1!")

import pytest

from tasks.store import TaskStore, set_task_store, get_task_store


@pytest.fixture
def _inmem_store(monkeypatch):
    # No GitHub configured → the endpoint takes the local path; ensure a clean store.
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    store = TaskStore(db=None)
    set_task_store(store)
    return store


async def test_quick_note_creates_task(_inmem_store):
    from backend.server import quick_notes_submit, _QuickNoteBody

    body = _QuickNoteBody(url="", instruction="add a healthcheck endpoint")
    user = {"_id": "u-quick", "email": "q@test.local"}

    result = await quick_notes_submit(body, user=user)

    assert result.get("task_id"), "a task should be created from the quick-note"
    pending = await _inmem_store.list_pending(limit=10)
    assert any(t.task_id == result["task_id"] for t in pending)
    task = await _inmem_store.get(result["task_id"])
    assert task is not None
    assert task.pending_agent_run is True
    assert "quick-note" in task.tags
    assert "healthcheck" in task.prompt


async def test_quick_note_url_only_creates_task(_inmem_store):
    from backend.server import quick_notes_submit, _QuickNoteBody

    body = _QuickNoteBody(url="https://example.com/feature-spec", instruction="")
    user = {"_id": "u-quick"}
    result = await quick_notes_submit(body, user=user)
    assert result.get("task_id")
    task = await get_task_store().get(result["task_id"])
    assert "example.com/feature-spec" in task.prompt
