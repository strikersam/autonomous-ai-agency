"""tests/test_weekly_digest.py — Weekly readiness digest tests."""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

_services_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "services")
sys.path.insert(0, _services_dir)
import weekly_digest as _wd
sys.path.pop(0)

build_digest = _wd.build_digest
send_digest = _wd.send_digest


class TestBuildDigest:
    @patch.object(_wd, "_count_open_auto_prs", return_value=3)
    @patch.object(_wd, "_load_readiness")
    def test_digest_contains_readiness_score(self, mock_load, mock_count):
        mock_load.return_value = {
            "score": 72,
            "grade": "B",
            "total_loops": 25,
            "by_level": {"L1": 10, "L2": 12, "L3": 3},
            "self_heal_coverage": 0.4,
            "dimensions": {"maturity": 70, "self_heal": 50, "governance": 90, "safety": 80},
            "drift_ok": True,
            "missing_from_registry": [],
            "stale_sources": [],
            "monthly_tokens": 5_000_000,
        }
        text = build_digest()
        assert "72/100" in text
        assert "Grade B" in text
        assert "25 loops" in text
        assert "5,000,000" in text
        assert "auto-PR branches:* 3" in text
        assert "No registry drift" in text

    @patch.object(_wd, "_count_open_auto_prs", return_value=0)
    @patch.object(_wd, "_load_readiness")
    def test_digest_shows_drift(self, mock_load, mock_count):
        mock_load.return_value = {
            "score": 50,
            "grade": "C",
            "total_loops": 10,
            "by_level": {"L1": 5, "L2": 5, "L3": 0},
            "self_heal_coverage": 0.2,
            "dimensions": {},
            "drift_ok": False,
            "missing_from_registry": ["new-workflow.yml"],
            "stale_sources": ["deleted.py"],
            "monthly_tokens": 1_000_000,
        }
        text = build_digest()
        assert "drift detected" in text
        assert "new-workflow.yml" in text
        assert "deleted.py" in text

    @patch.object(_wd, "_count_open_auto_prs", return_value=0)
    @patch.object(_wd, "_load_readiness")
    def test_digest_handles_error(self, mock_load, mock_count):
        mock_load.return_value = {"error": "kaboom"}
        text = build_digest()
        assert "kaboom" in text
        assert "Could not load" in text


class TestSendDigest:
    @patch("packages.notifications.service.NotificationDispatcher")
    def test_send_calls_dispatcher(self, mock_cls):
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        send_digest("test message")
        mock_instance.send_manual_notification.assert_called_once_with("test message")
