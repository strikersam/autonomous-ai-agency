"""Guard that the quick-note engine agents use NVIDIA NIM as the primary engine
(Anthropic/Opus is fallback-only).

These scripts import the `openai` package at module load, which isn't a test
dependency, so we assert the wiring structurally from source rather than importing
them. The check is intentionally simple: in each model-selection site the NVIDIA
branch must appear before the Anthropic branch.
"""
from __future__ import annotations

from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / ".github" / "scripts"


def _before(text: str, primary: str, fallback: str) -> bool:
    i, j = text.find(primary), text.find(fallback)
    assert i != -1, f"marker not found: {primary!r}"
    assert j != -1, f"marker not found: {fallback!r}"
    return i < j


def test_implement_agent_nvidia_primary() -> None:
    """implement_agent.py uses NVIDIA NIM exclusively — the Anthropic/Opus
    fallback was removed (it burned paid credits whenever NVIDIA failed)."""
    text = (_SCRIPTS / "implement_agent.py").read_text()
    assert "Using NVIDIA NIM as the primary engine" in text
    assert "Anthropic Claude Opus fallback" not in text


def test_implement_agent_primary_model_is_a_coder() -> None:
    text = (_SCRIPTS / "nvidia_models.py").read_text()
    # Verify the primary model in the shared NVIDIA_CANDIDATE_MODELS is
    # a coder (nemotron-super-49b), not a generic chat model.
    assert "nemotron-super" in text


def test_review_agent_nvidia_primary() -> None:
    text = (_SCRIPTS / "review_agent.py").read_text()
    assert _before(text, "# Primary: NVIDIA NIM", "# Optional fallback: Anthropic")


def test_apply_review_nvidia_primary() -> None:
    text = (_SCRIPTS / "apply_review.py").read_text()
    nvidia_pos = text.find("NVIDIA NIM")
    anthropic_pos = text.find("# Optional fallback: Claude Opus via Anthropic")
    assert nvidia_pos != -1, "NVIDIA NIM marker not found in apply_review.py"
    assert anthropic_pos != -1, "Anthropic fallback marker not found in apply_review.py"
    assert nvidia_pos < anthropic_pos, f"NVIDIA ({nvidia_pos}) must appear before Anthropic ({anthropic_pos})"


def test_baseline_pytest_timeout_is_generous_and_failure_is_caught() -> None:
    """Regression: _run_baseline_pytest() ran the FULL suite (no path filter,
    thousands of tests) with only a 120s subprocess timeout, and the
    TimeoutExpired it raised was uncaught in main() — crashing the whole
    Quick Note automation and forcing an endless "Attempt 0 failed —
    reopening for automatic retry" cycle every time the full suite (routinely
    >120s on the Actions runner) was slower than the timeout. Baseline pytest
    output is informational context for the agent's prompt, not a merge
    gate, so a slow or hung suite must degrade gracefully, not crash the
    script."""
    text = (_SCRIPTS / "implement_agent.py").read_text()
    fn_start = text.index("def _run_baseline_pytest")
    fn_end = text.index("\ndef ", fn_start + 1)
    fn_body = text[fn_start:fn_end]
    assert "timeout=120" not in fn_body, (
        "120s is too short for a full, unfiltered pytest run on a CI runner — "
        "confirmed by a production TimeoutExpired crash."
    )
    assert "TimeoutExpired" in fn_body, (
        "_run_baseline_pytest must catch subprocess.TimeoutExpired so a slow "
        "suite can't crash the whole automation."
    )
