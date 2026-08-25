"""Regression tests for ``scripts/parse_pytest_failures.py``.

Guards the two parser bugs that stalled the autonomous loop:

- Issue #1354 — ``agency-cycle.yml`` used ``grep -E '^(FAILED|ERROR) '`` over
  the raw log and picked up pytest's captured **log records**, emitting
  ``qwen-proxy:app_settings.py:70`` as a "failing test". Every follow-up
  ``pytest`` on that string died with "file or directory not found", so the
  self-healing agent escalated to a human on every single run.
- Issue #1352 — ``continuous-improvement.yml`` used ``grep '^FAILED '``, which
  never matches an ``ERROR`` summary line, so a run whose only failure was a
  fixture error reported no failing tests at all.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.parse_pytest_failures import extract_failures, is_node_id


REPO_ROOT = Path(__file__).resolve().parents[1]

# Verbatim shape of the output that produced the ghost IDs in issue #1354:
# an ERROR-level captured log record sits directly above the real summary.
LOG_RECORD_OUTPUT = """\
JWT_SECRET not set - using a randomly generated secret.
ERROR    qwen-proxy:app_settings.py:70 JWT_SECRET not set in production
ERROR    qwen-proxy:app_settings.py:120 CORS_ORIGINS is '*'
WARNING  qwen-proxy:store.py:106 SchedulerStore: load_all failed - using memory fallback
=========================== short test summary info ============================
ERROR tests/test_auth_me_regression.py::TestBackendAuthMe::test_valid_token_returns_user_profile - pymongo.errors.ServerSelectionTimeoutError: localhost:27017
1 error in 9.04s
"""

MIXED_OUTCOMES_OUTPUT = """\
=========================== short test summary info ============================
FAILED tests/test_alpha.py::test_one - AssertionError: nope
FAILED tests/test_beta.py::TestGroup::test_two - ValueError: bad
ERROR tests/test_gamma.py::test_three - RuntimeError: fixture blew up
ERROR tests/test_collect_failure.py
=================== 3 failed, 1 error, 6235 passed in 1895.84s ==================
"""


class TestIsNodeId:
    """The shape check that separates real node IDs from log locators."""

    @pytest.mark.parametrize("candidate", [
        "tests/test_alpha.py",
        "tests/test_alpha.py::test_one",
        "tests/test_beta.py::TestGroup::test_two",
        "tests/e2e/test_deep.py::test_nested",
    ])
    def test_accepts_real_node_ids(self, candidate: str) -> None:
        assert is_node_id(candidate) is True

    @pytest.mark.parametrize("candidate", [
        "qwen-proxy:app_settings.py:70",     # the exact ghost from issue #1354
        "qwen-proxy:app_settings.py:120",    # the exact ghost from issue #1354
        "qwen-proxy:store.py:106",
        "qwen-proxy:app_settings.py",        # logger:file with no lineno
        "SchedulerStore:",
        "localhost:27017",
        "some/path/without/extension",
    ])
    def test_rejects_log_locators_and_junk(self, candidate: str) -> None:
        assert is_node_id(candidate) is False


class TestExtractFailures:
    """End-to-end extraction over realistic pytest output."""

    def test_ignores_captured_log_records(self) -> None:
        """Issue #1354: log records must never be reported as failing tests."""
        failures = extract_failures(LOG_RECORD_OUTPUT)
        assert failures == [
            "tests/test_auth_me_regression.py::TestBackendAuthMe"
            "::test_valid_token_returns_user_profile"
        ]
        # The specific strings that broke the self-healing agent.
        assert "qwen-proxy:app_settings.py:70" not in failures
        assert "qwen-proxy:app_settings.py:120" not in failures

    def test_error_only_run_is_not_empty(self) -> None:
        """Issue #1352: an ERROR-only run must still report the failing test."""
        failures = extract_failures(LOG_RECORD_OUTPUT)
        assert failures, "ERROR summary lines must be picked up, not dropped"

    def test_collects_both_failed_and_error(self) -> None:
        failures = extract_failures(MIXED_OUTCOMES_OUTPUT)
        assert failures == [
            "tests/test_alpha.py::test_one",
            "tests/test_beta.py::TestGroup::test_two",
            "tests/test_gamma.py::test_three",
            "tests/test_collect_failure.py",
        ]

    def test_preserves_order_and_dedupes(self) -> None:
        output = (
            "=========================== short test summary info ============================\n"
            "FAILED tests/test_b.py::test_two - X\n"
            "FAILED tests/test_a.py::test_one - Y\n"
            "FAILED tests/test_b.py::test_two - X\n"
        )
        assert extract_failures(output) == [
            "tests/test_b.py::test_two",
            "tests/test_a.py::test_one",
        ]

    def test_respects_max_results(self) -> None:
        assert len(extract_failures(MIXED_OUTCOMES_OUTPUT, max_results=2)) == 2

    def test_clean_run_returns_empty(self) -> None:
        assert extract_failures("6235 passed, 78 skipped in 1895.84s\n") == []

    def test_no_summary_banner_still_validates(self) -> None:
        """Without a banner we scan everything, but the shape check still holds."""
        output = (
            "ERROR    qwen-proxy:app_settings.py:70 boom\n"
            "FAILED tests/test_real.py::test_thing - AssertionError\n"
        )
        assert extract_failures(output) == ["tests/test_real.py::test_thing"]


class TestCli:
    """The workflows call this as a subprocess, so the CLI contract matters."""

    def _run(self, tmp_path: Path, text: str, *args: str) -> str:
        source = tmp_path / "out.txt"
        source.write_text(text, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "scripts/parse_pytest_failures.py", str(source), *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout

    def test_csv_format(self, tmp_path: Path) -> None:
        stdout = self._run(tmp_path, MIXED_OUTCOMES_OUTPUT, "--format", "csv")
        assert stdout.strip() == (
            "tests/test_alpha.py::test_one,"
            "tests/test_beta.py::TestGroup::test_two,"
            "tests/test_gamma.py::test_three,"
            "tests/test_collect_failure.py"
        )

    def test_lines_format(self, tmp_path: Path) -> None:
        stdout = self._run(tmp_path, LOG_RECORD_OUTPUT)
        assert stdout.strip() == (
            "tests/test_auth_me_regression.py::TestBackendAuthMe"
            "::test_valid_token_returns_user_profile"
        )

    def test_clean_run_exits_zero_with_no_output(self, tmp_path: Path) -> None:
        assert self._run(tmp_path, "6235 passed in 10s\n").strip() == ""


class TestWorkflowsUseTheParser:
    """The naive greps must not come back — that is the whole bug."""

    @pytest.mark.parametrize("workflow", [
        "agency-cycle.yml",
        "continuous-improvement.yml",
    ])
    def test_workflow_calls_parser_not_grep(self, workflow: str) -> None:
        text = (REPO_ROOT / ".github/workflows" / workflow).read_text(encoding="utf-8")
        assert "scripts/parse_pytest_failures.py" in text, (
            f"{workflow} must extract failing tests via the shared parser"
        )
        assert "grep -E '^(FAILED|ERROR) '" not in text, (
            f"{workflow} still uses the grep that matched captured log records"
        )
        assert "grep '^FAILED '" not in text, (
            f"{workflow} still uses the grep that drops ERROR summary lines"
        )
