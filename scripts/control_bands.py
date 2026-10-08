"""Control-band detection for the closed maintenance loop (loops/bands.yaml).

Reads GitHub Actions runs (the JSON `gh api …/actions/workflows/<file>/runs`
returns), turns them into a per-day failure rate, and checks the most recent
days against a rolling baseline with Western Electric rules. Detection is
deterministic; a breach is written as an intent.md body the workflow files as
an issue, so the finding re-enters the pipeline like any other request.

    python scripts/control_bands.py --runs runs.json --metric ci_test_failure_rate \\
        --decision decision.json --intent intent.md
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

log = logging.getLogger("qwen-proxy")

REPO_ROOT = Path(__file__).resolve().parent.parent
BANDS_FILE = REPO_ROOT / "loops" / "bands.yaml"
_TIER_ORDER = {"none": 0, "1sigma": 1, "2sigma": 2, "3sigma": 3}


@dataclass
class Decision:
    """What the detector found, and the action its tier maps to."""

    metric: str
    tier: str
    rule: str
    action: str
    mean: float
    std: float
    recent: list[tuple[str, float]]


def load_metric(metric_id: str, path: Path = BANDS_FILE) -> dict:
    """The metric's config block from loops/bands.yaml."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    for metric in data["metrics"]:
        if metric["id"] == metric_id:
            return metric
    raise KeyError(f"metric {metric_id!r} not in {path}")


def daily_failure_rates(runs: list[dict]) -> list[tuple[str, float]]:
    """Per-day share of completed runs that failed, oldest first. Cancelled/skipped runs are ignored."""
    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for run in runs:
        conclusion = run.get("conclusion")
        if run.get("status") != "completed" or conclusion not in ("success", "failure", "timed_out"):
            continue
        day = str(run.get("created_at", ""))[:10]
        counts[day][1] += 1
        if conclusion != "success":
            counts[day][0] += 1
    return [(day, failed / total) for day, (failed, total) in sorted(counts.items()) if total]


def _beyond(values: list[float], limit: float) -> int:
    return sum(v > limit for v in values)


def classify(values: list[float], mean: float, std: float) -> tuple[str, str]:
    """Highest tier any Western Electric rule (upper side) assigns to the recent points."""
    if values and values[-1] > mean + 3 * std:
        return "3sigma", "one point beyond 3σ"
    if _beyond(values[-3:], mean + 2 * std) >= 2:
        return "2sigma", "two of three beyond 2σ"
    if _beyond(values[-5:], mean + std) >= 4:
        return "2sigma", "four of five beyond 1σ"
    if len(values) >= 8 and _beyond(values[-8:], mean) == 8:
        return "2sigma", "eight in a row above the mean"
    if values and values[-1] > mean + std:
        return "1sigma", "latest point beyond 1σ"
    return "none", "within band"


def evaluate(series: list[tuple[str, float]], metric: dict) -> Decision:
    """Split the series into baseline and recent points and classify the recent ones."""
    recent_n = int(metric["recent_days"])
    baseline = [v for _, v in series[:-recent_n]][-int(metric["baseline_days"]):]
    recent = series[-recent_n:]
    if len(baseline) < int(metric["min_baseline_points"]):
        return Decision(metric["id"], "none", f"insufficient baseline ({len(baseline)} days)",
                        "log", 0.0, 0.0, recent)
    mean = statistics.fmean(baseline)
    std = max(statistics.pstdev(baseline), float(metric["sigma_floor"]))
    tier, rule = classify([v for _, v in recent], mean, std)
    action = metric["tiers"].get(tier, {}).get("action", "log") if tier != "none" else "none"
    return Decision(metric["id"], tier, rule, action, round(mean, 4), round(std, 4), recent)


def render_intent(decision: Decision, metric: dict) -> str:
    """The breach as an intent.md (Stage 1 format) for the triage queue."""
    rows = "\n".join(f"| {day} | {rate:.0%} |" for day, rate in decision.recent)
    return f"""# Intent: {metric['id']} is out of its control band

Author: control-bands loop (scripts/control_bands.py). Status: draft — triage, then accept or close.

## Problem
{metric['description']} breached its band: **{decision.rule}** (tier {decision.tier}).
Baseline over the previous {metric['baseline_days']} days: mean {decision.mean:.1%}, σ {decision.std:.1%}.

| Day (UTC) | Failure rate |
|-----------|--------------|
{rows}

## Proposed outcome
Find what changed in this window (failing jobs, the commits that introduced them) and bring the
rate back inside the band with a fix PR or a revert — never by skipping or weakening tests.

## Affected users and systems
`{metric['workflow']}` on `{metric['branch']}`; every PR waiting on it.

## Constraints
Changes go through the normal PR review gate. Detection is deterministic; this issue was opened
without a model.

## Open questions
Is one job responsible, or is the rise spread across the suite? Is it environmental
(runner, network, a provider) or in the code?
"""


def main(argv: list[str] | None = None) -> int:
    """CLI: write decision JSON (always) and the intent body (only when the tier asks for an issue)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--metric", default="ci_test_failure_rate")
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--intent", type=Path, required=True)
    args = parser.parse_args(argv)

    metric = load_metric(args.metric)
    raw = json.loads(args.runs.read_text(encoding="utf-8"))
    runs = raw.get("workflow_runs", raw) if isinstance(raw, dict) else raw
    decision = evaluate(daily_failure_rates(runs), metric)
    args.decision.write_text(json.dumps(asdict(decision), indent=2), encoding="utf-8")
    if _TIER_ORDER[decision.tier] >= _TIER_ORDER["2sigma"]:
        args.intent.write_text(render_intent(decision, metric), encoding="utf-8")
    log.info("control band %s: tier=%s rule=%s", decision.metric, decision.tier, decision.rule)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
