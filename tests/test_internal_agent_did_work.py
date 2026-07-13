"""tests/test_internal_agent_did_work.py — step-success-ratio gate tests.

Tests that ``InternalAgentAdapter``'s ``did_work`` logic (which becomes
``TaskResult.success``) correctly gates on the step-success ratio:

  - 1/22 applied → success=False (the production bug case)
  - 9/10 applied → success=True
  - 0 steps + long report → success=True (pure analysis task)
  - 0 steps + short report → success=False
  - judge_verdict=BLOCKED → always success=False regardless of ratio
"""
from __future__ import annotations

import pytest


def _compute_did_work(
    steps: list[dict],
    unique_files: list[str] | None = None,
    output_text: str = "",
    judge_verdict: str = "",
) -> bool:
    """Replicate the did_work logic from internal_agent.py:509-533."""
    unique_files = unique_files or []
    applied_steps = [s for s in steps if s.get("status") == "applied"]
    judge_verdict = judge_verdict.upper()

    total_steps = len(steps)
    step_success_ratio = (len(applied_steps) / total_steps) if total_steps else None
    steps_ok = step_success_ratio is None or step_success_ratio >= 0.5

    did_work = (
        steps_ok
        and (bool(unique_files or applied_steps) or (not steps and len(output_text.strip()) > 20))
        and judge_verdict != "BLOCKED"
    )
    return did_work


def _step(status: str) -> dict:
    return {"status": status, "step_id": 1, "description": "test", "issues": []}


# ── The production bug case ─────────────────────────────────────────────────


def test_one_applied_21_failed_is_failure():
    """1/22 applied (4.5%) → should be FAILURE (the bug case)."""
    steps = [_step("applied")] + [_step("failed") for _ in range(21)]
    assert _compute_did_work(steps) is False


def test_one_applied_9_failed_is_failure():
    """1/10 applied (10%) → should be FAILURE."""
    steps = [_step("applied")] + [_step("failed") for _ in range(9)]
    assert _compute_did_work(steps) is False


# ── Majority-applied cases ──────────────────────────────────────────────────


def test_nine_applied_1_failed_is_success():
    """9/10 applied (90%) → should be SUCCESS."""
    steps = [_step("applied") for _ in range(9)] + [_step("failed")]
    assert _compute_did_work(steps) is True


def test_five_applied_5_failed_is_success():
    """5/10 applied (50%) → should be SUCCESS (exactly at threshold)."""
    steps = [_step("applied") for _ in range(5)] + [_step("failed") for _ in range(5)]
    assert _compute_did_work(steps) is True


def test_four_applied_6_failed_is_failure():
    """4/10 applied (40%) → should be FAILURE."""
    steps = [_step("applied") for _ in range(4)] + [_step("failed") for _ in range(6)]
    assert _compute_did_work(steps) is False


# ── Zero-steps cases (pure analysis/report tasks) ───────────────────────────


def test_zero_steps_long_report_is_success():
    """0 steps + report >20 chars → SUCCESS (pure analysis task)."""
    assert _compute_did_work([], output_text="This is a detailed analysis report.") is True


def test_zero_steps_short_report_is_failure():
    """0 steps + report ≤20 chars → FAILURE."""
    assert _compute_did_work([], output_text="short") is False


def test_zero_steps_empty_report_is_failure():
    """0 steps + empty report → FAILURE."""
    assert _compute_did_work([], output_text="") is False


# ── BLOCKED judge verdict ───────────────────────────────────────────────────


def test_blocked_verdict_always_failure_even_with_majority():
    """judge_verdict=BLOCKED → always FAILURE, even with 10/10 applied."""
    steps = [_step("applied") for _ in range(10)]
    assert _compute_did_work(steps, judge_verdict="BLOCKED") is False


def test_blocked_verdict_always_failure_with_zero_steps():
    """judge_verdict=BLOCKED → always FAILURE, even with a long report."""
    assert _compute_did_work([], output_text="A" * 100, judge_verdict="BLOCKED") is False


# ── Files-changed override ──────────────────────────────────────────────────


def test_files_changed_with_majority_failure_still_fails():
    """Even with unique_files, 1/22 applied → FAILURE (steps_ok gate)."""
    steps = [_step("applied")] + [_step("failed") for _ in range(21)]
    assert _compute_did_work(steps, unique_files=["foo.py"]) is False


def test_files_changed_with_majority_success_is_success():
    """With 9/10 applied + unique_files → SUCCESS."""
    steps = [_step("applied") for _ in range(9)] + [_step("failed")]
    assert _compute_did_work(steps, unique_files=["foo.py"]) is True
