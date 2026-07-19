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


# ── Issue #1072 follow-ups: context-rich message body ───────────────────────
# The user reported the approval message was useless because it didn't tell
# them (1) WHY the task needs approval, (2) WHAT the agent will actually do,
# (3) WHERE to inspect it on the dashboard. These tests pin those sections.

def test_message_includes_dashboard_link_when_public_url_set(captured, monkeypatch):
    monkeypatch.setenv("PUBLIC_URL", "https://demo.example.com")
    task = Task(
        owner_id="o@x.com", title="Deploy", requires_approval=True,
    )
    TaskExecutionCoordinator._notify_execution_gate(task)
    text, _ = captured[0]
    assert "https://demo.example.com/admin/tasks?task=" + task.task_id in text
    assert "Inspect on dashboard" in text


def test_message_excludes_dashboard_link_when_public_url_unset(captured, monkeypatch):
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    task = Task(
        owner_id="o@x.com", title="Deploy", requires_approval=True,
    )
    TaskExecutionCoordinator._notify_execution_gate(task)
    text, _ = captured[0]
    assert "Inspect on dashboard" not in text
    # No broken "https://" line should leak into the message.
    assert "https://" not in text


def test_message_includes_risk_class_hint_from_tags(captured):
    task = Task(
        owner_id="o@x.com",
        title="Deploy hotfix",
        description="Fixing prod issue",
        tags=["code-change", "deploy"],
        requires_approval=True,
    )
    TaskExecutionCoordinator._notify_execution_gate(task)
    text, _ = captured[0]
    assert "Why this needs your approval" in text
    assert "code-change" in text
    assert "deploy" in text


def test_message_includes_full_description_without_truncation(captured):
    """Issue #1072: description was truncated to 280 chars. Now it shows the
    full description (up to 1500 chars, then a `… view on dashboard` pointer)."""
    description = "Deploy a hotfix to revenue-critical checkout endpoint. " * 5
    task = Task(
        owner_id="o@x.com",
        title="Deploy",
        description=description,
        requires_approval=True,
    )
    TaskExecutionCoordinator._notify_execution_gate(task)
    text, _ = captured[0]
    # The first 280 chars used to be all the user saw; now they see much more.
    assert description[:280] in text
    # And the message includes the descriptive section banner.
    assert "What this task is" in text


def test_message_truncates_very_long_description_with_pointer(captured, monkeypatch):
    """Description > 1500 chars: shown truncated with a 'view on dashboard' pointer."""
    monkeypatch.setenv("PUBLIC_URL", "https://demo.example.com")
    description = "x" * 2000
    task = Task(
        owner_id="o@x.com",
        title="Deploy",
        description=description,
        requires_approval=True,
    )
    TaskExecutionCoordinator._notify_execution_gate(task)
    text, _ = captured[0]
    # Only the first 1500 chars get rendered (plus the truncation marker).
    assert ("x" * 1500) in text
    assert ("x" * 1501) not in text
    # And the operator is pointed to the dashboard for the full text.
    assert "full text on dashboard" in text


def test_message_includes_agent_label_when_assigned(captured):
    task = Task(
        owner_id="o@x.com",
        title="Deploy",
        agent_id="agent_revenue_strategist_42",
        requires_approval=True,
    )
    TaskExecutionCoordinator._notify_execution_gate(task)
    text, _ = captured[0]
    assert "Agent that will run" in text
    assert "agent_revenue_strategist_42" in text


def test_message_falls_back_to_review_reason_when_no_structured_hints(captured):
    """When no risk:tag or known tag matches and the task carries a free-form
    review_reason, surface it as the 'why' so the operator has context."""
    task = Task(
        owner_id="o@x.com",
        title="Migrate user data",
        description="Move pii",
        review_reason="Compliance officer requested a human review",
        requires_approval=True,
    )
    TaskExecutionCoordinator._notify_execution_gate(task)
    text, _ = captured[0]
    assert "Why this needs your approval" in text
    assert "Compliance officer requested a human review" in text


def test_message_uses_generic_risk_hint_when_no_context_available(captured):
    """Fallback: the 'why' section is never empty for a gated task."""
    task = Task(
        owner_id="o@x.com",
        title="Generic task",
        requires_approval=True,
    )
    TaskExecutionCoordinator._notify_execution_gate(task)
    text, _ = captured[0]
    assert "Why this needs your approval" in text
    assert "outward-facing" in text or "risky" in text
