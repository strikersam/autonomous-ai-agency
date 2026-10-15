"""The task copy of a non-git workspace gets a git baseline (production 2026-10-15).

Render's /app has no .git, so every task ran in a plain copy: the E2B seed
logged "git ls-files failed … not a git repository" and the sandbox started
empty, and the judge never had a baseline to diff against ("git diff 0 chars").
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from runtimes.adapters.internal_agent import InternalAgentAdapter


def _git(cwd: str, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout  # nosec - test-only, fixed git argv


def test_copy_of_a_non_git_workspace_is_a_git_repo_with_a_baseline(tmp_path):
    ws = tmp_path / "workspace"
    (ws / "pkg").mkdir(parents=True)
    (ws / "pkg" / "mod.py").write_text("x = 1\n", encoding="utf-8")
    wt, tmp = InternalAgentAdapter._create_worktree(str(ws), "task_abc")
    try:
        assert tmp is not None
        assert "pkg/mod.py" in _git(wt, "ls-files").split()
        Path(wt, "pkg", "mod.py").write_text("x = 2\n", encoding="utf-8")
        assert "+x = 2" in _git(wt, "diff", "HEAD")
        assert not (ws / ".git").exists()  # the original workspace is untouched
    finally:
        InternalAgentAdapter._remove_worktree(str(ws), wt, tmp)


def test_secret_files_never_enter_the_baseline(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "app.py").write_text("ok\n", encoding="utf-8")
    (ws / ".env").write_text("TOKEN=x\n", encoding="utf-8")
    (ws / "deploy.pem").write_text("k\n", encoding="utf-8")
    (ws / "secrets_store.py").write_text("code\n", encoding="utf-8")  # code about secrets is still code
    wt, tmp = InternalAgentAdapter._create_worktree(str(ws), "task_def")
    try:
        tracked = _git(wt, "ls-files").split()
        assert tracked == ["app.py", "secrets_store.py"]
    finally:
        InternalAgentAdapter._remove_worktree(str(ws), wt, tmp)


def test_global_git_signing_does_not_break_the_baseline(tmp_path, monkeypatch):
    # Verifier finding: commit.gpgsign=true with no usable key failed the commit.
    cfg = tmp_path / "gitconfig"
    cfg.write_text("[commit]\n\tgpgsign = true\n[gpg]\n\tprogram = false\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "a.py").write_text("x\n", encoding="utf-8")
    wt, tmp = InternalAgentAdapter._create_worktree(str(ws), "task_sig")
    try:
        assert _git(wt, "ls-files").split() == ["a.py"]
        assert _git(wt, "rev-parse", "HEAD").strip()
    finally:
        InternalAgentAdapter._remove_worktree(str(ws), wt, tmp)
