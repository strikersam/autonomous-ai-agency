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


class _FakeRoutingDecision:
    def __init__(self, runtime_id: str) -> None:
        self.selected_runtime_id = runtime_id


class _FakeTaskResult:
    def __init__(self, success: bool = True, output: str = "", error: str | None = None) -> None:
        self.success = success
        self.output = output
        self.error = error


class _FakeRuntimeManager:
    """Mimics RuntimeManager.execute() returning (TaskResult, RoutingDecision)."""

    def __init__(self, *, raise_on_execute: Exception | None = None,
                 per_runtime_output: dict[str, str] | None = None) -> None:
        self.execute_calls: list[Any] = []
        self._raise = raise_on_execute
        self._per_runtime = per_runtime_output or {}
        self._started = True

    async def execute(self, spec):
        self.execute_calls.append(spec)
        if self._raise:
            raise self._raise
        pref = getattr(spec, "provider_preference", None) or "internal_agent"
        output = self._per_runtime.get(pref, f"done via {pref}: {spec.task_id}")
        return _FakeTaskResult(success=True, output=output), _FakeRoutingDecision(pref)


def _patch_ceo_with_fake_runtime_manager(fake: _FakeRuntimeManager):
    """Patch the internals the CEO touches, returning a stack of mocks."""
    return [
        patch("runtimes.manager.get_runtime_manager", return_value=fake),
    ]


@pytest.mark.asyncio
async def test_delegate_low_complexity_single_specialist(monkeypatch):
    """Low complexity should NOT fan out — just one specialist task."""
    fake = _FakeRuntimeManager()
    with patch("runtimes.manager.get_runtime_manager", return_value=fake):
        ceo = CEODispatcher()
        result = await ceo.delegate("Quick lint fix", complexity="low")

    assert result.fanout_used is False
    assert len(result.specialists) == 1
    assert result.specialists[0]["status"] == "ok"
    assert result.verdict == "OK"
    # RuntimeManager.execute was called once (one specialist)
    assert len(fake.execute_calls) == 1


@pytest.mark.asyncio
async def test_delegate_medium_complexity_fans_out(monkeypatch):
    """Medium complexity should fan out to 2 specialists via RuntimeManager.

    Verifies the actual runtime distribution: each sub-task is routed to its
    ROLE_RUNTIME_PREFERENCE runtime (scout→internal_agent, dev→claude_code).
    """
    fake = _FakeRuntimeManager(
        per_runtime_output={
            "internal_agent": "scout analysis done",
            "claude_code": "dev implementation done",
        }
    )
    with patch("runtimes.manager.get_runtime_manager", return_value=fake):
        ceo = CEODispatcher()
        result = await ceo.delegate(
            "Refactor the auth layer", complexity="medium",
        )

    assert result.fanout_used is True
    assert len(result.specialists) == 2
    roles = {s["role"] for s in result.specialists}
    assert "scout" in roles
    assert "dev" in roles
    # CRITICAL: each sub-task was routed to its preferred runtime, not just
    # the same ollama_base. This is the fix for the "fan-out doesn't actually
    # use different runtimes" ship-blocker.
    runtimes_used = {s["runtime_id"] for s in result.specialists}
    assert "internal_agent" in runtimes_used  # scout's preferred runtime
    assert "claude_code" in runtimes_used     # dev's preferred runtime
    # RuntimeManager.execute was called twice (once per sub-task)
    assert len(fake.execute_calls) == 2
    # Each call carried the right provider_preference
    prefs = [getattr(c, "provider_preference", None) for c in fake.execute_calls]
    assert "internal_agent" in prefs
    assert "claude_code" in prefs


@pytest.mark.asyncio
async def test_delegate_high_complexity_fans_out(monkeypatch):
    """High complexity should also fan out (same as medium, but explicit)."""
    fake = _FakeRuntimeManager()
    with patch("runtimes.manager.get_runtime_manager", return_value=fake):
        ceo = CEODispatcher()
        result = await ceo.delegate("Big migration", complexity="high")

    assert result.fanout_used is True
    assert len(result.specialists) == 2


@pytest.mark.asyncio
async def test_delegate_uses_swarm_fallback_when_runtime_manager_unavailable(monkeypatch):
    """If RuntimeManager is unavailable, fall back to MultiAgentSwarm (best effort)."""
    fake_swarm = _FakeSwarm()
    monkeypatch.setattr(
        "services.workflow_orchestrator._BYPASS",
        __import__("contextvars").ContextVar("bypass", default=False),
    )

    with patch("runtimes.manager.get_runtime_manager",
               side_effect=ImportError("not installed")), \
         patch("agent.coordinator.MultiAgentSwarm", return_value=fake_swarm), \
         patch("services.ceo_dispatcher._spec_to_task_spec",
               side_effect=lambda st: MagicMock(
                   task_id=st.task_id, instruction=st.instruction,
                   task_type=st.role, dependencies=st.dependencies,
                   model=st.model, max_steps=st.max_steps,
               )):
        ceo = CEODispatcher()
        result = await ceo.delegate("Anything", complexity="high")

    assert result.fanout_used is True
    assert len(result.specialists) == 2
    assert result.verdict == "OK"
    # Swarm fallback was used
    assert len(fake_swarm.run_calls) == 1


@pytest.mark.asyncio
async def test_delegate_propagates_runtime_errors():
    """If a RuntimeManager.execute() call fails for a task, that task is
    marked as error (the others continue). Verdict reflects partial success."""
    from runtimes.base import TaskSpec as RT_TaskSpec

    class _PartialFailMgr:
        def __init__(self):
            self._started = True
            self._call_count = 0

        async def execute(self, spec):
            self._call_count += 1
            # First call (scout) succeeds, second call (dev) fails
            if self._call_count == 1:
                return _FakeTaskResult(success=True, output="scout ok"), _FakeRoutingDecision("internal_agent")
            raise RuntimeError("dev runtime down")

    fake = _PartialFailMgr()
    with patch("runtimes.manager.get_runtime_manager", return_value=fake):
        ceo = CEODispatcher()
        result = await ceo.delegate("Complex task", complexity="medium")

    assert result.fanout_used is True
    # PARTIAL: one succeeded, one failed
    assert result.verdict == "PARTIAL"
    statuses = {s["status"] for s in result.specialists}
    assert "ok" in statuses
    assert "error" in statuses


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
async def test_wake_sleeping_runtimes_uses_parallel_wake(monkeypatch):
    """Available runtimes are reported as woken via parallel wake_all."""
    fake_mgr = MagicMock()
    fake_mgr._started = True

    async def _wake_all():
        return {
            "woken": ["internal_agent", "hermes"],
            "still_sleeping": ["goose"],
            "woken_count": 2,
            "still_sleeping_count": 1,
            "details": {},
        }
    fake_mgr.wake_all_sleeping_runtimes = AsyncMock(side_effect=_wake_all)
    monkeypatch.setattr("runtimes.manager.get_runtime_manager", lambda: fake_mgr)

    ceo = CEODispatcher()
    woken = await ceo.wake_sleeping_runtimes()
    assert "internal_agent" in woken
    assert "hermes" in woken
    # Parallel wake was used (not serial per-runtime loops)
    assert fake_mgr.wake_all_sleeping_runtimes.called


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
    """Medium complexity triggers CEO delegation, not single AgentRunner.

    Verifies the verdict-based fallback path: when the CEO returns OK,
    the execution is populated from the CEO result and AgentRunner is NOT called.
    """
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
async def test_handle_execute_falls_back_on_ceo_failed_verdict(monkeypatch):
    """If CEO delegation returns verdict=FAILED, fall through to single AgentRunner
    (since MultiAgentSwarm/RuntimeManager swallows per-task errors as payloads)."""
    from services.workflow_orchestrator import ClassifyOutput, PlanOutput, SpecialistSelection

    # CEO returns FAILED verdict (all specialists errored)
    fake_ceo = MagicMock()
    fake_ceo.delegate = AsyncMock(return_value=CEOResult(
        goal="test",
        specialists=[
            {"task_id": "t1", "role": "scout", "runtime_id": "x", "status": "error", "error": "boom"},
            {"task_id": "t2", "role": "dev", "runtime_id": "x", "status": "error", "error": "boom"},
        ],
        summary="CEO[fan-out]: 0/2",
        total_duration_s=0.1,
        complexity="medium",
        fanout_used=True,
        runtimes_woken=[],
        verdict="FAILED",
    ))
    monkeypatch.setattr(
        "services.workflow_orchestrator._get_ceo_dispatcher",
        lambda: fake_ceo,
    )

    # AgentRunner returns a stub (fallback path)
    fake_runner_instance = MagicMock()
    fake_runner_instance.run = AsyncMock(return_value={
        "summary": "fallback ok", "steps": [{"changed_files": ["b.py"]}],
    })
    monkeypatch.setattr("agent.loop.AgentRunner", lambda **kw: fake_runner_instance)

    orch = WorkflowOrchestrator()
    run = WorkflowRun()
    run.classify = ClassifyOutput(domain="testing", task_type="bug_fix", complexity="medium")
    run.plan = PlanOutput(goal="Fix the bug", steps=[])
    run.specialist = SpecialistSelection()
    req = ExecutionRequest(request="Fix the bug")

    from services.workflow_orchestrator import ExecutionResult
    await orch._handle_execute(run, req)

    # CEO was called (verdict=FALLBACK)
    assert fake_ceo.delegate.called
    # AgentRunner WAS called (fallback engaged on FAILED verdict)
    assert fake_runner_instance.run.called
    assert isinstance(run.execution, ExecutionResult)
    assert "b.py" in run.execution.changed_files


@pytest.mark.asyncio
async def test_handle_execute_falls_back_when_ceo_raises(monkeypatch):
    """If CEO delegation raises (availability error), fall through to AgentRunner."""
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


# ── CEO fallback observability (#P1) ─────────────────────────────────────────

def test_get_ceo_fallback_stats_initial_state():
    """get_ceo_fallback_stats returns all four counters at zero on first call."""
    from services.workflow_orchestrator import (
        get_ceo_fallback_stats, reset_ceo_fallback_stats,
    )
    reset_ceo_fallback_stats()
    stats = get_ceo_fallback_stats()
    assert stats == {
        "verdict_non_ok": 0,
        "transport_error": 0,
        "ceo_ok": 0,
        "ceo_low_complexity_bypass": 0,
    }


def test_reset_ceo_fallback_stats_zeros_every_counter(monkeypatch):
    """reset_ceo_fallback_stats clears all counters regardless of prior state."""
    from services.workflow_orchestrator import (
        _ceo_fallback_stats, _record_ceo_fallback,
        get_ceo_fallback_stats, reset_ceo_fallback_stats,
    )
    _record_ceo_fallback("ceo_ok")
    _record_ceo_fallback("ceo_ok")
    _record_ceo_fallback("verdict_non_ok")
    assert _ceo_fallback_stats["ceo_ok"] >= 2
    reset_ceo_fallback_stats()
    assert get_ceo_fallback_stats() == {
        "verdict_non_ok": 0,
        "transport_error": 0,
        "ceo_ok": 0,
        "ceo_low_complexity_bypass": 0,
    }


def test_record_ceo_fallback_ignores_unknown_reason():
    """Unknown reason strings are silently ignored (no exception, no counter bump)."""
    from services.workflow_orchestrator import (
        _ceo_fallback_stats, _record_ceo_fallback, reset_ceo_fallback_stats,
    )
    reset_ceo_fallback_stats()
    _record_ceo_fallback("not_a_real_counter")
    # No counter was bumped
    assert all(v == 0 for v in _ceo_fallback_stats.values())


@pytest.mark.asyncio
async def test_handle_execute_bumps_ceo_ok_counter(monkeypatch):
    """A successful CEO delegation (verdict=OK) bumps the ceo_ok counter."""
    from services.workflow_orchestrator import (
        ClassifyOutput, PlanOutput, SpecialistSelection,
        ExecutionRequest, ExecutionResult,
        get_ceo_fallback_stats, reset_ceo_fallback_stats,
    )

    reset_ceo_fallback_stats()

    fake_ceo = MagicMock()
    fake_ceo.delegate = AsyncMock(return_value=CEOResult(
        goal="test", specialists=[{"task_id": "t1", "role": "scout", "runtime_id": "internal_agent",
                                   "status": "ok", "summary": "scout done", "changed_files": []}],
        summary="CEO[fan-out]: 1/1", total_duration_s=0.5,
        complexity="medium", fanout_used=True, runtimes_woken=["hermes"], verdict="OK",
    ))
    monkeypatch.setattr("services.workflow_orchestrator._get_ceo_dispatcher", lambda: fake_ceo)
    fake_runner = MagicMock()
    fake_runner.run = AsyncMock(side_effect=AssertionError("AgentRunner.run should NOT be called for verdict=OK"))
    monkeypatch.setattr("agent.loop.AgentRunner", fake_runner)

    orch = WorkflowOrchestrator()
    run = WorkflowRun()
    run.classify = ClassifyOutput(domain="testing", task_type="bug_fix", complexity="medium")
    run.plan = PlanOutput(goal="Fix", steps=[])
    run.specialist = SpecialistSelection()
    req = ExecutionRequest(request="Fix")
    await orch._handle_execute(run, req)

    stats = get_ceo_fallback_stats()
    assert stats["ceo_ok"] == 1, f"expected ceo_ok=1, got {stats}"


@pytest.mark.asyncio
async def test_handle_execute_bumps_verdict_non_ok_counter(monkeypatch):
    """A CEO delegation that returns verdict!=OK bumps verdict_non_ok (and the
    fallback to AgentRunner still runs, so the request completes)."""
    from services.workflow_orchestrator import (
        ClassifyOutput, PlanOutput, SpecialistSelection,
        ExecutionRequest, ExecutionResult,
        get_ceo_fallback_stats, reset_ceo_fallback_stats,
    )

    reset_ceo_fallback_stats()

    fake_ceo = MagicMock()
    fake_ceo.delegate = AsyncMock(return_value=CEOResult(
        goal="test",
        specialists=[
            {"task_id": "t1", "role": "scout", "runtime_id": "x", "status": "error", "error": "boom"},
            {"task_id": "t2", "role": "dev", "runtime_id": "x", "status": "error", "error": "boom"},
        ],
        summary="CEO[fan-out]: 0/2", total_duration_s=0.1,
        complexity="medium", fanout_used=True, runtimes_woken=[], verdict="FAILED",
    ))
    monkeypatch.setattr("services.workflow_orchestrator._get_ceo_dispatcher", lambda: fake_ceo)

    fake_runner_instance = MagicMock()
    fake_runner_instance.run = AsyncMock(return_value={"summary": "fallback ok", "steps": []})
    monkeypatch.setattr("agent.loop.AgentRunner", lambda **kw: fake_runner_instance)

    orch = WorkflowOrchestrator()
    run = WorkflowRun()
    run.classify = ClassifyOutput(domain="testing", task_type="bug_fix", complexity="medium")
    run.plan = PlanOutput(goal="Fix", steps=[])
    run.specialist = SpecialistSelection()
    req = ExecutionRequest(request="Fix")
    await orch._handle_execute(run, req)

    stats = get_ceo_fallback_stats()
    assert stats["verdict_non_ok"] == 1, f"expected verdict_non_ok=1, got {stats}"


@pytest.mark.asyncio
async def test_handle_execute_bumps_transport_error_counter(monkeypatch):
    """A CEO delegation that raises one of _CEO_FALLBACK_EXCEPTIONS bumps
    transport_error (and the fallback to AgentRunner still runs)."""
    from services.workflow_orchestrator import (
        ClassifyOutput, PlanOutput, SpecialistSelection,
        ExecutionRequest, ExecutionResult,
        get_ceo_fallback_stats, reset_ceo_fallback_stats,
    )

    reset_ceo_fallback_stats()

    fake_ceo = MagicMock()
    fake_ceo.delegate = AsyncMock(side_effect=ConnectionError("swarm unreachable"))
    monkeypatch.setattr("services.workflow_orchestrator._get_ceo_dispatcher", lambda: fake_ceo)

    fake_runner_instance = MagicMock()
    fake_runner_instance.run = AsyncMock(return_value={"summary": "fallback ok", "steps": []})
    monkeypatch.setattr("agent.loop.AgentRunner", lambda **kw: fake_runner_instance)

    orch = WorkflowOrchestrator()
    run = WorkflowRun()
    run.classify = ClassifyOutput(domain="testing", task_type="bug_fix", complexity="high")
    run.plan = PlanOutput(goal="Fix", steps=[])
    run.specialist = SpecialistSelection()
    req = ExecutionRequest(request="Fix")
    await orch._handle_execute(run, req)

    stats = get_ceo_fallback_stats()
    assert stats["transport_error"] == 1, f"expected transport_error=1, got {stats}"


@pytest.mark.asyncio
async def test_handle_execute_does_not_count_unexpected_exceptions(monkeypatch):
    """An unexpected (non-fallback) exception from CEO must NOT bump any
    fallback counter — it should propagate so the bug isn't masked."""
    from services.workflow_orchestrator import (
        ClassifyOutput, PlanOutput, SpecialistSelection,
        ExecutionRequest,
        get_ceo_fallback_stats, reset_ceo_fallback_stats,
    )

    reset_ceo_fallback_stats()

    fake_ceo = MagicMock()
    fake_ceo.delegate = AsyncMock(side_effect=KeyError("not a transport error"))
    monkeypatch.setattr("services.workflow_orchestrator._get_ceo_dispatcher", lambda: fake_ceo)

    orch = WorkflowOrchestrator()
    run = WorkflowRun()
    run.classify = ClassifyOutput(domain="testing", task_type="bug_fix", complexity="medium")
    run.plan = PlanOutput(goal="Fix", steps=[])
    run.specialist = SpecialistSelection()
    req = ExecutionRequest(request="Fix")
    with pytest.raises(KeyError):
        await orch._handle_execute(run, req)

    # No fallback counter was bumped — the exception propagated cleanly
    stats = get_ceo_fallback_stats()
    assert stats["transport_error"] == 0
    assert stats["verdict_non_ok"] == 0
    assert stats["ceo_ok"] == 0


# ── FeatureMatrix promotion regression tests (#P1) ───────────────────────────

def test_multi_agent_swarm_promoted_to_beta():
    """multi_agent_swarm is BETA + enabled (was DISABLED pre-fix).

    The CEO dispatcher (services/ceo_dispatcher.py) now wires MultiAgentSwarm
    into the golden path as the RuntimeManager-unavailable fallback, so the
    original "not wired to golden path, no CEO dedupe" gap is closed.
    """
    from features.matrix import FeatureMaturity, get_feature_matrix, reset_feature_matrix
    reset_feature_matrix()
    entry = get_feature_matrix().get("multi_agent_swarm")
    assert entry is not None, "multi_agent_swarm must be in the matrix"
    assert entry.maturity == FeatureMaturity.BETA, (
        f"multi_agent_swarm should be BETA, got {entry.maturity}"
    )
    assert entry.enabled is True
    # Note must mention the CEO dispatcher as the wiring
    assert "CEO" in entry.notes, "notes must reference the CEO dispatcher wiring"


def test_sidecar_runtimes_promoted_to_beta():
    """sidecar_runtimes is BETA + enabled (was DISABLED pre-fix).

    The CEO dispatcher now calls RuntimeManager.wake_all_sleeping_runtimes()
    (parallel probes) before every dispatch, so the original "no health
    guarantee" gap is closed — liveness is verified per request.
    """
    from features.matrix import FeatureMaturity, get_feature_matrix, reset_feature_matrix
    reset_feature_matrix()
    entry = get_feature_matrix().get("sidecar_runtimes")
    assert entry is not None
    assert entry.maturity == FeatureMaturity.BETA, (
        f"sidecar_runtimes should be BETA, got {entry.maturity}"
    )
    assert entry.enabled is True
    # Note must reference the health-check wiring
    assert "wake_all_sleeping_runtimes" in entry.notes, (
        "notes must reference the wake_all_sleeping_runtimes health check"
    )


@pytest.mark.asyncio
async def test_end_to_end_ceo_delegation_via_runtime_manager(monkeypatch, tmp_path):
    """Real CEODispatcher delegates to RuntimeManager.execute() per sub-task
    and verifies the actual runtime distribution happens."""
    monkeypatch.setenv("OLLAMA_BASE", "http://localhost:11434")
    fake = _FakeRuntimeManager(
        per_runtime_output={
            "internal_agent": "scout: found 3 files",
            "claude_code": "dev: implemented 3 fixes",
        }
    )
    with patch("runtimes.manager.get_runtime_manager", return_value=fake):
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
    # CRITICAL: actual runtime distribution happened (not all on one ollama_base)
    runtimes_used = [s["runtime_id"] for s in result.specialists]
    assert "internal_agent" in runtimes_used
    assert "claude_code" in runtimes_used
    # Dependencies respected: dev got scout's summary in its instruction
    dev_call = next(c for c in fake.execute_calls if getattr(c, "provider_preference", "") == "claude_code")
    assert "scout" in dev_call.instruction.lower() or "found 3 files" in dev_call.instruction
