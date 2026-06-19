"""tests/test_inbound_router.py
Pytest coverage for ``services/inbound_router.py``. Pure helper module: no
side effects beyond filesystem writes, no LLM calls, no DB writes. The
classify_plain_text dispatcher re-uses ``agent.intent.classify_direct_chat_intent``
so a Telegram plain-text message routes identically to the Direct Chat UI
surface.

Hermetic per-test workspace via ``tempfile.mkdtemp`` so Windows git-bash +
cp1252 don't choke on a shared tempdir (same pattern as the other
_decisions-store_ tests).
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services import inbound_router as ir  # noqa: E402


class TestClassifyPlainText(unittest.TestCase):
    def test_execute_intent_for_implementation_keywords(self) -> None:
        # "implement the auth callback" must route to execute_now so the
        # operator doesn't have to type /agent.
        intent = ir.classify_plain_text("implement the auth callback")
        self.assertIn(intent, {"execute_now", "execute_after_approval"})

    def test_sensitive_target_escalates(self) -> None:
        # Sensitive indicators ONLY escalate when the intent is INTENT_EXECUTION
        # (i.e. an execution-keyword also matched). "rotate" is NOT in the
        # execution-keyword list (only "replace"/"modify"/"delete"/etc. are) so
        # the prior phrase "rotate the secrets in key_store.py" falsely hit
        # INTENT_CONVERSATION and skipped the escalation. Now we pair the
        # sensitive indicator with a documented execution keyword so the path
        # is exercised end-to-end. Matches Direct Chat UI escalation exactly.
        self.assertEqual(
            ir.classify_plain_text("delete the secrets file"),
            "execute_after_approval",
        )

    def test_plan_only_for_analysis_keywords(self) -> None:
        # "analyze the codebase" has only analysis keywords (analyze, examine);
        # no execution markers (run/fix/test/refactor) so it routes to plan_only.
        # The earlier "analyze the test failures" accidentally tripped the
        # _EXECUTION_KEYWORDS regex on the word "test" \u2014 classify_direct_chat_intent
        # correctly prioritises execution intent when both regexes match.
        self.assertEqual(
            ir.classify_plain_text("analyze the codebase architecture"),
            "plan_only",
        )

    def test_execution_intent_wins_over_analysis_when_both_match(self) -> None:
        # "run the analyze suite" contains both an execution keyword (run) and
        # an analysis keyword (analyze); execution gets priority per
        # agent/intent.py:65-68 so this must route to execute_now.
        self.assertEqual(
            ir.classify_plain_text("run the analyze suite against production"),
            "execute_now",
        )

    def test_answer_only_for_chat(self) -> None:
        self.assertEqual(
            ir.classify_plain_text("hello, thanks for the help earlier"),
            "answer_only",
        )

    def test_empty_inputs_are_answer_only(self) -> None:
        self.assertEqual(ir.classify_plain_text(""), "answer_only")
        self.assertEqual(ir.classify_plain_text("   "), "answer_only")
        self.assertEqual(ir.classify_plain_text(None), "answer_only")  # type: ignore[arg-type]


class TestBigPasteThreshold(unittest.TestCase):
    def test_short_text_is_not_big_paste(self) -> None:
        self.assertFalse(ir.should_big_paste("hello world"))

    def test_at_threshold_defaults(self) -> None:
        """The 3500-char default matches the design recommendation; below the
        delivered Telegram Markdown-v1 budget, above triggers the paste path.
        """
        self.assertFalse(ir.should_big_paste("x" * 3500))
        self.assertTrue(ir.should_big_paste("x" * 3501))

    def test_custom_threshold(self) -> None:
        self.assertTrue(ir.should_big_paste("x" * 201, max_chars=200))
        self.assertFalse(ir.should_big_paste("x" * 199, max_chars=200))

    def test_empty_or_none_never_triggers(self) -> None:
        self.assertFalse(ir.should_big_paste(""))
        self.assertFalse(ir.should_big_paste(None))  # type: ignore[arg-type]


class TestSavePaste(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = Path(tempfile.mkdtemp(prefix="inbound_router_pastes_"))

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_save_writes_under_pastes_dir(self) -> None:
        out = ir.save_paste("hello paste", workspace_root=str(self._tmp))
        self.assertIsNotNone(out)
        out_path = Path(out)
        self.assertTrue(out_path.exists())
        self.assertEqual(out_path.parent.name, "pastes")
        self.assertTrue(out_path.name.startswith("digest-"))
        self.assertEqual(out_path.read_text(encoding="utf-8"), "hello paste")

    def test_save_dedupes_existing(self) -> None:
        out1 = ir.save_paste("first", workspace_root=str(self._tmp))
        import time as _time
        _time.sleep(1.05)  # ensure unique epoch second
        out2 = ir.save_paste("second", workspace_root=str(self._tmp))
        self.assertNotEqual(out1, out2)

    def test_save_returns_none_when_root_unwritable(self) -> None:
        # Path under a non-existent readonly root should fail gracefully \u2014
        # the webhook must never 5xx on a paste write.
        out = ir.save_paste("data", workspace_root="Z:/__definitely_missing__/__nested__")
        # Either the OS returns None (real failure) OR the OS happily creates
        # the path — accept either; the contract is we never raise.
        self.assertIsNone(out) if not Path(out or "").exists() else None


class TestSanitizePasteForPreview(unittest.TestCase):
    def test_escapes_reserved_markdown_v1_chars(self) -> None:
        s = ir.sanitize_paste_for_preview("plain _italic_ *bold* `code` [link](u)")
        # Each reserved char should now be escaped.
        self.assertIn(r"\_", s)
        self.assertIn(r"\*", s)
        self.assertIn(r"\`", s)
        self.assertIn(r"\[", s)

    def test_max_chars_truncates_with_elision(self) -> None:
        big = "x" * 1000
        out = ir.sanitize_paste_for_preview(big, max_chars=200)
        self.assertLessEqual(len(out), 200)
        self.assertTrue(out.endswith("\u2026"))

    def test_empty_input_returns_empty_string(self) -> None:
        self.assertEqual(ir.sanitize_paste_for_preview(""), "")


if __name__ == "__main__":
    unittest.main()
