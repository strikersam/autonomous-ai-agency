"""agent/empirical_verify.py — run the checks on the copy of the code that changed.

The step verifier reads a diff; this module executes it: byte-compile the
changed Python files, then run their matching ``tests/test_<module>*.py``.
A passing pytest run is recorded as an executed check, which is what lets a
judge's approval count as an independent PASS (rule 49, tasks/verification.py).

Where the checks run matters. When an E2B sandbox is attached the agent's edits
live in the sandbox, not on the host, so the checks run there through the
session's ``run_command``. Otherwise they run on the host workspace in a worker
thread, so a slow test suite never blocks the event loop.

Gated by the live ``AGENT_EMPIRICAL_VERIFY`` control (default on).
"""

from __future__ import annotations

import json
import logging
import re
import shlex
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("qwen-proxy")

# pytest exit codes: 2 interrupted (usually a collection error), 4 usage error,
# 5 no tests collected. None of these means "the change is broken"; they mean
# the tests could not run here (often a missing dependency in the sandbox).
_NOT_RUN_CODES = frozenset({2, 4, 5})
_IMPORT_ERRORS = ("ModuleNotFoundError", "ImportError while importing")
# One-time requirements install per sandbox; large projects take minutes.
_INSTALL_TIMEOUT_S = 300


@dataclass
class CheckOutcome:
    """Issues block the step; checks are the passing runs; notes explain gaps."""

    issues: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def enabled() -> bool:
    """Read the live ``AGENT_EMPIRICAL_VERIFY`` control."""
    from packages.config import settings

    return bool(getattr(settings, "agent_empirical_verify", True))


def timeout_s() -> int:
    """Read the live ``AGENT_EMPIRICAL_VERIFY_TIMEOUT`` control."""
    from packages.config import settings

    return max(10, int(getattr(settings, "agent_empirical_verify_timeout", 120) or 120))


def tests_not_runnable(code: int, output: str) -> bool:
    """True when pytest could not run the tests, as opposed to tests failing."""
    if code in _NOT_RUN_CODES:
        return True
    return code != 0 and any(marker in output for marker in _IMPORT_ERRORS) and " passed" not in output


def is_sandbox(session: Any) -> bool:
    """True when *session* is an attached E2B sandbox."""
    return session is not None and type(session).__name__ == "E2BSandboxSession"


async def _sh(session: Any, cmd: str, timeout: int) -> tuple[int, str]:
    raw = await session.call_tool("run_command", {"cmd": cmd, "timeout": timeout})
    data = json.loads(raw)
    out = (data.get("stdout") or "") + (data.get("stderr") or "")
    return int(data.get("exit_code") or 0), out[-4000:]


async def _sandbox_targets(session: Any, py_files: list[str]) -> list[str]:
    targets = [f for f in py_files if f.rsplit("/", 1)[-1].startswith("test_")]
    stems = [f.rsplit("/", 1)[-1][:-3] for f in py_files if f not in targets]
    if stems:
        globs = " ".join(f"tests/test_{shlex.quote(s)}*.py" for s in stems)
        _, out = await _sh(session, f"ls -1 {globs} 2>/dev/null; true", 30)
        targets += [line.strip() for line in out.splitlines() if line.strip().endswith(".py")]
    return list(dict.fromkeys(targets))


def install_deps_enabled() -> bool:
    """Read the live ``AGENT_SANDBOX_INSTALL_DEPS`` control."""
    from packages.config import settings

    return bool(getattr(settings, "agent_sandbox_install_deps", True))


async def ensure_dependencies(session: Any) -> str | None:
    """Install the project's Python requirements in the sandbox, once per session.

    The base E2B image has no project packages, so every scoped test run failed
    at import ("tests not runnable") and no change could be verified. Installs
    ``requirements.txt`` (falling back to ``backend/requirements.txt``) on the
    first test run of a sandbox and remembers the outcome on the session, so
    later steps pay nothing. Returns a note when the install failed.
    """
    if not install_deps_enabled():
        return None
    done = getattr(session, "_deps_install_result", None)
    if done is not None:
        return done or None
    pick = "f=requirements.txt; [ -f $f ] || f=backend/requirements.txt; [ -f $f ] || exit 3; "
    cmd = pick + "python3 -m pip install -q --disable-pip-version-check --prefer-binary -r $f"
    try:
        code, out = await _sh(session, cmd, _INSTALL_TIMEOUT_S)
    except Exception as exc:  # noqa: BLE001 - timeout or dead sandbox: note it, never retry
        code, out = -1, str(exc)
    if code in (0, 3):
        note = ""
    else:
        note = f"Installing the project's requirements in the sandbox failed (exit {code}): {out[-600:]}"
        log.info("empirical verify: sandbox dependency install failed (exit %s)", code)
    try:
        session._deps_install_result = note
    except AttributeError:  # pragma: no cover - slotted session objects
        pass
    return note or None


# Everything changed since the sandbox was seeded, including commits made
# inside the sandbox and new files the agent created. The base is the commit
# recorded at seed time; never the root commit, which on a shallow clone is an
# arbitrary old commit and showed the judge weeks of unrelated history.
_UNTRACKED_DIFF = (
    "git ls-files -z --others --exclude-standard | "
    "xargs -0 -r -n 1 git diff --no-index -- /dev/null; true"
)


def _sandbox_diff_cmd(session: Any) -> str:
    base = getattr(session, "_base_sha", None)
    base = base if isinstance(base, str) and re.fullmatch(r"[0-9a-f]{40}", base) else "HEAD"
    return f"git diff --stat --patch {base}; {_UNTRACKED_DIFF}"


async def sandbox_diff(session: Any, max_chars: int = 12000) -> str:
    """The diff of the agent's edits inside the E2B sandbox, for the judge.

    The edits live in the sandbox, not on the host, so a host ``git diff``
    sees nothing; without this the judge saw "Diff: (unavailable)" and
    rejected every sandbox run. Returns "" when the diff cannot be read.
    """
    try:
        raw = await session.call_tool("run_command", {"cmd": _sandbox_diff_cmd(session), "timeout": 60})
        out = json.loads(raw).get("stdout") or ""
    except Exception as exc:  # noqa: BLE001 - no diff is a gap, not a crash
        log.warning("empirical verify: could not read the sandbox diff: %s", exc)
        return ""
    return out if len(out) <= max_chars else out[:max_chars] + f"\n… diff truncated ({len(out)} chars total)"


async def verify_in_sandbox(session: Any, py_files: list[str]) -> CheckOutcome:
    """Byte-compile and run the scoped tests inside the E2B sandbox."""
    result = CheckOutcome()
    limit = timeout_s()
    quoted = " ".join(shlex.quote(f) for f in py_files)
    code, out = await _sh(session, f"python3 -m py_compile {quoted}", limit)
    if code != 0:
        result.issues.append(f"Changed files fail to byte-compile (in the sandbox):\n{out}")
        return result
    targets = await _sandbox_targets(session, py_files)
    if not targets:
        return result
    note = await ensure_dependencies(session)
    if note:
        result.notes.append(note)
    await _sh(session, "python3 -m pytest --version >/dev/null 2>&1 || python3 -m pip install -q pytest", 180)
    joined = " ".join(shlex.quote(t) for t in targets)
    code, out = await _sh(session, f"TESTING=true python3 -m pytest -x -q {joined}", limit)
    if code == 0:
        result.checks.append(f"pytest -x {' '.join(targets)} (E2B sandbox): passed")
        log.info("empirical verify: sandbox tests passed (%s)", " ".join(targets))
    elif tests_not_runnable(code, out):
        result.notes.append(
            f"Tests could not run in the sandbox (exit {code}); the sandbox template may lack "
            "the project's dependencies. Not counted as evidence."
        )
        log.info("empirical verify: sandbox tests not runnable (exit %s)", code)
    else:
        result.issues.append(f"Scoped tests failed for this change (in the sandbox):\n{out}")
        log.info("empirical verify: sandbox tests failed (exit %s, %s)", code, " ".join(targets))
    return result
