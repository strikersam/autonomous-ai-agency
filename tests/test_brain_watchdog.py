"""tests/test_brain_watchdog.py — Brain watchdog failover tests."""
from __future__ import annotations

import importlib
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# V2.0 Modernization: brain_watchdog moved to packages/ai/watchdog.py and
# brain_config_store moved to packages/ai/brain_config.py. Import directly
# from packages/ to avoid the heavy services/__init__.py cascade.
from packages.ai.watchdog import BrainWatchdog, reset_watchdog
from packages.ai import watchdog as _bw
from packages.ai import brain_config as _bcs


@pytest.fixture(autouse=True)
def _reset():
    reset_watchdog()
    yield
    reset_watchdog()


class TestBrainWatchdog:
    def test_success_resets_counter(self):
        wd = BrainWatchdog(max_failures=3)
        wd.record_failure("cerebras")
        wd.record_failure("cerebras")
        assert wd._failure_counts["cerebras"] == 2
        wd.record_success("cerebras")
        assert wd._failure_counts["cerebras"] == 0

    def test_no_failover_below_threshold(self):
        wd = BrainWatchdog(max_failures=3)
        assert wd.record_failure("cerebras") is None
        assert wd.record_failure("cerebras") is None

    def test_record_failure_logs_auth_cause(self, caplog):
        # A 401 must be logged as a key problem so "which provider keys work?"
        # is answerable from the failure log itself.
        wd = BrainWatchdog(max_failures=3)
        with caplog.at_level("WARNING"):
            wd.record_failure("anthropic-claude", status_code=401)
        assert any("check/rotate the API key" in r.message for r in caplog.records)

    def test_record_failure_logs_rate_limit_cause(self, caplog):
        wd = BrainWatchdog(max_failures=3)
        with caplog.at_level("WARNING"):
            wd.record_failure("nvidia", status_code=429)
        assert any("rate limited" in r.message for r in caplog.records)

    def test_record_failure_backward_compatible_without_status(self, caplog):
        # The status is optional: the historical single-arg call must still work
        # and must not append a cause clause when no status is known.
        wd = BrainWatchdog(max_failures=3)
        with caplog.at_level("WARNING"):
            assert wd.record_failure("cerebras") is None
        record = next(r for r in caplog.records if "cerebras failure #1" in r.message)
        assert " — " not in record.message   # no cause suffix without a status
        assert wd._failure_counts["cerebras"] == 1

    @patch.object(BrainWatchdog, "_persist_failover")
    @patch.object(BrainWatchdog, "_notify_failover")
    def test_failover_triggers_at_threshold(self, mock_notify, mock_persist):
        wd = BrainWatchdog(max_failures=3)
        # PR #1046: priority is now nvidia-first (nvidia, cerebras, groq, ollama).
        # When cerebras fails, nvidia is the first available candidate.
        with patch.object(_bw, "_is_provider_actually_available",
                          side_effect=lambda p: p in ("nvidia", "groq")):
            wd.record_failure("cerebras")
            wd.record_failure("cerebras")
            result = wd.record_failure("cerebras")

        assert result == "nvidia"
        mock_persist.assert_called_once_with("nvidia")
        mock_notify.assert_called_once_with("cerebras", "nvidia")
        assert wd._failure_counts["cerebras"] == 0

    @patch.object(BrainWatchdog, "_persist_failover")
    @patch.object(BrainWatchdog, "_notify_failover")
    def test_failover_skips_provider_without_key(self, mock_notify, mock_persist):
        wd = BrainWatchdog(max_failures=2)
        with patch.object(_bw, "_is_provider_actually_available",
                          side_effect=lambda p: p == "nvidia"):
            wd.record_failure("cerebras")
            result = wd.record_failure("cerebras")

        assert result == "nvidia"

    @patch.object(BrainWatchdog, "_persist_failover")
    @patch.object(BrainWatchdog, "_notify_failover")
    def test_no_failover_candidates(self, mock_notify, mock_persist):
        wd = BrainWatchdog(max_failures=1)
        with patch.object(_bw, "_is_provider_actually_available",
                          return_value=False):
            result = wd.record_failure("cerebras")

        assert result is None
        mock_persist.assert_not_called()

    @patch.object(BrainWatchdog, "_persist_failover")
    @patch.object(BrainWatchdog, "_notify_failover")
    def test_failover_log_recorded(self, mock_notify, mock_persist):
        wd = BrainWatchdog(max_failures=1)
        with patch.object(_bw, "_is_provider_actually_available",
                          side_effect=lambda p: p == "groq"):
            wd.record_failure("cerebras")

        assert len(wd.failover_log) == 1
        entry = wd.failover_log[0]
        assert entry["from_provider"] == "cerebras"
        assert entry["to_provider"] == "groq"

    def test_status_returns_current_state(self):
        wd = BrainWatchdog(max_failures=5)
        wd.record_failure("nvidia")
        wd.record_failure("nvidia")
        s = wd.status()
        assert s["failure_counts"]["nvidia"] == 2
        assert s["max_failures"] == 5
        assert s["failover_count"] == 0
