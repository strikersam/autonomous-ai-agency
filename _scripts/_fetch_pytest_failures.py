"""Pull the python-test failure log via gh run view --log and print the failing-test
summary block.

Writes the log to %TEMP%\\_last_failed_pytest_<dbId>.log so:
  - multiple failure runs coexist instead of clobbering each other
  - the file lands outside the repo tree (no spurious untracked entries)

Reviewer fixes folded in:
- Null/missing `createdAt` entries are KEPT (not silently dropped); they sort
  to the BOTTOM via a tuple key so we never lose data and never crash.
- `subprocess.run` on `gh run view` has `timeout=180` so a hung fetch can't
  freeze the caller.
- Log filename includes the `databaseId` so concurrent/consecutive runs
  don't clobber.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = "strikersam/autonomous-ai-agency"
BRANCH = "feat/colibri-brain-shim-test"
LOG_BASE = Path(os.environ.get("TEMP", "/tmp"))


def _gh_json(args):
    """Run a gh CLI call and parse its JSON stdout. Returns (parsed | None, stderr)."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(args, capture_output=True, env=env)
    try:
        return (
            json.loads(proc.stdout.decode("utf-8", errors="replace")),
            proc.stderr.decode("utf-8", errors="replace"),
        )
    except json.JSONDecodeError as exc:
        print(f"FAIL cannot parse gh JSON: {exc}", file=sys.stderr)
        print(
            "RAW OUTPUT (first 400):",
            proc.stdout[:400].decode("utf-8", errors="replace"),
            file=sys.stderr,
        )
        return None, proc.stderr.decode("utf-8", errors="replace")


def main() -> int:
    runs, err = _gh_json(
        [
            "gh", "run", "list",
            "--branch", BRANCH,
            "--limit", "15",
            "--json", "databaseId,name,conclusion,createdAt",
        ]
    )
    if runs is None:
        print(f"FAIL gh run list (unparseable JSON / auth missing): {err}", file=sys.stderr)
        return 2
    if not runs:
        print(
            "FAIL gh returned zero runs (gh auth missing? branch has no runs?)",
            file=sys.stderr,
        )
        return 3

    failures = [
        r
        for r in runs
        if r.get("conclusion") == "failure"
        and r.get("name") != "post-merge-telegram-notify"
    ]
    pytest_like = [
        r
        for r in failures
        if any(
            k in (r.get("name") or "").lower()
            for k in ("ci", "python", "pytest", "regression")
        )
        and "playwright" not in (r.get("name") or "").lower()
    ]
    # Reviewer fix: keep null-`createdAt` entries; sort them LAST (DESC) via a
    # tuple key. `not X` is True (= 1) for null/empty, False (= 0) for real
    # timestamps. In ASC, real entries (0) come before null (1). With
    # reverse=True, real entries come first, nulls fall to the bottom — no
    # crash, no silent drop.
    pytest_like.sort(
        key=lambda r: (not r.get("createdAt"), r.get("createdAt") or ""),
        reverse=True,
    )
    null_dropped = sum(1 for r in pytest_like if not r.get("createdAt"))
    print(
        f"TOTAL runs: {len(runs)} | FAILURES: {len(failures)} "
        f"| PYTEST-LIKE: {len(pytest_like)} (null-createdAt: {null_dropped})"
    )
    target = pytest_like[0] if pytest_like else (failures[0] if failures else None)
    if target is None:
        print("OK all recent runs green; nothing to diagnose")
        return 0
    print(f"SELECTED target.name={target.get('name')!r} dbId={target['databaseId']}")

    proc = subprocess.run(
        ["gh", "run", "view", str(target["databaseId"]), "--log"],
        capture_output=True,
        timeout=180,  # prevent hung fetch from freezing caller (reviewer fix)
    )
    body = proc.stdout.decode("utf-8", errors="replace")

    # Per-run log filename so multiple failures don't clobber each other.
    log_path = LOG_BASE / f"_last_failed_pytest_{target['databaseId']}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(body, encoding="utf-8")
    print(f"OK wrote {len(body)} chars to {log_path}")

    lines = body.split("\n")
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if (
            stripped.startswith("FAILED ")
            or "= FAILURES =" in line
            or " short test summary info" in line
            or ((" failed, " in line) and (" passed" in line))
        ):
            lo = max(0, i - 30)
            hi = min(len(lines), i + 30)
            print(f"--- failure context (lines {lo + 1}..{hi}) ---")
            for j in range(lo, hi):
                marker = ">>" if j == i else "  "
                print(f"{marker} {j + 1:5d} {lines[j]}")
            return 0
    print("--- no FAILED markers in log; tail (last 100 lines) ---")
    for ln in lines[-100:]:
        print(ln)
    return 0


if __name__ == "__main__":
    sys.exit(main())
