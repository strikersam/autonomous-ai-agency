"""Tests for task follow-up / rerun with conversation carry-over.

Before this, there was no way to give a task new guidance and re-run it — `retry()`
re-ran the same task with no new input, and the runtime never received the prior
thread as structured conversation. `follow_up()` appends the message and re-queues;
`_build_spec` now exposes the thread as `context["conversation"]` (the key the
runtime's AgentRunner actually reads).
"""

from __future__ import annotations

import pytest

from tasks.models import Task, TaskStatus
from tasks.service import TaskExecutionCoordinator, TaskWorkflowService
from tasks.store import TaskStore


def _wf() -> TaskWorkflowService:
    return TaskWorkflowService(store=TaskStore(db=None))


def test_follow_up_requeues_done_task():
    wf = _wf()
    task = Task(owner_id="u1", title="ship feature", status=TaskStatus.DONE)
    wf.follow_up(task, actor="u1", message="also add tests please")
    assert task.pending_agent_run is True
    assert task.status is TaskStatus.IN_PROGRESS
    assert any(c.body == "also add tests please" for c in task.comments)


def test_follow_up_requeues_failed_task_and_clears_error():
    wf = _wf()
    task = Task(owner_id="u1", title="x", status=TaskStatus.FAILED)
    task.error_message = "boom"
    wf.follow_up(task, actor="u1", message="try a different approach", model_preference="kimi-k2.6")
    assert task.pending_agent_run is True
    assert task.status is TaskStatus.IN_PROGRESS
    assert task.error_message is None
    assert task.model_preference == "kimi-k2.6"


def test_follow_up_empty_message_rejected():
    wf = _wf()
    task = Task(owner_id="u1", title="x", status=TaskStatus.DONE)
    with pytest.raises(ValueError):
        wf.follow_up(task, actor="u1", message="   ")


def test_build_spec_exposes_conversation_for_runtime():
    """The runtime reads context['conversation']; prior comments must be carried as
    role/content turns so follow-up guidance reaches the agent."""
    store = TaskStore(db=None)
    coord = TaskExecutionCoordinator(store=store, workspace_root=".")
    task = Task(owner_id="u1", title="do it", status=TaskStatus.IN_PROGRESS)
    # Simulate a thread: a user follow-up and an agent reply.
    coord.workflow.add_comment(task, author="u1", body="please refactor the parser")
    coord.workflow.add_comment(task, author="agent:dev", body="done, refactored parser.py")

    spec = coord._build_spec(task, None)
    convo = spec.context.get("conversation")
    assert convo, "conversation context must be populated"
    assert {"role": "user", "content": "please refactor the parser"} in convo
    assert {"role": "assistant", "content": "done, refactored parser.py"} in convo
