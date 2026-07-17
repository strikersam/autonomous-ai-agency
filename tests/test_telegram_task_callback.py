"""Telegram inline-button callbacks for the task pre-execution gate.

Regression: ``_process_task_callback`` used ``await workflow.approve_execution(...)``
even though ``approve_execution`` is synchronous — awaiting its ``Task`` return
value raised ``TypeError`` before the store update, so tapping Approve/Reject in
Telegram showed an error toast and never persisted the decision.
"""
from __future__ import annotations

import pytest

import telegram_bot
from tasks.models import Task, TaskStatus
from tasks.service import TaskWorkflowService
from tasks.store import TaskStore


class _Recorder:
    def __init__(self) -> None:
        self.answers: list[str | None] = []
        self.edits: list[str] = []

    async def answer(self, bot_token, callback_id, text=None):
        self.answers.append(text)

    async def edit(self, bot_token, chat_id, message_id, text):
        self.edits.append(text)


@pytest.fixture()
def store() -> TaskStore:
    return TaskStore()


@pytest.fixture()
def recorder(monkeypatch, store) -> _Recorder:
    rec = _Recorder()
    monkeypatch.setattr(telegram_bot, "_answer_callback", rec.answer)
    monkeypatch.setattr(telegram_bot, "_edit_message", rec.edit)
    # _process_task_callback does a lazy `from tasks.service import TaskWorkflowService`
    # and constructs it with no args; bind it to this test's in-memory store.
    import tasks.service as tasks_service

    monkeypatch.setattr(
        tasks_service, "TaskWorkflowService",
        lambda: TaskWorkflowService(store=store),
    )
    return rec


async def _parked_task(store: TaskStore) -> Task:
    task = Task(
        owner_id="o@x.com",
        title="Deploy to production",
        requires_approval=True,
        pending_agent_run=False,  # parked by the dispatcher's gate
    )
    await store.create(task)
    return task


@pytest.mark.asyncio
async def test_approve_button_approves_and_requeues(store, recorder):
    task = await _parked_task(store)

    await telegram_bot._process_task_callback(
        "tok", "cb1", 1, 2, "task_approve", task.task_id,
    )

    updated = await store.get(task.task_id)
    assert updated.execution_approved is True
    assert updated.status is TaskStatus.IN_PROGRESS
    assert updated.pending_agent_run is True  # dispatcher will pick it up
    assert recorder.answers == ["Approved ✅"]
    assert recorder.edits and "Approved" in recorder.edits[0]


@pytest.mark.asyncio
async def test_reject_button_blocks_task(store, recorder):
    task = await _parked_task(store)

    await telegram_bot._process_task_callback(
        "tok", "cb1", 1, 2, "task_reject", task.task_id,
    )

    updated = await store.get(task.task_id)
    assert updated.execution_approved is False
    assert updated.status is TaskStatus.BLOCKED
    assert "Rejected via Telegram" in (updated.blocked_reason or "")
    assert recorder.answers == ["Rejected ❌"]


@pytest.mark.asyncio
async def test_unknown_task_id_answers_not_found(store, recorder):
    await telegram_bot._process_task_callback(
        "tok", "cb1", 1, 2, "task_approve", "task_does_not_exist",
    )

    assert recorder.answers == ["Task not found."]


@pytest.mark.asyncio
async def test_callback_parser_routes_task_prefix():
    assert telegram_bot._parse_callback("task:approve:task_abc") == ("task_approve", "task_abc")
    assert telegram_bot._parse_callback("task:reject:task_abc") == ("task_reject", "task_abc")
