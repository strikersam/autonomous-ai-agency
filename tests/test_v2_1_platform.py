"""tests/test_v2_1_platform.py — Tests for the V2.1 Intelligence Platform.

Tests the Unified Tool Platform, Intelligence Layer, Provider Resilience,
and Knowledge Platform.
"""
from __future__ import annotations

import asyncio
import pytest

from packages.tools.base import Tool, ToolResult, ToolSchema
from packages.tools.registry import ToolRegistry, get_tool_registry
from packages.tools.browser import BrowserTool
from packages.tools.github_tool import GitHubTool
from packages.tools.shell import ShellTool
from packages.intelligence.planner import Planner, ExecutionPlan, PlanStep
from packages.intelligence.reflector import Reflector, Reflection
from packages.intelligence.verifier import Verifier, VerificationResult
from packages.intelligence.context import ContextOptimizer, ContextWindow
from packages.intelligence.self_improve import SelfImprover, get_self_improver
from packages.resilience.checkpoint import Checkpoint, CheckpointManager, get_checkpoint_manager
from packages.knowledge.store import KnowledgeStore, get_knowledge_store
from packages.knowledge.search import SemanticSearch, get_semantic_search


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


def test_browser_tool_schema():
    """BrowserTool has correct schema."""
    tool = BrowserTool()
    assert tool.name == "browser"
    assert "web" in tool.capabilities
    s = tool.schema()
    assert s.name == "browser"
    assert "action" in s.parameters


def test_github_tool_schema():
    """GitHubTool has correct schema."""
    tool = GitHubTool()
    assert tool.name == "github"
    assert "code" in tool.capabilities
    assert tool.requires_auth is True
    s = tool.schema()
    assert s.name == "github"
    assert "action" in s.parameters


def test_shell_tool_blocks_dangerous_commands():
    """ShellTool blocks dangerous commands."""
    tool = ShellTool()
    result = asyncio.run(tool.execute(command="rm -rf /"))
    assert result.success is False
    assert "Blocked" in result.error


def test_shell_tool_executes_safe_command():
    """ShellTool executes safe commands."""
    tool = ShellTool()
    result = asyncio.run(tool.execute(command="echo hello"))
    assert result.success is True
    assert "hello" in result.output


def test_shell_tool_timeout():
    """ShellTool enforces timeout."""
    tool = ShellTool()
    result = asyncio.run(tool.execute(command="sleep 5", timeout=1))
    assert result.success is False
    assert "timed out" in result.error.lower()


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


# ── Intelligence Layer: Verifier ─────────────────────────────────────────────


def test_verifier_passes_good_output():
    """Verifier passes good output."""
    v = Verifier()
    result = asyncio.run(v.verify("Write hello world", "Hello world! This is a test."))
    assert result.passed is True
    assert result.checks_passed == result.checks_total


def test_verifier_fails_empty_output():
    """Verifier fails empty output."""
    v = Verifier()
    result = asyncio.run(v.verify("Write hello world", ""))
    assert result.passed is False
    assert len(result.failures) > 0


def test_verifier_fails_with_errors():
    """Verifier detects error indicators in output."""
    v = Verifier()
    result = asyncio.run(v.verify("Write code", "Here is the code: error: undefined variable"))
    assert result.passed is False
    assert any("error" in f.lower() for f in result.failures)


def test_verifier_checks_requirements():
    """Verifier checks specific requirements."""
    v = Verifier()
    result = asyncio.run(v.verify(
        "Write a Python function",
        "def hello(): pass  # Python function definition",
        requirements=["must include def", "must include pass"],
    ))
    assert result.passed is True


# ── Intelligence Layer: Context Optimizer ────────────────────────────────────


def test_context_optimizer_no_compression_needed():
    """ContextOptimizer doesn't compress when under budget."""
    opt = ContextOptimizer(max_chars=1000)
    messages = [{"role": "user", "content": "Hello"}]
    window = opt.optimize(messages)
    assert window.compressed is False
    assert len(window.messages) == 1


def test_context_optimizer_truncate():
    """ContextOptimizer truncates when over budget."""
    opt = ContextOptimizer(max_chars=50)
    messages = [
        {"role": "system", "content": "You are helpful"},
        {"role": "user", "content": "First message that is long enough to be over budget"},
        {"role": "assistant", "content": "Response"},
        {"role": "user", "content": "Latest message"},
    ]
    window = opt.optimize(messages, strategy="truncate")
    assert window.compressed is True
    assert window.is_over_budget is False
    # System message should be kept
    assert window.messages[0]["role"] == "system"


def test_context_optimizer_summarize():
    """ContextOptimizer summarizes old messages."""
    opt = ContextOptimizer(max_chars=100)
    messages = [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Old message one with some content"},
        {"role": "user", "content": "Old message two with more content"},
        {"role": "user", "content": "Old message three with content"},
        {"role": "user", "content": "Recent"},
        {"role": "assistant", "content": "Reply"},
        {"role": "user", "content": "Latest"},
    ]
    window = opt.optimize(messages, strategy="summarize")
    assert window.compressed is True
    assert any("summary" in m.get("content", "").lower() for m in window.messages)


def test_context_optimizer_relevance_filter():
    """ContextOptimizer filters by relevance to goal."""
    opt = ContextOptimizer(max_chars=100)
    messages = [
        {"role": "system", "content": "System prompt for the assistant"},
        {"role": "user", "content": "Tell me about Python programming language and its features"},
        {"role": "assistant", "content": "Python is a versatile programming language used for web development and data science"},
        {"role": "user", "content": "What's the weather like today in San Francisco?"},
        {"role": "assistant", "content": "I don't know the current weather conditions in your area"},
        {"role": "user", "content": "How do I write Python code for a web server?"},
    ]
    window = opt.optimize(messages, goal="Python programming", strategy="relevance")
    assert window.compressed is True
    # Weather messages should be filtered out
    contents = [m["content"] for m in window.messages]
    assert not any("weather" in c.lower() for c in contents)


# ── Intelligence Layer: Self-Improvement ─────────────────────────────────────


def test_self_improver_review_low_quality():
    """SelfImprover suggests prompt improvement for low quality."""
    improver = SelfImprover()
    reflection = Reflection(quality_score=0.3, should_retry=True)
    suggestions = asyncio.run(improver.review_task(
        "Write code", "bad output", reflection, errors=["syntax error"],
    ))
    assert len(suggestions) > 0
    categories = [s.category for s in suggestions]
    assert "prompt" in categories
    assert "workflow" in categories


def test_self_improver_review_high_quality():
    """SelfImprover suggests knowledge creation for high quality."""
    improver = SelfImprover()
    reflection = Reflection(quality_score=0.95, should_retry=False)
    suggestions = asyncio.run(improver.review_task(
        "Write code", "def hello(): return 'world'", reflection,
    ))
    assert len(suggestions) > 0
    categories = [s.category for s in suggestions]
    assert "knowledge" in categories


def test_self_improver_approval():
    """SelfImprover tracks approval state."""
    improver = SelfImprover()
    reflection = Reflection(quality_score=0.2, should_retry=True)
    suggestions = asyncio.run(improver.review_task(
        "task", "output", reflection, errors=["error"],
    ))
    assert len(suggestions) > 0
    sugg_id = suggestions[0].id
    assert improver.approve(sugg_id) is True
    assert suggestions[0].approved is True


def test_self_improver_pending():
    """SelfImprover returns pending (unapproved) suggestions."""
    improver = SelfImprover()
    reflection = Reflection(quality_score=0.2, should_retry=True)
    asyncio.run(improver.review_task("task", "output", reflection, errors=["error"]))
    pending = improver.pending_suggestions()
    assert len(pending) > 0
    assert all(not s.approved for s in pending)


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


# ── Knowledge Platform: Semantic Search ──────────────────────────────────────


def test_semantic_search_finds_relevant():
    """Semantic search finds relevant knowledge entries."""
    store = KnowledgeStore()
    asyncio.run(store.remember("Python is a versatile programming language used for web development", tags=["python", "programming"]))
    asyncio.run(store.remember("The weather forecast shows rain tomorrow", tags=["weather"]))
    search = SemanticSearch()
    # Point search at the same store
    search._store = store
    results = asyncio.run(search.search("Python programming language"))
    assert len(results) > 0
    assert "Python" in results[0][1].content


def test_semantic_search_ranks_by_relevance():
    """Semantic search ranks more relevant entries higher."""
    store = KnowledgeStore()
    asyncio.run(store.remember("Python is a programming language", tags=["python"]))
    asyncio.run(store.remember("JavaScript is also a programming language", tags=["javascript"]))
    asyncio.run(store.remember("The sky is blue today", tags=["nature"]))
    search = SemanticSearch()
    search._store = store
    results = asyncio.run(search.search("Python programming"))
    assert len(results) > 0
    # Python entry should rank higher than sky entry
    top_content = results[0][1].content
    assert "Python" in top_content


def test_semantic_search_find_similar():
    """find_similar returns entries similar to given content."""
    store = KnowledgeStore()
    asyncio.run(store.remember("Machine learning models require training data", tags=["ml"]))
    asyncio.run(store.remember("Cooking recipes require fresh ingredients", tags=["cooking"]))
    search = SemanticSearch()
    search._store = store
    results = asyncio.run(search.find_similar("How do I train a machine learning model?"))
    assert len(results) > 0
    assert "machine learning" in results[0][1].content.lower()
