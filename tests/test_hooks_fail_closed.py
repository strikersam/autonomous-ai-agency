"""Git hooks in .claude/hooks fail closed (#1796, item 1).

Each test runs the real hook script in a throwaway repo. Three hooks let the
action through when they could not do their check:

- commit-msg: `grep -c ... || echo 0` produced "0\\n0" on no match, every `-eq`
  test errored, and a code commit with no changelog passed (rule 34 silently off);
- pre-push: no pytest meant "skipping test run" and exit 0 (rule 30);
- pre-commit: no python3 meant staged Python was committed unchecked.
"""
from __future__ import annotations

import os
import shutil
import subprocess  # nosec B404 - fixed argv against a tmp repo
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent.parent / ".claude" / "hooks"
SH = shutil.which("sh")

pytestmark = pytest.mark.skipif(SH is None or shutil.which("git") is None, reason="needs sh and git")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],  # nosec B603 B607
                   cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "changelog.md").write_text("# Changelog\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "init")
    return tmp_path


def _bin_without(tmp_path: Path, *tools: str) -> str:
    """A PATH holding only the tools a hook needs, so python/pytest are absent."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    for tool in tools:
        found = shutil.which(tool)
        assert found, tool
        (bindir / tool).symlink_to(found)
    return str(bindir)


def _run(hook: str, repo: Path, *args: str, path: str | None = None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_") and k != "VIRTUAL_ENV"}
    if path is not None:
        env["PATH"] = path
    return subprocess.run([SH, str(HOOKS / hook), *args], cwd=repo, env=env,  # nosec B603
                          capture_output=True, text=True)


def _commit_msg(repo: Path, subject: str) -> Path:
    msg = repo / "msg.txt"
    msg.write_text(subject + "\n")
    return msg


class TestCommitMsg:
    def test_code_without_changelog_is_blocked(self, repo):
        (repo / "app.py").write_text("print(1)\n")
        _git(repo, "add", "app.py")
        result = _run("commit-msg", repo, str(_commit_msg(repo, "feat: add app")))
        assert result.returncode == 1, result.stdout + result.stderr
        assert "BLOCKED" in result.stdout
        assert "Illegal number" not in result.stderr + result.stdout

    def test_code_with_changelog_passes(self, repo):
        (repo / "app.py").write_text("print(1)\n")
        (repo / "docs" / "changelog.md").write_text("# Changelog\n- entry\n")
        _git(repo, "add", "-A")
        assert _run("commit-msg", repo, str(_commit_msg(repo, "feat: add app"))).returncode == 0

    def test_exempt_prefix_passes_without_changelog(self, repo):
        (repo / "app.py").write_text("print(1)\n")
        _git(repo, "add", "app.py")
        assert _run("commit-msg", repo, str(_commit_msg(repo, "chore: tidy"))).returncode == 0

    def test_docs_only_commit_passes(self, repo):
        (repo / "README.md").write_text("hi\n")
        _git(repo, "add", "README.md")
        assert _run("commit-msg", repo, str(_commit_msg(repo, "feat: readme"))).returncode == 0


def test_pre_push_blocks_when_pytest_is_missing(repo, tmp_path):
    path = _bin_without(tmp_path, "git", "grep")
    result = _run("pre-push", repo, path=path)
    assert result.returncode != 0, result.stdout
    assert "push blocked" in result.stdout


def test_pre_commit_blocks_unchecked_python_when_python_is_missing(repo, tmp_path):
    (repo / "app.py").write_text("print(1)\n")
    _git(repo, "add", "app.py")
    path = _bin_without(tmp_path, "git", "grep", "head")
    result = _run("pre-commit", repo, path=path)
    assert result.returncode != 0, result.stdout
    assert "cannot syntax-check" in result.stdout
