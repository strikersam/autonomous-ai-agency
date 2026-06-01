"""Tests for agents.research_coordinator — multi-agent research orchestration."""

from __future__ import annotations

import pytest

from agents.research_coordinator import (
    AgentRole,
    ResearchAgent,
    ResearchOrchestrator,
    ResearchTask,
    TaskStatus,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _echo_handler(task: ResearchTask, context: dict[str, str]) -> str:
    """Test handler that echoes the task question + context keys."""
    ctx_keys = ",".join(sorted(context.keys()))
    return f"answered:{task.question}|ctx:{ctx_keys}"


def _failing_handler(task: ResearchTask, context: dict[str, str]) -> str:
    raise RuntimeError("boom")


@pytest.fixture
def orchestrator() -> ResearchOrchestrator:
    o = ResearchOrchestrator()
    for role in AgentRole:
        o.register_agent(ResearchAgent(name=f"{role.value}_agent",
                                       role=role, handler=_echo_handler))
    return o


# ── ResearchTask ──────────────────────────────────────────────────────────────


def test_task_initial_state_is_pending():
    t = ResearchTask("t1", "q?", AgentRole.WEB_SEARCHER)
    assert t.status == TaskStatus.PENDING
    assert t.result is None
    assert t.started_at is None


def test_task_is_ready_with_no_dependencies():
    t = ResearchTask("t1", "q?", AgentRole.WEB_SEARCHER)
    assert t.is_ready(completed_ids=set()) is True


def test_task_is_ready_after_dependency_completes():
    t = ResearchTask("t2", "q?", AgentRole.SUMMARIZER, depends_on=["t1"])
    assert t.is_ready(completed_ids=set()) is False
    assert t.is_ready(completed_ids={"t1"}) is True


def test_task_not_ready_when_already_running():
    t = ResearchTask("t1", "q?", AgentRole.WEB_SEARCHER)
    t.mark_running()
    assert t.is_ready(completed_ids=set()) is False


def test_task_mark_completed_records_result_and_time():
    t = ResearchTask("t1", "q?", AgentRole.WEB_SEARCHER)
    t.mark_running()
    t.mark_completed("done")
    assert t.status == TaskStatus.COMPLETED
    assert t.result == "done"
    assert t.completed_at is not None


def test_task_mark_failed_records_error():
    t = ResearchTask("t1", "q?", AgentRole.WEB_SEARCHER)
    t.mark_running()
    t.mark_failed("oops")
    assert t.status == TaskStatus.FAILED
    assert t.error == "oops"


def test_task_duration_seconds_after_completion():
    t = ResearchTask("t1", "q?", AgentRole.WEB_SEARCHER)
    t.mark_running()
    t.mark_completed("ok")
    duration = t.duration_seconds()
    assert duration is not None
    assert duration >= 0


def test_task_duration_none_before_completion():
    t = ResearchTask("t1", "q?", AgentRole.WEB_SEARCHER)
    assert t.duration_seconds() is None


# ── ResearchAgent ─────────────────────────────────────────────────────────────


def test_agent_can_handle_matching_role():
    a = ResearchAgent("web", AgentRole.WEB_SEARCHER, _echo_handler)
    t = ResearchTask("t1", "q?", AgentRole.WEB_SEARCHER)
    assert a.can_handle(t) is True


def test_agent_cannot_handle_other_roles():
    a = ResearchAgent("web", AgentRole.WEB_SEARCHER, _echo_handler)
    t = ResearchTask("t1", "q?", AgentRole.DOC_READER)
    assert a.can_handle(t) is False


def test_agent_execute_success_increments_counter():
    a = ResearchAgent("web", AgentRole.WEB_SEARCHER, _echo_handler)
    t = ResearchTask("t1", "What is X?", AgentRole.WEB_SEARCHER)
    a.execute(t, context={})
    assert t.status == TaskStatus.COMPLETED
    assert "answered:What is X?" in t.result
    assert a.tasks_completed == 1
    assert a.tasks_failed == 0


def test_agent_execute_handler_failure_marks_failed():
    a = ResearchAgent("web", AgentRole.WEB_SEARCHER, _failing_handler)
    t = ResearchTask("t1", "q?", AgentRole.WEB_SEARCHER)
    a.execute(t, context={})
    assert t.status == TaskStatus.FAILED
    assert "boom" in (t.error or "")
    assert a.tasks_failed == 1


def test_agent_execute_wrong_role_marks_failed():
    a = ResearchAgent("web", AgentRole.WEB_SEARCHER, _echo_handler)
    t = ResearchTask("t1", "q?", AgentRole.DOC_READER)
    a.execute(t, context={})
    assert t.status == TaskStatus.FAILED
    assert a.tasks_failed == 1


# ── ResearchOrchestrator ──────────────────────────────────────────────────────


def test_orchestrator_add_task_rejects_duplicates():
    o = ResearchOrchestrator()
    o.add_task(ResearchTask("t1", "q?", AgentRole.WEB_SEARCHER))
    with pytest.raises(ValueError):
        o.add_task(ResearchTask("t1", "q?", AgentRole.WEB_SEARCHER))


def test_orchestrator_plan_creates_dag():
    o = ResearchOrchestrator()
    plan = o.plan("how does feature X work?")
    assert len(plan) == 5
    ids = {t.task_id for t in plan}
    assert ids == {"web_search", "doc_read", "summarize", "critique", "synthesize"}


def test_orchestrator_plan_synthesize_depends_on_critic_and_summary():
    o = ResearchOrchestrator()
    o.plan("q?")
    synth = o.tasks["synthesize"]
    assert "summarize" in synth.depends_on
    assert "critique" in synth.depends_on


def test_orchestrator_run_completes_full_dag(orchestrator):
    orchestrator.plan("question?")
    orchestrator.run()
    statuses = {t.status for t in orchestrator.tasks.values()}
    assert statuses == {TaskStatus.COMPLETED}


def test_orchestrator_run_respects_dependency_order(orchestrator):
    orchestrator.plan("q?")
    orchestrator.run()
    # synthesize must complete after summarize and critique
    history = orchestrator.history
    assert history.index("synthesize") > history.index("summarize")
    assert history.index("synthesize") > history.index("critique")


def test_orchestrator_run_marks_blocked_when_no_agent_for_role():
    o = ResearchOrchestrator()
    # register only WEB_SEARCHER, leaving others without agents
    o.register_agent(ResearchAgent("web", AgentRole.WEB_SEARCHER, _echo_handler))
    o.plan("q?")
    o.run()
    # web_search completes; others can't all proceed
    assert o.tasks["web_search"].status == TaskStatus.COMPLETED
    blocked_or_pending = [
        t for t in o.tasks.values()
        if t.status in {TaskStatus.BLOCKED, TaskStatus.PENDING}
    ]
    assert len(blocked_or_pending) >= 1


def test_orchestrator_synthesize_returns_final_answer(orchestrator):
    orchestrator.plan("how does X work?")
    orchestrator.run()
    answer = orchestrator.synthesize()
    assert "how does X work?" in answer or "answered" in answer


def test_orchestrator_synthesize_fallback_when_incomplete():
    o = ResearchOrchestrator()
    o.add_task(ResearchTask("t1", "q?", AgentRole.WEB_SEARCHER))
    msg = o.synthesize()
    assert "incomplete" in msg.lower()


def test_orchestrator_status_counts(orchestrator):
    orchestrator.plan("q?")
    orchestrator.run()
    status = orchestrator.status()
    assert status["completed"] == 5
    assert status["pending"] == 0


def test_orchestrator_pick_agent_load_balances():
    o = ResearchOrchestrator()
    a1 = ResearchAgent("a1", AgentRole.WEB_SEARCHER, _echo_handler)
    a2 = ResearchAgent("a2", AgentRole.WEB_SEARCHER, _echo_handler)
    o.register_agent(a1)
    o.register_agent(a2)
    a1.tasks_completed = 5  # a1 already busy
    picked = o._pick_agent(AgentRole.WEB_SEARCHER)
    assert picked is a2  # least-loaded
