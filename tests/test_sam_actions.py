"""tests/test_sam_actions.py — SAM acts on the alerts bell instead of deflecting.

Regression: asked "look into the alerts and fix them", SAM replied "Please
review the alerts and take necessary actions" because its chat path had no
access to the alerts feed and no way to queue work.
"""

from __future__ import annotations

import asyncio

import pytest

import backend.server as server
import tasks.store as task_store_mod
from agent import sam_actions
from agent.sam import SamAgent
from tasks.store import TaskStore

USER_UTTERANCE = (
    "There are multiple errors which I am seeing that has been thrown on the "
    "alert I can can you please look into it and then fix them"
)

_FEED = [
    {"category": "error", "level": "error", "message": "Provider NVIDIA timed out after 30s",
     "created_at": "2026-09-25T10:00:00Z"},
    {"category": "error", "level": "error", "message": "Provider NVIDIA timed out after 45s",
     "created_at": "2026-09-25T09:59:00Z"},
    {"id": "alert-run-r1", "type": "error", "severity": "error", "title": "Run failed: r1",
     "message": "Execution failed", "created_at": "2026-09-25T09:58:00Z"},
    {"id": "alert-approval-r2", "type": "approval", "severity": "warning",
     "title": "Run awaiting approval: r2", "message": "", "created_at": ""},
    {"category": "quick_note", "message": "Quick-note queued", "created_at": ""},
]


@pytest.fixture
def store(monkeypatch) -> TaskStore:
    fresh = TaskStore()
    monkeypatch.setattr(task_store_mod, "_global_store", fresh)

    async def _feed(limit: int = 50) -> dict:
        return {"logs": list(_FEED)}

    monkeypatch.setattr(server, "_get_activity_impl", _feed)
    return fresh


@pytest.mark.parametrize("text,expected", [
    (USER_UTTERANCE, "fix"),
    ("SAM, fix the errors", "fix"),
    ("what alerts do I have?", "read"),
    ("create a task to fix the CI pipeline", None),
    ("what's the agency status", None),
])
def test_detect_alert_intent(text, expected):
    assert sam_actions.detect_alert_intent(text) == expected


def test_fix_request_queues_runnable_tasks(store):
    reply = asyncio.run(SamAgent().process_command(USER_UTTERANCE, owner_id="u1"))

    tasks = list(store._mem.values())
    # Two timeouts differ only in a number -> one fix task; plus the failed run.
    # The approval and the quick-note are not fixable errors.
    assert len(tasks) == 2
    assert all(t["pending_agent_run"] is True for t in tasks)
    assert all(t["owner_id"] == "u1" and "alert-fix" in t["tags"] for t in tasks)
    assert "queued 2 fix tasks" in reply
    assert "review the alerts" not in reply.lower()


def test_repeat_fix_request_does_not_duplicate(store):
    agent = SamAgent()
    asyncio.run(agent.process_command(USER_UTTERANCE, owner_id="u1"))
    reply = asyncio.run(agent.process_command("fix the alerts", owner_id="u1"))

    assert len(store._mem) == 2
    assert "already had a fix task" in reply


def test_read_request_summarises_without_creating_tasks(store):
    reply = asyncio.run(SamAgent().process_command("what alerts do I have?"))

    assert store._mem == {}
    assert "3 open alerts" in reply


def test_no_fixable_alerts(store, monkeypatch):
    async def _empty(limit: int = 50) -> dict:
        return {"logs": []}

    monkeypatch.setattr(server, "_get_activity_impl", _empty)
    reply = asyncio.run(SamAgent().process_command("fix the alerts"))

    assert store._mem == {}
    assert "nothing broken" in reply


def test_feed_failure_is_reported_not_raised(store, monkeypatch):
    async def _boom(limit: int = 50) -> dict:
        raise RuntimeError("db down")

    monkeypatch.setattr(server, "_get_activity_impl", _boom)
    reply = asyncio.run(SamAgent().process_command("fix the alerts"))

    assert "couldn't reach the alerts feed" in reply
