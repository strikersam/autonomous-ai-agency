"""tests/test_dispatcher_iso8601.py — regression test for the TaskDispatcher
auto-retry crash when ``task.updated_at`` is an ISO 8601 string.

Production error:
  TaskDispatcher error: '<' not supported between instances of 'float' and 'str'

Root cause: ``_auto_retry_blocked()`` in ``tasks/dispatcher.py`` did
``(now - task.updated_at) < _BLOCKED_COOLDOWN_S`` where ``now`` is a float
and ``task.updated_at`` can be an ISO 8601 string. The subtraction
``now - task.updated_at`` raises ``TypeError``.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from tasks.dispatcher import TaskDispatcher
from tasks.models import Task, TaskStatus
from tasks.store import TaskStore


def _make_task(status: TaskStatus, updated_at) -> Task:
    """Build a task with a specific updated_at value (bypassing the validator)."""
    task = Task(
        owner_id="user1",
        title="Test task",
        source="test",
        status=status,
    )
    task.updated_at = updated_at
    task.pending_agent_run = False
    task.auto_retry_count = 0
    return task


@pytest.mark.asyncio
async def test_auto_retry_blocked_does_not_crash_on_iso8601_updated_at():
    """The dispatcher's _auto_retry_blocked must not crash when a BLOCKED
    task has updated_at as an ISO 8601 string."""
    store = TaskStore()  # in-memory

    # Create a BLOCKED task with updated_at as an ISO 8601 string
    # (old enough to pass the cooldown gate)
    old_ts = time.time() - 600  # 10 minutes ago
    old_iso = datetime.fromtimestamp(old_ts, timezone.utc).isoformat()
    task = _make_task(TaskStatus.BLOCKED, old_iso)

    # Insert directly into the store's in-memory dict
    doc = task.model_dump()
    doc["updated_at"] = old_iso
    doc["status"] = TaskStatus.BLOCKED.value
    doc["pending_agent_run"] = False
    store._mem[task.task_id] = doc

    # Build a minimal dispatcher
    coordinator = MagicMock()
    coordinator._active_task_ids = set()
    coordinator.workflow = MagicMock()
    coordinator.workflow.retry = MagicMock()
    coordinator.execute = AsyncMock()

    dispatcher = TaskDispatcher(
        workspace_root="/tmp",
        store=store,
        coordinator=coordinator,
        max_concurrency=1,
    )

    # Must NOT raise TypeError: '<' not supported between instances of 'float' and 'str'
    await dispatcher._auto_retry_blocked()


@pytest.mark.asyncio
async def test_auto_retry_blocked_handles_float_updated_at():
    """The dispatcher's _auto_retry_blocked must still work with float updated_at."""
    store = TaskStore()

    old_ts = time.time() - 600  # 10 minutes ago
    task = _make_task(TaskStatus.BLOCKED, old_ts)

    doc = task.model_dump()
    doc["updated_at"] = old_ts
    doc["status"] = TaskStatus.BLOCKED.value
    doc["pending_agent_run"] = False
    store._mem[task.task_id] = doc

    coordinator = MagicMock()
    coordinator._active_task_ids = set()
    coordinator.workflow = MagicMock()
    coordinator.workflow.retry = MagicMock()
    coordinator.execute = AsyncMock()

    dispatcher = TaskDispatcher(
        workspace_root="/tmp",
        store=store,
        coordinator=coordinator,
        max_concurrency=1,
    )

    # Must not crash
    await dispatcher._auto_retry_blocked()


@pytest.mark.asyncio
async def test_auto_retry_blocked_skips_recent_iso8601_task():
    """A BLOCKED task with a recent ISO 8601 updated_at should be skipped
    (cooldown not yet expired), not crash."""
    store = TaskStore()

    recent_ts = time.time() - 10  # 10 seconds ago
    recent_iso = datetime.fromtimestamp(recent_ts, timezone.utc).isoformat()
    task = _make_task(TaskStatus.BLOCKED, recent_iso)

    doc = task.model_dump()
    doc["updated_at"] = recent_iso
    doc["status"] = TaskStatus.BLOCKED.value
    doc["pending_agent_run"] = False
    store._mem[task.task_id] = doc

    coordinator = MagicMock()
    coordinator._active_task_ids = set()
    coordinator.workflow = MagicMock()
    coordinator.workflow.retry = MagicMock()
    coordinator.execute = AsyncMock()

    dispatcher = TaskDispatcher(
        workspace_root="/tmp",
        store=store,
        coordinator=coordinator,
        max_concurrency=1,
    )

    # Must not crash, and must NOT retry (too recent)
    await dispatcher._auto_retry_blocked()
    # retry should NOT have been called (cooldown not expired)
    coordinator.workflow.retry.assert_not_called()
