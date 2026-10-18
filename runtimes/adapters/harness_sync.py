"""runtimes/adapters/harness_sync.py — carry the harness spec across task worktrees.

`InternalAgentAdapter` runs each task in a throwaway worktree and deletes it
afterwards, so a `.agency/harness.md` written during the run (agent/harness_spec.py)
would vanish before the next task could read it. These helpers copy that one file
into the worktree before the run and back to the persistent workspace after it.

Only the single known path is copied, as a regular file under a size cap. Content
need not be trusted here: `harness_spec.build_block()` only injects entries whose
citation matches a lesson this platform recorded, so a file the agent rewrote
during the run cannot add instructions.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

log = logging.getLogger("qwen-proxy")

_SPEC_RELPATH = Path(".agency") / "harness.md"
_MAX_BYTES = 64 * 1024


def _copy_spec(src_root: str, dst_root: str) -> bool:
    """Copy the spec between workspace roots; True when the destination changed."""
    src, dst = Path(src_root) / _SPEC_RELPATH, Path(dst_root) / _SPEC_RELPATH
    try:
        if src.is_symlink() or not src.is_file() or src.stat().st_size > _MAX_BYTES:
            return False
        if dst.is_file() and dst.read_bytes() == src.read_bytes():
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        # Write-then-replace so a crash never leaves a half-written spec.
        tmp = dst.with_name(f".{dst.name}.{os.getpid()}.tmp")
        shutil.copyfile(src, tmp)
        os.replace(tmp, dst)
        return True
    except OSError as exc:
        log.debug("harness spec sync skipped: %s", exc)
        return False


def seed_spec(base_workspace: str, worktree: str) -> bool:
    """Make the persistent spec visible inside a fresh worktree."""
    if os.path.realpath(base_workspace) == os.path.realpath(worktree):
        return False
    return _copy_spec(base_workspace, worktree)


def persist_spec(worktree: str, base_workspace: str) -> bool:
    """Save a spec refined during the run back to the persistent workspace."""
    if os.path.realpath(base_workspace) == os.path.realpath(worktree):
        return False
    return _copy_spec(worktree, base_workspace)
