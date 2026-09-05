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
async def test_task_dedup_ignores_same_title_without_source_id(monkeypatch):
    """Self-heal must NOT delete same-title tasks that lack a source_id.

    Regression test for the dispatch-breaking bug fixed by removing
    title-based dedup: each task without a source_id is a distinct
    execution attempt (e.g. separate GitHub issue runs sharing a title)
    and must survive the heal cycle.
    """
    from tasks.store import TaskStore, get_task_store
    from tasks.models import Task, TaskStatus
    from services.self_heal import _heal_task_duplicates

    store = TaskStore()  # in-memory by default

    # Same title+source, but NO source_id — must NOT be deduped.
    t1 = Task(owner_id="user1", title="Fix bug", source="ceo_agency",
              status=TaskStatus.TODO)
    t2 = Task(owner_id="user1", title="Fix bug", source="ceo_agency",
              status=TaskStatus.TODO)
    await store.create(t1)
    await store.create(t2)

    all_tasks = await store.list_all(limit=100)
    assert len(all_tasks) >= 2

    # Monkeypatch the store singleton
    import tasks.store as ts
    original_get = ts.get_task_store
    ts.get_task_store = lambda: store

    try:
        result = await _heal_task_duplicates()
        assert result["deleted"] == 0

        remaining = await store.list_all(limit=100)
        assert len(remaining) >= 2
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
async def test_blocked_backlog_retires_old_blocked(monkeypatch):
    """A BLOCKED task older than the retire age becomes terminal FAILED.

    It must be pinned at/above the reconciler's auto-retry cap so the FAILED
    pass cannot resurrect it, cleared of pending_agent_run, and — critically —
    keep its execution_log (store.update does a whole-document replace, so the
    retirement must re-fetch the full task, not persist a log-less copy).
    """
    monkeypatch.setenv("BLOCKED_TASK_RETIRE_SEC", "3600")  # 1h
    monkeypatch.setenv("TASK_AUTO_RETRY_MAX", "5")
    from tasks.store import TaskStore
    from tasks.models import Task, TaskStatus
    from services.self_heal import _heal_blocked_backlog

    store = TaskStore()  # in-memory by default

    old = Task(owner_id="user1", title="Doomed", status=TaskStatus.BLOCKED,
               blocked_reason="No runtime available after 5 attempts")
    old.add_log("attempt 5 failed", event_type="runtime_unavailable")
    old.updated_at = time.time() - 7200  # blocked 2h ago
    await store.create(old)

    fresh = Task(owner_id="user1", title="Just blocked", status=TaskStatus.BLOCKED,
                 blocked_reason="brain down")
    fresh.updated_at = time.time()  # blocked just now
    await store.create(fresh)

    import tasks.store as ts
    original_get = ts.get_task_store
    ts.get_task_store = lambda: store
    try:
        result = await _heal_blocked_backlog()
        assert result["retired"] == 1
        assert result["blocked_total"] == 2

        retired = await store.get(old.task_id)
        assert retired.status == TaskStatus.FAILED
        assert retired.pending_agent_run is False
        assert retired.auto_retry_count >= 5           # above cap → not resurrected
        assert len(retired.execution_log) >= 1         # log preserved through replace

        kept = await store.get(fresh.task_id)
        assert kept.status == TaskStatus.BLOCKED       # too fresh → left alone
    finally:
        ts.get_task_store = original_get


@pytest.mark.asyncio
async def test_purge_backlog_deletes_only_aged_terminal(monkeypatch):
    """Purge removes aged DONE/FAILED tasks, and nothing else."""
    monkeypatch.setenv("SELF_HEAL_PURGE_ENABLED", "true")
    monkeypatch.setenv("SELF_HEAL_PURGE_DAYS", "3")
    from tasks.store import TaskStore
    from tasks.models import Task, TaskStatus
    from services.self_heal import _heal_purge_backlog

    store = TaskStore()
    old = time.time() - 5 * 86400   # 5 days ago
    recent = time.time() - 3600     # 1 hour ago

    old_done = Task(owner_id="u1", title="old done", status=TaskStatus.DONE)
    old_done.updated_at = old
    old_failed = Task(owner_id="u1", title="old failed", status=TaskStatus.FAILED)
    old_failed.updated_at = old
    recent_failed = Task(owner_id="u1", title="recent failed", status=TaskStatus.FAILED)
    recent_failed.updated_at = recent
    old_todo = Task(owner_id="u1", title="old todo", status=TaskStatus.TODO)
    old_todo.updated_at = old
    for t in (old_done, old_failed, recent_failed, old_todo):
        await store.create(t)

    import tasks.store as ts
    original_get = ts.get_task_store
    ts.get_task_store = lambda: store
    try:
        result = await _heal_purge_backlog()
        assert result["deleted"] == 2                       # both aged terminals
        assert await store.get(old_done.task_id) is None
        assert await store.get(old_failed.task_id) is None
        assert await store.get(recent_failed.task_id) is not None   # too fresh
        assert await store.get(old_todo.task_id) is not None        # not terminal
    finally:
        ts.get_task_store = original_get


@pytest.mark.asyncio
async def test_purge_backlog_respects_disable_flag(monkeypatch):
    monkeypatch.setenv("SELF_HEAL_PURGE_ENABLED", "false")
    from services.self_heal import _heal_purge_backlog
    result = await _heal_purge_backlog()
    assert result["deleted"] == 0
    assert result["action"] == "disabled"


@pytest.mark.asyncio
async def test_telegram_no_token():
    """Self-heal skips Telegram when no token is set."""
    from services.self_heal import _heal_telegram
    result = await _heal_telegram()
    assert result["action"] == "no_token"


@pytest.mark.asyncio
async def test_telegram_webhook_mode_is_not_cleared(monkeypatch):
    """In webhook mode, self-heal must NOT delete the webhook — that regression
    left inline buttons dead (self_heal fought the startup registration every
    cycle). It bails out before any getWebhookInfo/deleteWebhook call."""
    import httpx as _httpx

    from services.self_heal import _heal_telegram

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "s3cret_ABC-123")

    def _boom(*a, **k):  # any Telegram HTTP call here would be the bug
        raise AssertionError("self_heal must not call Telegram in webhook mode")

    monkeypatch.setattr(_httpx, "AsyncClient", _boom)

    result = await _heal_telegram()
    assert result == {"action": "webhook_mode_skip", "cleared": False}


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
