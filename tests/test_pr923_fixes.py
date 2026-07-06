"""tests/test_pr923_fixes.py — regression tests for PR #923 (5 production issues).

Covers:
1. nuclear_cleanup dedup-by-name pipeline (Issue 5: 2000+ schedules)
2. reconcile_stranded_tasks FAILED-task pass (Issue 3: failed tasks never re-picked)
3. TaskCoordinator timeout → re-queue (Issue 2: 300s timeout hard-fails tasks)
4. SAM voice drops hardcoded model (Issue 4: SAM fails when BRAIN_PREFERENCE=ollama)
5. brain.py BRAIN_PREFERENCE=ollama guard (Issue 1: stale BrainConfig blocks chat)

No sensitive credentials used — all tests use mock/fake objects and inspect
source code. No real HTTP requests, no real LLM calls, no real DB connections.
"""
from __future__ import annotations

import asyncio
import inspect
import os
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Issue 5: nuclear_cleanup dedup-by-name pipeline
# ─────────────────────────────────────────────────────────────────────────────

class FakeDeleteResult:
    def __init__(self, count: int):
        self.deleted_count = count


class FakeScheduleCollection:
    """Minimal async MongoDB-like collection for testing nuclear_cleanup."""
    def __init__(self, docs: list[dict]):
        self._docs = list(docs)

    async def delete_many(self, query):
        deleted = 0
        remaining = []
        for doc in self._docs:
            if self._matches(doc, query):
                deleted += 1
            else:
                remaining.append(doc)
        self._docs = remaining
        return FakeDeleteResult(deleted)

    def _matches(self, doc, query):
        for key, cond in query.items():
            if key == "tags":
                if "$in" in cond:
                    tags = doc.get("tags", [])
                    if not any(t in tags for t in cond["$in"]):
                        return False
            elif key == "run_count":
                if "$gt" in cond:
                    if not (doc.get("run_count", 0) > cond["$gt"]):
                        return False
            elif key == "job_id":
                if "$in" in cond:
                    if doc.get("job_id") not in cond["$in"]:
                        return False
        return True

    async def count_documents(self, query):
        return len(self._docs)

    def aggregate(self, pipeline):
        # Minimal aggregate implementation for the dedup pipeline
        # Only handles the sort + group + match used by nuclear_cleanup
        sorted_docs = sorted(self._docs, key=lambda d: d.get("updated_at", ""), reverse=True)
        groups: dict[str, list] = {}
        for doc in sorted_docs:
            name = doc.get("name", "")
            groups.setdefault(name, []).append(doc.get("job_id"))
        result = [
            {"_id": name, "job_ids": ids, "count": len(ids)}
            for name, ids in groups.items() if len(ids) > 1
        ]
        # Return an awaitable with to_list
        async def _to_list(length=None):
            return result
        agg = MagicMock()
        agg.to_list = _to_list
        return agg


class FakeDB:
    def __init__(self, schedules):
        self.schedules = schedules


@pytest.mark.asyncio
async def test_nuclear_cleanup_deletes_run_once_and_stuck():
    """nuclear_cleanup should delete run-once jobs and stuck agency jobs."""
    from packages.scheduler.cleanup import nuclear_cleanup

    docs = [
        {"job_id": "j1", "name": "task-a", "tags": ["run-once"], "run_count": 1, "updated_at": "2026-01-01"},
        {"job_id": "j2", "name": "task-b", "tags": ["agency"], "run_count": 15, "updated_at": "2026-01-01"},
        {"job_id": "j3", "name": "task-c", "tags": ["agency"], "run_count": 2, "updated_at": "2026-01-01"},  # not stuck
    ]
    db = FakeDB(FakeScheduleCollection(docs))
    result = await nuclear_cleanup(db)
    assert result["deleted_run_once"] == 1
    assert result["deleted_stuck"] == 1


@pytest.mark.asyncio
async def test_nuclear_cleanup_dedup_by_name():
    """nuclear_cleanup should keep newest job per name, delete duplicates."""
    from packages.scheduler.cleanup import nuclear_cleanup

    docs = [
        {"job_id": "j1", "name": "dup-task", "tags": ["agency"], "run_count": 0, "updated_at": "2026-01-01"},
        {"job_id": "j2", "name": "dup-task", "tags": ["agency"], "run_count": 0, "updated_at": "2026-01-02"},  # newest
        {"job_id": "j3", "name": "dup-task", "tags": ["agency"], "run_count": 0, "updated_at": "2026-01-03"},  # actually newest
        {"job_id": "j4", "name": "unique-task", "tags": [], "run_count": 0, "updated_at": "2026-01-01"},
    ]
    db = FakeDB(FakeScheduleCollection(docs))
    result = await nuclear_cleanup(db)
    # 3 docs with name "dup-task" → keep 1, delete 2
    assert result["deduped"] == 2


@pytest.mark.asyncio
async def test_nuclear_cleanup_returns_empty_when_no_schedules_collection():
    """nuclear_cleanup should gracefully handle a DB without a schedules collection."""
    from packages.scheduler.cleanup import nuclear_cleanup

    # Use a plain object that has no 'schedules' attribute — getattr returns None
    class EmptyDB:
        pass

    result = await nuclear_cleanup(EmptyDB())
    assert result["deleted_run_once"] == 0
    assert result["deleted_stuck"] == 0
    assert result["deduped"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# Issue 3: reconcile_stranded_tasks FAILED-task pass
# ─────────────────────────────────────────────────────────────────────────────

def test_reconcile_stranded_tasks_has_failed_task_pass():
    """reconcile_stranded_tasks source code must include a FAILED-task re-queue pass.

    Source-inspection test: verifies the third pass for FAILED tasks exists.
    """
    import tasks.store as store_mod
    src = inspect.getsource(store_mod.TaskStore.reconcile_stranded_tasks)
    # Must query for FAILED status
    assert "FAILED" in src or "TaskStatus.FAILED" in src
    # Must re-queue (set pending_agent_run=True + status=TODO)
    assert "pending_agent_run = True" in src
    assert "TaskStatus.TODO" in src
    # Must check auto_retry_count cap
    assert "auto_retry_cap" in src


# ─────────────────────────────────────────────────────────────────────────────
# Issue 2: TaskCoordinator timeout → re-queue (not hard-fail)
# ─────────────────────────────────────────────────────────────────────────────

def test_task_timeout_uses_requeue_not_hardfail():
    """tasks/service.py execute() must call _requeue_or_block_unavailable on TimeoutError.

    Source-inspection test: verifies asyncio.TimeoutError is treated as transient.
    """
    import tasks.service as svc_mod
    src = inspect.getsource(svc_mod.TaskExecutionCoordinator.execute)
    # Find the asyncio.TimeoutError except block
    assert "asyncio.TimeoutError" in src
    # The timeout handler must call _requeue_or_block_unavailable, NOT
    # self.workflow.transition(... TaskStatus.FAILED ...)
    timeout_block_start = src.index("except asyncio.TimeoutError:")
    # Find the next except or finally after the timeout block
    remaining = src[timeout_block_start:]
    lines = remaining.split("\n")
    block_lines = []
    for i, line in enumerate(lines[1:], 1):
        if line.strip().startswith("except ") or line.strip().startswith("finally:"):
            break
        block_lines.append(line)
    block_text = "\n".join(block_lines)
    assert "_requeue_or_block_unavailable" in block_text, (
        "asyncio.TimeoutError handler must call _requeue_or_block_unavailable, "
        "not hard-fail the task. Got: " + block_text
    )


def test_task_execution_timeout_default_is_600():
    """TASK_EXECUTION_TIMEOUT_SEC default must be 600 (was 300, too tight)."""
    import tasks.service as svc_mod
    src = inspect.getsource(svc_mod.TaskExecutionCoordinator.__init__)
    assert '"600"' in src or "'600'" in src, (
        "TASK_EXECUTION_TIMEOUT_SEC default should be 600s, not 300s"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Issue 1: chat agent-run budget default is 600s (was 240s)
# ─────────────────────────────────────────────────────────────────────────────

def test_chat_agent_run_budget_default_is_600():
    """CHAT_AGENT_RUN_BUDGET_SEC default must be 600 (was 240, too tight)."""
    import backend.server as srv
    # The module-level constant should be 600.0 when the env var is not set.
    # We check the source to avoid env-var interference.
    src = inspect.getsource(srv)
    assert '"600"' in src or "'600'" in src, (
        "CHAT_AGENT_RUN_BUDGET_SEC default should be 600s"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Issue 1: brain.py BRAIN_PREFERENCE=ollama guard
# ─────────────────────────────────────────────────────────────────────────────

def test_brain_resolver_has_ollama_preference_guard():
    """brain.py resolve_active_brain must skip stale cloud BrainConfig when BRAIN_PREFERENCE=ollama.

    Source-inspection test: verifies the guard exists.
    """
    import packages.ai.brain as brain_mod
    src = inspect.getsource(brain_mod.resolve_active_brain)
    assert "BRAIN_PREFERENCE" in src or "get_brain_preference" in src
    assert "ollama" in src.lower()
    # Must log a warning when ignoring stale config
    assert "ignoring persisted BrainConfig" in src or "log.warning" in src


# ─────────────────────────────────────────────────────────────────────────────
# Issue 4: SAM voice drops hardcoded model
# ─────────────────────────────────────────────────────────────────────────────

def test_sam_voice_does_not_hardcode_nvidia_model():
    """agent/sam.py call_llm must NOT pass model='meta/llama-3.3-70b-instruct'.

    Source-inspection test: verifies the hardcoded model was removed so
    call_llm resolves the active provider's default model (works for both
    NVIDIA NIM and Ollama).
    """
    import agent.sam as sam_mod
    src = inspect.getsource(sam_mod)
    # Find the call_llm invocation in the _generate_response method
    # It should NOT have model="meta/llama-3.3-70b-instruct"
    call_llm_section = src[src.index("call_llm"):]
    # Take the next 300 chars after call_llm to see the args
    args_section = call_llm_section[:400]
    assert 'model="meta/llama-3.3-70b-instruct"' not in args_section, (
        "SAM voice must NOT hardcode the NVIDIA model — it breaks when "
        "BRAIN_PREFERENCE=ollama. Let call_llm resolve the active provider's "
        "default model. Got: " + args_section[:200]
    )


# ─────────────────────────────────────────────────────────────────────────────
# Issue 5: schedule descriptions are populated
# ─────────────────────────────────────────────────────────────────────────────

def test_company_agency_create_passes_description():
    """services/company_agency.py scheduler.create must pass a description= kwarg."""
    import services.company_agency as ca_mod
    src = inspect.getsource(ca_mod)
    # Find the scheduler.create call
    assert "description=" in src, (
        "company_agency scheduler.create must pass description= so schedules "
        "have a human-readable label in the 2000+ list"
    )


def test_legacy_scheduler_create_passes_description():
    """backend/server.py legacy_scheduler_create must pass description= kwarg."""
    import backend.server as srv
    src = inspect.getsource(srv)
    # Find the legacy_scheduler_create function
    func_start = src.index("async def legacy_scheduler_create")
    func_end = src.index("\n\n", func_start)
    func_src = src[func_start:func_end]
    assert "description=" in func_src, (
        "legacy_scheduler_create must pass description= so schedules have a label"
    )
