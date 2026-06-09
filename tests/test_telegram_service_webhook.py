"""Regression tests for telegram_service.NotificationDispatcher._notify_webhook.

Covers the two bugs found by CodeRabbit on PR 487:
  1. Webhook payload must pass `error` and `result` through _redact_for_notification()
     so secrets, emails, and IPs cannot leak.
  2. _notify_webhook() must actually invoke _send() (was a no-op that defined
     the inner function but never started a thread to run it).
"""
from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from telegram_service import NotificationDispatcher, _redact_for_notification


class _FakeResponse:
    status_code = 200


def _wait_for_threads(timeout: float = 2.0) -> None:
    """Drain any daemon threads spawned by the dispatcher (webhook/telegram)."""
    deadline = threading.active_count()
    for _ in range(int(timeout * 10)):
        if threading.active_count() <= deadline:
            return
        threading.Event().wait(0.1)


def _make_task(*, error: object = None, result: object = "") -> SimpleNamespace:
    return SimpleNamespace(
        task_id="task-123",
        kind="unit_test",
        status="done" if error is None else "failed",
        error=error,
        result=result,
    )


class TestRedactForNotification:
    def test_redacts_sk_prefixed_token(self) -> None:
        assert "sk-<REDACTED>" in _redact_for_notification("key=sk-abcdefghijklmnop1234")

    def test_redacts_email(self) -> None:
        assert "<EMAIL_REDACTED>" in _redact_for_notification("contact alice@example.com today")

    def test_redacts_ip(self) -> None:
        assert "<IP_REDACTED>" in _redact_for_notification("server at 10.0.0.5:8000")


class TestNotifyWebhookRedaction:
    """The webhook payload MUST NOT contain raw secrets / emails / IPs."""

    def test_payload_redacts_secret_in_error(self) -> None:
        captured: dict = {}

        def fake_post(url, json=None, **_kwargs):
            captured.update(json or {})
            return _FakeResponse()

        dispatcher = NotificationDispatcher(webhook_url="https://hooks.example.com/test")
        task = _make_task(error="auth failed for token=sk-abcdefghijklmnop1234")

        with patch("httpx.Client") as client_cls:
            client = MagicMock()
            client.post.side_effect = fake_post
            client.__enter__.return_value = client
            client.__exit__.return_value = False
            client_cls.return_value = client

            dispatcher._notify_webhook(task)
            _wait_for_threads()

        assert "sk-abcdefghijklmnop1234" not in captured["error"]
        assert "sk-<REDACTED>" in captured["error"]

    def test_payload_redacts_email_in_result(self) -> None:
        captured: dict = {}

        def fake_post(url, json=None, **_kwargs):
            captured.update(json or {})
            return _FakeResponse()

        dispatcher = NotificationDispatcher(webhook_url="https://hooks.example.com/test")
        task = _make_task(result="contact alice@example.com for details")

        with patch("httpx.Client") as client_cls:
            client = MagicMock()
            client.post.side_effect = fake_post
            client.__enter__.return_value = client
            client.__exit__.return_value = False
            client_cls.return_value = client

            dispatcher._notify_webhook(task)
            _wait_for_threads()

        assert "alice@example.com" not in captured["result"]
        assert "<EMAIL_REDACTED>" in captured["result"]

    def test_payload_keeps_safe_fields_unredacted(self) -> None:
        captured: dict = {}

        def fake_post(url, json=None, **_kwargs):
            captured.update(json or {})
            return _FakeResponse()

        dispatcher = NotificationDispatcher(webhook_url="https://hooks.example.com/test")
        # No error arg -> _make_task defaults status to "done"
        task = _make_task(result="simple result")

        with patch("httpx.Client") as client_cls:
            client = MagicMock()
            client.post.side_effect = fake_post
            client.__enter__.return_value = client
            client.__exit__.return_value = False
            client_cls.return_value = client

            dispatcher._notify_webhook(task)
            _wait_for_threads()

        assert captured["task_id"] == "task-123"
        assert captured["kind"] == "unit_test"
        assert captured["status"] == "done"
        assert captured["error"] is None
        assert captured["result"] == "simple result"


class TestNotifyWebhookActuallyFires:
    """Regression: _notify_webhook used to define _send() but never call it."""

    def test_notify_webhook_actually_calls_post(self) -> None:
        post_calls: list = []

        def fake_post(url, json=None, **_kwargs):
            post_calls.append((url, json))
            return _FakeResponse()

        dispatcher = NotificationDispatcher(webhook_url="https://hooks.example.com/test")
        task = _make_task()

        with patch("httpx.Client") as client_cls:
            client = MagicMock()
            client.post.side_effect = fake_post
            client.__enter__.return_value = client
            client.__exit__.return_value = False
            client_cls.return_value = client

            dispatcher._notify_webhook(task)
            _wait_for_threads()

        assert len(post_calls) == 1, "webhook should fire exactly once"
        assert post_calls[0][0] == "https://hooks.example.com/test"
        assert post_calls[0][1]["task_id"] == "task-123"

    def test_no_webhook_url_skips_silently(self) -> None:
        dispatcher = NotificationDispatcher(webhook_url="")
        task = _make_task()

        with patch("httpx.Client") as client_cls:
            client = MagicMock()
            client_cls.return_value = client
            dispatcher._notify_webhook(task)
            _wait_for_threads()

        client.post.assert_not_called()
