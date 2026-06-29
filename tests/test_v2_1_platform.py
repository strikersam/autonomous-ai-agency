"""tests/test_v2_1_platform.py — Tests for the V2.1 Intelligence Platform.

Tests the Unified Tool Platform, Intelligence Layer, Provider Resilience,
and Knowledge Platform.
"""
from __future__ import annotations

import asyncio
import pytest

from packages.tools.base import Tool, ToolResult, ToolSchema
from packages.tools.registry import ToolRegistry, get_tool_registry
from packages.intelligence.planner import Planner, ExecutionPlan, PlanStep
from packages.intelligence.reflector import Reflector, Reflection
from packages.resilience.checkpoint import Checkpoint, CheckpointManager, get_checkpoint_manager
from packages.knowledge.store import KnowledgeStore, get_knowledge_store


# ── Unified Tool Platform ────────────────────────────────────────────────────


class _FakeTool(Tool):
    """Test tool implementation."""
    @property
    def name(self) -> str:
        return "fake_tool"
    @property
    def description(self) -> str:
        return "A fake tool for testing"
    @property
    def capabilities(self) -> list[str]:
        return ["test", "fake"]
    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, output=kwargs)
    def schema(self) -> ToolSchema:
        return ToolSchema(name="fake_tool", description="A fake tool for testing")


def test_tool_registry_register_and_get():
    """Tools can be registered and retrieved by name."""
    reg = ToolRegistry()
    tool = _FakeTool()
    reg.register(tool)
    assert reg.get("fake_tool") is tool


def test_tool_registry_find_by_capability():
    """Tools can be found by capability tag."""
    reg = ToolRegistry()
    reg.register(_FakeTool())
    found = reg.find_by_capability("test")
    assert len(found) == 1
    assert found[0].name == "fake_tool"


def test_tool_registry_find_by_query():
    """Tools can be found by name/description substring."""
    reg = ToolRegistry()
    reg.register(_FakeTool())
    found = reg.find("fake")
    assert len(found) == 1


def test_tool_registry_execute():
    """Tool execution returns ToolResult."""
    reg = ToolRegistry()
    reg.register(_FakeTool())
    result = asyncio.run(reg.execute("fake_tool", key="value"))
    assert result.success is True
    assert result.output == {"key": "value"}


def test_tool_registry_execute_unknown():
    """Executing an unknown tool returns failure."""
    reg = ToolRegistry()
    result = asyncio.run(reg.execute("nonexistent"))
    assert result.success is False
    assert "not found" in result.error


def test_tool_registry_to_openai_functions():
    """Registry exports OpenAI function-calling format."""
    reg = ToolRegistry()
    reg.register(_FakeTool())
    funcs = reg.to_openai_functions()
    assert len(funcs) == 1
    assert funcs[0]["name"] == "fake_tool"


# ── Intelligence Layer: Planner ──────────────────────────────────────────────


def test_planner_creates_plan():
    """Planner creates an execution plan for a goal."""
    planner = Planner()
    plan = asyncio.run(planner.create_plan("Write a hello world script"))
    assert plan.goal == "Write a hello world script"
    assert len(plan.steps) > 0
    assert plan.steps[0].status == "pending"


def test_execution_plan_next_step():
    """ExecutionPlan finds the next executable step."""
    plan = ExecutionPlan(
        goal="test",
        steps=[
            PlanStep(id="s1", description="step 1"),
            PlanStep(id="s2", description="step 2", depends_on=["s1"]),
        ],
    )
    assert plan.next_step.id == "s1"
    plan.steps[0].status = "completed"
    assert plan.next_step.id == "s2"


def test_execution_plan_is_complete():
    """Plan is complete when all steps are completed/skipped."""
    plan = ExecutionPlan(
        goal="test",
        steps=[PlanStep(id="s1", description="step 1", status="completed")],
    )
    assert plan.is_complete is True


# ── Intelligence Layer: Reflector ────────────────────────────────────────────


def test_reflector_good_output():
    """Reflector gives high quality score for good output."""
    r = Reflector()
    result = asyncio.run(r.reflect("Say hello", "Hello, world! How are you?"))
    assert result.quality_score > 0.5
    assert result.should_retry is False


def test_reflector_empty_output():
    """Reflector gives zero quality for empty output."""
    r = Reflector()
    result = asyncio.run(r.reflect("Say hello", ""))
    assert result.quality_score == 0.0
    assert result.should_retry is True


def test_reflector_with_errors():
    """Reflector suggests retry when errors occur."""
    r = Reflector()
    result = asyncio.run(r.reflect("Say hello", "hi", errors=["Connection failed"]))
    assert result.quality_score < 0.5
    assert result.should_retry is True


# ── Provider Resilience: Checkpointing ───────────────────────────────────────


def test_checkpoint_save_and_get():
    """Checkpoints can be saved and retrieved."""
    mgr = CheckpointManager()
    cp = Checkpoint(task_id="task1", step_id="step1", provider_id="nvidia", model="llama-3.3-70b")
    mgr.save(cp)
    latest = mgr.get_latest("task1")
    assert latest is not None
    assert latest.step_id == "step1"


def test_checkpoint_can_resume():
    """Can resume on a different provider."""
    mgr = CheckpointManager()
    mgr.save(Checkpoint(task_id="task1", step_id="step1", provider_id="nvidia", model="m1"))
    assert mgr.can_resume("task1", "cerebras") is True
    assert mgr.can_resume("task1", "nvidia") is False


def test_checkpoint_resume_state():
    """Resume state returns the saved state."""
    mgr = CheckpointManager()
    mgr.save(Checkpoint(
        task_id="task1", step_id="step1", provider_id="nvidia", model="m1",
        state={"progress": "halfway", "data": [1, 2, 3]},
    ))
    state = mgr.resume_state("task1")
    assert state["progress"] == "halfway"
    assert state["data"] == [1, 2, 3]


def test_checkpoint_clear():
    """Clear removes all checkpoints for a task."""
    mgr = CheckpointManager()
    mgr.save(Checkpoint(task_id="task1", step_id="step1", provider_id="nvidia", model="m1"))
    mgr.clear("task1")
    assert mgr.get_latest("task1") is None


# ── Knowledge Platform ───────────────────────────────────────────────────────


def test_knowledge_remember_and_recall():
    """Knowledge can be stored and retrieved."""
    store = KnowledgeStore()
    entry_id = asyncio.run(store.remember(
        "Python is a programming language",
        source="test",
        tags=["programming", "python"],
    ))
    results = asyncio.run(store.recall("Python programming"))
    assert len(results) > 0
    assert "Python" in results[0].content


def test_knowledge_short_vs_long_term():
    """Short-term knowledge stays in-process."""
    store = KnowledgeStore()
    asyncio.run(store.remember("quick note", long_term=False))
    results = asyncio.run(store.recall("quick note"))
    assert len(results) > 0


def test_knowledge_forget():
    """Knowledge can be removed."""
    store = KnowledgeStore()
    entry_id = asyncio.run(store.remember("temporary knowledge"))
    removed = asyncio.run(store.forget(entry_id))
    assert removed is True
    results = asyncio.run(store.recall("temporary knowledge"))
    assert len(results) == 0


def test_knowledge_relevance_ranking():
    """More relevant knowledge ranks higher."""
    store = KnowledgeStore()
    asyncio.run(store.remember("The sky is blue", tags=["nature"]))
    asyncio.run(store.remember("Python programming language", tags=["programming"]))
    results = asyncio.run(store.recall("Python programming language"))
    assert len(results) > 0
    assert "Python" in results[0].content
