"""Checks an agent's changes must pass before it may open a pull request.

The first agent PRs to reach GitHub (2026-10-04, #1656–#1660) were all red or
empty: a test importing a module that was never written, three root-level
``async_queue.py`` files with no tests, no changelog entry. CI caught them only
after a PR existed. This gate runs the same basic checks in the agent's own
clone first, and its findings go back into the task so the next attempt can
fix them.
"""

from __future__ import annotations

import logging
import subprocess  # nosec B404 - fixed argv, list form, no shell
import sys
from pathlib import Path

log = logging.getLogger("qwen-proxy")

_TEST_TIMEOUT_S = 300
_CHANGELOGS = ("CHANGELOG.md", "docs/changelog.md")
_PARITY_SCRIPT = "scripts/check_changelog_parity.py"


def _is_test(path: str) -> bool:
    name = Path(path).name
    return name.startswith("test_") or "/tests/" in f"/{path}"


def _run(argv: list[str], root: Path) -> tuple[int, str]:
    try:
        proc = subprocess.run(  # nosec B603 - fixed interpreter argv, list form
            argv, cwd=root, capture_output=True, text=True, timeout=_TEST_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return 1, f"timed out after {_TEST_TIMEOUT_S}s"
    return proc.returncode, (proc.stdout + proc.stderr)[-2000:]


def pr_blockers(root: str | Path, changed_files: list[str]) -> list[str]:
    """Reasons the change is not ready for a PR; empty when it may open one."""
    root = Path(root)
    changed = sorted({f.replace("\\", "/") for f in changed_files})
    py = [f for f in changed if f.endswith(".py") and (root / f).exists()]
    source = [f for f in py if not _is_test(f)]
    tests = [f for f in py if _is_test(f)]
    blockers: list[str] = []

    if py:
        rc, out = _run([sys.executable, "-m", "py_compile", *py], root)
        if rc != 0:
            return [f"Changed files do not compile:\n{out}"]
    if source and not tests:
        blockers.append(
            "Code changed without tests: add or update tests/test_<module>.py "
            f"covering {', '.join(source[:5])}."
        )
    if tests:
        rc, out = _run([sys.executable, "-m", "pytest", "-x", "-q", *tests], root)
        if rc != 0:
            blockers.append(f"Tests fail:\n{out}")
    if source:
        missing = [c for c in _CHANGELOGS if c not in changed]
        if missing:
            blockers.append(
                "Behaviour change without a changelog entry: add the same entry under "
                f"'## [Unreleased]' in {' and '.join(_CHANGELOGS)} (missing: {', '.join(missing)})."
            )
        elif (root / _PARITY_SCRIPT).exists():
            rc, out = _run([sys.executable, _PARITY_SCRIPT], root)
            if rc != 0:
                blockers.append(f"Changelog files differ (they must be byte-identical):\n{out}")
    if blockers:
        log.info("pr_gate: %d blocker(s) for %d changed file(s)", len(blockers), len(changed))
    return blockers
