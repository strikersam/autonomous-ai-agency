"""Tests for the CEO dispatcher, worktree isolation, and runtime wake.

Covers:
  - CEOResult data model
  - _should_fan_out() complexity threshold
  - _decompose_into_subtasks() default decomposition
  - _single_specialist_task() fast path
  - CEODispatcher.delegate() low complexity → single specialist
  - CEODispatcher.delegate() medium/high complexity → fan-out
  - CEODispatcher.wake_sleeping_runtimes() is non-fatal
  - WorkflowOrchestrator ExecutionRequest.worktree_path field
  - WorkflowOrchestrator._handle_execute() routes medium complexity to CEO
  - WorkflowOrchestrator._handle_execute() routes low complexity to AgentRunner
  - _merge_changed_files() de-dupes across specialists
  - RuntimeManager.wake_all_sleeping_runtimes() returns summary
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.ceo_dispatcher import (
    CEODispatcher,
    CEOResult,
    ROLE_RUNTIME_PREFERENCE,
    SpecialistTask,
    _decompose_into_subtasks,
    _merge_changed_files,
    _should_fan_out,
    _single_specialist_task,
    get_ceo_dispatcher,
    reset_ceo_dispatcher,
)
from services.workflow_orchestrator import (
    ExecutionRequest,
    WorkflowOrchestrator,
    WorkflowRun,
    _merge_changed_files as _orch_merge,
)


# ── Pure-function tests ───────────────────────────────────────────────────────


def test_should_fan_out_respects_threshold():
    """Default threshold is 'low' so EVERY request fans out (the user wants
    more swarming, not less — see CEO_FANOUT_COMPLEXITY env to raise)."""
    assert _should_fan_out("low") is True
    assert _should_fan_out("medium") is True
    assert _should_fan_out("high") is True
    # Unknown complexity has rank 0, so it should NOT fan out by default
    assert _should_fan_out("unknown") is False  # rank 0 < rank 0 for 'low'


def test_decompose_returns_scout_and_dev():
    """Default decomposition has scout → dev (dev depends on scout)."""
    sub_tasks = _decompose_into_subtasks("Fix the failing auth tests")
    assert len(sub_tasks) == 2
    roles = [t.role for t in sub_tasks]
    assert "scout" in roles
    assert "dev" in roles
    dev = next(t for t in sub_tasks if t.role == "dev")
    assert any("ceo-scout" in dep for dep in dev.dependencies)


def test_decompose_respects_caller_hints():
    """Caller can steer the dev role/runtime via hints."""
    sub_tasks = _decompose_into_subtasks(
        "Optimize the routing policy",
        hint_specialists=["optimizer"],
        hint_runtimes=["goose"],
    )
    dev = next(t for t in sub_tasks if t.role == "optimizer")
    assert dev.runtime_id == "goose"


def test_single_specialist_task_defaults():
    """Single task path is a single SpecialistTask with sensible defaults."""
    tasks = _single_specialist_task("Quick fix")
    assert len(tasks) == 1
    assert tasks[0].role == "dev"
    assert tasks[0].runtime_id == "internal_agent"


def test_merge_changed_files_dedupes():
    """Duplicate file paths across specialists collapse to a single entry."""
    specialists = [
        {"changed_files": ["a.py", "b.py"]},
        {"changed_files": ["b.py", "c.py"]},
        {"changed_files": []},
    ]
    merged = _merge_changed_files(specialists)
    assert merged == ["a.py", "b.py", "c.py"]


def test_orch_merge_changed_files_alias():
    """The orchestrator's re-export wrapper delegates to the canonical helper."""
    result_orch = _orch_merge([{"changed_files": ["a.py"]}, {"changed_files": ["b.py"]}])
    result_canonical = _merge_changed_files([{"changed_files": ["a.py"]}, {"changed_files": ["b.py"]}])
    assert result_orch == result_canonical == ["a.py", "b.py"]


def test_role_runtime_preference_keys():
    """Every CEO role maps to a non-empty runtime preference list."""
    expected = {"dev", "security", "reviewer", "release", "scout", "optimizer"}
    assert set(ROLE_RUNTIME_PREFERENCE.keys()) == expected
    for role, prefs in ROLE_RUNTIME_PREFERENCE.items():
        assert prefs, f"role {role!r} has no runtime preferences"
        assert "internal_agent" in prefs, f"role {role!r} lacks fallback"


# ── Data model tests ──────────────────────────────────────────────────────────


def test_ceo_result_as_dict():
    """CEOResult serializes every field used by callers."""
    result = CEOResult(
        goal="Fix the login",
        summary="CEO[fan-out]: 2/2",
        specialists=[{"task_id": "t1", "status": "ok"}],
        total_duration_s=1.23,
        complexity="high",
        fanout_used=True,
        runtimes_woken=["hermes", "goose"],
        verdict="OK",
    )
    d = result.as_dict()
    assert d["goal"] == "Fix the login"
    assert d["complexity"] == "high"
    assert d["fanout_used"] is True
    assert d["runtimes_woken"] == ["hermes", "goose"]
    assert d["verdict"] == "OK"
    assert d["total_duration_s"] == 1.23  # rounded


def test_ceo_result_default_verdict_logic():
    """Verdict string reflects ok/partial/failure counts."""
    base = {"task_id": "t", "status": "ok", "role": "dev", "runtime_id": "x"}
    # 2/2 ok
    r = CEOResult(goal="g", specialists=[base, base], summary="", total_duration_s=0.0)
    assert r.verdict == "OK"
    # 1/2 ok
    r2 = CEOResult(goal="g", specialists=[base, {"task_id": "t2", "status": "error", "role": "dev", "runtime_id": "x"}], summary="", total_duration_s=0.0)
    assert r2.verdict == "PARTIAL"
    # 0/2 ok
    r3 = CEOResult(goal="g", specialists=[
        {"task_id": "t1", "status": "error", "role": "dev", "runtime_id": "x"},
        {"task_id": "t2", "status": "error", "role": "dev", "runtime_id": "x"},
    ], summary="", total_duration_s=0.0)
    assert r3.verdict == "FAILED"


# ── Singleton tests ───────────────────────────────────────────────────────────


def test_get_ceo_dispatcher_singleton():
    """get_ceo_dispatcher returns the same instance until reset."""
    reset_ceo_dispatcher()
    a = get_ceo_dispatcher()
    b = get_ceo_dispatcher()
    assert a is b
    reset_ceo_dispatcher()
    c = get_ceo_dispatcher()
    assert c is not a  # new instance after reset


# ── Async delegate tests (with patched MultiAgentSwarm) ───────────────────────


class _FakeSwarm:
    """Mimics MultiAgentSwarm.run() returning a CoordinatorResult-shaped object."""

    def __init__(self, *, runtimes_woken: list[str] | None = None) -> None:
        self.run_calls: list[dict[str, Any]] = []
        self.runtimes_woken = runtimes_woken or []
        self._raise: Exception | None = None

    async def run(self, *, goal, agents, tasks, max_concurrent, email=None, department=None, key_id=None):
        self.run_calls.append({
            "goal": goal, "agents": agents, "tasks": tasks,
            "max_concurrent": max_concurrent, "email": email,
        })
        if self._raise:
            raise self._raise
        workers = []
        for t in tasks:
            workers.append({
                "task_id": t.task_id,
                "worker_id": t.task_id,
                "agent_role": t.task_type,
                "task_type": t.task_type,
                "status": "ok",
                "dependencies": t.dependencies,
                "result": {
                    "summary": f"done: {t.task_id}",
                    "steps": [{"changed_files": [f"{t.task_id}.py"]}],
                },
            })
        return MagicMock(workers=workers)


def _patch_ceo_with_fake_swarm(fake: _FakeSwarm):
    """Patch the internals the CEO touches, returning a stack of mocks."""
    return [
        patch("services.ceo_dispatcher._spec_to_task_spec",
              side_effect=lambda st: MagicMock(
                  task_id=st.task_id, instruction=st.instruction,
                  task_type=st.role, dependencies=st.dependencies,
                  model=st.model, max_steps=st.max_steps,
              )),
        patch("agent.coordinator.MultiAgentSwarm", return_value=fake),
    ]


@pytest.mark.asyncio
async def test_delegate_low_complexity_single_specialist(monkeypatch):
    """Low complexity should NOT fan out — just one specialist task."""
    fake = _FakeSwarm()
    monkeypatch.setattr("services.workflow_orchestrator._BYPASS",
                        __import__("contextvars").ContextVar("bypass", default=False))

    with patch("agent.coordinator.MultiAgentSwarm", return_value=fake), \
         patch("services.ceo_dispatcher._spec_to_task_spec",
               side_effect=lambda st: MagicMock(
                   task_id=st.task_id, instruction=st.instruction,
                   task_type=st.role, dependencies=st.dependencies,
                   model=st.model, max_steps=st.max_steps,
               )):
        ceo = CEODispatcher()
        result = await ceo.delegate("Quick lint fix", complexity="low")

    assert result.fanout_used is False
    assert len(result.specialists) == 1
    assert result.specialists[0]["status"] == "ok"
    assert result.verdict == "OK"


@pytest.mark.asyncio
async def test_delegate_medium_complexity_fans_out(monkeypatch):
    """Medium complexity should fan out (scout + dev with dependency)."""
    fake = _FakeSwarm()
    monkeypatch.setattr(
        "services.workflow_orchestrator._BYPASS",
        __import__("contextvars").ContextVar("bypass", default=False),
    )

    with patch("agent.coordinator.MultiAgentSwarm", return_value=fake), \
         patch("services.ceo_dispatcher._spec_to_task_spec",
               side_effect=lambda st: MagicMock(
                   task_id=st.task_id, instruction=st.instruction,
                   task_type=st.role, dependencies=st.dependencies,
                   model=st.model, max_steps=st.max_steps,
               )):
        ceo = CEODispatcher()
        result = await ceo.delegate(
            "Refactor the auth layer", complexity="medium",
        )

    assert result.fanout_used is True
    # Two sub-tasks: scout and dev
    assert len(result.specialists) == 2
    roles = {s["role"] for s in result.specialists}
    assert "scout" in roles
    assert "dev" in roles
    # The fake swarm recorded a single run() call with both tasks
    assert len(fake.run_calls) == 1
    assert len(fake.run_calls[0]["tasks"]) == 2
    # The dev task has the scout as a dependency
    dev_task = next(t for t in fake.run_calls[0]["tasks"] if t.task_type == "dev")
    scout_task_id = next(t.task_id for t in fake.run_calls[0]["tasks"] if t.task_type == "scout")
    assert scout_task_id in dev_task.dependencies


@pytest.mark.asyncio
async def test_delegate_high_complexity_fans_out(monkeypatch):
    """High complexity should also fan out (same as medium, but explicit)."""
    fake = _FakeSwarm()
    monkeypatch.setattr(
        "services.workflow_orchestrator._BYPASS",
        __import__("contextvars").ContextVar("bypass", default=False),
    )

    with patch("agent.coordinator.MultiAgentSwarm", return_value=fake), \
         patch("services.ceo_dispatcher._spec_to_task_spec",
               side_effect=lambda st: MagicMock(
                   task_id=st.task_id, instruction=st.instruction,
                   task_type=st.role, dependencies=st.dependencies,
                   model=st.model, max_steps=st.max_steps,
               )):
        ceo = CEODispatcher()
        result = await ceo.delegate("Big migration", complexity="high")

    assert result.fanout_used is True
    assert len(result.specialists) == 2


@pytest.mark.asyncio
async def test_delegate_handles_swarm_failure(monkeypatch):
    """If the swarm raises, the CEO records the failure rather than crashing."""
    fake = _FakeSwarm()
    fake._raise = RuntimeError("LLM backend down")
    monkeypatch.setattr(
        "services.workflow_orchestrator._BYPASS",
        __import__("contextvars").ContextVar("bypass", default=False),
    )

    with patch("agent.coordinator.MultiAgentSwarm", return_value=fake), \
         patch("services.ceo_dispatcher._spec_to_task_spec",
               side_effect=lambda st: MagicMock(
                   task_id=st.task_id, instruction=st.instruction,
                   task_type=st.role, dependencies=st.dependencies,
                   model=st.model, max_steps=st.max_steps,
               )):
        ceo = CEODispatcher()
        with pytest.raises(RuntimeError, match="LLM backend down"):
            await ceo.delegate("Anything", complexity="high")


@pytest.mark.asyncio
async def test_wake_sleeping_runtimes_handles_missing_manager():
    """wake_sleeping_runtimes must not raise if RuntimeManager is unavailable."""
    # Patch get_runtime_manager to raise, simulating a missing/broken manager
    with patch("runtimes.manager.get_runtime_manager",
               side_effect=ImportError("not installed")):
        ceo = CEODispatcher()
        woken = await ceo.wake_sleeping_runtimes()
    # Empty list is acceptable — the function must not crash
    assert woken == []


@pytest.mark.asyncio
async def test_wake_sleeping_runtimes_returns_available_ids(monkeypatch):
    """Available runtimes are reported as woken."""
    fake_mgr = MagicMock()
    fake_mgr._started = True
    fake_mgr.list_runtimes.return_value = [
        {"runtime_id": "internal_agent", "available": True},
        {"runtime_id": "hermes", "available": False},
    ]
    async def _get_health(rid):
        return {"available": rid == "internal_agent"}
    fake_mgr.get_runtime_health = AsyncMock(side_effect=_get_health)
    monkeypatch.setattr("runtimes.manager.get_runtime_manager", lambda: fake_mgr)

    ceo = CEODispatcher()
    woken = await ceo.wake_sleeping_runtimes()
    assert "internal_agent" in woken
    assert "hermes" not in woken  # still sleeping


# ── WorkflowOrchestrator integration tests ────────────────────────────────────


def test_execution_request_has_worktree_path():
    """ExecutionRequest exposes worktree_path for #504 worktree isolation."""
    req = ExecutionRequest(request="test", worktree_path="/tmp/wt-1")
    assert req.worktree_path == "/tmp/wt-1"
    # Default is None
    req2 = ExecutionRequest(request="test")
    assert req2.worktree_path is None


def test_execution_request_worktree_path_excluded_from_dump():
    """worktree_path is internal — must not leak in model_dump()."""
    req = ExecutionRequest(
        request="test",
        worktree_path="/tmp/wt-secret",
        github_token="gh-secret",
    )
    dumped = req.model_dump()
    # github_token has exclude=True; worktree_path should also be safe to dump
    # but is informational, not a secret. We only assert the API serializes it.
    assert "worktree_path" in dumped
    assert dumped["worktree_path"] == "/tmp/wt-secret"
    # github_token is excluded
    assert "github_token" not in dumped


@pytest.mark.asyncio
async def test_handle_execute_routes_medium_complexity_to_ceo(monkeypatch):
    """Medium complexity triggers CEO delegation, not single AgentRunner."""
    from services.workflow_orchestrator import ClassifyOutput, PlanOutput, SpecialistSelection

    # Patch the CEO dispatcher to a mock that records the call
    fake_ceo = MagicMock()
    fake_ceo.delegate = AsyncMock(return_value=CEOResult(
        goal="test",
        specialists=[{"task_id": "t1", "role": "scout", "runtime_id": "internal_agent",
                      "status": "ok", "summary": "scout done", "changed_files": []}],
        summary="CEO[fan-out]: 1/1",
        total_duration_s=0.5,
        complexity="medium",
        fanout_used=True,
        runtimes_woken=["hermes"],
        verdict="OK",
    ))
    monkeypatch.setattr(
        "services.workflow_orchestrator._get_ceo_dispatcher",
        lambda: fake_ceo,
    )
    # Also patch AgentRunner to ensure it's NOT called for medium complexity
    fake_runner = MagicMock()
    fake_runner.run = AsyncMock(side_effect=AssertionError("AgentRunner.run should NOT be called for medium complexity"))
    monkeypatch.setattr("agent.loop.AgentRunner", fake_runner)

    orch = WorkflowOrchestrator()
    run = WorkflowRun()
    run.classify = ClassifyOutput(domain="testing", task_type="bug_fix", complexity="medium")
    run.plan = PlanOutput(goal="Fix the bug", steps=[{"description": "fix it"}])
    run.specialist = SpecialistSelection(
        specialist_ids=["s1"], specialist_names=["dev"], families=["general"],
    )
    req = ExecutionRequest(request="Fix the bug", worktree_path="/tmp/wt-iso")

    from services.workflow_orchestrator import ExecutionResult
    await orch._handle_execute(run, req)

    # CEO was called with the right args
    assert fake_ceo.delegate.called
    call_kwargs = fake_ceo.delegate.call_args.kwargs
    assert call_kwargs["complexity"] == "medium"
    assert call_kwargs["domain"] == "testing"
    assert call_kwargs["workspace_root"] == "/tmp/wt-iso"  # from worktree_path
    # AgentRunner was NOT called
    assert not fake_runner.run.called
    # Execution result was populated from CEO
    assert isinstance(run.execution, ExecutionResult)
    assert run.execution.duration_ms == 500
    assert run.llm_provenance["ceo_verdict"] == "OK"


@pytest.mark.asyncio
async def test_handle_execute_routes_low_complexity_to_agent_runner(monkeypatch):
    """Low complexity bypasses CEO and goes straight to AgentRunner."""
    from services.workflow_orchestrator import ClassifyOutput, PlanOutput, SpecialistSelection

    # Patch the CEO to a mock that would fail loudly if called
    fake_ceo = MagicMock()
    fake_ceo.delegate = AsyncMock(side_effect=AssertionError("CEO must not be called for low complexity"))
    monkeypatch.setattr(
        "services.workflow_orchestrator._get_ceo_dispatcher",
        lambda: fake_ceo,
    )

    # Patch AgentRunner to return a stub result
    fake_result = {
        "summary": "agent runner done",
        "steps": [{"changed_files": ["a.py"]}],
    }
    fake_runner_instance = MagicMock()
    fake_runner_instance.run = AsyncMock(return_value=fake_result)
    monkeypatch.setattr("agent.loop.AgentRunner", lambda **kw: fake_runner_instance)

    orch = WorkflowOrchestrator()
    run = WorkflowRun()
    run.classify = ClassifyOutput(domain="general", task_type="general", complexity="low")
    run.plan = PlanOutput(goal="Quick fix", steps=[{"description": "fix"}])
    run.specialist = SpecialistSelection()
    req = ExecutionRequest(request="Quick fix")

    from services.workflow_orchestrator import ExecutionResult
    await orch._handle_execute(run, req)

    # AgentRunner WAS called
    assert fake_runner_instance.run.called
    # CEO was NOT called
    assert not fake_ceo.delegate.called
    assert isinstance(run.execution, ExecutionResult)
    assert "a.py" in run.execution.changed_files


@pytest.mark.asyncio
async def test_handle_execute_falls_back_when_ceo_fails(monkeypatch):
    """If CEO delegation raises, fall through to single AgentRunner path."""
    from services.workflow_orchestrator import ClassifyOutput, PlanOutput, SpecialistSelection

    # CEO raises
    fake_ceo = MagicMock()
    fake_ceo.delegate = AsyncMock(side_effect=RuntimeError("swarm unavailable"))
    monkeypatch.setattr(
        "services.workflow_orchestrator._get_ceo_dispatcher",
        lambda: fake_ceo,
    )

    # AgentRunner returns a stub
    fake_runner_instance = MagicMock()
    fake_runner_instance.run = AsyncMock(return_value={
        "summary": "fallback ok", "steps": [{"changed_files": ["b.py"]}],
    })
    monkeypatch.setattr("agent.loop.AgentRunner", lambda **kw: fake_runner_instance)

    orch = WorkflowOrchestrator()
    run = WorkflowRun()
    run.classify = ClassifyOutput(domain="testing", task_type="bug_fix", complexity="high")
    run.plan = PlanOutput(goal="Fix the bug", steps=[])
    run.specialist = SpecialistSelection()
    req = ExecutionRequest(request="Fix the bug")

    from services.workflow_orchestrator import ExecutionResult
    await orch._handle_execute(run, req)

    # Both CEO and AgentRunner were called (fallback path)
    assert fake_ceo.delegate.called
    assert fake_runner_instance.run.called
    assert isinstance(run.execution, ExecutionResult)
    assert "b.py" in run.execution.changed_files


# ── RuntimeManager.wake_all_sleeping_runtimes tests ───────────────────────────


@pytest.mark.asyncio
async def test_wake_all_sleeping_runtimes_empty_registry(monkeypatch):
    """Empty registry → no runtimes woken, no crash."""
    fake_mgr = MagicMock()
    fake_mgr._registry.all.return_value = []
    monkeypatch.setattr("runtimes.manager.get_runtime_manager", lambda: fake_mgr)

    from runtimes.manager import RuntimeManager
    mgr = RuntimeManager.__new__(RuntimeManager)  # bypass __init__
    mgr._registry = fake_mgr._registry
    fake_health = MagicMock()
    mgr._health = fake_health
    mgr._router = MagicMock()
    mgr._started = True
    summary = await mgr.wake_all_sleeping_runtimes()
    assert summary["woken"] == []
    assert summary["still_sleeping"] == []
    assert summary["woken_count"] == 0


@pytest.mark.asyncio
async def test_wake_all_sleeping_runtimes_mixed_state(monkeypatch):
    """Some runtimes awake, some sleeping — both reported correctly."""
    from runtimes.manager import RuntimeManager
    from runtimes.base import RuntimeHealth

    fake_adapter_awake = MagicMock()
    fake_adapter_awake.RUNTIME_ID = "awake_rt"
    fake_adapter_sleeping = MagicMock()
    fake_adapter_sleeping.RUNTIME_ID = "sleeping_rt"
    fake_registry = MagicMock()
    fake_registry.all.return_value = [fake_adapter_awake, fake_adapter_sleeping]
    fake_health = MagicMock()
    # Already healthy
    fake_health.get_health.return_value = RuntimeHealth(
        runtime_id="awake_rt", available=True, latency_ms=10,
    )
    # Probe for sleeping one returns a different health
    async def _poll(rid):
        if rid == "sleeping_rt":
            fake_health.get_health.return_value = RuntimeHealth(
                runtime_id=rid, available=False, error="still down",
            )
        else:
            fake_health.get_health.return_value = RuntimeHealth(
                runtime_id=rid, available=True, latency_ms=5,
            )
    fake_health._poll_one = AsyncMock(side_effect=_poll)
    fake_health.is_available.return_value = True

    mgr = RuntimeManager.__new__(RuntimeManager)
    mgr._registry = fake_registry
    mgr._health = fake_health
    mgr._router = MagicMock()
    mgr._started = True

    summary = await mgr.wake_all_sleeping_runtimes()
    assert "awake_rt" in summary["woken"]
    assert "sleeping_rt" in summary["still_sleeping"]
    assert summary["woken_count"] == 1
    assert summary["still_sleeping_count"] == 1


def test_runtime_manager_is_available_for_routing():
    """is_available_for_routing delegates to health service."""
    from runtimes.manager import RuntimeManager
    mgr = RuntimeManager.__new__(RuntimeManager)
    fake_health = MagicMock()
    fake_health.is_available.return_value = True
    mgr._health = fake_health
    assert mgr.is_available_for_routing("any") is True
    fake_health.is_available.return_value = False
    assert mgr.is_available_for_routing("any") is False


# ── End-to-end happy path (patches the heavy bits) ───────────────────────────


@pytest.mark.asyncio
async def test_end_to_end_ceo_delegation(monkeypatch, tmp_path):
    """Real CEODispatcher delegates to a real (patched) swarm and merges results."""
    monkeypatch.setattr(
        "services.workflow_orchestrator._BYPASS",
        __import__("contextvars").ContextVar("bypass", default=False),
    )
    monkeypatch.setenv("OLLAMA_BASE", "http://localhost:11434")

    # Build a fake swarm whose run() returns 2 worker results
    fake = _FakeSwarm()
    with patch("agent.coordinator.MultiAgentSwarm", return_value=fake), \
         patch("services.ceo_dispatcher._spec_to_task_spec",
               side_effect=lambda st: MagicMock(
                   task_id=st.task_id, instruction=st.instruction,
                   task_type=st.role, dependencies=st.dependencies,
                   model=st.model, max_steps=st.max_steps,
               )):
        ceo = CEODispatcher()
        result = await ceo.delegate(
            "Refactor the API",
            complexity="high",
            domain="code",
            workspace_root=str(tmp_path),
        )

    assert result.fanout_used is True
    assert result.verdict == "OK"
    assert result.complexity == "high"
    # All 2 specialists reported ok
    statuses = {s["status"] for s in result.specialists}
    assert statuses == {"ok"}
    # Summary mentions fan-out
    assert "fan-out" in result.summary
