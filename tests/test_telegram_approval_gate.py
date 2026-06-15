"""Tests for the TELEGRAM_CHAT_ID single-var convention and the proactive
Telegram approval-gate push (Autonomy Charter G1).

Covers:
  - NotificationDispatcher._parse_chat_ids() honoring TELEGRAM_CHAT_ID as a
    fallback for notification delivery.
  - NotificationDispatcher.send_approval_gate() — message content, inline
    [Approve]/[Reject] keyboard, and redaction.
  - TelegramBotManager.start()/get_status() accepting TELEGRAM_CHAT_ID as a
    fallback for "users configured" (no TELEGRAM_ALLOWED_USER_IDS required).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from telegram_service import NotificationDispatcher, TelegramBotManager


class _FakeResponse:
    status_code = 200


@pytest.fixture(autouse=True)
def _clear_telegram_env(monkeypatch):
    for var in (
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "TELEGRAM_NOTIFY_CHAT_IDS",
        "TELEGRAM_ADMIN_USER_IDS",
        "TELEGRAM_ALLOWED_USER_IDS",
    ):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def _inline_threads(monkeypatch):
    """Run NotificationDispatcher's background-thread sends synchronously."""

    class _SyncThread:
        def __init__(self, target=None, daemon=None, *args, **kwargs):
            self._target = target

        def start(self):
            if self._target is not None:
                self._target()

    monkeypatch.setattr("telegram_service.threading.Thread", _SyncThread)


# ── NotificationDispatcher._parse_chat_ids ───────────────────────────────────


def test_parse_chat_ids_uses_telegram_chat_id(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "8120976")
    assert NotificationDispatcher._parse_chat_ids() == [8120976]


def test_parse_chat_ids_notify_chat_ids_takes_precedence(monkeypatch):
    monkeypatch.setenv("TELEGRAM_NOTIFY_CHAT_IDS", "111,222")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "8120976")
    assert NotificationDispatcher._parse_chat_ids() == [111, 222]


def test_parse_chat_ids_falls_back_to_admin_then_allowed(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ADMIN_USER_IDS", "555")
    assert NotificationDispatcher._parse_chat_ids() == [555]

    monkeypatch.delenv("TELEGRAM_ADMIN_USER_IDS")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "777")
    assert NotificationDispatcher._parse_chat_ids() == [777]


def test_parse_chat_ids_empty_when_nothing_set():
    assert NotificationDispatcher._parse_chat_ids() == []


# ── NotificationDispatcher.send_approval_gate ────────────────────────────────


def test_send_approval_gate_returns_false_without_config():
    dispatcher = NotificationDispatcher(telegram_token="", telegram_chat_ids=[])  # nosec B106 - test fixture, not a real token
    assert dispatcher.send_approval_gate(run_id="wfo_x", company_id=None, goal="do x") is False


def test_send_approval_gate_sends_message_with_approve_reject_keyboard(_inline_threads):
    captured: dict = {}

    def fake_post(url, json=None, **_kwargs):
        captured["url"] = url
        captured["json"] = json
        return _FakeResponse()

    dispatcher = NotificationDispatcher(telegram_token="tok", telegram_chat_ids=[100])  # nosec B106 - test fixture, not a real token

    with patch("httpx.Client") as client_cls:
        client = MagicMock()
        client.post.side_effect = fake_post
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        client_cls.return_value = client

        result = dispatcher.send_approval_gate(
            run_id="wfo_abc123",
            company_id="acme-co",
            goal="Upgrade payments webhook",
            plan_steps=["Step one", "Step two"],
            risk_reason="touches payments",
        )

    assert result is True
    assert captured["url"] == "https://api.telegram.org/bottok/sendMessage"
    assert captured["json"]["chat_id"] == 100
    text = captured["json"]["text"]
    assert "wfo_abc123" in text
    assert "acme-co" in text
    assert "Upgrade payments webhook" in text
    assert "touches payments" in text
    assert "Step one" in text and "Step two" in text

    keyboard = captured["json"]["reply_markup"]["inline_keyboard"]
    assert keyboard == [[
        {"text": "✅ Approve", "callback_data": "wfo:approve:wfo_abc123"},
        {"text": "❌ Reject", "callback_data": "wfo:reject:wfo_abc123"},
    ]]


def test_send_approval_gate_redacts_goal_and_steps(_inline_threads):
    captured: dict = {}

    def fake_post(url, json=None, **_kwargs):
        captured["json"] = json
        return _FakeResponse()

    dispatcher = NotificationDispatcher(telegram_token="tok", telegram_chat_ids=[100])  # nosec B106 - test fixture, not a real token

    with patch("httpx.Client") as client_cls:
        client = MagicMock()
        client.post.side_effect = fake_post
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        client_cls.return_value = client

        dispatcher.send_approval_gate(
            run_id="wfo_x",
            company_id=None,
            goal="contact alice@example.com about token=sk-abcdefghijklmnop1234",
            plan_steps=["ping bob@example.com"],
        )

    text = captured["json"]["text"]
    assert "alice@example.com" not in text
    assert "bob@example.com" not in text
    assert "sk-abcdefghijklmnop1234" not in text
    assert "<EMAIL_REDACTED>" in text


def test_send_approval_gate_sends_to_all_configured_chats(_inline_threads):
    posts: list = []

    def fake_post(url, json=None, **_kwargs):
        posts.append(json["chat_id"])
        return _FakeResponse()

    dispatcher = NotificationDispatcher(telegram_token="tok", telegram_chat_ids=[100, 200])  # nosec B106 - test fixture, not a real token

    with patch("httpx.Client") as client_cls:
        client = MagicMock()
        client.post.side_effect = fake_post
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        client_cls.return_value = client

        dispatcher.send_approval_gate(run_id="wfo_x", company_id=None, goal="g")

    assert posts == [100, 200]


# ── TelegramBotManager: TELEGRAM_CHAT_ID fallback ────────────────────────────


def test_telegram_bot_manager_start_requires_token(tmp_path):
    mgr = TelegramBotManager(root=tmp_path)
    assert mgr.start() is False


def test_telegram_bot_manager_start_requires_allowed_or_chat_id(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    mgr = TelegramBotManager(root=tmp_path)
    assert mgr.start() is False


def test_telegram_bot_manager_start_accepts_chat_id_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "8120976")
    mgr = TelegramBotManager(root=tmp_path)
    monkeypatch.setattr(mgr, "_run_bot", lambda: None)
    assert mgr.start(blocking=True) is True


def test_telegram_bot_manager_status_users_configured_via_chat_id(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "8120976")
    mgr = TelegramBotManager(root=tmp_path)
    status = mgr.get_status()
    assert status["token_configured"] is True
    assert status["users_configured"] is True


def test_telegram_bot_manager_status_users_not_configured_without_chat_id(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    mgr = TelegramBotManager(root=tmp_path)
    status = mgr.get_status()
    assert status["users_configured"] is False
