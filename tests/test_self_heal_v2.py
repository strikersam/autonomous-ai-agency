"""tests/test_self_heal.py — Self-healing system tests."""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("TELEGRAM_BOT_TOKEN", "RUN_TELEGRAM_BOT", "SELF_HEAL_INTERVAL_SEC"):
        monkeypatch.delenv(k, raising=False)
    yield


@pytest.mark.asyncio
async def test_brain_reset_when_all_unhealthy(monkeypatch):
    """When all brain providers are unhealthy, self-heal resets all breakers."""
    from services import brain_failover
    from services.self_heal import _heal_brain_failover

    brain_failover.reset_failover_manager()
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.setenv("ALLOW_PAID_BRAIN", "false")  # exclude paid providers

    fm = brain_failover.get_failover_manager()
    # Mark all providers as failed
    for p in fm.get_providers():
        fm.record_failure(p.id, "rate_limited", 429)

    providers = fm.get_providers()
    healthy_before = sum(1 for p in providers if p.is_healthy)
    assert healthy_before == 0, f"All providers should be unhealthy, got {healthy_before} healthy"

    result = await _heal_brain_failover()
    assert result["reset"] is True
    assert result["reset_count"] >= 1

    brain_failover.reset_failover_manager()


@pytest.mark.asyncio
async def test_brain_no_reset_when_healthy(monkeypatch):
    """When some providers are healthy, self-heal does NOT reset."""
    from services import brain_failover
    from services.self_heal import _heal_brain_failover

    brain_failover.reset_failover_manager()
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")

    result = await _heal_brain_failover()
    assert result["reset"] is False
    assert result["healthy"] >= 1

    brain_failover.reset_failover_manager()


@pytest.mark.asyncio
async def test_task_dedup(monkeypatch):
    """Self-heal deletes duplicate tasks with the same source_id.

    UNIT 1 (commit 312e9ba) changed the dedup strategy from title+source
    to source_id only — title-based dedup was deliberately removed because
    it was too aggressive (deleted legitimately different tasks that
    happened to share a title). This test was updated to match: the two
    tasks now share a source_id (the dedup key) rather than just a title.

    The store's ``create()`` already deduplicates by source_id at insert
    time, so to test the heal function's dedup (which cleans up duplicates
    that slipped in via race conditions or legacy data), we insert the two
    tasks directly into the store's in-memory dict, bypassing ``create()``.
    """
    from tasks.store import TaskStore, get_task_store
    from tasks.models import Task, TaskStatus
    from services.self_heal import _heal_task_duplicates

    store = TaskStore()  # in-memory by default

    # Create two tasks with the SAME source_id — the dedup key.
    # Both are TODO status (not in_progress — in_progress tasks are never deleted).
    t1 = Task(owner_id="user1", title="Fix bug", source="ceo_direct",
              source_id="strikersam/autonomous-ai-agency#999",
              status=TaskStatus.TODO)
    t2 = Task(owner_id="user1", title="Fix bug", source="ceo_direct",
              source_id="strikersam/autonomous-ai-agency#999",
              status=TaskStatus.TODO)
    # Insert directly into the store's in-memory dict, bypassing create()'s
    # source_id dedup — this simulates a race condition or legacy data.
    store._mem[t1.task_id] = t1.model_dump()
    store._mem[t2.task_id] = t2.model_dump()

    # Both should exist (different task_ids, same source_id)
    all_tasks = await store.list_all(limit=100)
    assert len(all_tasks) >= 2

    # Monkeypatch the store singleton
    import tasks.store as ts
    original_get = ts.get_task_store
    ts.get_task_store = lambda: store

    try:
        result = await _heal_task_duplicates()
        assert result["deleted"] >= 1
    finally:
        ts.get_task_store = original_get


@pytest.mark.asyncio
async def test_stuck_task_cleanup(monkeypatch):
    """Self-heal moves tasks stuck in IN_PROGRESS back to TODO."""
    from tasks.store import TaskStore
    from tasks.models import Task, TaskStatus
    from services.self_heal import _heal_stuck_tasks

    store = TaskStore()  # in-memory by default

    # Create a stuck task (started 1 hour ago)
    t = Task(owner_id="user1", title="Stuck task", status=TaskStatus.IN_PROGRESS)
    t.started_at = time.time() - 3600  # 1 hour ago
    await store.create(t)

    import tasks.store as ts
    original_get = ts.get_task_store
    ts.get_task_store = lambda: store

    try:
        result = await _heal_stuck_tasks()
        assert result["moved"] >= 1

        # Verify the task was moved
        task = await store.get(t.task_id)
        assert task.status == TaskStatus.TODO
        assert task.pending_agent_run is True
    finally:
        ts.get_task_store = original_get


@pytest.mark.asyncio
async def test_telegram_no_token():
    """Self-heal skips Telegram when no token is set."""
    from services.self_heal import _heal_telegram
    result = await _heal_telegram()
    assert result["action"] == "no_token"


@pytest.mark.asyncio
async def test_full_cycle_runs(monkeypatch):
    """The full self-heal cycle runs without errors."""
    from services import brain_failover
    from services.self_heal import run_self_heal_cycle

    brain_failover.reset_failover_manager()
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")

    result = await run_self_heal_cycle()
    assert "task_dedup" in result
    assert "brain_reset" in result
    assert "stuck_tasks" in result
    assert "telegram" in result

    brain_failover.reset_failover_manager()


def test_self_heal_module_imports():
    """The self_heal module imports cleanly."""
    from services.self_heal import (
        run_self_heal_cycle,
        start_self_heal_scheduler,
        stop_self_heal_scheduler,
    )
    assert callable(run_self_heal_cycle)
    assert callable(start_self_heal_scheduler)
    assert callable(stop_self_heal_scheduler)
