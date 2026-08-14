"""tests/test_list_pending_priority.py — dispatch queue is priority-ordered.

Regression for "portfolio tasks aren't getting picked up": the dispatcher pulls
the front of ``TaskStore.list_pending`` (often ``limit=1``), so its ordering is
the scheduling policy. It sorted purely by ``updated_at``, so a freshly
materialized HIGH-priority initiative queued behind the entire older backlog and
was serviced last. Ordering is now priority-first, oldest-updated within a tier.
"""
from __future__ import annotations

import pytest

from tasks.models import Task, TaskPriority, TaskStatus
from tasks.store import TaskStore, _priority_rank


def test_priority_rank_is_total_and_ordered():
    assert _priority_rank(TaskPriority.URGENT) > _priority_rank(TaskPriority.HIGH)
    assert _priority_rank(TaskPriority.HIGH) > _priority_rank(TaskPriority.MEDIUM)
    assert _priority_rank(TaskPriority.MEDIUM) > _priority_rank(TaskPriority.LOW)
    # Accepts the raw string value too, and never raises on unknown/None.
    assert _priority_rank("high") == _priority_rank(TaskPriority.HIGH)
    assert _priority_rank(None) == 0
    assert _priority_rank("nonsense") == 0


@pytest.mark.asyncio
async def test_list_pending_orders_by_priority_then_updated_at(monkeypatch):
    monkeypatch.setenv("TESTING", "true")
    store = TaskStore()  # in-memory mode

    def mk(title: str, priority: TaskPriority) -> Task:
        return Task(
            owner_id="system",
            title=title,
            prompt="do work",
            priority=priority,
            status=TaskStatus.TODO,
            pending_agent_run=True,
        )

    # Created in a deliberately unhelpful order (low first, urgent last).
    for t in [
        mk("low-new", TaskPriority.LOW),
        mk("high-old", TaskPriority.HIGH),
        mk("high-new", TaskPriority.HIGH),
        mk("urgent", TaskPriority.URGENT),
        mk("medium", TaskPriority.MEDIUM),
    ]:
        await store.create(t)

    # Pin updated_at so the within-tier oldest-first tiebreak is deterministic:
    # high-old (50) must precede high-new (200).
    updated_at = {"low-new": 100, "high-old": 50, "high-new": 200, "urgent": 300, "medium": 10}
    for doc in store._mem.values():
        doc["updated_at"] = updated_at[doc["title"]]

    pending = await store.list_pending(limit=10)
    assert [p.title for p in pending] == [
        "urgent",     # rank 3
        "high-old",   # rank 2, updated_at 50 (older)
        "high-new",   # rank 2, updated_at 200
        "medium",     # rank 1
        "low-new",    # rank 0
    ]


@pytest.mark.asyncio
async def test_list_pending_respects_limit_after_priority_sort(monkeypatch):
    monkeypatch.setenv("TESTING", "true")
    store = TaskStore()

    await store.create(Task(owner_id="system", title="lo", prompt="x",
                            priority=TaskPriority.LOW, status=TaskStatus.TODO,
                            pending_agent_run=True))
    await store.create(Task(owner_id="system", title="hi", prompt="x",
                            priority=TaskPriority.URGENT, status=TaskStatus.TODO,
                            pending_agent_run=True))

    # limit=1 must return the URGENT task, not whichever was created first.
    pending = await store.list_pending(limit=1)
    assert len(pending) == 1
    assert pending[0].title == "hi"
