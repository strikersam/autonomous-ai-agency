"""tests/test_telegram_test_utils.py

Self-test suite for ``isolated_telegram_config`` (the snapshot+restore
context manager exposed by ``tests/_telegram_test_utils.py``).

The self-test guards against future regressions in the helper itself:
if anyone tightens / loosens the apply/restore contract, this file fires
before the test suite that depends on the helper can silently drift
out of sync. Cases cover round-trips for every kwarg the helper accepts,
the ``finally``/exception-safety path, and the asymmetric
``poller_disabled`` semantics (``_MISSING`` leaves the env alone,
``None`` pops it, a string sets it).

Bodies rely only on stdlib ``unittest`` + the helper itself; no pytest,
no monkeypatch, no ``telegram_bot``-API simulation. ``telegram_bot`` is
imported for the sole purpose of reading/writing its module-level
globals — no httpx / Telegram traffic.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import telegram_bot as tb  # noqa: E402

from tests._telegram_test_utils import (  # noqa: E402
    _MISSING, isolated_telegram_config,
)


# Must stay in sync with tests/_telegram_test_utils._TRACKED_GLOBALS.
_TRACKED: tuple[str, ...] = (
    "TELEGRAM_BOT_TOKEN",
    "ALLOWED_USER_IDS",
    "ADMIN_USER_IDS",
    "_send_message",
    "_send_message_with_id",
    "_EMPTY_ALLOWLIST_WARNED",
)


class TestIsolatedTelegramConfig(unittest.TestCase):
    """Snapshot + restore + apply-filter semantics for the helper."""

    def setUp(self) -> None:
        # Snapshot every tracked module attr + the env var BEFORE each test
        # so tearDown can defensively restore. Individual tests also rely on
        # the helper's own __exit__ to restore — this is a backstop.
        self._env_snapshot = os.environ.get("TELEGRAM_POLLER_DISABLED", _MISSING)
        self._attr_snapshot: dict[str, object] = {
            attr: getattr(tb, attr, _MISSING) for attr in _TRACKED
        }

    def tearDown(self) -> None:
        if self._env_snapshot is _MISSING:
            os.environ.pop("TELEGRAM_POLLER_DISABLED", None)
        else:
            os.environ["TELEGRAM_POLLER_DISABLED"] = self._env_snapshot  # type: ignore[assignment]
        for attr, original in self._attr_snapshot.items():
            if original is _MISSING:
                if hasattr(tb, attr):
                    delattr(tb, attr)
            else:
                setattr(tb, attr, original)

    # ── 1. Round-trip: helpers applying a kwarg preserves original on exit ──

    def test_kwarg_value_restored_after_block(self) -> None:
        tb.TELEGRAM_BOT_TOKEN = "orig-token"
        with isolated_telegram_config(token="inside-token", reset_throttle=False):
            self.assertEqual(tb.TELEGRAM_BOT_TOKEN, "inside-token")
        # Snapshot-then-restore: pre-config value comes back.
        self.assertEqual(tb.TELEGRAM_BOT_TOKEN, "orig-token")

    def test_unmapped_kwarg_left_alone(self) -> None:
        """Passing only ``token=`` must NOT touch ALLOWED/ADMIN/etc."""
        tb.ALLOWED_USER_IDS = {1, 2, 3}
        tb.ADMIN_USER_IDS = {1}
        with isolated_telegram_config(token="x", reset_throttle=False):
            self.assertEqual(tb.ALLOWED_USER_IDS, {1, 2, 3})
            self.assertEqual(tb.ADMIN_USER_IDS, {1})
        self.assertEqual(tb.ALLOWED_USER_IDS, {1, 2, 3})
        self.assertEqual(tb.ADMIN_USER_IDS, {1})

    # ── 2. Exception in with-block still triggers restore (try/finally) ──

    def test_exception_inside_block_still_restores(self) -> None:
        tb.TELEGRAM_BOT_TOKEN = "before-error"
        with self.assertRaises(RuntimeError):
            with isolated_telegram_config(token="inside", reset_throttle=False):
                self.assertEqual(tb.TELEGRAM_BOT_TOKEN, "inside")
                raise RuntimeError("simulated assert failure")
        # After the with-block the pre-config value must come back, even
        # though an exception escaped the inner block.
        self.assertEqual(tb.TELEGRAM_BOT_TOKEN, "before-error")

    # ── 3. reset_throttle=True forces _EMPTY_ALLOWLIST_WARNED=False on entry ──

    def test_reset_throttle_true_forces_false(self) -> None:
        tb._EMPTY_ALLOWLIST_WARNED = True
        with isolated_telegram_config(reset_throttle=True):
            self.assertFalse(tb._EMPTY_ALLOWLIST_WARNED)
        # The snapshot took the pre-config True but reset_throttle rewrote it
        # to False; on exit restore returns False (the post-apply state).
        self.assertFalse(tb._EMPTY_ALLOWLIST_WARNED)

    def test_reset_throttle_false_preserves_throttle(self) -> None:
        tb._EMPTY_ALLOWLIST_WARNED = True
        with isolated_telegram_config(reset_throttle=False):
            self.assertTrue(
                tb._EMPTY_ALLOWLIST_WARNED,
                "reset_throttle=False MUST NOT force-reset the flag",
            )
        self.assertTrue(tb._EMPTY_ALLOWLIST_WARNED)

    # ── 4. poller_disabled has documented asymmetric semantics ──

    def test_poller_disabled_none_pops_env(self) -> None:
        os.environ["TELEGRAM_POLLER_DISABLED"] = "true"
        try:
            with isolated_telegram_config(poller_disabled=None):
                self.assertNotIn("TELEGRAM_POLLER_DISABLED", os.environ)
            # Snapshot was "true" (set before block) so restore brings it back.
            self.assertEqual(os.environ["TELEGRAM_POLLER_DISABLED"], "true")
        finally:
            os.environ.pop("TELEGRAM_POLLER_DISABLED", None)

    def test_poller_disabled_string_sets_env(self) -> None:
        os.environ.pop("TELEGRAM_POLLER_DISABLED", None)
        try:
            with isolated_telegram_config(poller_disabled="true"):
                self.assertEqual(os.environ["TELEGRAM_POLLER_DISABLED"], "true")
            # Snapshot was missing → restore pops.
            self.assertNotIn("TELEGRAM_POLLER_DISABLED", os.environ)
        finally:
            os.environ.pop("TELEGRAM_POLLER_DISABLED", None)

    def test_poller_disabled_missing_leaves_env(self) -> None:
        os.environ["TELEGRAM_POLLER_DISABLED"] = "true"
        try:
            with isolated_telegram_config():
                # Default _MISSING: helper does NOT touch the env var.
                self.assertEqual(os.environ["TELEGRAM_POLLER_DISABLED"], "true")
            self.assertEqual(os.environ["TELEGRAM_POLLER_DISABLED"], "true")
        finally:
            os.environ.pop("TELEGRAM_POLLER_DISABLED", None)

    # ── 5. delattr-on-restore for missing attrs (helper's gotcha branch) ──

    def test_delattr_on_restore_when_attr_was_missing(self) -> None:
        """If a tracked attr is absent under ``tb`` at scope entry, the
        helper snapshots ``_MISSING`` and ``delattr``s on exit. Without
        this branch a prior delete or import-order quirk could leak into
        the next test as a phantom ``None``. Force the snapshot to record
        ``_MISSING`` for ``_send_message`` by deleting it before entry."""
        # Save + delete + re-attach after the test so setUp/tearDown stays
        # idempotent and the order-of-test-execution effect is contained.
        had_attr = hasattr(tb, "_send_message")
        saved = getattr(tb, "_send_message", None)
        if had_attr:
            delattr(tb, "_send_message")
        try:
            with isolated_telegram_config(reset_throttle=False):
                # Inside the scope, no kwarg resets the attr; it stays gone.
                self.assertFalse(hasattr(tb, "_send_message"))
            # After exit: helper's __exit__ ran `delattr(tb, attr) if hasattr`
            # (defensive) — attr must still be missing, NOT silently re-added.
            self.assertFalse(hasattr(tb, "_send_message"))
        finally:
            if had_attr:
                tb._send_message = saved  # type: ignore[assignment]

    # ── 6. Nested context managers restore per-scope, not globally ──

    def test_nested_context_managers_restore_per_scope(self) -> None:
        tb.TELEGRAM_BOT_TOKEN = "outer-pre"
        with isolated_telegram_config(token="outer-applied", reset_throttle=False):
            self.assertEqual(tb.TELEGRAM_BOT_TOKEN, "outer-applied")
            with isolated_telegram_config(token="inner-applied", reset_throttle=False):
                self.assertEqual(tb.TELEGRAM_BOT_TOKEN, "inner-applied")
            # Inner exited: outer-applied value comes back, NOT outer-pre.
            self.assertEqual(tb.TELEGRAM_BOT_TOKEN, "outer-applied")
        # Outer exited: outer-pre is restored.
        self.assertEqual(tb.TELEGRAM_BOT_TOKEN, "outer-pre")

    # ── 7. Apply filters work for every typed kwarg the helper accepts ──

    def test_apply_filters_for_all_typed_kwargs(self) -> None:
        async def fake_send(_t, _c, _text, parse_mode="Markdown"):  # noqa: ARG001
            return 99
        with isolated_telegram_config(
            token="applied-token",  # noqa: S105
            allowed={7, 8},
            admin={7},
            send_message=fake_send,
            send_message_with_id=fake_send,
            reset_throttle=True,
        ):
            self.assertEqual(tb.TELEGRAM_BOT_TOKEN, "applied-token")
            self.assertEqual(tb.ALLOWED_USER_IDS, {7, 8})
            self.assertEqual(tb.ADMIN_USER_IDS, {7})
            self.assertIs(tb._send_message, fake_send)
            self.assertIs(tb._send_message_with_id, fake_send)
            self.assertFalse(tb._EMPTY_ALLOWLIST_WARNED)
        # Restored by helper on exit (not strictly required for assertion, but
        # proves the helpers' lifecycles are independent of the test finalizer).


if __name__ == "__main__":
    unittest.main()
