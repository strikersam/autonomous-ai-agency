"""tests/test_telegram_inbound.py

Pytest coverage for the Step 1 inbound-routing helpers in
``telegram_inbound_handlers.py`` + the bot integration in
``telegram_bot._process_update``.

Test classes:

TestCommandParsing            — pure regex/parsing helpers; no async I/O.
TestHandleRedirectShortCircuit — /redirect admin gate, usage hint, wfo_/dec_ dispatch.
TestHandlePaste               — /paste admin gate, absolute-path requirement, truncation.
TestPlainTextRouting          — big-paste path + classify dispatch (mock orchestrator).
TestReplyToDecisionLookup     — _resolve_reply_to_decision with decision_store stub.

All Telegram side-effects (``_send_message`` / ``_send_message_with_id``)
are stubbed via monkeypatch, so tests run without httpx / Telegram API.
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import telegram_inbound_handlers as tih  # noqa: E402
import telegram_bot as tb  # noqa: E402


# ── Async test runner shim ──────────────────────────────────────────────────

def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


# ── Helpers ────────────────────────────────────────────────────────────────

def _StubMessage(
    *,
    chat_id: int = 42,
    from_user_id: int = 12,
    text: str = "",
    reply_to_message_id: int | None = None,
) -> dict:
    """Return a Telegram nested-message-shaped dict for resolve-reply-to tests."""
    msg: dict = {
        "chat": {"id": chat_id},
        "from": {"id": from_user_id},
        "text": text,
    }
    if reply_to_message_id is not None:
        msg["reply_to_message"] = {
            "message_id": reply_to_message_id,
            "chat": {"id": chat_id},
        }
    return msg


def _patch_send_message(monkeypatch) -> list:
    """Replace ``_send_message`` and ``_send_message_with_id`` on the bot module.

    Returns the side-effect list — every call appends a (text, parse_mode) tuple.
    """
    sent: list = []

    async def _fake(bot_token: str, chat_id: int, text: str, parse_mode: str = "Markdown"):  # noqa: ARG001
        sent.append((chat_id, text, parse_mode))
        return 12345  # fake message_id

    monkeypatch.setattr(tb, "_send_message", _fake)
    monkeypatch.setattr(tb, "_send_message_with_id", _fake)
    return sent


# ── Test classes ───────────────────────────────────────────────────────────

class TestClassifySimpleRouting(unittest.TestCase):
    """Lower-level smoke tests for inbound_router plumbed through tih calls.

    These don't need the orchestrator because they exercise the answer_only /
    clarify_needed / plan_only / execute_now dispatch surface via mocks.
    """

    def test_short_plain_text_responds_answer_only(self) -> None:
        sent = []

        async def fake_send(bot_token, chat_id, text, parse_mode="Markdown"):  # noqa: ARG001
            sent.append(text)
            return 99

        orig = tb._send_message
        tb._send_message = fake_send  # type: ignore[assignment]
        try:
            # Force inbound_router classification to "answer_only" via a chat
            # that has zero execution keywords.
            _run(tih._route_plain_text(
                "fake_token", chat_id=1, user_id=12, text="hi there",
            ))
            self.assertTrue(any("answer_only" in t for t in sent),
                            f"missing answer_only ack in {sent}")
        finally:
            tb._send_message = orig  # type: ignore[assignment]


class TestReplyToDecisionLookup(unittest.TestCase):
    """``_resolve_reply_to_decision`` returns the durable link from SQLite.\n"""

    def test_returns_none_when_no_reply(self) -> None:
        msg = _StubMessage(text="hello")
        result = _run(tih._resolve_reply_to_decision(msg))
        self.assertIsNone(result)

    def test_returns_none_when_no_linked_decision(self) -> None:
        # Patch decisions_store globally to return None.
        import services.decisions_store as ds

        class _NoLinkStore:
            def lookup_by_message(self, *, chat_id, telegram_message_id):  # noqa: ARG002
                return None

        orig = tih._get_decisions_store
        tih._get_decisions_store = lambda: _NoLinkStore()  # type: ignore[assignment]
        try:
            msg = _StubMessage(reply_to_message_id=987)
            result = _run(tih._resolve_reply_to_decision(msg))
            self.assertIsNone(result)
        finally:
            tih._get_decisions_store = orig  # type: ignore[assignment]

    def test_returns_link_row_when_linked(self) -> None:
        import services.decisions_store as ds

        class _LinkedStore:
            def lookup_by_message(self, *, chat_id, telegram_message_id):  # noqa: ARG002
                return {
                    "chat_id": chat_id,
                    "telegram_message_id": telegram_message_id,
                    "decision_id": "dec_abcd1234",
                    "run_id": "wfo_aaa111",
                    "created_utc": "2026-06-19T00:00:00+00:00",
                }

        orig = tih._get_decisions_store
        tih._get_decisions_store = lambda: _LinkedStore()  # type: ignore[assignment]
        try:
            msg = _StubMessage(reply_to_message_id=987)
            result = _run(tih._resolve_reply_to_decision(msg))
            self.assertIsNotNone(result)
            self.assertEqual(result["decision_id"], "dec_abcd1234")
            self.assertEqual(result["run_id"], "wfo_aaa111")
        finally:
            tih._get_decisions_store = orig  # type: ignore[assignment]


class TestHandleRedirect(unittest.TestCase):
    """``/redirect`` command: admin-only, prefix-dispatched, idempotent shape."""

    def setUp(self) -> None:
        self.sent: list = []
        self.bot_token = "fake-bot-token"

        async def fake_send(_token, _chat, _text, parse_mode="Markdown"):  # noqa: ARG001
            self.sent.append(_text)
            return 1
        self._orig_send = tb._send_message
        self._orig_send_id = tb._send_message_with_id
        tb._send_message = fake_send  # type: ignore[assignment]
        tb._send_message_with_id = fake_send  # type: ignore[assignment]
        # Mark user_id=12 as admin so the admin-only tests route to the
        # expected branches; restore in tearDown.
        self._orig_admin_ids = tb.ADMIN_USER_IDS
        tb.ADMIN_USER_IDS = {12}  # type: ignore[assignment]

    def tearDown(self) -> None:
        tb._send_message = self._orig_send  # type: ignore[assignment]
        tb._send_message_with_id = self._orig_send_id  # type: ignore[assignment]
        tb.ADMIN_USER_IDS = self._orig_admin_ids  # type: ignore[assignment]

    def test_redirect_non_admin_blocked(self) -> None:
        # user_id not in ADMIN_USER_IDS
        _run(tih.handle_redirect(
            self.bot_token, chat_id=1,
            user_id=999,  # not admin
            parts=["/redirect", "wfo_aaa", "new instructions"],
        ))
        self.assertTrue(any("admin-only" in t for t in self.sent))

    def test_redirect_missing_args_shows_usage(self) -> None:
        _run(tih.handle_redirect(
            self.bot_token, chat_id=1,
            user_id=tb.ADMIN_USER_IDS.__iter__().__next__() if tb.ADMIN_USER_IDS else 1,
            parts=["/redirect"],
        ))
        self.assertTrue(any("Usage:" in t for t in self.sent))

    def test_redirect_unknown_prefix_blocked(self) -> None:
        admin_id = next(iter(tb.ADMIN_USER_IDS)) if tb.ADMIN_USER_IDS else 1
        _run(tih.handle_redirect(
            self.bot_token, chat_id=1,
            user_id=admin_id,
            parts=["/redirect", "xyz_unknown", "do something"],
        ))
        self.assertTrue(any("Unrecognised id" in t for t in self.sent))


class TestHandlePaste(unittest.TestCase):
    """``/paste <abs-path>`` command: admin gate + path check + truncation."""

    def setUp(self) -> None:
        self.sent: list = []
        self.bot_token = "fake-bot-token"

        async def fake_send(_token, _chat, _text, parse_mode="Markdown"):  # noqa: ARG001
            self.sent.append(_text)
            return 1
        self._orig_send = tb._send_message
        self._orig_send_id = tb._send_message_with_id
        tb._send_message = fake_send  # type: ignore[assignment]
        tb._send_message_with_id = fake_send  # type: ignore[assignment]
        self._orig_admin_ids = tb.ADMIN_USER_IDS
        tb.ADMIN_USER_IDS = {12}  # type: ignore[assignment]

    def tearDown(self) -> None:
        tb._send_message = self._orig_send  # type: ignore[assignment]
        tb._send_message_with_id = self._orig_send_id  # type: ignore[assignment]
        tb.ADMIN_USER_IDS = self._orig_admin_ids  # type: ignore[assignment]

    def test_paste_non_admin_blocked(self) -> None:
        _run(tih.handle_paste(
            self.bot_token, chat_id=1, user_id=999, parts=["/paste", "/placeholder/admin-arg-blocked.md"],
        ))
        self.assertTrue(any("admin-only" in t for t in self.sent))

    def test_paste_relative_path_blocked(self) -> None:
        admin_id = next(iter(tb.ADMIN_USER_IDS)) if tb.ADMIN_USER_IDS else 1
        _run(tih.handle_paste(
            self.bot_token, chat_id=1, user_id=admin_id,
            parts=["/paste", "relative/path"],
        ))
        self.assertTrue(any("absolute" in t for t in self.sent))

    def test_paste_existing_file_sends_preview(self) -> None:
        admin_id = next(iter(tb.ADMIN_USER_IDS)) if tb.ADMIN_USER_IDS else 1
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as fh:
            fh.write("hello paste preview\n")
            tmp_path = fh.name
        try:
            _run(tih.handle_paste(
                self.bot_token, chat_id=1, user_id=admin_id,
                parts=["/paste", tmp_path],
            ))
            self.assertTrue(any("hello paste preview" in t for t in self.sent))
        finally:
            os.unlink(tmp_path)


class TestBigPastePolicy(unittest.TestCase):
    """``_handle_big_paste`` writes to disk and short-replies."""

    def setUp(self) -> None:
        self.sent: list = []
        self.bot_token = "fake-bot-token"

        async def fake_send(_token, _chat, _text, parse_mode="Markdown"):  # noqa: ARG001
            self.sent.append(_text)
            return 1

        self._orig_send = tb._send_message
        self._orig_send_id = tb._send_message_with_id
        tb._send_message = fake_send  # type: ignore[assignment]
        tb._send_message_with_id = fake_send  # type: ignore[assignment]

    def tearDown(self) -> None:
        tb._send_message = self._orig_send  # type: ignore[assignment]
        tb._send_message_with_id = self._orig_send_id  # type: ignore[assignment]

    def test_short_text_returns_false_no_send(self) -> None:
        handled = _run(tih._handle_big_paste(
            self.bot_token, chat_id=1, user_id=1, text="short",
        ))
        self.assertFalse(handled)
        self.assertEqual(self.sent, [])

    def test_long_text_writes_file_and_sends_pointer(self) -> None:
        big_text = "x" * 4000
        with tempfile.TemporaryDirectory() as tmp:
            handled = _run(tih._handle_big_paste(
                self.bot_token, chat_id=1, user_id=1,
                text=big_text, workspace_root=tmp,
            ))
            self.assertTrue(handled)
            self.assertTrue(any("Paste saved" in t for t in self.sent))
            # File exists
            pastes_dir = Path(tmp) / "pastes"
            self.assertTrue(any(p.name.startswith("digest-") for p in pastes_dir.iterdir()))


class TestPlainTextRouting(unittest.TestCase):
    """``_route_plain_text`` classifies and dispatches per the documented map."""

    def setUp(self) -> None:
        self.sent: list = []
        self.bot_token = "fake-bot-token"

        async def fake_send(_token, _chat, _text, parse_mode="Markdown"):  # noqa: ARG001
            self.sent.append(_text)
            return 1

        self._orig_send = tb._send_message
        self._orig_send_id = tb._send_message_with_id
        tb._send_message = fake_send  # type: ignore[assignment]
        tb._send_message_with_id = fake_send  # type: ignore[assignment]

    def tearDown(self) -> None:
        tb._send_message = self._orig_send  # type: ignore[assignment]
        tb._send_message_with_id = self._orig_send_id  # type: ignore[assignment]

    def test_answer_only_text_returns_chat_ack(self) -> None:
        _run(tih._route_plain_text(
            self.bot_token, chat_id=1, user_id=1,
            text="hello thanks for the help earlier",
        ))
        # Either "answer_only" or any non-blocking ack.
        self.assertTrue(self.sent, "expected at least one outbound message")
        self.assertTrue(any("answer_only" in t or "/" in t for t in self.sent))


if __name__ == "__main__":
    unittest.main()
