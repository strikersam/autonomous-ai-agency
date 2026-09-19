"""Tests for the "Analyze failures" step of
``.github/workflows/nightly-regression.yml``.

Observed live (run 35414763080, 2026-09-19): the "Full Browser Regression"
job's "Run Telegram approval e2e" sub-step failed, which is exactly the case
this step exists to classify. Instead the "Analyze failures" step itself
crashed:

    line 21: [: 0
    0: integer expression expected
    ##[error]Unable to process file command 'output' successfully.
    ##[error]Invalid format '0'

Root cause: ``grep -c PATTERN FILE`` already prints "0" (its exact count) and
exits with status 1 when nothing matches. Wrapping it as
``$(grep -c ... 2>/dev/null || echo 0)`` fires the ``|| echo 0`` fallback *in
addition* to that printed "0" — both writes land in the same command
substitution's stdout, so the variable becomes the two-line string "0\\n0"
instead of "0". That breaks every ``[ "$VAR" -gt 0 ]`` comparison below it,
and the doubled `echo "key=$VAR" >> $GITHUB_OUTPUT` line corrupts the special
GITHUB_OUTPUT file format, which GitHub Actions itself then rejects.

The consequence is worse than a broken step: this job only runs when the
regression suite has already failed (``needs.regression.result == 'failure'``),
so this crash silently disables the auto-fix PR and the fallback
issue-filing for every real nightly regression failure — the safety net
these two jobs exist to provide never fires.

This test runs the *actual* shell extracted from the workflow file (not a
reimplementation), so it fails if the pattern regresses.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github/workflows/nightly-regression.yml"


@pytest.fixture(scope="module")
def analyze_script() -> str:
    """Extract the exact `run: |` block of the "Analyze failures" step."""
    text = WORKFLOW.read_text(encoding="utf-8")
    m = re.search(
        r'- name: Analyze failures\n\s*id: analyze\n\s*run: \|\n(.*?)\n\n(?=\s*- name:)',
        text,
        re.DOTALL,
    )
    assert m, "could not find the 'Analyze failures' step in nightly-regression.yml"
    block = m.group(1)
    # De-indent: every line is indented 10 spaces relative to the `run: |` key.
    lines = [line[10:] if len(line) >= 10 else line for line in block.splitlines()]
    return "\n".join(lines)


def _run_analyze(script: str, failure_log_content: str | None) -> dict[str, str]:
    """Run the extracted script against a fake regression-output.txt and
    return the parsed GITHUB_OUTPUT key/value pairs."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        failure_log = tmp_path / "regression-output.txt"
        if failure_log_content is not None:
            failure_log.write_text(failure_log_content, encoding="utf-8")
        github_output = tmp_path / "github_output.txt"
        github_output.write_text("", encoding="utf-8")

        wrapped = script.replace(
            '"/tmp/e2e-artifacts/regression-output.txt"', f'"{failure_log}"'
        )
        result = subprocess.run(
            ["bash", "-e", "-c", wrapped],  # nosec - constant argv, list form, no shell
            env={"GITHUB_OUTPUT": str(github_output), "PATH": "/usr/bin:/bin"},
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, (
            f"analyze step exited {result.returncode}\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )

        outputs: dict[str, str] = {}
        for line in github_output.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            # A corrupted double-count ("0\n0") produces a line with no "="
            # at all once split on the real newline — this assertion is what
            # would have caught the original bug directly.
            assert "=" in line, f"malformed GITHUB_OUTPUT line: {line!r}"
            key, _, value = line.partition("=")
            outputs[key] = value
        return outputs


class TestAnalyzeFailuresDoesNotCrashOnNoMatch:
    """The exact case that broke run 35414763080: a regression-output.txt
    with no console/CRUD/server-error markers in it at all."""

    def test_no_match_does_not_crash(self, analyze_script: str) -> None:
        outputs = _run_analyze(analyze_script, "some unrelated pytest output\n")
        assert outputs["console_errors"] == "0"
        assert outputs["crud_failures"] == "0"
        assert outputs["server_errors"] == "0"
        assert outputs["can_fix"] == "false"
        assert outputs["reason"] == "Unknown failure mode"

    def test_missing_log_file_short_circuits(self, analyze_script: str) -> None:
        outputs = _run_analyze(analyze_script, None)
        assert outputs == {"can_fix": "false"}


class TestAnalyzeFailuresClassifiesRealFailures:
    def test_server_error_blocks_auto_fix(self, analyze_script: str) -> None:
        outputs = _run_analyze(
            analyze_script, "boom: got a 500 Internal Server Error\n"
        )
        assert outputs["server_errors"] == "1"
        assert outputs["can_fix"] == "false"
        assert "Server errors" in outputs["reason"]

    def test_crud_failure_allows_auto_fix(self, analyze_script: str) -> None:
        outputs = _run_analyze(analyze_script, "could not find the submit button\n")
        assert outputs["crud_failures"] == "1"
        assert outputs["server_errors"] == "0"
        assert outputs["can_fix"] == "true"

    def test_multiple_console_errors_are_counted(self, analyze_script: str) -> None:
        outputs = _run_analyze(
            analyze_script, "console error: X\nconsole error: Y\n"
        )
        assert outputs["console_errors"] == "2"
        assert outputs["can_fix"] == "true"
