"""tests/test_reconciler_iso8601.py — regression test for the TaskDispatcher
reconciler crash when ``updated_at`` is an ISO 8601 string.

The error in production was::

    TaskDispatcher reconciler error: could not convert string to float:
    '2026-07-12T18:09:19.017649+00:00'

Root cause: ``reconcile_stranded_tasks()`` in ``tasks/store.py`` called
``float(updated_at)`` on the raw DB doc. Some tasks have ``updated_at``
stored as an ISO 8601 datetime string (not a float timestamp), which
makes ``float()`` raise ``ValueError``. The fix: a ``_ts_to_float()``
helper that normalises both float timestamps and ISO 8601 strings to a
float epoch.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import pytest

from tasks.store import TaskStore, _ts_to_float
from tasks.models import Task, TaskStatus


# ── _ts_to_float helper tests ──────────────────────────────────────────────


def test_ts_to_float_handles_float():
    assert _ts_to_float(1783782595.99) == 1783782595.99


def test_ts_to_float_handles_int():
    assert _ts_to_float(1783782595) == 1783782595.0


def test_ts_to_float_handles_iso8601_with_timezone():
    """The exact string from the production error."""
    ts = _ts_to_float("2026-07-12T18:09:19.017649+00:00")
    assert isinstance(ts, float)
    assert ts > 1_700_000_000  # sanity: after 2023


def test_ts_to_float_handles_iso8601_z():
    ts = _ts_to_float("2026-07-12T18:09:19Z")
    assert isinstance(ts, float)
    assert ts > 1_700_000_000


def test_ts_to_float_handles_iso8601_no_timezone():
    ts = _ts_to_float("2026-07-12T18:09:19")
    assert isinstance(ts, float)
    assert ts > 1_700_000_000


def test_ts_to_float_handles_numeric_string():
    assert _ts_to_float("1783782595.99") == 1783782595.99


def test_ts_to_float_handles_none():
    assert _ts_to_float(None) == 0.0


def test_ts_to_float_handles_garbage():
    assert _ts_to_float("not-a-date") == 0.0


def test_ts_to_float_handles_empty_string():
    assert _ts_to_float("") == 0.0


# ── reconcile_stranded_tasks regression tests ──────────────────────────────


@pytest.mark.asyncio
async def test_reconciler_does_not_crash_on_iso8601_updated_at():
    """The reconciler must not crash when a FAILED task has updated_at as
    an ISO 8601 string.

    This is the exact scenario that caused the production error:
    ``could not convert string to float: '2026-07-12T18:09:19.017649+00:00'``
    """
    store = TaskStore()  # in-memory by default

    # Create a FAILED task with updated_at as an ISO 8601 string.
    # This simulates a task written by a code path that stored the
    # timestamp as a string instead of a float.
    task = Task(
        owner_id="user1",
        title="Failed task with ISO updated_at",
        source="test",
        status=TaskStatus.FAILED,
    )
    # Insert directly into the store's in-memory dict, bypassing the
    # model validator so updated_at stays as a string.
    doc = task.model_dump()
    doc["updated_at"] = "2026-07-12T18:09:19.017649+00:00"
    doc["status"] = TaskStatus.FAILED.value
    doc["pending_agent_run"] = False
    doc["auto_retry_count"] = 0
    store._mem[task.task_id] = doc

    # The reconciler must NOT raise — it should normalise the timestamp
    # and either re-queue the task (if old enough) or skip it (if too
    # recent). Either way, no crash.
    recovered = await store.reconcile_stranded_tasks(
        active_task_ids=set(),
        stale_threshold_s=300,
    )
    # The task should be re-queued (the ISO timestamp is old enough).
    assert recovered >= 0  # no crash is the main assertion


@pytest.mark.asyncio
async def test_reconciler_requeues_old_iso8601_failed_task():
    """A FAILED task with an old ISO 8601 updated_at should be re-queued."""
    store = TaskStore()

    task = Task(
        owner_id="user1",
        title="Old failed task",
        source="test",
        status=TaskStatus.FAILED,
    )
    # Set updated_at to 2 hours ago as an ISO 8601 string
    old_time = datetime.now(timezone.utc)
    old_ts = old_time.timestamp() - 7200  # 2 hours ago
    old_iso = datetime.fromtimestamp(old_ts, timezone.utc).isoformat()

    doc = task.model_dump()
    doc["updated_at"] = old_iso
    doc["status"] = TaskStatus.FAILED.value
    doc["pending_agent_run"] = False
    doc["auto_retry_count"] = 0
    store._mem[task.task_id] = doc

    recovered = await store.reconcile_stranded_tasks(
        active_task_ids=set(),
        stale_threshold_s=300,
    )
    assert recovered >= 1  # the old FAILED task should be re-queued

    # Verify the task is now TODO + pending_agent_run
    updated_doc = store._mem[task.task_id]
    assert updated_doc["status"] == TaskStatus.TODO.value
    assert updated_doc["pending_agent_run"] is True


@pytest.mark.asyncio
async def test_reconciler_skips_recent_iso8601_failed_task():
    """A FAILED task with a recent ISO 8601 updated_at should be skipped
    (the 120s MIN_RETRY_AGE_S gate)."""
    store = TaskStore()

    task = Task(
        owner_id="user1",
        title="Recent failed task",
        source="test",
        status=TaskStatus.FAILED,
    )
    # Set updated_at to 10 seconds ago as an ISO 8601 string
    recent_ts = time.time() - 10
    recent_iso = datetime.fromtimestamp(recent_ts, timezone.utc).isoformat()

    doc = task.model_dump()
    doc["updated_at"] = recent_iso
    doc["status"] = TaskStatus.FAILED.value
    doc["pending_agent_run"] = False
    doc["auto_retry_count"] = 0
    store._mem[task.task_id] = doc

    recovered = await store.reconcile_stranded_tasks(
        active_task_ids=set(),
        stale_threshold_s=300,
    )
    # Should NOT be re-queued (too recent — MIN_RETRY_AGE_S = 120)
    assert recovered == 0

    # Verify the task is still FAILED
    updated_doc = store._mem[task.task_id]
    assert updated_doc["status"] == TaskStatus.FAILED.value


@pytest.mark.asyncio
async def test_reconciler_does_not_crash_on_iso8601_in_progress():
    """The first pass (stranded IN_PROGRESS) must also handle ISO 8601
    updated_at strings without crashing."""
    store = TaskStore()

    task = Task(
        owner_id="user1",
        title="Stranded in-progress task",
        source="test",
        status=TaskStatus.IN_PROGRESS,
    )
    # Set updated_at to 1 hour ago as an ISO 8601 string
    old_ts = time.time() - 3600
    old_iso = datetime.fromtimestamp(old_ts, timezone.utc).isoformat()

    doc = task.model_dump()
    doc["updated_at"] = old_iso
    doc["status"] = TaskStatus.IN_PROGRESS.value
    doc["pending_agent_run"] = False
    doc["auto_retry_count"] = 0
    store._mem[task.task_id] = doc

    # The reconciler must NOT raise on the string comparison
    recovered = await store.reconcile_stranded_tasks(
        active_task_ids=set(),
        stale_threshold_s=300,
    )
    # The stranded task should be re-queued
    assert recovered >= 1
    updated_doc = store._mem[task.task_id]
    assert updated_doc["status"] == TaskStatus.TODO.value
    assert updated_doc["pending_agent_run"] is True
