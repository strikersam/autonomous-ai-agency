"""State files must merge without conflicts.

On 2026-09-23 every open PR conflicted on `.claude/state/active-tasks.md`,
`.claude/state/NEXT_ACTION.md` and `graphify-out/GRAPH_REPORT.md` and nowhere
else. `.gitattributes` now gives those files merge strategies; this replays the
collision in a throwaway repository using the real attributes and driver hook.
"""
from __future__ import annotations

import shutil
import subprocess  # nosec B404 — fixed argv, test-only
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(  # nosec B603 B607 — fixed argv
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd, capture_output=True, text=True, check=False,
    )


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "master")
    shutil.copy(REPO / ".gitattributes", tmp_path / ".gitattributes")
    hook = tmp_path / ".claude/hooks/git-merge-drivers"
    hook.parent.mkdir(parents=True)
    shutil.copy(REPO / ".claude/hooks/git-merge-drivers", hook)
    _write(tmp_path, ".claude/state/active-tasks.md", "| # | Task |\n|---|---|\n| 69 | old |\n")
    _write(tmp_path, ".claude/state/NEXT_ACTION.md", "# Next Action\n\nbase state\n")
    _write(tmp_path, "graphify-out/GRAPH_REPORT.md", "Built from commit: `base`\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "base")
    subprocess.run(["sh", str(hook)], cwd=tmp_path, check=True)  # nosec B603 B607
    return tmp_path


def _both_sides_edit(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "feature")
    _write(repo, ".claude/state/active-tasks.md",
           "| # | Task |\n|---|---|\n| 70 | feature row |\n| 69 | old |\n")
    _write(repo, ".claude/state/NEXT_ACTION.md", "# Next Action\n\nfeature state\n")
    _write(repo, "graphify-out/GRAPH_REPORT.md", "Built from commit: `feature`\n")
    _git(repo, "commit", "-q", "-am", "feature")
    _git(repo, "checkout", "-q", "master")
    _write(repo, ".claude/state/active-tasks.md",
           "| # | Task |\n|---|---|\n| 70 | master row |\n| 69 | old |\n")
    _write(repo, ".claude/state/NEXT_ACTION.md", "# Next Action\n\nmaster state\n")
    _write(repo, "graphify-out/GRAPH_REPORT.md", "Built from commit: `master`\n")
    _git(repo, "commit", "-q", "-am", "master")
    _git(repo, "checkout", "-q", "feature")


def test_merging_master_into_a_branch_does_not_conflict(repo: Path) -> None:
    _both_sides_edit(repo)
    result = _git(repo, "merge", "--no-edit", "master")
    assert result.returncode == 0, result.stdout + result.stderr


def test_both_tracker_rows_survive(repo: Path) -> None:
    _both_sides_edit(repo)
    _git(repo, "merge", "--no-edit", "master")
    tasks = (repo / ".claude/state/active-tasks.md").read_text(encoding="utf-8")
    assert "feature row" in tasks and "master row" in tasks
    nxt = (repo / ".claude/state/NEXT_ACTION.md").read_text(encoding="utf-8")
    assert "feature state" in nxt and "master state" in nxt


def test_graph_report_takes_the_incoming_side(repo: Path) -> None:
    _both_sides_edit(repo)
    _git(repo, "merge", "--no-edit", "master")
    report = (repo / "graphify-out/GRAPH_REPORT.md").read_text(encoding="utf-8")
    assert report == "Built from commit: `master`\n"
