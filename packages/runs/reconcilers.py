"""packages/runs/reconcilers.py — ask the outside world whether a recorded side effect happened.

Registered with ``OperationLedger`` (``register_builtin_reconcilers``) and used
by the recovery tick for operations whose deadline passed while ``executing``:

* ``git_push`` (repeat safe: pushing the same commit again is a no op, and the
  push is never forced): ``git ls-remote`` on the recorded branch. The recorded
  SHA at the branch head is ``done``; a missing or different head is
  ``not_done``; any error is ``unknown``.
* ``open_pull_request`` (repeat safe: GitHub refuses a second open PR for one
  head): an open PR from the recorded head branch is ``done``, none is
  ``not_done``, any error is ``unknown``.

Subprocesses run in list form under a hard timeout that kills the process.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from packages.runs.models import OperationRecord
from packages.runs.operations import DONE, NOT_DONE, UNKNOWN, register_reconciler

log = logging.getLogger("qwen-proxy")

GIT_TIMEOUT_S = 30.0
_SAFE_REF = re.compile(r"^[A-Za-z0-9._/\-]{1,200}$")
_SHA = re.compile(r"^[0-9a-f]{7,64}$")


async def run_git(args: list[str], cwd: str, timeout_s: float = GIT_TIMEOUT_S) -> tuple[int, str]:
    """Run ``git *args`` in *cwd*; kill it at the timeout (raises ``TimeoutError``)."""
    proc = await asyncio.create_subprocess_exec(
        "git", *args, cwd=cwd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.DEVNULL,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout_s)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise
    return proc.returncode or 0, out.decode(errors="replace")


async def reconcile_git_push(op: OperationRecord) -> str:
    """``done`` when the remote branch head is the recorded SHA (see the module docstring)."""
    target = op.target or {}
    branch, sha, cwd = target.get("branch"), target.get("sha"), target.get("cwd")
    remote = target.get("remote") or "origin"
    if not (isinstance(branch, str) and _SAFE_REF.match(branch) and isinstance(sha, str)
            and _SHA.match(sha) and isinstance(cwd, str) and _SAFE_REF.match(remote)):
        return UNKNOWN
    try:
        rc, out = await run_git(["ls-remote", "--heads", remote, f"refs/heads/{branch}"], cwd)
    except Exception:
        log.warning("git_push reconciler: ls-remote failed for %s", op.op_id, exc_info=True)
        return UNKNOWN
    if rc != 0:
        return UNKNOWN
    heads = [line.split()[0] for line in out.splitlines() if line.strip()]
    return DONE if any(h.startswith(sha) or sha.startswith(h) for h in heads) else NOT_DONE


def _github_client() -> Any:
    from agent.agency import _gh_token
    from agent.github_tools import GitHubTools

    return GitHubTools(_gh_token() or None)


async def reconcile_open_pull_request(op: OperationRecord) -> str:
    """``done`` when an open PR from the recorded head branch exists."""
    target = op.target or {}
    owner, repo, head = target.get("owner"), target.get("repo"), target.get("head")
    if not all(isinstance(v, str) and v for v in (owner, repo, head)):
        return UNKNOWN
    try:
        pulls = await _github_client().list_pull_requests(owner, repo, state="open")
    except Exception:
        log.warning("open_pull_request reconciler: listing PRs failed for %s", op.op_id,
                    exc_info=True)
        return UNKNOWN
    found = any((p.get("head") or {}).get("ref") == head for p in pulls)
    return DONE if found else NOT_DONE


def register_builtin_reconcilers() -> None:
    """Register the git push and pull request reconcilers (idempotent)."""
    register_reconciler("git_push", reconcile_git_push, repeat_safe=True)
    register_reconciler("open_pull_request", reconcile_open_pull_request, repeat_safe=True)
