#!/usr/bin/env python3
"""tests/test_daily_digest.py — Coverage for the daily review aggregator
and Markdown-v1 formatter. Mocks workflow_orchestrator.list_runs; uses a
real DecisionsStore against a temp SQLite file (mkdtemp = cross-platform).
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


@dataclass
class FakeRun:
    run_id: str
    status: str
    goal: str = ""
    created_at: str = ""
    finished_at: str = ""


class _FakeOrchestrator:
    def __init__(self, runs: list[FakeRun]) -> None:
        self._runs = runs

    def list_runs(self) -> list[FakeRun]:
        return list(self._runs)


def _tmp_db_path(name: str) -> str:
    tmp_root = Path(tempfile.mkdtemp(prefix=f"daily_digest_{name}_"))
    return str(tmp_root / "decisions.sqlite")


def _fresh_stores(name: str) -> Any:
    from services.decisions_store import (
        DecisionsStore,
        reset_decisions_store_singleton,
    )
    from services import daily_digest as mod

    reset_decisions_store_singleton()
    ds = DecisionsStore(db_path=_tmp_db_path(name))
    mod.reset_decisions_store_for_tests = (lambda: reset_decisions_store_singleton())  # type: ignore
    return ds


class DailyDigestAggregatorTests(unittest.TestCase):
    def setUp(self) -> None:
        from services.daily_digest import (
            aggregate_last_24h,
            format_digest_markdown,
            build_daily_digest,
            compute_cutoff,
        )

        self.aggregate = aggregate_last_24h
        self.format = format_digest_markdown
        self.build = build_daily_digest
        self.compute_cutoff = compute_cutoff
        self._store = _fresh_stores(self._testMethodName)
        self._artifacts_to_cleanup: list[Path] = []

    def tearDown(self) -> None:
        import shutil
        for path in self._artifacts_to_cleanup:
            try:
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                elif path.exists():
                    path.unlink()
            except OSError as exc:
                print(f"warning: failed to cleanup {path}: {exc}", file=sys.stderr)

    def _now_iso(self, hours_ago: int = 0) -> str:
        return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()

    def test_empty_stores_returns_zero_counts(self) -> None:
        orch = _FakeOrchestrator(runs=[])
        s = self.aggregate(
            decisions_store=self._store,
            workflow_orchestrator=orch,
            cutoff_utc=self.compute_cutoff(24),
        )
        self.assertEqual(s.counts, {
            "awaiting_review": 0,
            "pending_decisions": 0,
            "recent_wins_24h": 0,
        })
        self.assertEqual(s.recent_wins, [])
        self.assertEqual(s.awaiting_review, [])
        self.assertEqual(s.pending_decisions, [])

    def test_aggregator_categorizes_by_status(self) -> None:
        runs = [
            FakeRun("wfo_a", "awaiting_approval", goal="Refactor auth", created_at=self._now_iso(2)),
            FakeRun("wfo_b", "needs_user", goal="Review dep bump", created_at=self._now_iso(4)),
            FakeRun("wfo_c", "completed", goal="Daily standup", finished_at=self._now_iso(1)),
            FakeRun("wfo_d", "completed", goal="Yesterday's job", finished_at=self._now_iso(48)),
            FakeRun("wfo_e", "failed", finished_at=self._now_iso(1)),
        ]
        self._store.create(decision_type="risky_module", context={"module": "rbac.py"})
        self._store.create(decision_type="secret_touch", context={"secret": "JWT_SECRET"})
        orch = _FakeOrchestrator(runs=runs)
        s = self.aggregate(
            decisions_store=self._store,
            workflow_orchestrator=orch,
            cutoff_utc=self.compute_cutoff(24),
        )
        awaiting_ids = sorted(r["run_id"] for r in s.awaiting_review)
        self.assertEqual(awaiting_ids, ["wfo_a", "wfo_b"])
        self.assertEqual(len(s.pending_decisions), 2)
        win_ids = [w["run_id"] for w in s.recent_wins]
        self.assertEqual(win_ids, ["wfo_c"])
        self.assertEqual(s.counts["awaiting_review"], 2)
        self.assertEqual(s.counts["pending_decisions"], 2)
        self.assertEqual(s.counts["recent_wins_24h"], 1)

    def test_format_includes_all_three_sections_when_populated(self) -> None:
        from services.daily_digest import DigestSummary
        s = DigestSummary(
            awaiting_review=[{"run_id": "wfo_x", "goal": "Test awaiting run"}],
            recent_wins=[{"run_id": "wfo_y", "goal": "Test won run", "finished_utc": "x"}],
            pending_decisions=[{
                "decision_id": "dec_zz",
                "decision_type": "merge",
                "context": {"one_liner": "Approve the merge"},
                "created_utc": "x",
            }],
            counts={"awaiting_review": 1, "pending_decisions": 1, "recent_wins_24h": 1},
        )
        md = self.format(s, generated_utc="2026-06-19T00:00:00+00:00")
        self.assertIn("Daily Review Digest", md)
        self.assertIn("Awaiting your review", md)
        self.assertIn("Pending decisions", md)
        self.assertIn("Recent wins", md)
        self.assertIn("wfo\\_x", md)  # underscore is escaped
        self.assertIn("/approve", md)

    def test_format_with_zero_data_is_short_summary(self) -> None:
        from services.daily_digest import DigestSummary
        s = DigestSummary(
            counts={"awaiting_review": 0, "pending_decisions": 0, "recent_wins_24h": 0},
        )
        md = self.format(s)
        self.assertIn("awaiting\\_review=0", md)
        self.assertIn("pending\\_decisions=0", md)

    def test_build_writes_truncated_file_when_markdown_exceeds_budget(self) -> None:
        """Forces truncation by lowering _TRUNCATE_THRESHOLD for the duration of
        the test (the production formatter caps each goal to 120 chars/row,
        so a single 4500-char goal alone cannot exceed 4000 chars of body).
        """
        from services import daily_digest as mod

        big_goal = "REALLY_LONG_GOAL_TOKEN " + ("X" * 4500)
        runs = [
            FakeRun("wfo_huge", "awaiting_approval", goal=big_goal, created_at=self._now_iso(1)),
        ]
        orch = _FakeOrchestrator(runs=runs)
        ws_root = tempfile.mkdtemp(prefix="digest_workspace_")
        self._artifacts_to_cleanup.append(Path(ws_root))
        original_threshold = mod._TRUNCATE_THRESHOLD
        mod._TRUNCATE_THRESHOLD = 100
        try:
            payload = self.build(
                decisions_store=self._store,
                workflow_orchestrator=orch,
                cutoff_utc=self.compute_cutoff(24),
                workspace_root=ws_root,
            )
            self.assertIsNotNone(payload.truncated_path, "expected truncation to fire with monkeypatched threshold")
            self.assertTrue(Path(payload.truncated_path).exists())
            written = Path(payload.truncated_path).read_text(encoding="utf-8")
            self.assertGreater(len(written), 100)  # the FULL body is on disk
            # The markdown_body is the SHORT pointer version (under budget)
            self.assertLess(len(payload.markdown_body), 4096)
            # Path-component assertions: file lives at <ws_root>/pastes/digest-<date>.md,
            # cross-platform (forgiving both / and \ separators).
            truncated = Path(payload.truncated_path)
            self.assertEqual(truncated.parent.name, "pastes")
            self.assertTrue(truncated.name.startswith("digest-"))
            self.assertTrue(str(Path(ws_root).resolve()) in str(truncated.resolve()))
        finally:
            mod._TRUNCATE_THRESHOLD = original_threshold

    def test_build_returns_short_body_when_no_truncation_needed(self) -> None:
        runs = []
        orch = _FakeOrchestrator(runs=runs)
        ws_root = tempfile.mkdtemp(prefix="digest_workspace2_")
        self._artifacts_to_cleanup.append(Path(ws_root))
        payload = self.build(
            decisions_store=self._store,
            workflow_orchestrator=orch,
            cutoff_utc=self.compute_cutoff(24),
            workspace_root=ws_root,
        )
        self.assertIsNone(payload.truncated_path)
        self.assertIn("Daily Review Digest", payload.markdown_body)

    def test_aggregator_tolerates_orchestrator_without_list_runs(self) -> None:
        """If a custom orchestrator object is passed without list_runs, the
        aggregator must not crash — it just returns empty awaiting/wins."""

        class BareOrchestrator:
            pass

        s = self.aggregate(
            decisions_store=self._store,
            workflow_orchestrator=BareOrchestrator(),
            cutoff_utc=self.compute_cutoff(24),
        )
        self.assertEqual(s.awaiting_review, [])
        self.assertEqual(s.recent_wins, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
