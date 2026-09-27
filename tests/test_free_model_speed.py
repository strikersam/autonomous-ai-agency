"""Free-model speed and timeout handling.

Two failure modes made agency tasks on free providers time out at
``TASK_EXECUTION_TIMEOUT_SEC`` (600s) with nothing to show:

1. Nemotron 3 — the default free NVIDIA brain — thinks by default, which
   multiplies every call's latency. ``with_nemotron_thinking_off`` turns it off
   unless the ``NEMOTRON_THINKING`` control says otherwise.
2. The agent loop's own time budget defaulted to off, so the coordinator's
   ``asyncio.wait_for`` cancelled the run mid-step and every finished step was
   lost. The coordinator now hands its timeout down as ``time_budget_s``.
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
    spec = coord._build_spec(Task(owner_id="u", title="t"), agent=None)
    assert spec.context["time_budget_s"] == pytest.approx(540)


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
