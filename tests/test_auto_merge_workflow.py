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


@pytest.fixture(scope="module")
def merge_step() -> dict:
    steps = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["auto-merge"]["steps"]
    return next(s for s in steps if s.get("name") == "Merge PR")


def test_gh_is_told_which_repository(merge_step: dict) -> None:
    assert merge_step["env"]["GH_REPO"] == "${{ github.repository }}"


def test_dependabot_prs_are_left_to_their_own_workflow(merge_step: dict) -> None:
    """--admin here would merge the major bumps dependabot-auto-merge holds back."""
    assert "^dependabot/" in merge_step["run"]


def test_unreadable_metadata_does_not_merge(merge_step: dict) -> None:
    assert 'if [ -z "$HEAD_BRANCH" ]' in merge_step["run"]


def test_guards_run_before_the_merge(merge_step: dict) -> None:
    run = merge_step["run"]
    merge_at = run.index("gh pr merge")
    for guard in ("isDraft", "^agent/", "^dependabot/"):
        assert run.index(guard) < merge_at, guard


def test_merge_waits_for_every_required_check(merge_step: dict) -> None:
    """#1873 merged with Security Gate red and #1863 with its Python tests
    skipped: --admin overrode branch protection on any green CI run. --auto
    lets GitHub merge only once every required check passes."""
    run = merge_step["run"]
    merge_cmd = run[run.index("gh pr merge"):].split("||")[0]
    assert "--admin" not in merge_cmd
    assert "--auto" in merge_cmd
    assert "--match-head-commit" in merge_cmd


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
