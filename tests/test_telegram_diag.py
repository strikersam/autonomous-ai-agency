"""tests/test_telegram_diag.py

Regression test for the new ``/diag`` (admin) command in
``telegram_bot._process_update``. The command surfaces the bot's runtime
config so an operator can diagnose silent-drop / 401 / 409 / poller issues
in a single round-trip instead of grepping logs.

Cases:
  * admin sees a rich config snapshot (token-masked prefix, allowlist ids,
    admin ids, poller state, proxy base, "You" identifier).
  * non-admin gets a permission-denied message.
  * empty-allowlist diagnostic surfaces the "messages silently dropped" hint.
  * empty-token / short-token diagnostic surfaces the placeholder labels
    without leaking the actual token when the mask would overlap.
  * poller-disabled env flag is reflected.
  * silent-drop path emits a remediation hint when ALLOWED is empty.

Tests stub ``tb._send_message`` directly; no httpx / Telegram traffic.
"""
from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.notifications import bot as tb  # noqa: E402


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


class _GlobalsRestorer:
    """Snapshot/restore tb globals + TELEGRAM_POLLER_DISABLED env var."""
    _GLOBAL_ATTRS = (
        "TELEGRAM_BOT_TOKEN",
        "ALLOWED_USER_IDS",
        "ADMIN_USER_IDS",
        "_send_message",
        "_send_message_with_id",
        "_EMPTY_ALLOWLIST_WARNED",
    )

    def __init__(self, test: unittest.TestCase) -> None:
        self._test = test
        self._saved: dict[str, object] = {}

    def save(self) -> None:
        for attr in self._GLOBAL_ATTRS:
            self._saved[attr] = getattr(tb, attr, None)
        self._saved_poll_disable = os.environ.get("TELEGRAM_POLLER_DISABLED")

    def restore(self) -> None:
        for attr, original in self._saved.items():
            if original is _MISSING:
                if hasattr(tb, attr):
                    delattr(tb, attr)
            else:
                setattr(tb, attr, original)
        if self._saved_poll_disable is None:
            os.environ.pop("TELEGRAM_POLLER_DISABLED", None)
        else:
            os.environ["TELEGRAM_POLLER_DISABLED"] = self._saved_poll_disable


_MISSING = object()


class TestDiagCommand(unittest.TestCase):
    """``/diag`` behaviour under admin + non-admin + empty-allowlist states."""

    def setUp(self) -> None:
        self._r = _GlobalsRestorer(self)
        # Snapshot FIRST so tearDown restores whatever setUp / the test set.
        self._r.save()                # module uses it to avoid spamming the log on every silent drop.
        # Default config: token present, allowlist = {12, 99}, admin
        # allowlist = {12}, poller active.
        tb.TELEGRAM_BOT_TOKEN = "12345678901234567890:AAAA7END"  # noqa: S105
        tb.ALLOWED_USER_IDS = {12, 99}
        tb.ADMIN_USER_IDS = {12}
        os.environ.pop("TELEGRAM_POLLER_DISABLED", None)
        self.sent: list = []
        self._stub_send()

    def tearDown(self) -> None:
        self._r.restore()

    def _stub_send(self) -> None:
        """Replace ``_send_message`` for the next ``_process_update`` call."""
        self._orig_send = tb._send_message
        self._orig_send_id = tb._send_message_with_id

        async def _fake(_token, _chat, _text, parse_mode="Markdown"):  # noqa: ARG001
            self.sent.append(_text)
            return 12345

        tb._send_message = _fake  # type: ignore[assignment]
        tb._send_message_with_id = _fake  # type: ignore[assignment]

    def _restore_send(self) -> None:
        tb._send_message = self._orig_send  # type: ignore[assignment]
        tb._send_message_with_id = self._orig_send_id  # type: ignore[assignment]

    def _drive_diag_as(self, user_id: int) -> str:
        """Drive _process_update with a /diag message and return the response.

        Restores ``tb._send_message`` BEFORE returning so the next test sees
        a clean module state. Wrapped in try/finally so an assertion failure
        on this side still restores the real sender.
        """
        try:
            update = {
                "message": {
                    "chat": {"id": 1, "from": {"id": user_id}},
                    "from": {"id": user_id},
                    "text": "/diag",
                }
            }
            _run(tb._process_update("fake-token", update))
            self.assertTrue(
                self.sent,
                "_process_update must emit at least one message in response to /diag",
            )
            return self.sent[-1]
        finally:
            self._restore_send()

    def test_admin_sees_rich_diagnostic(self) -> None:
        text = self._drive_diag_as(12)
        self.assertIn("Telegram bot diagnostic", text)
        self.assertIn("Token:", text)
        self.assertIn("Allowed IDs:", text)
        self.assertIn("Admin IDs:", text)
        self.assertIn("Poller:", text)
        self.assertIn("Proxy base:", text)
        # Token masked (first 4 + last 4 with ellipsis). Token is
        # "12345678901234567890:AAAA7END" → mask is "1234…7END".
        self.assertIn("1234\u20267END", text)
        # Allowed IDs are sorted ints, comma-separated.
        self.assertIn("12, 99", text)
        self.assertIn("12", text)
        self.assertIn("ACTIVE", text)

    def test_admin_passes_allowlist_when_empty(self) -> None:
        # Locks the admin-bypass contract: admin seat authenticates
        # regardless of ALLOWED_USER_IDS so /diag stays reachable even
        # when the operator's allowlist is misconfigured.
        tb.ALLOWED_USER_IDS = set()
        tb.ADMIN_USER_IDS = {12}
        self.assertTrue(tb._is_allowed(12))

    def test_non_admin_sees_permission_denied(self) -> None:
        text = self._drive_diag_as(99)
        self.assertIn("Permission denied", text)
        # Diagnostic body MUST NOT leak the masked token to non-admins.
        self.assertNotIn("1234\u20267END", text)

    def test_empty_allowlist_diagnostic(self) -> None:
        tb.ALLOWED_USER_IDS = set()
        tb.ADMIN_USER_IDS = {12}
        text = self._drive_diag_as(12)
        self.assertIn("EMPTY \u2014 messages silently dropped", text)

    def test_poller_disabled_reflected(self) -> None:
        os.environ["TELEGRAM_POLLER_DISABLED"] = "true"
        text = self._drive_diag_as(12)
        self.assertIn("DISABLED", text)

    def test_empty_token_reported_with_clear_remediation(self) -> None:
        # Empty token + empty allowlist + empty admin list → the bootstrap we
        # were debugging in the original operator report. /diag must surface
        # both the empty-token placeholder AND the silent-drop hint.
        tb.TELEGRAM_BOT_TOKEN = ""
        tb.ALLOWED_USER_IDS = set()
        tb.ADMIN_USER_IDS = set()
        # Forcing an admin gate for the run (test-setUp we still have {12};
        # we want _drive_diag_as to read the empty state without our setUp
        # allowlist leaking into the assertion).
        tb.ADMIN_USER_IDS = {12}
        text = self._drive_diag_as(12)
        self.assertIn("`<empty>`", text)
        self.assertIn("EMPTY \u2014 messages silently dropped", text)

    def test_short_token_masks_too_short(self) -> None:
        # Length 8 token → first-4 / last-4 would overlap and leak the full
        # value. /diag MUST refuse to print overlapping regions.
        tb.TELEGRAM_BOT_TOKEN = "abcdEFGH"
        text = self._drive_diag_as(12)
        # Token itself must NOT appear in the diagnostic output.
        self.assertNotIn("abcdEFGH", text)
        self.assertIn("too short", text)


class TestSilentDropRemediation(unittest.TestCase):
    """The Operator Charter §"Telegram bot" silent-drop path MUST surface
    a remediation hint in the log when the allowlist is empty.

    Drives ``_process_update`` with a non-allowlisted user and captures log
    output via ``assertLogs`` so future refactors of the silent-drop branch
    can't quietly remove the helper message.
    """

    def setUp(self) -> None:
        tb.TELEGRAM_BOT_TOKEN = "real-token-placeholder-1234567890"
        tb.ALLOWED_USER_IDS = set()  # exact broken state
        tb.ADMIN_USER_IDS = {12}
        tb._EMPTY_ALLOWLIST_WARNED = False  # Throttle must start clean.

    def tearDown(self) -> None:
        tb._EMPTY_ALLOWLIST_WARNED = False  # Clean up module-level throttle.

    def test_warning_contains_chat_id_remediation(self) -> None:
        with self.assertLogs("qwen-telegram", level="WARNING") as captured:
            update = {
                "message": {
                    "chat": {"id": 1, "from": {"id": 999}},
                    "from": {"id": 999},
                    "text": "hello",
                }
            }
            # Stub _send_message so the silent-drop's lack-of-reply doesn't
            # escape us via Telegram.
            async def _fake(_t, _c, _text, parse_mode="Markdown"):  # noqa: ARG001
                return None
            orig = tb._send_message
            tb._send_message = _fake  # type: ignore[assignment]
            try:
                _run(tb._process_update("fake-token", update))
            finally:
                tb._send_message = orig  # type: ignore[assignment]
        # Find the silent-drop warning — should mention TELEGRAM_CHAT_ID.
        relevant = [r for r in captured.records if "allowlist EMPTY" in r.getMessage()]
        self.assertTrue(
            relevant,
            f"expected an 'allowlist EMPTY' WARNING; saw:\n"
            f"{[r.getMessage() for r in captured.records]}",
        )
        self.assertIn("TELEGRAM_CHAT_ID", relevant[0].getMessage())

    def test_second_silent_drop_downgraded_to_info(self) -> None:
        """Once we've warned once, subsequent silent drops must NOT spam the log."""
        # First drop sets the throttle flag.
        async def _fake(_t, _c, _text, parse_mode="Markdown"):  # noqa: ARG001
            return None
        orig = tb._send_message
        for user_id in (999, 998, 997):
            tb._send_message = _fake  # type: ignore[assignment]
            try:
                with self.assertLogs("qwen-telegram", level="DEBUG") as captured:
                    update = {
                        "message": {
                            "chat": {"id": 1, "from": {"id": user_id}},
                            "from": {"id": user_id},
                            "text": "hi",
                        }
                    }
                    _run(tb._process_update("fake-token", update))
            finally:
                tb._send_message = orig  # type: ignore[assignment]
            if user_id == 999:
                # First drop: WARNING with explicit hint.
                warn_lines = [
                    r for r in captured.records
                    if r.levelname == "WARNING" and "allowlist EMPTY" in r.getMessage()
                ]
                self.assertTrue(
                    warn_lines,
                    "first silent drop must log a WARNING with the hint",
                )
            else:
                # Subsequent drops: no fresh WARNING with the hint.
                warn_lines = [
                    r for r in captured.records
                    if r.levelname == "WARNING" and "allowlist EMPTY" in r.getMessage()
                ]
                self.assertFalse(
                    warn_lines,
                    f"later silent drops must NOT re-emit the hint WARNING; "
                    f"saw: {[r.getMessage() for r in captured.records]}",
                )


if __name__ == "__main__":
    unittest.main()
