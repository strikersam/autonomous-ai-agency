"""Ship-code delivery for the internal agent runtime.

Two jobs, both about making "DONE" mean the work actually landed:

* ``clone_repo_workspace`` gives a ship-code task a real git clone of its
  target repo to work in. The production image is built with ``.git`` excluded
  (``.dockerignore``) and only part of the tree copied in, so the old fallback —
  a plain copy of the app directory — could never commit, push or open a PR:
  every change was deleted with the temp dir while the task showed DONE.
* ``assess_delivery`` turns the agent run into an honest outcome: changed files
  that never reached GitHub are a failure (retryable), and a ship-code task that
  changed nothing, or that the judge rejected, waits for a human instead of
  being closed.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import re
import tempfile
from dataclasses import dataclass

log = logging.getLogger("qwen-proxy")

AGENT_GIT_NAME = "Agency Agent"
AGENT_GIT_EMAIL = "agency-agent@users.noreply.github.com"

# Task types whose whole point is a code change; finishing one with no change
# needs a human look (the initiative may already be done, or the agent stalled).
CODE_CHANGE_TASK_TYPES = frozenset({"portfolio_initiative", "issue"})

_GITHUB_REPO_RE = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)
_BRANCH_RE = re.compile(r"^[A-Za-z0-9/_.-]{1,100}$")
_CLONE_TIMEOUT_S = 180


@dataclass
class DeliveryOutcome:
    """What the adapter should report for one agent run."""

    success: bool
    output: str
    task_status: str | None = None
    review_reason: str | None = None


def parse_github_repo(repo_url: str) -> tuple[str, str] | None:
    """Return ``(owner, repo)`` for a plain https GitHub repo URL, else None."""
    match = _GITHUB_REPO_RE.match((repo_url or "").strip())
    if not match:
        return None
    return match.group("owner"), match.group("repo")


async def _git(*args: str, cwd: str | None = None) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        "git", *args, cwd=cwd,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, err = await asyncio.wait_for(proc.communicate(), timeout=_CLONE_TIMEOUT_S)
    except asyncio.TimeoutError:
        proc.kill()
        return 1, "timed out"
    return proc.returncode or 0, err.decode(errors="replace")


async def clone_repo_workspace(
    repo_url: str, base_branch: str, token: str, task_id: str
) -> tempfile.TemporaryDirectory | None:
    """Shallow-clone *repo_url* at *base_branch* into a temp dir. None on failure.

    The token travels as a one-off auth header, so it is never written to
    ``.git/config`` or put in a URL that could surface in an error message.
    """
    parsed = parse_github_repo(repo_url)
    if parsed is None or not _BRANCH_RE.match(base_branch or ""):
        log.warning("Task %s: not cloning — unsupported repo %r / branch %r",
                    task_id, repo_url, base_branch)
        return None
    owner, repo = parsed
    slug = re.sub(r"[^A-Za-z0-9_-]", "-", str(task_id))[:40]
    tmp = tempfile.TemporaryDirectory(prefix=f"llm-task-clone-{slug}-")
    args = ["clone", "--depth", "1", "--branch", base_branch,
            f"https://github.com/{owner}/{repo}.git", tmp.name]
    if token:
        basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        args = ["-c", f"http.https://github.com/.extraheader=AUTHORIZATION: basic {basic}", *args]
    rc, err = await _git(*args)
    if rc != 0:
        log.warning("Task %s: clone of %s/%s failed (rc=%s): %s",
                    task_id, owner, repo, rc, err.replace(token, "***") if token else err)
        tmp.cleanup()
        return None
    for key, value in (("user.name", AGENT_GIT_NAME), ("user.email", AGENT_GIT_EMAIL)):
        await _git("config", key, value, cwd=tmp.name)
    log.info("Task %s: working in a fresh clone of %s/%s@%s", task_id, owner, repo, base_branch)
    return tmp


def assess_delivery(
    *,
    did_work: bool,
    output: str,
    auto_commit: bool,
    task_type: str,
    changed_files: list[str],
    commits: list[str],
    pr_url: str | None,
    judge_verdict: str,
) -> DeliveryOutcome:
    """Decide the honest outcome of a run (see module docstring)."""
    if not did_work:
        return DeliveryOutcome(success=False, output=output)
    if auto_commit and changed_files and not pr_url:
        stage = "committed but never pushed / no PR opened" if commits else "never committed"
        return DeliveryOutcome(
            success=False,
            output=(
                f"Not delivered: {len(changed_files)} file(s) changed but the work was "
                f"{stage}, and the workspace is discarded after the run. "
                f"Agent report: {output[:500]}"
            ),
        )
    if str(judge_verdict).upper() == "REJECTED":
        return DeliveryOutcome(
            success=True, output=output, task_status="in_review",
            review_reason="The judge rejected this result — review before closing.",
        )
    if auto_commit and not changed_files and task_type in CODE_CHANGE_TASK_TYPES:
        return DeliveryOutcome(
            success=True, output=output, task_status="in_review",
            review_reason=(
                "The agent changed no files. Check whether the work is already done "
                "before closing; otherwise retry."
            ),
        )
    return DeliveryOutcome(success=True, output=output)
