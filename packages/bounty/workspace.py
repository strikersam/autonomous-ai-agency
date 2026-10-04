"""packages/bounty/workspace.py — clone, inspect, guard and push a bounty patch.

The clone is made without credentials so the token never sits in the
workspace the solver can read. The token is supplied only to ``git push``,
through ``GIT_CONFIG_*`` environment variables rather than argv or the remote
URL, and the diff is scanned for it before anything leaves the runner.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("qwen-proxy")

SANDBOX_EXCLUDES = (".bounty-venv/", "node_modules/", "__pycache__/", ".pytest_cache/", "*.egg-info/")
_FORBIDDEN_PREFIXES = (".github/", ".gitlab-ci", ".circleci/", ".git/")
_SECRET_RE = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|gh[ousr]_[A-Za-z0-9]{20,}|"
    r"sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|nvapi-[A-Za-z0-9_-]{20,}|gsk_[A-Za-z0-9]{20,})"
)


@dataclass
class GitResult:
    """Exit code and combined output of one git call."""

    code: int
    out: str


async def git(workdir: Path, *args: str, env: dict[str, str] | None = None,
              timeout: float = 300.0) -> GitResult:
    """Run ``git <args>`` in *workdir* (list form, no shell)."""
    base_env = {k: v for k, v in os.environ.items()
                if k in {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR"}}
    base_env["GIT_TERMINAL_PROMPT"] = "0"
    proc = await asyncio.create_subprocess_exec(
        "git", *args, cwd=str(workdir), env={**base_env, **(env or {})},
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return GitResult(124, "git timed out")
    return GitResult(proc.returncode or 0, out.decode("utf-8", errors="replace"))


async def clone(repo: str, dest: Path) -> str:
    """Shallow-clone public *repo* into *dest*; return the default branch name."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = await git(dest.parent, "clone", "--depth", "50", "--no-tags",
                       f"https://github.com/{repo}.git", dest.name)
    if result.code != 0:
        raise RuntimeError(f"clone of {repo} failed: {result.out[-300:]}")
    exclude = dest / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    with exclude.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(SANDBOX_EXCLUDES) + "\n")
    head = await git(dest, "rev-parse", "--abbrev-ref", "HEAD")
    return head.out.strip() or "main"


@dataclass
class PatchReport:
    """What the solver changed, and whether it is allowed out."""

    diff: str = ""
    files: list[str] = field(default_factory=list)
    added: int = 0
    deleted: int = 0
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when the patch passed every guard."""
        return not self.problems


async def inspect_patch(workdir: Path, max_lines: int, token: str = "") -> PatchReport:
    """Stage everything and check the patch against the guards."""
    await git(workdir, "add", "-A")
    report = PatchReport(diff=(await git(workdir, "diff", "--cached")).out)
    status = (await git(workdir, "diff", "--cached", "--name-status")).out
    for line in status.splitlines():
        code, _, path = line.partition("\t")
        report.files.append(path)
        if code.startswith("D"):
            report.problems.append(f"deletes {path}")
        if path.startswith(_FORBIDDEN_PREFIXES):
            report.problems.append(f"touches protected path {path}")
    for line in (await git(workdir, "diff", "--cached", "--numstat")).out.splitlines():
        added, deleted, path = (line.split("\t") + ["", "", ""])[:3]
        if added == "-":
            report.problems.append(f"binary change to {path}")
            continue
        report.added += int(added or 0)
        report.deleted += int(deleted or 0)
    if not report.files:
        report.problems.append("empty patch")
    if report.added + report.deleted > max_lines:
        report.problems.append(f"patch is {report.added + report.deleted} lines (limit {max_lines})")
    if (token and token in report.diff) or _SECRET_RE.search(report.diff):
        report.problems.append("patch contains a credential-shaped string")
    return report


def _auth_env(token: str) -> dict[str, str]:
    basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    return {
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
        "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {basic}",
    }


async def commit_and_push(workdir: Path, *, branch: str, fork: str, message: str,
                          login: str, token: str) -> None:
    """Commit the staged patch as *login* and push it to *branch* on *fork*."""
    ident = ["-c", f"user.name={login}", "-c", f"user.email={login}@users.noreply.github.com"]
    steps = [
        ("checkout", ("checkout", "-B", branch)),
        ("commit", (*ident, "commit", "-m", message)),
    ]
    for name, args in steps:
        result = await git(workdir, *args)
        if result.code != 0:
            raise RuntimeError(f"git {name} failed: {result.out[-300:]}")
    pushed = await git(workdir, "push", "--force", f"https://github.com/{fork}.git",
                       f"HEAD:refs/heads/{branch}", env=_auth_env(token))
    if pushed.code != 0:
        raise RuntimeError("push to fork failed: " + pushed.out[-300:].replace(token, "***"))
