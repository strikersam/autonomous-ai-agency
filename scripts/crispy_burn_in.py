"""scripts/crispy_burn_in.py — Evaluate CRISPY burn-in criteria for promotion.

Roadmap item N4 follow-up: promotion of ``crispy_workflow`` from
EXPERIMENTAL → stable in ``features/matrix.py`` must be backed by *data*.
This script fetches the run-history metric from ``/api/autonomy/status``
and evaluates the burn-in criteria defined in
``docs/plans/next-pass-roadmap.md``.

Used by ``.github/workflows/crispy-burn-in-check.yml`` (weekly cron) to:
  - Open a "CRISPY ready for promotion" issue when all criteria are met, OR
  - Comment on an existing tracking issue with the current gap.

Exit codes:
  0  All burn-in criteria met (ready for promotion)
  1  One or more criteria not yet met (not ready — see stderr for the gap)
  2  Could not fetch /api/autonomy/status (backend down, misconfigured URL)

Usage::

    python scripts/crispy_burn_in.py --status-url https://your-app.onrender.com/api/autonomy/status
    python scripts/crispy_burn_in.py --json /tmp/status.json   # offline mode
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from typing import Any


# ── Burn-in criteria (mirrors docs/plans/next-pass-roadmap.md N4) ────────────
# These are the EXACT thresholds the roadmap documents. Changing them here
# requires updating the roadmap doc in the same PR — they're a contract.

MIN_TOTAL_RUNS = 20
MIN_SUCCESS_RATE = 0.80  # ≥80% of runs reach 'done'
MIN_WINDOW_DAYS = 7
# PhaseSequenceError is the canonical "phase ordering violated" failure.
# Zero of these over the burn-in window is the workspace-isolation guarantee.
FORBIDDEN_FAILURE_SUBSTRINGS = ("PhaseSequenceError",)


def evaluate_burn_in(history: dict[str, Any] | None) -> dict[str, Any]:
    """Evaluate the burn-in criteria against a ``crispy_run_history`` payload.

    Returns a dict with:
      - ``ready`` (bool): all criteria met
      - ``criteria`` (list[dict]): one entry per criterion with name, met, value, threshold
      - ``gap`` (str | None): human-readable summary of what's missing (None when ready)
    """
    if not history:
        # Treat None / empty dict / missing as "no data yet" — return criteria
        # with all-auto-checks failed so the operator sees the gap clearly.
        history = {}

    total_runs = history.get("total_runs", 0)
    success_rate = history.get("success_rate", 0.0)
    window_days = history.get("window_days")
    last_failure_reasons = history.get("last_failure_reasons", []) or []

    # Check for forbidden failure types in the recent failure reasons
    forbidden_hits = [
        r for r in last_failure_reasons
        if any(sub in r for sub in FORBIDDEN_FAILURE_SUBSTRINGS)
    ]

    criteria = [
        {
            "name": "total_runs",
            "met": total_runs >= MIN_TOTAL_RUNS,
            "value": total_runs,
            "threshold": f">= {MIN_TOTAL_RUNS}",
        },
        {
            "name": "success_rate",
            "met": success_rate >= MIN_SUCCESS_RATE,
            "value": success_rate,
            "threshold": f">= {MIN_SUCCESS_RATE}",
        },
        {
            "name": "window_days",
            "met": (window_days or 0) >= MIN_WINDOW_DAYS,
            "value": window_days,
            "threshold": f">= {MIN_WINDOW_DAYS}",
        },
        {
            "name": "no_phase_sequence_errors",
            "met": len(forbidden_hits) == 0,
            "value": len(forbidden_hits),
            "threshold": "0 PhaseSequenceError events in last_failure_reasons",
        },
        {
            "name": "risky_module_review_signoff",
            # This criterion is satisfied OFFLINE — by the promotion PR itself
            # carrying the risky-module-review sign-off comment. The burn-in
            # script can't check it directly; it's the human gate. We surface
            # it as 'pending' so the operator knows to obtain sign-off before
            # flipping the flag.
            "met": False,  # always pending — human gate
            "value": "pending",
            "threshold": "risky-module-review sign-off on the promotion PR",
        },
    ]

    # The 'ready' flag excludes the human-gate criterion (we can't auto-check it).
    # Promotion requires ALL auto-checkable criteria + the human gate.
    auto_criteria = [c for c in criteria if c["name"] != "risky_module_review_signoff"]
    all_auto_met = all(c["met"] for c in auto_criteria)

    if all_auto_met:
        gap = (
            "All auto-checkable burn-in criteria met. "
            "Final gate: obtain risky-module-review sign-off on the promotion PR "
            "(flip crispy_workflow from EXPERIMENTAL → stable in features/matrix.py, "
            "update loops/registry.yaml level/maturity)."
        )
    else:
        missing = [c["name"] for c in auto_criteria if not c["met"]]
        gap = (
            f"Not yet ready — missing: {', '.join(missing)}. "
            f"Current: total_runs={total_runs}/{MIN_TOTAL_RUNS}, "
            f"success_rate={success_rate:.2%}/{MIN_SUCCESS_RATE:.0%}, "
            f"window_days={window_days}/{MIN_WINDOW_DAYS}, "
            f"phase_sequence_errors={len(forbidden_hits)}."
        )

    return {
        "ready": all_auto_met,
        "criteria": criteria,
        "gap": gap,
    }


def fetch_status_json(url: str) -> dict[str, Any]:
    """Fetch /api/autonomy/status and return the parsed JSON."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status != 200:
                raise RuntimeError(f"HTTP {resp.status} from {url}")
            return json.loads(resp.read().decode())
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not fetch {url}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate CRISPY burn-in criteria (N4).")
    parser.add_argument(
        "--status-url",
        default=os.environ.get("AUTONOMY_STATUS_URL", ""),
        help="URL of /api/autonomy/status. Defaults to $AUTONOMY_STATUS_URL.",
    )
    parser.add_argument(
        "--json",
        type=argparse.FileType("r"),
        default=None,
        help="Offline mode: read the status JSON from a file instead of fetching.",
    )
    args = parser.parse_args()

    if args.json:
        status = json.load(args.json)
    else:
        if not args.status_url:
            print("ERROR: --status-url or --json required (set AUTONOMY_STATUS_URL env)", file=sys.stderr)
            return 2
        try:
            status = fetch_status_json(args.status_url)
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2

    history = status.get("crispy_run_history")
    result = evaluate_burn_in(history)

    # Print the evaluation as JSON to stdout (the workflow consumes this)
    print(json.dumps({
        "ready": result["ready"],
        "criteria": result["criteria"],
        "gap": result["gap"],
        "history": history,
    }, indent=2))

    return 0 if result["ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
