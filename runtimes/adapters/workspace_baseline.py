"""A git baseline for a plain copy of the agent workspace.

Production 2026-10-15: Render's /app has no .git, so ``InternalAgentAdapter``
ran every task in a plain copy. The E2B seed failed ("not a git repository")
and the sandbox started empty, and the judge had no baseline to diff the
agent's edits against ("git diff 0 chars" on every brief).
"""

from __future__ import annotations

import logging
import subprocess  # nosec B404 - fixed git argv, list form, no shell
from pathlib import Path

log = logging.getLogger("qwen-proxy")

# Never committed, so never seeded into a sandbox or shown to a model.
BASELINE_EXCLUDES = (".env", ".env.*", "*.env", "*.pem", "*.key", "*.p12", "id_rsa*", "credentials.json")

_IDENTITY = ["-c", "user.email=agent@localhost", "-c", "user.name=Agent", "-c", "core.hooksPath=/dev/null",
             "-c", "commit.gpgsign=false"]


def git_baseline(path: str) -> bool:
    """Make *path* a git repo with one commit of its files; False on failure (best-effort)."""
    try:
        _git(path, "init", "-q")
        exclude = Path(path, ".git", "info", "exclude")
        exclude.parent.mkdir(parents=True, exist_ok=True)
        exclude.write_text("\n".join(BASELINE_EXCLUDES) + "\n", encoding="utf-8")
        _git(path, "add", "-A")
        _git(path, *_IDENTITY, "commit", "-q", "--allow-empty", "-m", "task baseline")
        return True
    except (subprocess.SubprocessError, OSError) as exc:
        log.warning("Could not give the task copy a git baseline: %s", exc)
        return False


def _git(cwd: str, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, timeout=120)  # nosec - fixed git argv, list form
