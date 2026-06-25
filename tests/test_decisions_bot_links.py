"""tests/test_decisions_bot_links.py
Pytest coverage for the new ``bot_message_links`` helpers in
``services/decisions_store.py``. The bot needs a durable mapping from
``(chat_id, telegram_message_id) -> decision_id`` so a reply to a
decision-prompt message can look up the original decision_id across bot
restarts. The helpers here are the only surface that needs regression
coverage.

Hermetic per-test SQLite via ``tempfile.mkdtemp`` so Windows git-bash +
cp1252 don't choke on a shared tempdir (same pattern as
``tests/test_decisions_store.py``).
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services import decisions_store as ds  # noqa: E402


class TestDecisionsBotLinks(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = Path(tempfile.mkdtemp(prefix="decisions_bot_links_"))
        self._db = self._tmp / "decisions_bot_links.sqlite"
        # Module-singleton bypass — the bot uses get_decisions_store(),
        # but tests need a hermetic DB. Construct the wrapped class directly.
        self.store = ds.DecisionsStore(db_path=str(self._db))
        # Always test as if no pre-existing rows
        self.chat_id = 4242

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)
        ds.reset_decisions_store_singleton()

    def _seed_decision(self, parent_run_id: str | None = None) -> str:
        return self.store.create(
            decision_type="telegram_reply",
            parent_run_id=parent_run_id or "wfo_test01",
            context={"chat_id": self.chat_id},
        )

    def test_link_then_lookup_roundtrip(self) -> None:
        dec = self._seed_decision()
        self.assertTrue(
            self.store.link_message(
                chat_id=self.chat_id,
                telegram_message_id=99,
                decision_id=dec,
                run_id="wfo_test01",
            )
        )
        row = self.store.lookup_by_message(self.chat_id, 99)
        self.assertIsNotNone(row)
        self.assertEqual(row["decision_id"], dec)
        self.assertEqual(row["run_id"], "wfo_test01")
        self.assertEqual(row["chat_id"], self.chat_id)
        self.assertEqual(row["telegram_message_id"], 99)

    def test_link_is_idempotent_for_same_chat_msg_pair(self) -> None:
        """Re-sending the same Telegram message (offset rewind, bot restart
        re-delivery) must collapse to a single linkage rather than double-linking.
        The PK is (chat_id, telegram_message_id), and we use INSERT OR REPLACE.\n        """
        dec_a = self._seed_decision(parent_run_id="wfo_a")
        dec_b = self._seed_decision(parent_run_id="wfo_b")
        self.assertTrue(
            self.store.link_message(
                chat_id=self.chat_id, telegram_message_id=7,
                decision_id=dec_a, run_id="wfo_a",
            )
        )
        self.assertTrue(
            self.store.link_message(
                chat_id=self.chat_id, telegram_message_id=7,
                decision_id=dec_b, run_id="wfo_b",
            )
        )
        row = self.store.lookup_by_message(self.chat_id, 7)
        self.assertIsNotNone(row)
        # Latest write wins (OR REPLACE) \u2014 the bot restart scenario where the bot
        # already linked once and now re-links under a fresh decision_id.
        self.assertEqual(row["decision_id"], dec_b)
        self.assertEqual(row["run_id"], "wfo_b")

    def test_lookup_returns_none_for_unlinked_message(self) -> None:
        self.assertIsNone(self.store.lookup_by_message(self.chat_id, 123456789))
        self.assertIsNone(
            self.store.lookup_by_message(chat_id=9999, telegram_message_id=1)
        )

    def test_link_without_run_id_is_allowed(self) -> None:
        """Decision prompts that exist *before* the orchestrator creates a run
        (e.g. a dependency-bump alert) only have a decision_id; run_id is
        nullable on insert.\n        """
        dec = self._seed_decision(parent_run_id=None)
        self.assertTrue(
            self.store.link_message(
                chat_id=self.chat_id, telegram_message_id=11,
                decision_id=dec, run_id=None,
            )
        )
        row = self.store.lookup_by_message(self.chat_id, 11)
        self.assertEqual(row["run_id"], None)
        self.assertEqual(row["decision_id"], dec)

    def test_unlink_expired_drops_only_old_rows(self) -> None:
        dec_recent = self._seed_decision(parent_run_id="wfo_recent")
        dec_old = self._seed_decision(parent_run_id="wfo_old")
        # Link two rows
        self.store.link_message(
            chat_id=self.chat_id, telegram_message_id=1,
            decision_id=dec_recent, run_id="wfo_recent",
        )
        # Simulate the second row being written 14 days ago directly by
        # reaching into the table (test-only path).
        with self.store._connect() as conn:
            conn.execute(
                "UPDATE bot_message_links SET created_utc = ? WHERE telegram_message_id = 1",
                ((datetime.now(timezone.utc) - timedelta(days=14)).isoformat(),),
            )
            conn.execute(
                "INSERT INTO bot_message_links "
                "(chat_id, telegram_message_id, decision_id, run_id, created_utc) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    self.chat_id, 2, dec_old, "wfo_old",
                    (datetime.now(timezone.utc) - timedelta(days=14)).isoformat(),
                ),
            )
        # Bump recent link to ensure it's now (use the natural API).
        self.store.link_message(
            chat_id=self.chat_id, telegram_message_id=3,
            decision_id=dec_recent, run_id="wfo_recent",
        )
        # Cutoff: 7 days ago.
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        deleted = self.store.unlink_expired(cutoff)
        self.assertEqual(deleted, 2)
        self.assertIsNotNone(self.store.lookup_by_message(self.chat_id, 3))
        self.assertIsNone(self.store.lookup_by_message(self.chat_id, 1))
        self.assertIsNone(self.store.lookup_by_message(self.chat_id, 2))


if __name__ == "__main__":
    unittest.main()
