"""A git baseline for a plain copy of the agent workspace.

Production 2026-10-15: Render's /app has no .git, so ``InternalAgentAdapter``
ran every task in a plain copy. The E2B seed failed ("not a git repository")
and the sandbox started empty, and the judge had no baseline to diff the
agent's edits against ("git diff 0 chars" on every brief).
"""

from __future__ import annotations

import fnmatch
import logging
import subprocess  # nosec B404 - fixed git argv, list form, no shell
from pathlib import Path, PurePath

log = logging.getLogger("qwen-proxy")

# Never committed, so never seeded into a sandbox or shown to a model: secrets,
# then the app's own runtime state (local databases, provider records, chat
# history), which is user data and is not part of any task. A sandbox is a
# third-party service, so anything matched here must not reach one.
#
# A denylist cannot be complete. It is the backstop for the fallback paths (a
# plain copy, a directory walk); a real git checkout is protected first by what
# it tracks.
BASELINE_EXCLUDES = (
    ".env", ".env.*", "*.env", "*.pem", "*.key", "*.p12", "*.pfx", "*.jks", "*.keystore",
    "id_rsa*", "id_dsa*", "id_ecdsa*", "id_ed25519*", ".ssh/", ".aws/", ".kube/", ".gnupg/",
    ".netrc", ".npmrc", ".pypirc", ".git-credentials", "credentials.json", "token.json",
    "service-account*.json", "secrets.json", "secrets.yaml", "secrets.yml",
    ".data/", "*.db", "*.db3", "*.sqlite", "*.sqlite3", "*-wal", "*-shm", "*-journal",
    ".instance_id", ".activation_audit.jsonl",
)
# Templates are meant to be read and edited (.env.example is tracked on purpose
# and CLAUDE.md rule 37 requires updating it). Excluding one made an agent's new
# copy overwrite the real file on the way back.
TEMPLATE_SUFFIXES = (".example", ".sample", ".template", ".dist")
# The same patterns as bare, lower-case names, matched one path component at a time.
EXCLUDED_NAMES = tuple(pattern.rstrip("/").lower() for pattern in BASELINE_EXCLUDES)
_COPY_SKIP = (".git", "__pycache__", "*.pyc", "node_modules")


def _name_excluded(name: str) -> bool:
    lowered = name.lower()
    if lowered.endswith(TEMPLATE_SUFFIXES):
        return False
    return any(fnmatch.fnmatchcase(lowered, pattern) for pattern in EXCLUDED_NAMES)


def is_excluded(rel_path: str) -> bool:
    """True when any component of *rel_path* is a secret or runtime-state name."""
    return any(_name_excluded(part) for part in PurePath(rel_path).parts)


def copy_ignore(_directory: str, names: list[str]) -> set[str]:
    """``shutil.copytree`` ignore callback: bulky dirs, secrets and runtime state."""
    return {
        name for name in names
        if _name_excluded(name) or any(fnmatch.fnmatchcase(name, skip) for skip in _COPY_SKIP)
    }


def _git_exclude_lines() -> list[str]:
    """Patterns for ``.git/info/exclude``, re-including the template files."""
    return [*BASELINE_EXCLUDES, *(f"!*{suffix}" for suffix in TEMPLATE_SUFFIXES)]

_IDENTITY = ["-c", "user.email=agent@localhost", "-c", "user.name=Agent", "-c", "core.hooksPath=/dev/null",
             "-c", "commit.gpgsign=false"]


def git_baseline(path: str) -> bool:
    """Make *path* a git repo with one commit of its files; False on failure (best-effort)."""
    try:
        _git(path, "init", "-q")
        exclude = Path(path, ".git", "info", "exclude")
        exclude.parent.mkdir(parents=True, exist_ok=True)
        exclude.write_text("\n".join(_git_exclude_lines()) + "\n", encoding="utf-8")
        _git(path, "add", "-A")
        _add_ignored_templates(path)
        _git(path, *_IDENTITY, "commit", "-q", "--allow-empty", "-m", "task baseline")
        return True
    except (subprocess.SubprocessError, OSError) as exc:
        log.warning("Could not give the task copy a git baseline: %s", exc)
        return False


def _add_ignored_templates(path: str) -> None:
    """Track template files a workspace ``.gitignore`` hides (e.g. ``.env*``).

    ``.gitignore`` outranks ``.git/info/exclude``, so the ``!*.example`` lines
    there cannot restore them; without this the tracked-file seed omits them.
    """
    listed = subprocess.run(  # nosec B603, B607 - fixed git argv, list form, no shell
        ["git", "ls-files", "--others", "--ignored", "--exclude-standard", "-z"],
        cwd=path, check=True, capture_output=True, text=True, timeout=120,
    ).stdout
    templates = [
        f for f in listed.split("\0")
        if f and f.lower().endswith(TEMPLATE_SUFFIXES) and not is_excluded(f)
    ]
    for start in range(0, len(templates), 200):
        _git(path, "add", "-f", "--", *templates[start:start + 200])


def _git(cwd: str, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, timeout=120)  # nosec - fixed git argv, list form
