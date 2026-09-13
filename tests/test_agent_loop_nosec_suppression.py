"""Regression test: bandit `# nosec` annotations in agent/loop.py actually work.

bandit==1.9.4's NOSEC_COMMENT_TESTS regex only registers the *last* code in a
comma-separated nosec list, so `# nosec B603,B607` suppresses B607 but leaves
B603 firing. Three subprocess.run calls in AgentRunner._commit_step carried
exactly that broken form. See CHANGELOG.md's 2026-09-13 entry and
tests/test_changelog_check_workflow.py::_is_exempt, which documents and works
around the same bandit bug.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

BANDIT = shutil.which("bandit")
LOOP_PY = Path(__file__).resolve().parent.parent / "agent" / "loop.py"


@pytest.mark.skipif(BANDIT is None, reason="bandit CLI not installed in this environment")
def test_all_subprocess_nosec_lines_in_agent_loop_are_actually_suppressed():
    proc = subprocess.run(
        [
            BANDIT,
            str(LOOP_PY),
            "-f",
            "json",
            "-q",
            "--skip",
            "B101,B105,B110,B112,B404,B314,B405,B310",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    report = json.loads(proc.stdout)
    flagged_lines = {r["line_number"] for r in report["results"] if r["test_id"] in ("B603", "B607")}

    source_lines = LOOP_PY.read_text().splitlines()
    nosec_subprocess_lines = {
        i + 1 for i, line in enumerate(source_lines) if "nosec" in line and re.search(r"\bB60[37]\b", line)
    }
    # Sanity check that this test is actually exercising something.
    assert nosec_subprocess_lines, "expected at least one B603/B607 nosec annotation in agent/loop.py"

    still_flagged = flagged_lines & nosec_subprocess_lines
    assert not still_flagged, (
        f"bandit still reports B603/B607 on lines annotated nosec: {sorted(still_flagged)}. "
        "bandit 1.9.4's NOSEC_COMMENT_TESTS regex only honours the LAST code in a "
        "comma-separated nosec list (e.g. `# nosec B603,B607` suppresses only B607) "
        "— use a bare `# nosec` instead."
    )
