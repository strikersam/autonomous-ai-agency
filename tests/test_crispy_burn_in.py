"""tests/test_crispy_burn_in.py — N4 follow-up: burn-in criteria evaluator.

Tests ``scripts/crispy_burn_in.py::evaluate_burn_in()`` against the criteria
documented in ``docs/plans/next-pass-roadmap.md``. The evaluator is a pure
function over the ``crispy_run_history`` payload — no network, no fixtures
beyond the dict.
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"


@pytest.fixture(scope="module")
def burn_in():
    """Load scripts/crispy_burn_in.py as a module."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    if "crispy_burn_in" in sys.modules:
        del sys.modules["crispy_burn_in"]
    mod = importlib.import_module("crispy_burn_in")
    yield mod
    sys.path.remove(str(SCRIPTS_DIR))


# ── Empty / null history ─────────────────────────────────────────────────────

def test_evaluate_burn_in_returns_not_ready_for_null_history(burn_in):
    """When crispy_run_history is null (backend not initialized), the result
    must be 'not ready' with all-auto-criteria failing — not a crash."""
    result = burn_in.evaluate_burn_in(None)
    assert result["ready"] is False
    # All auto-checkable criteria must be present and failing.
    criteria_by_name = {c["name"]: c for c in result["criteria"]}
    assert criteria_by_name["total_runs"]["met"] is False
    assert criteria_by_name["success_rate"]["met"] is False
    assert criteria_by_name["window_days"]["met"] is False
    # The gap message should mention the missing data
    assert "total_runs" in result["gap"] or "window_days" in result["gap"]


def test_evaluate_burn_in_returns_not_ready_for_empty_dict(burn_in):
    """An empty dict (no runs yet) must report all criteria as not met."""
    result = burn_in.evaluate_burn_in({})
    assert result["ready"] is False
    # total_runs=0 < 20, success_rate=0 < 0.8, window_days=None < 7
    criteria_by_name = {c["name"]: c for c in result["criteria"]}
    assert criteria_by_name["total_runs"]["met"] is False
    assert criteria_by_name["success_rate"]["met"] is False
    assert criteria_by_name["window_days"]["met"] is False
    assert criteria_by_name["no_phase_sequence_errors"]["met"] is True  # 0 is OK


# ── Criteria thresholds ──────────────────────────────────────────────────────

def test_evaluate_burn_in_meets_all_auto_criteria(burn_in):
    """When all auto-checkable criteria are met, ready=True with the human-gate
    message in the gap (the risky-module-review sign-off is the final step)."""
    history = {
        "total_runs": 25,            # >= 20
        "completed_runs": 22,
        "failed_runs": 3,
        "cancelled_runs": 0,
        "success_rate": 0.88,        # >= 0.80
        "phase_outcomes": {"design": {"complete": 25, "failed": 0}},
        "last_failure_reasons": [],  # no PhaseSequenceError
        "window_days": 10,           # >= 7
    }
    result = burn_in.evaluate_burn_in(history)
    assert result["ready"] is True
    assert "risky-module-review" in result["gap"].lower()
    # The human-gate criterion is always 'pending' (met=False) — it's not auto-checkable
    criteria_by_name = {c["name"]: c for c in result["criteria"]}
    assert criteria_by_name["risky_module_review_signoff"]["met"] is False
    assert criteria_by_name["risky_module_review_signoff"]["value"] == "pending"


def test_evaluate_burn_in_fails_on_insufficient_runs(burn_in):
    """total_runs below the threshold → not ready, even if everything else is green."""
    history = {
        "total_runs": 15,            # < 20
        "success_rate": 0.90,
        "window_days": 10,
        "last_failure_reasons": [],
    }
    result = burn_in.evaluate_burn_in(history)
    assert result["ready"] is False
    assert "total_runs" in result["gap"]


def test_evaluate_burn_in_fails_on_low_success_rate(burn_in):
    """success_rate below 80% → not ready."""
    history = {
        "total_runs": 25,
        "success_rate": 0.65,        # < 0.80
        "window_days": 10,
        "last_failure_reasons": [],
    }
    result = burn_in.evaluate_burn_in(history)
    assert result["ready"] is False
    assert "success_rate" in result["gap"]


def test_evaluate_burn_in_fails_on_short_window(burn_in):
    """window_days below 7 → not ready (need at least a week of evidence)."""
    history = {
        "total_runs": 25,
        "success_rate": 0.90,
        "window_days": 3,            # < 7
        "last_failure_reasons": [],
    }
    result = burn_in.evaluate_burn_in(history)
    assert result["ready"] is False
    assert "window_days" in result["gap"]


def test_evaluate_burn_in_fails_on_phase_sequence_error(burn_in):
    """PhaseSequenceError in last_failure_reasons → not ready (workspace
    isolation violated — the core issue that got CRISPY demoted in #467)."""
    history = {
        "total_runs": 25,
        "success_rate": 0.90,
        "window_days": 10,
        "last_failure_reasons": [
            "verify: PhaseSequenceError: predecessor 'design' not complete",
            "code: AssertionError: 1 != 2",
        ],
    }
    result = burn_in.evaluate_burn_in(history)
    assert result["ready"] is False
    criteria_by_name = {c["name"]: c for c in result["criteria"]}
    assert criteria_by_name["no_phase_sequence_errors"]["met"] is False
    assert criteria_by_name["no_phase_sequence_errors"]["value"] == 1  # one hit


def test_evaluate_burn_in_accepts_other_failure_types(burn_in):
    """Non-PhaseSequenceError failures (assertion errors, etc.) don't block
    promotion — only phase-sequence violations do (the workspace-isolation
    guarantee). The success_rate criterion catches generic failures."""
    history = {
        "total_runs": 25,
        "success_rate": 0.90,
        "window_days": 10,
        "last_failure_reasons": [
            "verify: AssertionError: 1 != 2",  # not a PhaseSequenceError
            "code: TimeoutError",
        ],
    }
    result = burn_in.evaluate_burn_in(history)
    assert result["ready"] is True  # PhaseSequenceError-free + all other criteria met


# ── Boundary conditions ──────────────────────────────────────────────────────

def test_evaluate_burn_in_exact_threshold_meets(burn_in):
    """Exact threshold values meet the criteria (>=, not >)."""
    history = {
        "total_runs": 20,            # exactly 20
        "success_rate": 0.80,        # exactly 0.80
        "window_days": 7,            # exactly 7
        "last_failure_reasons": [],
    }
    result = burn_in.evaluate_burn_in(history)
    assert result["ready"] is True


def test_evaluate_burn_in_handles_none_window_days(burn_in):
    """window_days=None (no runs yet, but total_runs > 0 somehow) is treated
    as 0 — fails the window check, not a crash."""
    history = {
        "total_runs": 5,
        "success_rate": 1.0,
        "window_days": None,
        "last_failure_reasons": [],
    }
    result = burn_in.evaluate_burn_in(history)
    assert result["ready"] is False
    criteria_by_name = {c["name"]: c for c in result["criteria"]}
    assert criteria_by_name["window_days"]["met"] is False


# ── CLI smoke test ───────────────────────────────────────────────────────────

def test_burn_in_cli_offline_mode_reads_json(burn_in, tmp_path, capsys):
    """The --json flag lets the workflow (and tests) run offline against a
    saved status payload — no network needed."""
    import json
    status_file = tmp_path / "status.json"
    status_file.write_text(json.dumps({
        "crispy_run_history": {
            "total_runs": 25,
            "success_rate": 0.90,
            "window_days": 10,
            "last_failure_reasons": [],
        }
    }))
    # Reload the module so __main__ sees the args
    import importlib
    importlib.reload(burn_in)
    import sys as _sys
    old_argv = _sys.argv
    _sys.argv = ["crispy_burn_in.py", "--json", str(status_file)]
    try:
        exit_code = burn_in.main()
    finally:
        _sys.argv = old_argv
    assert exit_code == 0  # ready
    captured = capsys.readouterr()
    assert '"ready": true' in captured.out.lower() or '"ready":true' in captured.out.lower()


def test_burn_in_cli_offline_mode_exits_1_when_not_ready(burn_in, tmp_path):
    """When criteria aren't met, exit 1 (so the workflow can detect the
    not-yet-ready state — but the workflow itself doesn't fail, see yml)."""
    import json
    status_file = tmp_path / "status.json"
    status_file.write_text(json.dumps({
        "crispy_run_history": {
            "total_runs": 5,  # < 20
            "success_rate": 0.90,
            "window_days": 10,
            "last_failure_reasons": [],
        }
    }))
    import importlib
    importlib.reload(burn_in)
    import sys as _sys
    old_argv = _sys.argv
    _sys.argv = ["crispy_burn_in.py", "--json", str(status_file)]
    try:
        exit_code = burn_in.main()
    finally:
        _sys.argv = old_argv
    assert exit_code == 1  # not ready
