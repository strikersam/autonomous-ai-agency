"""tests/test_task_service_failed_comment.py — verify that a FAILED
TaskResult still posts the agent_comment as a task comment.

Bug 3: ``tasks/service.py::_apply_result`` line 1193-1201 dropped the
agent_comment on the FAILED path — it returned before reaching the
``add_comment`` call. The fix posts the comment BEFORE transitioning
to FAILED so the per-step failure details (from the ``report`` field)
appear on the task even when it fails.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tasks.models import Task, TaskStatus
from tasks.service import TaskExecutionCoordinator


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.update = AsyncMock()
    store.get = AsyncMock(return_value=None)
    return store


@pytest.fixture
def mock_workflow():
    wf = MagicMock()
    wf.transition = MagicMock()
    wf.add_comment = MagicMock()
    return wf


@pytest.fixture
def coordinator(mock_store, mock_workflow):
    coord = TaskExecutionCoordinator.__new__(TaskExecutionCoordinator)
    coord.store = mock_store
    coord.workflow = mock_workflow
    return coord


@pytest.fixture
def sample_task():
    return Task(
        owner_id="user1",
        title="Test task",
        source="test",
        status=TaskStatus.IN_PROGRESS,
    )


def _make_result(success: bool, output: str = "", agent_comment: str | None = None):
    """Build a minimal TaskResult-like object for _apply_result."""
    result = MagicMock()
    result.success = success
    result.output = output
    result.runtime_id = "internal_agent"
    result.model_used = "test-model"
    result.tokens_used = 100
    result.cost_usd = 0.01
    result.provider_used = "nvidia-nim"
    result.execution_time_ms = 5000
    result.artifacts = []
    result.tool_calls = []
    metadata = {}
    if agent_comment:
        metadata["agent_comment"] = agent_comment
    result.metadata = metadata
    return result


# ── FAILED path: agent_comment MUST be posted ──────────────────────────────


@pytest.mark.asyncio
async def test_failed_result_posts_agent_comment(coordinator, sample_task, mock_workflow):
    """A FAILED TaskResult with agent_comment must post it as a task comment."""
    result = _make_result(
        success=False,
        output="Execution failed",
        agent_comment="## Goal: test\n**Applied steps:** 1/22\n### Failed step details\n- Step 5 (verification): syntax error",
    )

    await coordinator._apply_result(sample_task, None, result)

    # The comment MUST be posted even on the FAILED path
    mock_workflow.add_comment.assert_called()
    call_args = mock_workflow.add_comment.call_args
    assert "Failed step details" in call_args.kwargs.get("body", "") or "Failed step details" in str(call_args)

    # The task MUST transition to FAILED
    mock_workflow.transition.assert_called()
    transition_args = mock_workflow.transition.call_args
    assert transition_args.args[1] == TaskStatus.FAILED


@pytest.mark.asyncio
async def test_failed_result_without_comment_still_fails(coordinator, sample_task, mock_workflow):
    """A FAILED TaskResult without agent_comment transitions to FAILED without crashing."""
    result = _make_result(
        success=False,
        output="Execution failed",
        agent_comment=None,
    )

    await coordinator._apply_result(sample_task, None, result)

    # No comment to post
    mock_workflow.add_comment.assert_not_called()
    # Still transitions to FAILED
    mock_workflow.transition.assert_called()
    transition_args = mock_workflow.transition.call_args
    assert transition_args.args[1] == TaskStatus.FAILED


@pytest.mark.asyncio
async def test_failed_result_sets_error_message(coordinator, sample_task):
    """A FAILED TaskResult sets task.error_message to result.output."""
    result = _make_result(
        success=False,
        output="Task marked as FAILED: 1/22 steps applied",
    )

    await coordinator._apply_result(sample_task, None, result)

    assert sample_task.error_message == "Task marked as FAILED: 1/22 steps applied"


# ── SUCCESS path: agent_comment still posted (existing behaviour) ───────────


@pytest.mark.asyncio
async def test_success_result_posts_agent_comment(coordinator, sample_task, mock_workflow):
    """A SUCCESS TaskResult with agent_comment posts it as a task comment."""
    result = _make_result(
        success=True,
        output="Execution completed",
        agent_comment="## Goal: test\n**Applied steps:** 10/10",
    )

    await coordinator._apply_result(sample_task, None, result)

    mock_workflow.add_comment.assert_called()
    mock_workflow.transition.assert_called()
    transition_args = mock_workflow.transition.call_args
    assert transition_args.args[1] == TaskStatus.DONE
