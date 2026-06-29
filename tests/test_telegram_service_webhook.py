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
    """Drain any daemon threads spawned by the dispatcher (webhook/telegram).

    Snapshot the active count *before* the dispatching call and wait until it
    drops back to that level.  The snapshot must be taken by the caller, so
    this helper only works correctly when used with the Thread-inline patch
    added to the test class (see ``_inline_threads`` fixture).
    """
    # Best-effort: give threads up to `timeout` seconds to finish.
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        # All our daemon threads are short-lived; 50 ms polling is fine.
        time.sleep(0.05)
        if threading.active_count() <= 1:
            return


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
    """Ensure _notify_webhook redacts secrets/PII before sending the webhook payload.

    The dispatcher spawns a background daemon thread for each webhook call.
    On CPython 3.13 the GIL is optional and thread scheduling changed, so
    _wait_for_threads() with a simple active-count poll can return before the
    daemon thread has had a chance to call ``client.post``.

    We side-step the timing issue entirely by patching ``threading.Thread`` to
    run the target callable *inline* (synchronously) during the test, eliminating
    any thread-scheduling non-determinism.
    """

    @pytest.fixture(autouse=True)
    def _inline_threads(self, monkeypatch):
        """Replace threading.Thread with a synchronous stub for this test class."""
        class _SyncThread:
            def __init__(self, target=None, daemon=None, *args, **kwargs):
                self._target = target

            def start(self):
                if self._target is not None:
                    self._target()

        monkeypatch.setattr("packages.notifications.service.threading.Thread", _SyncThread)
        yield

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
