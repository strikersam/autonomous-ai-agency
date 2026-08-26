"""Tests for ``scripts/triage_orphaned_context_prs.py``.

The rule worth guarding is the one that keeps recovery honest: an exhaustion
backed by a recorded analysis must survive the sweep, or the sweep quietly
undoes the analysis gate and the loop goes back to grinding on work it has
already correctly judged unfixable.
"""
from __future__ import annotations

import pytest

from scripts.triage_orphaned_context_prs import (
    ACTION_CLEAR_EXHAUSTED,
    ACTION_REOPEN,
    ACTION_SKIP,
    ANALYSIS_MARKER,
    decide,
    issue_number_from_branch,
)


def _issue(state="OPEN", labels=(), comments=()):
    return {
        "state": state,
        "labels": [{"name": n} for n in labels],
        "comments": [{"body": b} for b in comments],
    }


class TestBranchParsing:
    @pytest.mark.parametrize("branch,expected", [
        ("claude/context-issue-1349", 1349),
        ("claude/context-issue-1", 1),
    ])
    def test_extracts_issue_number(self, branch: str, expected: int) -> None:
        assert issue_number_from_branch(branch) == expected

    @pytest.mark.parametrize("branch", [
        "claude/render-bottleneck-alternatives-sv8aj1",
        "dependabot/pip/idna-gte-3.19",
        "quick-note/issue-1349",
        "master",
    ])
    def test_ignores_unrelated_branches(self, branch: str) -> None:
        assert issue_number_from_branch(branch) is None


class TestDecisions:
    def test_closed_issue_is_reopened(self) -> None:
        """The exact state of the 7 stranded plans: closed, PR still open."""
        d = decide(_issue(state="CLOSED", labels=["quick-note:exhausted"]))
        assert d.action == ACTION_REOPEN
        assert "unreachable" in d.reason

    def test_exhausted_without_analysis_is_recovered(self) -> None:
        d = decide(_issue(labels=["quick-note:exhausted"], comments=["❌ Failed after 3 attempts"]))
        assert d.action == ACTION_CLEAR_EXHAUSTED
        assert "never asked why" in d.reason

    def test_exhausted_with_analysis_is_left_alone(self) -> None:
        """Recovery must not undo a verdict that was actually reasoned."""
        d = decide(_issue(
            labels=["quick-note:exhausted"],
            comments=[f"{ANALYSIS_MARKER} — `exhausted`\n\n2 real failing tests"],
        ))
        assert d.action == ACTION_SKIP
        assert "should stand" in d.reason

    def test_rejected_is_never_touched(self) -> None:
        d = decide(_issue(state="CLOSED", labels=["quick-note:rejected"]))
        assert d.action == ACTION_SKIP
        assert "deliberate decision" in d.reason

    def test_rejected_wins_over_closed(self) -> None:
        """A rejected issue stays rejected even though it is also stranded."""
        d = decide(_issue(state="CLOSED", labels=["quick-note:rejected", "quick-note:exhausted"]))
        assert d.action == ACTION_SKIP

    def test_healthy_open_issue_is_skipped(self) -> None:
        assert decide(_issue(labels=["retry:1"])).action == ACTION_SKIP


class TestWorkflowWiring:
    def test_sweep_workflow_uses_this_script(self) -> None:
        from pathlib import Path

        wf = Path(__file__).resolve().parents[1] / ".github/workflows/orphaned-pr-sweep.yml"
        assert wf.exists(), "orphaned-pr-sweep.yml must exist"
        assert "triage_orphaned_context_prs.py" in wf.read_text(encoding="utf-8")
