"""Guards on ``.github/workflows/auto-merge.yml``.

The job has no checkout step, so every ``gh`` call without a repository fell
over with "fatal: not a git repository" (run 35843550240, PR #1562). The merge
failure was swallowed as a warning and the draft/planning guards silently read
their fallbacks, so the workflow had not merged anything while looking green.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/auto-merge.yml"


SCRIPT = WORKFLOW.parents[1] / "scripts/autonomy_merge.py"


def _steps() -> list[dict]:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["auto-merge"]["steps"]


@pytest.fixture(scope="module")
def guard_step() -> dict:
    return next(s for s in _steps() if s.get("id") == "guard")


@pytest.fixture(scope="module")
def gate_step() -> dict:
    return next(s for s in _steps() if s.get("name") == "Autonomy merge gate")


def test_gh_is_told_which_repository(guard_step: dict, gate_step: dict) -> None:
    assert guard_step["env"]["GH_REPO"] == "${{ github.repository }}"
    assert gate_step["env"]["REPO"] == "${{ github.repository }}"


def test_unreadable_metadata_does_not_merge(guard_step: dict) -> None:
    assert "not merging blind" in guard_step["run"]


def test_guards_run_before_the_gate(guard_step: dict, gate_step: dict) -> None:
    assert "isDraft" in guard_step["run"] and "gh pr merge" not in guard_step["run"]
    assert gate_step["if"] == "steps.guard.outputs.pr_ready == 'true'"


def test_dependabot_prs_are_left_to_their_own_workflow() -> None:
    """--admin here would merge the major bumps dependabot-auto-merge holds back."""
    assert '"dependabot/"' in SCRIPT.read_text(encoding="utf-8")


def test_merge_waits_for_every_required_check() -> None:
    """#1873 merged with Security Gate red and #1863 with its Python tests
    skipped: --admin overrode branch protection on any green CI run. --auto
    lets GitHub merge only once every required check passes."""
    script = SCRIPT.read_text(encoding="utf-8")
    merge_cmd = script[script.index('"pr", "merge"'):].split(")")[0]
    assert "--admin" not in script
    assert '"--auto"' in merge_cmd
    assert '"--match-head-commit"' in merge_cmd


def test_no_workflow_merges_with_admin() -> None:
    """Any `gh pr merge --admin` in a workflow skips required checks."""
    workflows = WORKFLOW.parent
    offenders = [
        f"{p.name}:{n}"
        for p in sorted(workflows.glob("*.yml"))
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if "--admin" in line and not line.lstrip().startswith("#")
    ]
    assert offenders == []
