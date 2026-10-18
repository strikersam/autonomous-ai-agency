"""runtimes/adapters/harness_sync.py — carry the harness spec across task worktrees.

`InternalAgentAdapter` runs each task in a throwaway worktree and deletes it
afterwards, so a `.agency/harness.md` written during the run (agent/harness_spec.py)
would vanish before the next task could read it. `seed_spec` copies the persistent
spec into the worktree; `persist_spec` brings back what the run changed.

Concurrent tasks are seeded from the same base spec, so the run's *changes* (entries
added and retired relative to the seed) are merged into the current base spec instead
of replacing it. The run's audit history is appended to the base history file.

Content need not be trusted here: `harness_spec.build_block()` only injects entries
whose citation matches a lesson this platform recorded, so a file the agent rewrote
during the run cannot add instructions. Only the two known paths are touched, as
regular files under a size cap.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from agent.harness_spec import SpecEntry, apply_delta, is_contained, read_entries

log = logging.getLogger("qwen-proxy")

_SPEC_RELPATH = Path(".agency") / "harness.md"
_HISTORY_RELPATH = Path(".agency") / "harness-history.jsonl"
_MAX_BYTES = 64 * 1024


def _regular_file(path: Path) -> bool:
    """True for a plain, size-capped file; symlinks are refused."""
    try:
        return not path.is_symlink() and path.is_file() and path.stat().st_size <= _MAX_BYTES
    except OSError:
        return False


def seed_spec(base_workspace: str, worktree: str) -> frozenset[str]:
    """Copy the persistent spec into a fresh worktree; return the signatures seeded."""
    src, dst = Path(base_workspace) / _SPEC_RELPATH, Path(worktree) / _SPEC_RELPATH
    if os.path.realpath(base_workspace) == os.path.realpath(worktree) or not _regular_file(src):
        return frozenset()
    if not (is_contained(base_workspace) and is_contained(worktree)):
        return frozenset()
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    except OSError as exc:
        log.debug("harness spec seed skipped: %s", exc)
        return frozenset()
    return frozenset(e.signature for e in read_entries(worktree))


def _append_history(worktree: str, base_workspace: str) -> None:
    """Append worktree history lines the base file does not already hold."""
    src, dst = Path(worktree) / _HISTORY_RELPATH, Path(base_workspace) / _HISTORY_RELPATH
    if not _regular_file(src) or not (is_contained(worktree) and is_contained(base_workspace)):
        return
    try:
        have = set(dst.read_text(encoding="utf-8").splitlines()) if dst.is_file() else set()
        fresh = [ln for ln in src.read_text(encoding="utf-8").splitlines() if ln and ln not in have]
        if fresh:
            dst.parent.mkdir(parents=True, exist_ok=True)
            with dst.open("a", encoding="utf-8") as fh:
                fh.write("\n".join(fresh) + "\n")
    except (OSError, UnicodeDecodeError) as exc:
        log.debug("harness history sync skipped: %s", exc)


def persist_spec(worktree: str, base_workspace: str, seeded: frozenset[str] = frozenset()) -> None:
    """Merge what a run changed in its spec, and its history, into the base workspace."""
    if os.path.realpath(base_workspace) == os.path.realpath(worktree):
        return
    spec = Path(worktree) / _SPEC_RELPATH
    if _regular_file(spec) and is_contained(worktree):
        after: list[SpecEntry] = read_entries(worktree)
        now = {e.signature for e in after}
        added = [e for e in after if e.signature not in seeded]
        apply_delta(base_workspace, added, set(seeded) - now)
    _append_history(worktree, base_workspace)
