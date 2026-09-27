"""Free-model speed and timeout handling.

Two failure modes made agency tasks on free providers time out at
``TASK_EXECUTION_TIMEOUT_SEC`` (600s) with nothing to show:

1. Nemotron 3 — the default free NVIDIA brain — thinks by default, which
   multiplies every call's latency. ``with_nemotron_thinking_off`` turns it off
   unless the ``NEMOTRON_THINKING`` control says otherwise.
2. The agent loop's own time budget defaulted to off, so the coordinator's
   ``asyncio.wait_for`` cancelled the run mid-step and every finished step was
   lost. The coordinator now hands down a ``time_budget_deadline``.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time as real_time
from pathlib import Path
from typing import Any

import pytest

import agent.loop as loop_mod
from agent.loop import AgentRunner
from agent.models import AgentPlan
from packages.ai.router import with_nemotron_thinking_off
from packages.config import control_overrides
from tasks.models import Task
from tasks.service import TaskExecutionCoordinator


@pytest.fixture
def clean_overrides():
    applied_before = dict(control_overrides._applied)
    yield
    control_overrides.apply_overrides({})
    control_overrides._applied.clear()
    control_overrides._applied.update(applied_before)


# ── 1. Nemotron thinking off ─────────────────────────────────────────────────


def test_nemotron3_gets_thinking_disabled_by_default(clean_overrides):
    control_overrides.apply_overrides({})
    payload = {"model": "nvidia/nemotron-3-super-120b-a12b", "messages": []}
    out = with_nemotron_thinking_off(payload)
    assert out["chat_template_kwargs"] == {"enable_thinking": False}
    assert "chat_template_kwargs" not in payload  # caller's dict is not mutated


@pytest.mark.parametrize(
    "model",
    ["openai/gpt-oss-120b", "mistralai/mistral-nemotron", "nvidia/llama-3.3-nemotron-super-49b-v1", ""],
)
def test_other_models_are_untouched(model: str):
    payload = {"model": model, "messages": []}
    assert with_nemotron_thinking_off(payload) is payload


def test_caller_supplied_template_kwargs_win():
    payload = {
        "model": "nvidia/nemotron-3-super-120b-a12b",
        "chat_template_kwargs": {"enable_thinking": True},
    }
    assert with_nemotron_thinking_off(payload) is payload


def test_platform_control_override_turns_thinking_back_on(clean_overrides):
    control_overrides.apply_overrides({"NEMOTRON_THINKING": "true"})
    payload = {"model": "nvidia/nemotron-3-super-120b-a12b"}
    assert with_nemotron_thinking_off(payload) is payload

    control_overrides.apply_overrides({"NEMOTRON_THINKING": "false"})
    assert "chat_template_kwargs" in with_nemotron_thinking_off(payload)


# ── 2. Time budget handed down from the coordinator ──────────────────────────


def test_build_spec_passes_time_budget_below_the_hard_timeout():
    class _Store:
        async def get(self, _id):
            return None

        async def update(self, _t):
            pass

    coord = TaskExecutionCoordinator(
        store=_Store(),
        agent_store=None,
        runtime_manager=None,
        workspace_root=os.path.join(tempfile.gettempdir(), "test-workspace"),  # nosec B108
        execution_timeout_s=600,
    )
    before = real_time.time()
    spec = coord._build_spec(Task(owner_id="u", title="t"), agent=None)
    assert spec.context["time_budget_deadline"] == pytest.approx(before + 540, abs=5)


def test_budget_shrinks_across_runtime_retries():
    """The deadline is absolute: a retry on a fallback runtime gets what is left."""
    from runtimes.adapters.internal_agent import _remaining_budget_s

    now = real_time.time()
    assert _remaining_budget_s({"time_budget_deadline": now + 300}) == pytest.approx(300, abs=2)
    assert _remaining_budget_s({"time_budget_deadline": now - 50}) == 1.0
    assert _remaining_budget_s({"time_budget_s": 120}) == 120.0
    assert _remaining_budget_s({}) is None


def test_nvidia_attempts_are_capped_below_the_request_budget():
    from packages.llm.config import reload_config

    cfg = reload_config()
    assert cfg.providers["nvidia"].timeout_sec == 60


class _FakeClock:
    """Stand-in for the ``time`` module inside agent.loop with a manual perf_counter."""

    def __init__(self) -> None:
        self.now = 0.0

    def perf_counter(self) -> float:
        return self.now

    def __getattr__(self, name: str) -> Any:
        return getattr(real_time, name)


def _run_with_budget(tmp_path: Path, monkeypatch, budget: float | None) -> dict[str, Any]:
    clock = _FakeClock()
    monkeypatch.setattr(loop_mod, "time", clock)
    root = tmp_path / "repo"
    root.mkdir()
    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)
    plan = AgentPlan.model_validate({
        "goal": "Three slow steps",
        "steps": [
            {"id": i, "description": f"step {i}", "files": ["shared.py"], "type": "edit"}
            for i in (1, 2, 3)
        ],
    })

    async def fake_plan(*_a: Any, **_k: Any) -> AgentPlan:
        return plan

    async def fake_step(_goal: str, step: dict[str, Any], *_a: Any, **_k: Any) -> dict[str, Any]:
        clock.now += 30.0  # each step takes 30s of "wall clock"
        return {"step_id": step["id"], "status": "applied", "changed_files": [], "issues": []}

    async def fake_chat_text(_model: str, _messages: list[dict[str, str]]) -> str:
        return '{"verdict":"APPROVED","security":"PASS","correctness":"PASS","notes":""}'

    runner._generate_plan = fake_plan  # type: ignore[method-assign]
    runner._execute_step = fake_step  # type: ignore[method-assign]
    runner._chat_text = fake_chat_text  # type: ignore[method-assign]
    return asyncio.run(runner.run(
        instruction="go", history=[], requested_model=None,
        auto_commit=False, max_steps=5, time_budget_s=budget,
    ))


def test_runner_stops_before_a_step_it_cannot_finish(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("AGENT_TIME_BUDGET_S", raising=False)
    # Budget 100s → stop threshold 80s. After two 30s steps, 60s + a projected
    # 30s step = 90s > 80s, so the third step must not start.
    result = _run_with_budget(tmp_path, monkeypatch, budget=100.0)
    assert [s["step_id"] for s in result["steps"]] == [1, 2]
    assert result["time_budget_exceeded"] is True


def test_runner_without_budget_runs_every_step(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("AGENT_TIME_BUDGET_S", raising=False)
    result = _run_with_budget(tmp_path, monkeypatch, budget=None)
    assert [s["step_id"] for s in result["steps"]] == [1, 2, 3]
    assert result["time_budget_exceeded"] is False


# ── 3. Exploration inside a step respects the run budget ─────────────────────


def _explore(tmp_path: Path, monkeypatch, budget: float) -> int:
    clock = _FakeClock()
    monkeypatch.setattr(loop_mod, "time", clock)
    root = tmp_path / "repo"
    root.mkdir()
    for i in range(20):
        (root / f"f{i}.txt").write_text("x\n", encoding="utf-8")
    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)
    runner._run_started = 0.0
    runner._run_budget_s = budget
    calls = 0

    async def fake_chat_json(_model: str, _messages: list[dict[str, str]]) -> dict[str, Any]:
        nonlocal calls
        clock.now += 30.0  # each tool-selection call takes 30s
        calls += 1
        return {"tool": "read_file", "args": {"path": f"f{calls}.txt"}}

    async def fake_chat_text(_model: str, _messages: list[dict[str, str]]) -> str:
        return "analysis done"

    runner._chat_json = fake_chat_json  # type: ignore[method-assign]
    runner._chat_text = fake_chat_text  # type: ignore[method-assign]
    step = {"id": 1, "description": "look around", "files": [], "type": "analyze"}
    asyncio.run(runner._execute_step("goal", step, None))
    return calls


def test_step_stops_exploring_once_budget_is_mostly_spent(tmp_path: Path, monkeypatch):
    # Budget 100s → exploration stops past 60s: calls at t=0, 30, 60, then stop.
    assert _explore(tmp_path, monkeypatch, budget=100.0) == 3


def test_step_without_budget_explores_until_its_call_cap(tmp_path: Path, monkeypatch):
    assert _explore(tmp_path, monkeypatch, budget=0.0) == 15


def test_run_budget_clock_includes_planning(tmp_path: Path, monkeypatch):
    """Planning time counts: a 70s plan against a 100s budget leaves room for one step."""
    monkeypatch.delenv("AGENT_TIME_BUDGET_S", raising=False)
    clock = _FakeClock()
    monkeypatch.setattr(loop_mod, "time", clock)
    root = tmp_path / "repo"
    root.mkdir()
    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)
    plan = AgentPlan.model_validate({
        "goal": "g",
        "steps": [{"id": i, "description": f"s{i}", "files": ["a.py"], "type": "edit"} for i in (1, 2)],
    })

    async def fake_plan(*_a: Any, **_k: Any) -> AgentPlan:
        clock.now += 70.0
        return plan

    async def fake_step(_goal: str, step: dict[str, Any], *_a: Any, **_k: Any) -> dict[str, Any]:
        clock.now += 5.0
        return {"step_id": step["id"], "status": "applied", "changed_files": [], "issues": []}

    async def fake_chat_text(_model: str, _messages: list[dict[str, str]]) -> str:
        return '{"verdict":"APPROVED","security":"PASS","correctness":"PASS","notes":""}'

    runner._generate_plan = fake_plan  # type: ignore[method-assign]
    runner._execute_step = fake_step  # type: ignore[method-assign]
    runner._chat_text = fake_chat_text  # type: ignore[method-assign]
    result = asyncio.run(runner.run(
        instruction="go", history=[], requested_model=None,
        auto_commit=False, max_steps=5, time_budget_s=100.0,
    ))
    # Step 1 starts at 70s (< 80s); step 2 would start at 75 + 5 projected = 80 → stop.
    assert [s["step_id"] for s in result["steps"]] == [1]
    assert result["time_budget_exceeded"] is True


# ── 4. Gemini is a free-tier provider ────────────────────────────────────────


def test_google_gemini_is_free_tier():
    from packages.ai.brain_config import get_provider_tier
    from services.brain_failover import _PROVIDER_REGISTRY

    assert get_provider_tier("google") == "free"
    assert {s["id"]: s["tier"] for s in _PROVIDER_REGISTRY}["google"] == "free"


# ── 5. Advertised Repowise tools are dispatched, inside the workspace ────────


def _runner_with_files(tmp_path: Path) -> AgentRunner:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "app.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("TOP-SECRET\n", encoding="utf-8")
    return AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)


def test_repowise_tools_no_longer_unsupported(tmp_path: Path):
    runner = _runner_with_files(tmp_path)
    overview = asyncio.run(runner._dispatch_tool_unguarded("get_overview", {}))
    assert isinstance(overview, dict)
    context = asyncio.run(runner._dispatch_tool_unguarded("get_context", {"targets": ["app.py"]}))
    assert "print('hi')" in context
    assert asyncio.run(runner._dispatch_tool_unguarded("get_why", {"target": "app.py"}))


@pytest.mark.parametrize("target", ["../secret.txt", "*/../../secret.txt", "fn:../secret.txt", str(Path("/etc/passwd"))])
def test_get_context_refuses_targets_outside_the_workspace(tmp_path: Path, target: str):
    runner = _runner_with_files(tmp_path)
    out = asyncio.run(runner._dispatch_tool_unguarded("get_context", {"targets": [target]}))
    assert "TOP-SECRET" not in out
    assert "root:" not in out


# ── 6. The packages/llm gateway (the agent loop's real path) applies it too ──


def test_llm_gateway_openai_payload_disables_nemotron_thinking(clean_overrides):
    from packages.llm.providers.base import OpenAICompatible
    from packages.llm.types import LLMRequest

    control_overrides.apply_overrides({})
    provider = OpenAICompatible.__new__(OpenAICompatible)
    request = LLMRequest(messages=[{"role": "user", "content": "hi"}])
    payload = provider.build_payload(request, "nvidia/nemotron-3-super-120b-a12b")
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}
    other = provider.build_payload(request, "openai/gpt-oss-120b")
    assert "chat_template_kwargs" not in other


# ── 7. Mistral is a free fallback in the gateway ─────────────────────────────


def test_mistral_is_reachable_without_paid_routing(monkeypatch):
    """Operator-confirmed free key: Mistral must survive the allow_paid=False filter."""
    from packages.llm import config as llm_config
    from packages.llm import registry as llm_registry

    monkeypatch.delenv("LLM_CONFIG_DIR", raising=False)
    llm_config.reset()
    llm_registry.reset()
    try:
        cfg = llm_config.get_config()
        assert cfg.providers["mistral"].tier == "free"
        assert cfg.providers["mistral"].timeout_sec == 60
        free = llm_registry.get_registry().candidates(provider_id="mistral", allow_paid=False)
        assert {"mistral-small-latest", "mistral-large-latest"} <= {m.id for m in free}
    finally:
        llm_config.reset()
        llm_registry.reset()
