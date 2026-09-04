"""Regression: dispatcher auto-retry must not reset its own retry budget.

Before this fix, TaskWorkflowService.retry() unconditionally cleared
``auto_retry_count`` and emitted a ``runtime_retry_reset`` event. The
dispatcher's ``_auto_retry_blocked`` loop re-queues BLOCKED tasks by calling
that same retry(), so the auto-retry budget was wiped on every cycle: the count
reset to 0, got incremented to 1, and never reached ``_AUTO_RETRY_MAX`` (5). A
task that deterministically timed out (e.g. a poison ``portfolio_initiative``
that hangs the full 600s) was re-queued forever — one E2B clone every ~10 min,
a flood of ``Execution timed out after 600s`` / ``blocked after 5 failed
dispatch attempts`` errors, and no progress.

``reset_auto_retry=False`` makes the dispatcher's retry preserve the budget so
the cap is actually reached; the default (True) still resets for human retries.
"""
from __future__ import annotations

from tasks.service import TaskWorkflowService
from tasks.store import TaskStore
from tasks.models import Task, TaskStatus, TaskPriority


def _blocked_task(auto_retry_count: int) -> Task:
    return Task(
        owner_id="system",
        title="auto-retry-reset-test",
        status=TaskStatus.BLOCKED,
        priority=TaskPriority.MEDIUM,
        blocked_reason="Execution timed out after 600s after 5 attempts",
        auto_retry_count=auto_retry_count,
        error_message="Execution timed out after 600s",
    )


def _has_reset_event(task: Task) -> bool:
    return any(e.event_type == "runtime_retry_reset" for e in task.execution_log)


def test_auto_retry_preserves_budget() -> None:
    """reset_auto_retry=False (the dispatcher path) keeps auto_retry_count."""
    wf = TaskWorkflowService(store=TaskStore())
    task = _blocked_task(auto_retry_count=3)

    wf.retry(task, actor="system:auto-retry", reset_auto_retry=False)

    assert task.auto_retry_count == 3, "dispatcher auto-retry must NOT reset the count"
    assert not _has_reset_event(task), "auto-retry must not emit runtime_retry_reset"
    assert task.status == TaskStatus.IN_PROGRESS
    assert task.error_message is None


def test_human_retry_resets_budget() -> None:
    """The default (human) path still resets the count and emits the reset event."""
    wf = TaskWorkflowService(store=TaskStore())
    task = _blocked_task(auto_retry_count=4)

    wf.retry(task, actor="user:alice")

    assert task.auto_retry_count == 0, "human retry resets the auto-retry counter"
    assert _has_reset_event(task), "human retry must emit runtime_retry_reset"
    assert task.status == TaskStatus.IN_PROGRESS


def test_auto_retry_count_accumulates_to_cap() -> None:
    """Simulate the dispatcher loop: count climbs 1..5 instead of sticking at 1.

    The dispatcher checks ``auto_retry_count >= _AUTO_RETRY_MAX`` BEFORE
    re-queueing, then increments. With the budget preserved, five cycles bring
    the count to the cap so the sixth is skipped — the loop terminates.
    """
    wf = TaskWorkflowService(store=TaskStore())
    task = _blocked_task(auto_retry_count=0)
    cap = 5

    cycles = 0
    while task.auto_retry_count < cap and cycles < 100:
        wf.retry(task, actor="system:auto-retry", reset_auto_retry=False)
        task.auto_retry_count += 1            # dispatcher increments after retry()
        task.status = TaskStatus.BLOCKED      # task times out again → re-blocked
        cycles += 1

    assert cycles == cap, "must reach the cap in exactly `cap` cycles, not loop forever"
    assert task.auto_retry_count == cap
