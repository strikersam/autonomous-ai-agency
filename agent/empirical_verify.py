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
import shlex
import subprocess  # nosec B404 - list-form argv only, no shell
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
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
    # One structured record per check (agent/verification_evidence.CheckResult):
    # passed, failed, not_run, unavailable, timed_out or untrusted — never collapsed.
    results: list[dict[str, Any]] = field(default_factory=list)

    def record(self, check_id: str, strategy: str, status: str, *, files: list[str],
               command: str = "", exit_code: int | None = None, output: str = "",
               reason: str = "", started: float | None = None, attempts: int = 1) -> None:
        """Append a structured check result (redacted on construction)."""
        from agent.verification_evidence import CheckResult

        began = started if started is not None else time.time()
        self.results.append(CheckResult(
            check_id=check_id, strategy=strategy, status=status, command=command,
            exit_code=exit_code, files=list(files), output_tail=output, reason=reason,
            started_at=began, duration_s=round(max(0.0, time.time() - began), 3), attempts=attempts,
        ).model_dump())


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


# Everything changed since the sandbox was seeded (its root commit), including
# commits made inside the sandbox and new files the agent created.
_SANDBOX_DIFF_CMD = (
    "base=$(git rev-list --max-parents=0 HEAD 2>/dev/null | tail -n 1); "
    "git diff --stat --patch ${base:-HEAD}; "
    "git ls-files -z --others --exclude-standard | "
    "xargs -0 -r -n 1 git diff --no-index -- /dev/null; true"
)


async def sandbox_diff(session: Any, max_chars: int = 12000) -> str:
    """The diff of the agent's edits inside the E2B sandbox, for the judge.

    The edits live in the sandbox, not on the host, so a host ``git diff``
    sees nothing; without this the judge saw "Diff: (unavailable)" and
    rejected every sandbox run. Returns "" when the diff cannot be read.
    """
    try:
        raw = await session.call_tool("run_command", {"cmd": _SANDBOX_DIFF_CMD, "timeout": 60})
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
    began = time.time()
    code, out = await _sh(session, f"python3 -m py_compile {quoted}", limit)
    if code != 0:
        result.issues.append(f"Changed files fail to byte-compile (in the sandbox):\n{out}")
        result.record("static:py_compile", "static", "failed", files=py_files, command="py_compile (E2B)",
                      exit_code=code, output=out, started=began)
        return result
    result.record("static:py_compile", "static", "passed", files=py_files, command="py_compile (E2B)",
                  exit_code=0, started=began)
    targets = await _sandbox_targets(session, py_files)
    if not targets:
        result.record("unit:pytest", "unit", "not_run", files=py_files,
                      reason="no tests/test_<module>*.py matches the changed files")
        return result
    note = await ensure_dependencies(session)
    if note:
        result.notes.append(note)
    await _sh(session, "python3 -m pytest --version >/dev/null 2>&1 || python3 -m pip install -q pytest", 180)
    joined = " ".join(shlex.quote(t) for t in targets)
    cmd = f"TESTING=true python3 -m pytest -x -q {joined}"
    began = time.time()
    code, out = await _sh(session, cmd, limit)
    if code != 0 and not tests_not_runnable(code, out):
        # Confirm a failure once on identical code: pass-after-fail is flakiness,
        # which is neither proof nor a defect in the change.
        code2, out2 = await _sh(session, cmd, limit)
        if code2 == 0:
            _record_flaky(result, py_files, targets, f"pytest -x {' '.join(targets)} (E2B sandbox)", out, began)
            return result
    _record_pytest(result, code, out, py_files, targets, f"pytest -x {' '.join(targets)} (E2B sandbox)", began, sandbox=True)
    return result


def _record_flaky(result: CheckOutcome, files: list[str], targets: list[str], command: str,
                  out: str, began: float) -> None:
    result.issues.append(
        "Scoped tests are flaky: they failed, then passed on an identical re-run. "
        f"Neither run is evidence; stabilise the test.\n{out}"
    )
    result.record("unit:pytest", "unit", "untrusted", files=files + targets, command=command, exit_code=None,
                  output=out, reason="flaky: failed then passed on identical code", started=began, attempts=2)


def _record_pytest(result: CheckOutcome, code: int, out: str, files: list[str], targets: list[str],
                   command: str, began: float, *, sandbox: bool) -> None:
    where = " (in the sandbox)" if sandbox else ""
    kind = "sandbox tests" if sandbox else "tests"
    covered = files + targets
    if code == 0:
        result.checks.append(f"{command}: passed")
        result.record("unit:pytest", "unit", "passed", files=covered, command=command, exit_code=0,
                      output=out, started=began)
        log.info("empirical verify: %s passed (%s)", kind, " ".join(targets))
    elif tests_not_runnable(code, out):
        result.notes.append(
            f"Tests could not run{where} (exit {code}); the environment may lack "
            "the project's dependencies. Not counted as evidence."
        )
        if not sandbox:
            result.issues.append(f"Scoped tests failed for this change:\n{out}")
        result.record("unit:pytest", "unit", "unavailable", files=covered, command=command, exit_code=code,
                      output=out, reason="tests could not run (collection or import error)", started=began)
        log.info("empirical verify: %s not runnable (exit %s)", kind, code)
    else:
        result.issues.append(f"Scoped tests failed for this change{where}:\n{out}")
        result.record("unit:pytest", "unit", "failed", files=covered, command=command, exit_code=code,
                      output=out, started=began)
        log.info("empirical verify: %s failed (exit %s, %s)", kind, code, " ".join(targets))


def _host_targets(root: Path, py_files: list[str]) -> list[str]:
    targets: list[str] = []
    for f in py_files:
        if Path(f).name.startswith("test_"):
            targets.append(f)
        else:
            targets.extend(str(p.relative_to(root)) for p in root.glob(f"tests/test_{Path(f).stem}*.py"))
    return list(dict.fromkeys(targets))


def verify_on_host(root: Path, py_files: list[str], env: dict[str, str]) -> CheckOutcome:
    """Byte-compile and run the scoped tests in the host workspace (blocking; run in a thread)."""
    result = CheckOutcome()
    limit = timeout_s()

    def run(argv: list[str]) -> tuple[int, str]:
        proc = subprocess.run(  # nosec B603 - fixed interpreter argv, list form (no shell)
            argv, cwd=root, capture_output=True, text=True, timeout=limit, env=env,
        )
        return proc.returncode, (proc.stdout + proc.stderr)[-4000:]

    began = time.time()
    stage = "static"
    try:
        code, out = run([sys.executable, "-m", "py_compile", *py_files])
        if code != 0:
            result.issues.append(f"Changed files fail to byte-compile:\n{out}")
            result.record("static:py_compile", "static", "failed", files=py_files, command="py_compile",
                          exit_code=code, output=out, started=began)
            return result
        result.record("static:py_compile", "static", "passed", files=py_files, command="py_compile",
                      exit_code=0, started=began)
        targets = _host_targets(root, py_files)
        if not targets:
            result.record("unit:pytest", "unit", "not_run", files=py_files,
                          reason="no tests/test_<module>*.py matches the changed files")
            return result
        stage, began = "unit", time.time()
        argv = [sys.executable, "-m", "pytest", "-x", "-q", *targets]
        code, out = run(argv)
        if code != 0 and not tests_not_runnable(code, out):
            code2, _ = run(argv)
            if code2 == 0:
                _record_flaky(result, py_files, targets, f"pytest -x {' '.join(targets)}", out, began)
                return result
        _record_pytest(result, code, out, py_files, targets, f"pytest -x {' '.join(targets)}", began, sandbox=False)
    except subprocess.TimeoutExpired:
        result.issues.append(f"Empirical verification timed out after {limit}s.")
        result.record(f"{stage}:{'py_compile' if stage == 'static' else 'pytest'}", stage, "timed_out",
                      files=py_files, reason=f"timed out after {limit}s", started=began)
    except OSError as exc:
        log.debug("Empirical verification unavailable: %s", exc)
        result.record(f"{stage}:{'py_compile' if stage == 'static' else 'pytest'}", stage, "unavailable",
                      files=py_files, reason=f"could not start the check: {type(exc).__name__}", started=began)
    return result
