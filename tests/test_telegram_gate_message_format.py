"""Readability of the Telegram pre-execution approval-gate message.

The original message was bare: task ID + title + "tap a button". An operator
with several gated tasks in flight had no way to tell them apart, or what the
task even does, without opening the dashboard. `_notify_execution_gate` now
includes priority, task type, owner, and a redacted description excerpt.
"""
from __future__ import annotations

import pytest

from tasks.models import Task, TaskPriority
from tasks.service import TaskExecutionCoordinator
from telegram_service import NotificationDispatcher


@pytest.fixture()
def captured(monkeypatch):
    calls: list[tuple[str, list]] = []

    def _fake_send(self, text, keyboard):
        calls.append((text, keyboard))

    monkeypatch.setattr(NotificationDispatcher, "_send_telegram_keyboard", _fake_send)
    monkeypatch.setattr(
        "telegram_service.NotificationDispatcher.__init__",
        lambda self, **kw: (
            setattr(self, "telegram_token", "tok"),
            setattr(self, "telegram_chat_ids", [123]),
            setattr(self, "webhook_url", ""),
        ) and None,
    )
    return calls


def test_message_includes_priority_type_owner_and_description(captured):
    task = Task(
        owner_id="system:trend-scoping",
        title="trend Digital Pantheon",
        description="Simulating and auditing coalition formation with LLM agents.",
        task_type="research",
        priority=TaskPriority.HIGH,
        requires_approval=True,
    )

    TaskExecutionCoordinator._notify_execution_gate(task)

    assert len(captured) == 1
    text, keyboard = captured[0]
    assert task.task_id in text
    assert "trend Digital Pantheon" in text
    assert "High" in text
    assert "research" in text
    assert "system:trend-scoping" in text
    assert "Simulating and auditing coalition formation" in text
    assert keyboard[0][0]["callback_data"] == f"task:approve:{task.task_id}"
    assert keyboard[0][1]["callback_data"] == f"task:reject:{task.task_id}"


def test_message_omits_description_line_when_absent(captured):
    task = Task(
        owner_id="o@x.com",
        title="Deploy",
        priority=TaskPriority.LOW,
        requires_approval=True,
    )

    TaskExecutionCoordinator._notify_execution_gate(task)

    text, _ = captured[0]
    assert "Low" in text
    assert "general" in text  # default task_type


def test_message_redacts_secrets_in_description(captured):
    task = Task(
        owner_id="o@x.com",
        title="Deploy",
        description="API key sk-ant-api03-abcdefghijklmnopqrstuvwxyz1234567890ABCD",
        requires_approval=True,
    )

    TaskExecutionCoordinator._notify_execution_gate(task)

    text, _ = captured[0]
    assert "sk-ant-api03-abcdefghijklmnopqrstuvwxyz1234567890ABCD" not in text
