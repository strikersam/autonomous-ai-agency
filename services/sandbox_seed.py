"""Pack a host workspace into the archive a sandbox is seeded from.

Seeding used to depend on ``git ls-files``. When the workspace was not a git
repository (the deployed app directory is not one), that failed, the caller
carried on, and the agent was handed an empty sandbox: ``list_files`` and
``search_code`` returned nothing and the task could not succeed. The listing
now falls back to walking the directory, so a workspace with files always
yields a seed.

Everything here is blocking (git, the filesystem, gzip) and is meant to be
called through ``asyncio.to_thread``.
"""
from __future__ import annotations

import io
import logging
import os
import subprocess
import tarfile

from runtimes.adapters.workspace_baseline import is_excluded

log = logging.getLogger("qwen-proxy")

# Never worth shipping to a sandbox, and large enough to matter.
_SKIP_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "dist", "build", ".next", ".cache",
})
_MAX_FILES = 20000
_MAX_FILE_BYTES = 5 * 1024 * 1024
_GIT_TIMEOUT_S = 30


def _git_tracked(worktree_path: str) -> list[str] | None:
    """Tracked files, or ``None`` when *worktree_path* is not a usable git repo."""
    try:
        result = subprocess.run(  # nosec B603, B607 - constant git argv, list form, no shell
            ["git", "ls-files", "-z"], cwd=worktree_path, capture_output=True, text=True,
            timeout=_GIT_TIMEOUT_S,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.info("sandbox seed: git unavailable in %s (%s); walking the directory", worktree_path, exc)
        return None
    if result.returncode != 0:
        log.info("sandbox seed: %s is not a git repo; walking the directory", worktree_path)
        return None
    return [f for f in result.stdout.split("\0") if f]  # -z: no quoting of odd names


def _walked(worktree_path: str) -> list[str]:
    """Relative paths of regular files under *worktree_path*, skipping bulky dirs."""
    found: list[str] = []
    for root, dirs, names in os.walk(worktree_path):
        dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS and not is_excluded(d))
        for name in sorted(names):
            if is_excluded(name):
                continue
            found.append(os.path.relpath(os.path.join(root, name), worktree_path))
            if len(found) >= _MAX_FILES:
                log.warning("sandbox seed: stopped at %d files in %s", _MAX_FILES, worktree_path)
                return found
    return found


def list_seed_files(worktree_path: str) -> list[str]:
    """Files to seed: git-tracked when it is a git repo, otherwise a directory walk.

    A git repo with nothing tracked seeds nothing; it is not treated as "not
    git", because the walk has no ``.gitignore`` to protect it. Either way,
    anything matching the baseline excludes (secrets, runtime state) is dropped.
    """
    tracked = _git_tracked(worktree_path)
    files = tracked if tracked is not None else _walked(worktree_path)
    return [f for f in files if not is_excluded(f)]


def pack_seed(worktree_path: str) -> tuple[bytes, int]:
    """Return ``(tar.gz bytes, file count)`` for *worktree_path*; ``(b"", 0)`` if empty.

    Symlinks are stored as links, never followed, and oversized or unreadable
    files are skipped, so nothing outside the workspace is packed.
    """
    files = list_seed_files(worktree_path)
    if not files:
        return b"", 0
    buf = io.BytesIO()
    packed = 0
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for rel in files:
            full = os.path.join(worktree_path, rel)
            try:
                if not os.path.lexists(full) or os.path.isdir(full) and not os.path.islink(full):
                    continue
                if not os.path.islink(full) and os.path.getsize(full) > _MAX_FILE_BYTES:
                    continue
                tar.add(full, arcname=rel, recursive=False)
                packed += 1
            except (OSError, PermissionError, tarfile.TarError):
                continue  # one unreadable file must not lose the whole seed
    return (buf.getvalue(), packed) if packed else (b"", 0)
