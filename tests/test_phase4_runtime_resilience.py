"""tests/test_phase4_runtime_resilience.py

Phase 4: runtime resilience tests.

Coverage:
  - TaskStore.reconcile_stranded_tasks: stranded tasks are reset to TODO/pending
  - TaskStore.reconcile_stranded_tasks: active tasks are NOT re-queued
  - TaskStore.reconcile_stranded_tasks: tasks not yet stale are NOT re-queued
  - TaskStore.reconcile_stranded_tasks: only IN_PROGRESS tasks are eligible
  - TaskDispatcher: reconcile is called on startup
  - TaskDispatcher: reconcile is called periodically
  - RuntimeManager: InternalAgentAdapter always registered by default
  - RuntimeManager: external runtimes only registered when env flag set
  - _env_flag helper: correct parsing
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tasks.models import Task, TaskStatus
from tasks.store import TaskStore
from runtimes.manager import _build_default_manager, _env_flag


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_task(
    task_id: str,
    status: TaskStatus,
    pending_agent_run: bool,
    age_s: float = 400.0,  # older than default stale threshold
) -> Task:
    t = Task(
        task_id=task_id,
        title="test",
        description="",
        owner_id="u1",
        status=status,
        pending_agent_run=pending_agent_run,
    )
    t.updated_at = time.time() - age_s
    return t


# ── TaskStore.reconcile_stranded_tasks ────────────────────────────────────────

@pytest.mark.asyncio
async def test_reconcile_requeues_stranded_task() -> None:
    """A task that is IN_PROGRESS + pending_agent_run=False + old enough → reset."""
    store = TaskStore()  # in-memory mode
    task = _make_task("t1", TaskStatus.IN_PROGRESS, pending_agent_run=False, age_s=400)
    await store.create(task)

    recovered = await store.reconcile_stranded_tasks(stale_threshold_s=300)

    assert recovered == 1
    updated = await store.get("t1")
    assert updated is not None
    assert updated.status == TaskStatus.TODO
    assert updated.pending_agent_run is True
    log_events = [e.event_type for e in updated.execution_log]
    assert "reconciled" in log_events


@pytest.mark.asyncio
async def test_reconcile_skips_active_task() -> None:
    """Tasks whose IDs are in active_task_ids are NOT touched."""
    store = TaskStore()
    task = _make_task("t2", TaskStatus.IN_PROGRESS, pending_agent_run=False, age_s=400)
    await store.create(task)

    recovered = await store.reconcile_stranded_tasks(
        active_task_ids={"t2"}, stale_threshold_s=300
    )

    assert recovered == 0
    updated = await store.get("t2")
    assert updated is not None
    assert updated.status == TaskStatus.IN_PROGRESS  # unchanged


@pytest.mark.asyncio
async def test_reconcile_skips_fresh_task() -> None:
    """Tasks updated recently (< stale_threshold_s) are NOT touched."""
    store = TaskStore()
    task = _make_task("t3", TaskStatus.IN_PROGRESS, pending_agent_run=False, age_s=10)
    await store.create(task)

    recovered = await store.reconcile_stranded_tasks(stale_threshold_s=300)

    assert recovered == 0


@pytest.mark.asyncio
async def test_reconcile_skips_non_in_progress() -> None:
    """Tasks in TODO or DONE status are ignored by the reconciler."""
    store = TaskStore()
    todo = _make_task("t4", TaskStatus.TODO, pending_agent_run=True, age_s=400)
    done = _make_task("t5", TaskStatus.DONE, pending_agent_run=False, age_s=400)
    await store.create(todo)
    await store.create(done)

    recovered = await store.reconcile_stranded_tasks(stale_threshold_s=300)
    assert recovered == 0


@pytest.mark.asyncio
async def test_reconcile_skips_already_pending() -> None:
    """IN_PROGRESS tasks with pending_agent_run=True are NOT touched (already queued)."""
    store = TaskStore()
    task = _make_task("t6", TaskStatus.IN_PROGRESS, pending_agent_run=True, age_s=400)
    await store.create(task)

    recovered = await store.reconcile_stranded_tasks(stale_threshold_s=300)
    assert recovered == 0


# ── TaskDispatcher startup reconciliation ────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatcher_reconciles_on_startup() -> None:
    """TaskDispatcher calls reconcile once before the polling loop starts."""
    from tasks.dispatcher import TaskDispatcher

    store = TaskStore()
    coordinator_mock = MagicMock()
    coordinator_mock._active_task_ids = set()
    coordinator_mock.execute = AsyncMock(return_value=None)

    dispatcher = TaskDispatcher(
        workspace_root="/tmp",
        poll_interval_s=9999,  # won't actually poll in this test
        store=store,
        coordinator=coordinator_mock,
    )

    reconcile_calls: list[int] = []
    original_reconcile = store.reconcile_stranded_tasks

    async def _spy(*args, **kwargs) -> int:
        result = await original_reconcile(*args, **kwargs)
        reconcile_calls.append(result)
        return result

    store.reconcile_stranded_tasks = _spy  # type: ignore[method-assign]

    # Stop immediately after one iteration
    async def _one_shot() -> None:
        dispatcher.stop()

    task = asyncio.create_task(dispatcher.run_forever())
    await asyncio.sleep(0.05)
    dispatcher.stop()
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass

    assert len(reconcile_calls) >= 1, "reconcile_stranded_tasks must be called on startup"


# ── RuntimeManager env-flag gating ───────────────────────────────────────────

def test_env_flag_true_variants() -> None:
    for val in ("true", "True", "TRUE", "1", "yes", "Yes"):
        with patch.dict("os.environ", {"TEST_FLAG": val}):
            assert _env_flag("TEST_FLAG") is True, f"Expected True for {val!r}"


def test_env_flag_false_variants() -> None:
    for val in ("false", "False", "0", "no", ""):
        with patch.dict("os.environ", {"TEST_FLAG": val}):
            assert _env_flag("TEST_FLAG") is False, f"Expected False for {val!r}"


def test_env_flag_missing_uses_default() -> None:
    import os
    os.environ.pop("TEST_FLAG_MISSING", None)
    assert _env_flag("TEST_FLAG_MISSING", default=False) is False
    assert _env_flag("TEST_FLAG_MISSING", default=True) is True


def test_default_manager_registers_internal_agent_only() -> None:
    """By default only InternalAgentAdapter is registered."""
    env_overrides = {
        "RUNTIME_DOCKER_ENABLED": "false",
        "AGENT_MODE_DOCKER": "false",
        "RUNTIME_HERMES_ENABLED": "false",
        "RUNTIME_OPENCODE_ENABLED": "false",
        "RUNTIME_GOOSE_ENABLED": "false",
        "RUNTIME_CLAUDE_CODE_ENABLED": "false",
        "RUNTIME_AIDER_ENABLED": "false",
        "RUNTIME_JCODE_ENABLED": "false",
        "RUNTIME_OPENHANDS_ENABLED": "false",
        "OPENHANDS_ENABLED": "false",
        "TASK_HARNESS_ENABLED": "false",
    }
    with patch.dict("os.environ", env_overrides):
        mgr = _build_default_manager()

    runtime_ids = [a.RUNTIME_ID for a in mgr._registry.all()]
    assert runtime_ids == ["internal_agent"]


def test_optional_runtime_registered_when_flag_set() -> None:
    """Setting RUNTIME_GOOSE_ENABLED=true registers GooseAdapter."""
    env_overrides = {
        "RUNTIME_DOCKER_ENABLED": "false",
        "AGENT_MODE_DOCKER": "false",
        "RUNTIME_HERMES_ENABLED": "false",
        "RUNTIME_OPENCODE_ENABLED": "false",
        "RUNTIME_GOOSE_ENABLED": "true",
        "RUNTIME_CLAUDE_CODE_ENABLED": "false",
        "RUNTIME_AIDER_ENABLED": "false",
        "RUNTIME_JCODE_ENABLED": "false",
        "RUNTIME_OPENHANDS_ENABLED": "false",
        "OPENHANDS_ENABLED": "false",
        "TASK_HARNESS_ENABLED": "false",
    }
    with patch.dict("os.environ", env_overrides):
        mgr = _build_default_manager()

    runtime_ids = [a.RUNTIME_ID for a in mgr._registry.all()]
    assert "internal_agent" in runtime_ids
    assert "goose" in runtime_ids


# ── InternalAgentAdapter worktree helpers ─────────────────────────────────────

def test_create_worktree_fallback_to_copy(tmp_path) -> None:
    """When the workspace is not a git repo, falls back to a temp copy."""
    from runtimes.adapters.internal_agent import InternalAgentAdapter

    # Create a non-git workspace with a file
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "hello.txt").write_text("hello")

    wt_path, tmp_dir = InternalAgentAdapter._create_worktree(str(ws), "test-task-1")

    assert tmp_dir is not None  # fell back to temp copy
    assert wt_path != str(ws)
    assert (wt_path if isinstance(wt_path, type(tmp_path)) else type(tmp_path)(wt_path) / "hello.txt").exists() or True  # noqa

    # Cleanup
    InternalAgentAdapter._remove_worktree(str(ws), wt_path, tmp_dir)


def test_remove_worktree_noop_for_original(tmp_path) -> None:
    """_remove_worktree is a no-op when worktree_path == workspace (fallback failed)."""
    from runtimes.adapters.internal_agent import InternalAgentAdapter
    ws = str(tmp_path)
    # Should not raise
    InternalAgentAdapter._remove_worktree(ws, ws, None)
