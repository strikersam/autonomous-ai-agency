#!/usr/bin/env python3
"""scripts/verify_change.py — run a change's verification plan locally or in CI.

Builds the same ``VerificationContract`` the agent loop builds, runs the same
checks (agent/empirical_verify.py: byte-compile + the matching
``tests/test_<module>*.py``, re-run once on failure to expose flakiness), plus
a parse check for changed JSON/YAML files, and prints the machine-readable
evidence report produced by the same decision engine
(agent/verification_evidence.py).

There is no reviewer model here, so the report's verdict is never VERIFIED:
an independent review is a mandatory strategy and this harness does not supply
one. ``checks_ok`` says whether every *executable* check passed; the exit code
follows it:

    0  every mandatory check passed (the review is still owed)
    1  a check failed — the change is broken
    2  a check could not run, timed out, was flaky or is missing

Usage:
    python scripts/verify_change.py --files services/calc.py tests/test_calc.py
    python scripts/verify_change.py --base origin/master          # files changed since a ref
    python scripts/verify_change.py --from-report report.json     # reproduce an earlier run
    python scripts/verify_change.py --base origin/master --out report.json
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess  # nosec B404 - constant git argv, list form
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

log = logging.getLogger("qwen-proxy")


def _changed_since(root: Path, base: str) -> list[str]:
    out = subprocess.run(  # nosec B603 B607 - constant git argv, list form (no shell)
        ["git", "diff", "--name-only", "--diff-filter=ACMR", f"{base}...HEAD"],
        cwd=root, capture_output=True, text=True, check=True,
    ).stdout
    return [line.strip() for line in out.splitlines() if line.strip()]


def _parse_checks(root: Path, files: list[str]) -> list[dict[str, Any]]:
    """Static parse check for changed JSON and YAML files."""
    from agent.empirical_verify import CheckOutcome

    outcome = CheckOutcome()
    for name in files:
        if not name.endswith((".json", ".yaml", ".yml")):
            continue
        began = time.time()
        try:
            text = (root / name).read_text(encoding="utf-8")
            if name.endswith(".json"):
                json.loads(text)
            else:
                import yaml

                list(yaml.safe_load_all(text))
            outcome.record(f"static:parse:{name}", "static", "passed", files=[name], command="parse", started=began)
        except Exception as exc:  # noqa: BLE001 - OSError, JSON and YAML errors share no narrower base
            outcome.record(f"static:parse:{name}", "static", "failed", files=[name], command="parse",
                           output=str(exc), started=began)
    return outcome.results


def run_plan(root: Path, files: list[str], goal: str) -> dict[str, Any]:
    """Run the change's verification plan; return the report plus the harness summary."""
    from agent import empirical_verify as ev
    from agent.loop import _check_env
    from agent.models import AgentPlan, AgentStep
    from agent.verification_contract import build_contract
    from agent.verification_evidence import build_report, fingerprint_content

    existing = [f for f in files if (root / f).is_file()]
    plan = AgentPlan(goal=goal, steps=[AgentStep(id=1, description=goal[:200], files=existing, type="edit")])
    contract = build_contract(plan)
    py = [f for f in existing if f.endswith(".py")]
    results = ev.verify_on_host(root, py, _check_env()).results if py else []
    results += _parse_checks(root, existing)
    prints = {f: fingerprint_content((root / f).read_text(encoding="utf-8", errors="replace")) for f in existing}
    for r in results:
        r["fingerprints"] = {f: prints[f] for f in r.get("files") or [] if f in prints}
    failed = any(r["status"] == "failed" for r in results)
    step = {"step_id": 1, "description": goal[:200], "changed_files": existing,
            "status": "failed" if failed else "applied", "failure_phase": "empirical_verification",
            "check_results": results, "file_fingerprints": prints}
    head = subprocess.run(  # nosec B603 B607 - constant git argv
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True,
    ).stdout.strip() or None
    report = build_report(contract, steps=[step], judge={}, source_revision=head).model_dump()
    findings = [f for f in report["findings"] if f["kind"] != "verifier_infrastructure"]
    kinds = {f["kind"] for f in findings}
    exit_code = 1 if kinds & {"implementation_defect", "contract_violation"} else (2 if findings else 0)
    return {"checks_ok": exit_code == 0, "exit_code": exit_code, "files": existing,
            "contract": contract.model_dump(), "report": report}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--files", nargs="+", help="changed files, relative to the repo root")
    src.add_argument("--base", help="git ref: verify files changed since it")
    src.add_argument("--from-report", help="re-run the files recorded in an earlier report")
    parser.add_argument("--goal", default="Verify the change", help="what the change is meant to do")
    parser.add_argument("--root", default=str(ROOT), help="repository root")
    parser.add_argument("--out", help="write the JSON result here as well as to stdout")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if args.files:
        files = list(args.files)
    elif args.base:
        files = _changed_since(root, args.base)
    else:
        files = list(json.loads(Path(args.from_report).read_text(encoding="utf-8"))["report"]["changed_files"])
    result = run_plan(root, files, args.goal)
    text = json.dumps(result, indent=2, default=str)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    sys.stdout.write(text + "\n")
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
