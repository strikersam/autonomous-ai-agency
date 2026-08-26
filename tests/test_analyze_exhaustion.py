"""Tests for ``scripts/analyze_exhaustion.py``.

The case that matters most is the one that actually happened: the loop was fed
`qwen-proxy:app_settings.py:70` (a captured log record, not a test), pytest
refused to collect it, and the workflow marked the issue `quick-note:exhausted`
three attempts later. That verdict was wrong — the agent was never handed a
fixable task — and it stranded the work permanently.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.analyze_exhaustion import (
    VERDICT_EXHAUSTED,
    VERDICT_INFRA,
    VERDICT_TRIAGE,
    analyze,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

# Verbatim shape of the run that produced issues #1354 / #1360.
GHOST_ID_OUTPUT = """\
=== FAILURE: qwen-proxy:app_settings.py:70 ===
ERROR: file or directory not found: qwen-proxy:app_settings.py:70

no tests ran in 0.00s
"""

INFRA_OUTPUT = """\
=========================== short test summary info ============================
ERROR tests/test_auth_me_regression.py::TestBackendAuthMe::test_valid_token_returns_user_profile - pymongo.errors.ServerSelectionTimeoutError: localhost:27017: [Errno 111] Connection refused
1 error in 9.00s
"""

REAL_FAILURE_OUTPUT = """\
=========================== short test summary info ============================
FAILED tests/test_alpha.py::test_one - AssertionError: expected 3 got 4
FAILED tests/test_beta.py::test_two - AssertionError: mismatch
2 failed in 3.10s
"""


class TestNeedsTriage:
    """A run with no collectable test must never be blamed on the agent."""

    def test_ghost_id_is_not_exhausted(self) -> None:
        result = analyze(GHOST_ID_OUTPUT, attempts=3)
        assert result.verdict == VERDICT_TRIAGE
        assert result.failures == []

    def test_ghost_id_report_explains_why(self) -> None:
        report = analyze(GHOST_ID_OUTPUT, attempts=3).report
        assert "needs-triage" in report
        assert "not a test node ID" in report

    def test_empty_output_is_triage_not_exhausted(self) -> None:
        assert analyze("", attempts=3).verdict == VERDICT_TRIAGE


class TestBlockedInfrastructure:
    """An unreachable service is not a failure the agent could have fixed."""

    def test_mongo_outage_is_not_exhausted(self) -> None:
        result = analyze(INFRA_OUTPUT, attempts=3)
        assert result.verdict == VERDICT_INFRA
        assert result.failures == [
            "tests/test_auth_me_regression.py::TestBackendAuthMe"
            "::test_valid_token_returns_user_profile"
        ]

    def test_infra_report_names_the_category(self) -> None:
        assert "infrastructure_error" in analyze(INFRA_OUTPUT, attempts=3).report


class TestGenuinelyExhausted:
    """Real failing tests still earn the label — the gate must not be a no-op."""

    def test_real_failures_are_exhausted(self) -> None:
        result = analyze(REAL_FAILURE_OUTPUT, attempts=3)
        assert result.verdict == VERDICT_EXHAUSTED
        assert len(result.failures) == 2

    def test_report_lists_each_failing_test(self) -> None:
        report = analyze(REAL_FAILURE_OUTPUT, attempts=3).report
        assert "tests/test_alpha.py::test_one" in report
        assert "tests/test_beta.py::test_two" in report


class TestCli:
    """The workflow branches on the verdict file, so that contract matters."""

    def _run(self, tmp_path: Path, text: str) -> str:
        source = tmp_path / "out.txt"
        source.write_text(text, encoding="utf-8")
        verdict = tmp_path / "verdict.txt"
        subprocess.run(  # nosec B603 - constant argv, list form, no shell
            [
                sys.executable,
                "scripts/analyze_exhaustion.py",
                str(source),
                "--attempts",
                "3",
                "--verdict-file",
                str(verdict),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return verdict.read_text(encoding="utf-8").strip()

    @pytest.mark.parametrize("text,expected", [
        (GHOST_ID_OUTPUT, VERDICT_TRIAGE),
        (INFRA_OUTPUT, VERDICT_INFRA),
        (REAL_FAILURE_OUTPUT, VERDICT_EXHAUSTED),
    ])
    def test_verdict_file(self, tmp_path: Path, text: str, expected: str) -> None:
        assert self._run(tmp_path, text) == expected


class TestWorkflowUsesTheGate:
    """The label must not be reachable without the analysis that justifies it."""

    def test_process_quick_note_calls_the_analyzer(self) -> None:
        text = (REPO_ROOT / ".github/workflows/process-quick-note.yml").read_text(
            encoding="utf-8"
        )
        assert "scripts/analyze_exhaustion.py" in text, (
            "process-quick-note.yml must analyse a run before marking it exhausted"
        )
