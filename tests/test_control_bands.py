"""Control-band detection for the closed maintenance loop (scripts/control_bands.py)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import control_bands as cb

METRIC = cb.load_metric("ci_test_failure_rate")


def _series(baseline: list[float], recent: list[float]) -> list[tuple[str, float]]:
    values = baseline + recent
    return [(f"2026-09-{i + 1:02d}" if i < 30 else f"2026-10-{i - 29:02d}", v) for i, v in enumerate(values)]


QUIET = [0.10, 0.12, 0.08, 0.10, 0.11, 0.09, 0.10, 0.12, 0.08, 0.10] * 3  # mean 0.10, σ ≈ 0.013 → floor 0.02


@pytest.mark.parametrize("recent,tier,rule", [
    ([0.10] * 7 + [0.20], "3sigma", "one point beyond 3σ"),
    ([0.10] * 6 + [0.15, 0.15], "2sigma", "two of three beyond 2σ"),
    ([0.10] * 3 + [0.13, 0.13, 0.13, 0.13, 0.10], "2sigma", "four of five beyond 1σ"),
    ([0.11] * 8, "2sigma", "eight in a row above the mean"),
    ([0.10] * 7 + [0.125], "1sigma", "latest point beyond 1σ"),
    ([0.10, 0.09, 0.10, 0.11, 0.10, 0.09, 0.10, 0.10], "none", "within band"),
    ([0.0] * 8, "none", "within band"),
])
def test_western_electric_rules(recent, tier, rule):
    decision = cb.evaluate(_series(QUIET, recent), METRIC)
    assert (decision.tier, decision.rule) == (tier, rule)
    assert decision.action == {"3sigma": "propose", "2sigma": "diagnose", "1sigma": "log", "none": "none"}[tier]


def test_short_history_never_alerts():
    decision = cb.evaluate(_series([0.1] * 5, [0.9] * 8), METRIC)
    assert decision.tier == "none" and decision.rule.startswith("insufficient baseline")


def test_daily_failure_rates_ignore_cancelled_and_in_progress_runs():
    runs = [
        {"status": "completed", "conclusion": "success", "created_at": "2026-10-01T01:00:00Z"},
        {"status": "completed", "conclusion": "failure", "created_at": "2026-10-01T02:00:00Z"},
        {"status": "completed", "conclusion": "cancelled", "created_at": "2026-10-01T03:00:00Z"},
        {"status": "in_progress", "conclusion": None, "created_at": "2026-10-01T04:00:00Z"},
        {"status": "completed", "conclusion": "timed_out", "created_at": "2026-10-02T01:00:00Z"},
    ]
    assert cb.daily_failure_rates(runs) == [("2026-10-01", 0.5), ("2026-10-02", 1.0)]


def test_cli_writes_intent_only_on_a_breach(tmp_path: Path):
    def runs_for(rates: list[float]) -> list[dict]:
        out = []
        for i, rate in enumerate(rates):
            day = f"2026-{9 + i // 30:02d}-{i % 30 + 1:02d}T00:00:00Z"
            failed = round(rate * 10)
            out += [{"status": "completed", "conclusion": "failure" if j < failed else "success",
                     "created_at": day} for j in range(10)]
        return out

    for rates, breach in ((QUIET + [0.1] * 7 + [0.6], True), (QUIET + [0.1] * 8, False)):
        runs = tmp_path / "runs.json"
        runs.write_text(json.dumps(runs_for(rates)))
        intent = tmp_path / "intent.md"
        intent.unlink(missing_ok=True)
        cb.main(["--runs", str(runs), "--decision", str(tmp_path / "d.json"), "--intent", str(intent)])
        assert intent.exists() is breach
        if breach:
            body = intent.read_text()
            assert body.startswith("# Intent: ci_test_failure_rate is out of its control band")
            for section in ("## Problem", "## Proposed outcome", "## Affected users and systems",
                            "## Constraints", "## Open questions"):
                assert section in body


def test_bands_config_matches_the_workflow():
    workflow = (cb.REPO_ROOT / ".github" / "workflows" / "control-bands.yml").read_text()
    assert f"workflows/{METRIC['workflow']}/runs" in workflow
    assert f"branch={METRIC['branch']}" in workflow
