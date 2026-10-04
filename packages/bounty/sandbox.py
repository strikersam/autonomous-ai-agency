"""packages/bounty/sandbox.py — run a stranger's test suite without trusting it.

Tests from a third-party repository are arbitrary code. They run in a
throwaway Docker container with no environment variables from the runner, no
network during the test phase, and CPU/memory/pid limits. Dependency install
needs the network, so it is a separate container that still sees no secrets.
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("qwen-proxy")

_LIMITS = ("--memory", "2g", "--cpus", "2", "--pids-limit", "512", "--security-opt", "no-new-privileges")


@dataclass(frozen=True)
class TestPlan:
    """Image plus install and test commands for one project type."""

    kind: str
    image: str
    install: str
    test: str


PYTHON = TestPlan(
    "python", "python:3.12-slim",
    "python -m venv /w/.bounty-venv && /w/.bounty-venv/bin/pip install -q pytest && "
    "(/w/.bounty-venv/bin/pip install -q -e '.[test]' || /w/.bounty-venv/bin/pip install -q -e . || "
    "/w/.bounty-venv/bin/pip install -q -r requirements.txt || true)",
    "/w/.bounty-venv/bin/python -m pytest -x -q --no-header -p no:cacheprovider",
)
NODE = TestPlan(
    "node", "node:20-slim",
    "npm ci --ignore-scripts --no-audit --no-fund || npm install --ignore-scripts --no-audit --no-fund",
    "npm test --silent",
)


@dataclass
class TestOutcome:
    """Result of one sandboxed test run."""

    status: str  # passed | failed | unverified
    log: str = ""


def _user_args() -> list[str]:
    # Run as the runner's uid so files the container creates stay editable by git.
    getuid = getattr(os, "getuid", None)
    getgid = getattr(os, "getgid", None)
    user = ["--user", f"{getuid()}:{getgid()}"] if getuid and getgid else []
    return [*user, "-e", "HOME=/tmp"]


def plan_for(workdir: Path) -> TestPlan | None:
    """Pick a test plan from the files at the repository root."""
    if any((workdir / f).exists() for f in ("pyproject.toml", "setup.py", "setup.cfg")):
        return PYTHON
    if (workdir / "package.json").exists():
        return NODE
    return None


async def _docker(args: list[str], timeout: float) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        "docker", *args, env={"PATH": "/usr/bin:/bin:/usr/local/bin"},
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 124, "timed out"
    return proc.returncode or 0, out.decode("utf-8", errors="replace")


def docker_available() -> bool:
    """True when a docker CLI is on PATH."""
    return shutil.which("docker") is not None


async def install(workdir: Path, plan: TestPlan, timeout: float = 600.0) -> tuple[int, str]:
    """Install dependencies (network on, no secrets)."""
    return await _docker(["run", "--rm", *_LIMITS, *_user_args(), "-v", f"{workdir}:/w", "-w", "/w",
                          plan.image, "sh", "-c", plan.install], timeout)


async def run_tests(workdir: Path, plan: TestPlan, timeout: float = 600.0) -> TestOutcome:
    """Run the test command with the network disabled."""
    code, out = await _docker(["run", "--rm", "--network", "none", *_LIMITS,
                               *_user_args(), "-v", f"{workdir}:/w",
                               "-w", "/w", plan.image, "sh", "-c", plan.test], timeout)
    return TestOutcome("passed" if code == 0 else "failed", out[-6000:])
