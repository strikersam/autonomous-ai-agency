"""Tests for trend_analysis.py — last30days-style window over TrendWatcher (issue #493)."""
from __future__ import annotations

import asyncio
import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

from trend_analysis import TrendItem, TrendReport, _within_window, run_trend_analysis


class TestWindow:
    def test_recent_date_in_window(self):
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        assert _within_window(now)

    def test_old_date_out_of_window(self):
        old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=90)).isoformat()
        assert not _within_window(old)

    def test_unparseable_date_kept(self):
        assert _within_window("not-a-date")
        assert _within_window("")


class TestRunTrendAnalysis:
    def _fake_alert(self, title, score, published=""):
        a = MagicMock()
        a.as_dict.return_value = {
            "source": "hackernews", "title": title, "summary": "s",
            "url": "https://example.com", "relevance_score": score,
            "published": published, "tags": ["ai"],
        }
        return a

    def test_report_sorted_filtered_and_persisted(self, tmp_path, monkeypatch):
        import trend_analysis as ta
        monkeypatch.setattr(ta, "TRENDS_DIR", tmp_path)
        old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=90)).isoformat()
        watcher = MagicMock()
        watcher.fetch = AsyncMock(return_value=[
            self._fake_alert("low", 0.1),
            self._fake_alert("high", 0.9),
            self._fake_alert("stale", 0.99, published=old),
        ])
        with patch("agent.trend_watcher.get_trend_watcher", return_value=watcher):
            report = asyncio.run(run_trend_analysis(limit=5))
        assert isinstance(report, TrendReport)
        assert report.total_items == 2  # stale filtered out
        assert report.top_items[0].title == "high"  # sorted by relevance
        assert (tmp_path / "trend_summary.md").exists()
        assert "high" in (tmp_path / "trend_summary.md").read_text(encoding="utf-8")

    def test_trend_item_forbids_extras(self):
        import pytest
        with pytest.raises(Exception):
            TrendItem(source="x", title="t", bogus_field=1)
