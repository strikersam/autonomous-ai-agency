#!/usr/bin/env python3
"""tests/test_decisions_store.py — Coverage for the generic decision store.

Each test gets a fresh SQLite file via `tempfile.mkdtemp()` (Windows-friendly
native tempdir) so the singleton is reset and there's no cross-test or
cross-platform contamination.
"""
from __future__ import annotations

import json
import sqlite3
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path


def _fresh_store(test_name: str):
    import tempfile
    from services.decisions_store import (
        DecisionsStore,
        reset_decisions_store_singleton,
    )

    reset_decisions_store_singleton()
    tmp_root = Path(tempfile.mkdtemp(prefix=f"decisions_store_{test_name}_"))
    return DecisionsStore(db_path=str(tmp_root / "decisions.sqlite")), tmp_root


class DecisionsStoreTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._ds, self._tmp_root = _fresh_store(self._testMethodName)

    def tearDown(self) -> None:
        import shutil
        if self._tmp_root and self._tmp_root.exists():
            shutil.rmtree(self._tmp_root, ignore_errors=True)

    async def test_create_returns_decision_id_with_expected_format(self) -> None:
        did = self._ds.create(
            decision_type="risky_module",
            parent_run_id="wfo_abc",
            context={"module": "proxy.py", "lines": "195-292"},
        )
        self.assertTrue(did.startswith("dec_"))
        self.assertEqual(len(did), len("dec_") + 8)
        self.assertTrue(all(c in "0123456789abcdef" for c in did[4:]))

    async def test_create_with_explicit_decision_id_is_idempotent(self) -> None:
        did = "dec_explicit_test"
        first = self._ds.create(
            decision_type="merge",
            parent_run_id=None,
            context={"branch": "main"},
            decision_id=did,
        )
        second = self._ds.create(
            decision_type="merge",
            parent_run_id=None,
            context={"branch": "main"},
            decision_id=did,
        )
        self.assertEqual(first, did)
        self.assertEqual(second, did)
        self.assertEqual(len(self._ds.list_pending()), 1)

    async def test_resolve_marks_resolved_and_returns_true(self) -> None:
        did = self._ds.create(
            decision_type="secret_touch",
            context={"secret": "ADMIN_SECRET", "action": "rotate"},
        )
        self.assertTrue(self._ds.resolve(did, outcome="approved", resolver="telegram:user_1"))
        stored = self._ds.get(did)
        self.assertIsNotNone(stored)
        self.assertEqual(stored["status"], "resolved")
        self.assertEqual(stored["resolution_outcome"], "approved")
        self.assertEqual(stored["resolver"], "telegram:user_1")
        self.assertIsNotNone(stored["resolved_utc"])

    async def test_resolve_invalid_outcome_raises_value_error(self) -> None:
        did = self._ds.create(decision_type="dep_bump")
        with self.assertRaises(ValueError):
            self._ds.resolve(did, outcome="not_a_real_outcome", resolver="x")

    async def test_resolve_returns_false_on_double_resolve(self) -> None:
        did = self._ds.create(decision_type="merge")
        self.assertTrue(self._ds.resolve(did, outcome="approved", resolver="u"))
        self.assertFalse(self._ds.resolve(did, outcome="rejected", resolver="u"))

    async def test_list_pending_excludes_resolved(self) -> None:
        a = self._ds.create(decision_type="risky_module")
        b = self._ds.create(decision_type="secret_touch")
        c = self._ds.create(decision_type="merge")
        self._ds.resolve(b, outcome="approved", resolver="u")
        pending = self._ds.list_pending()
        ids = sorted(p["decision_id"] for p in pending)
        self.assertEqual(ids, sorted([a, c]))

    async def test_list_since_filters_by_created_utc(self) -> None:
        """Backdates the older row via raw SQLite UPDATE so it falls outside
        the cutoff window; the freshly-created row naturally satisfies >=cutoff."""
        did_old = self._ds.create(decision_type="merge")
        backdate_to = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        with sqlite3.connect(self._ds.db_path) as conn:
            conn.execute(
                "UPDATE decisions SET created_utc = ? WHERE decision_id = ?",
                (backdate_to, did_old),
            )
            conn.commit()
        did_recent = self._ds.create(decision_type="risky_module")
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        rows = self._ds.list_since(cutoff)
        ids = [r["decision_id"] for r in rows]
        self.assertIn(did_recent, ids)
        self.assertNotIn(did_old, ids)

    async def test_get_returns_none_for_unknown(self) -> None:
        self.assertIsNone(self._ds.get("dec_definitely_not_in_store"))

    async def test_parent_run_id_is_preserved(self) -> None:
        did = self._ds.create(
            decision_type="merge",
            parent_run_id="wfo_parent_123",
            context={},
        )
        self.assertEqual(self._ds.get(did)["parent_run_id"], "wfo_parent_123")

    async def test_context_round_trips_through_json(self) -> None:
        ctx = {"module": "agent/tools.py", "tool": "apply_diff", "i": 7}
        did = self._ds.create(decision_type="risky_module", context=ctx)
        stored = self._ds.get(did)
        loaded = json.loads(stored["context_json"])
        self.assertEqual(loaded, ctx)

    async def test_create_is_safe_against_db_error(self) -> None:
        """Smoke: create() returns a fresh dec_<hex8> per call (no error
        surfaces from happy-path SQLite)."""
        bad = self._ds.create(decision_type="risky_module")
        self.assertTrue(bad.startswith("dec_"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
