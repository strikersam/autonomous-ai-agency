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


def test_implement_agent_never_escalates_to_paid() -> None:
    """implement_agent.py must not spend paid credits behind the operator.

    This used to assert the literal string "Using NVIDIA NIM as the primary
    engine", which encoded a premise that turned out to be the bug: pinning one
    provider in this script meant that when every NVIDIA model reached
    end-of-life on 2026-08-26, the loop had nothing to fall back to and the
    agency stopped producing work. Routing moved to `ProviderRouter`.

    The *intent* behind the original assertion is unchanged and still worth
    guarding — it was never "use NVIDIA", it was "do not silently reach for a
    paid provider". `allow_commercial_fallback=False` is what enforces that now,
    and it is a stronger guarantee than a comment ordering check, because the
    router classifies which providers are commercial rather than this file.
    """
    text = (_SCRIPTS / "implement_agent.py").read_text()
    assert "allow_commercial_fallback=False" in text, (
        "the loop must never escalate to a paid provider on its own"
    )
    assert "Anthropic Claude Opus fallback" not in text


def test_implement_agent_routes_through_the_shared_router() -> None:
    """Rule 2: all LLM calls go through packages/ai/router.py.

    A private model list in this script is what caused the outage — it could not
    see that its models were dead, and had no other provider to try.
    """
    text = (_SCRIPTS / "implement_agent.py").read_text()
    assert "from packages.ai.router import ProviderRouter" in text
    assert "integrate.api.nvidia.com" not in text, (
        "provider endpoints belong to the router, not to this script"
    )


def test_nemotron_is_preferred_when_choosing_a_model() -> None:
    """Nemotron first — asserted against behaviour, not file contents.

    This used to grep `nvidia_models.py` for the literal "nemotron-super", which
    told you nothing useful: the file it inspected was imported by nothing, and
    the id it looked for reached end-of-life on 2026-08-26 while the assertion
    kept passing. Ids are now discovered from the provider, so the durable
    property is the ranking, which is what this exercises.
    """
    import sys

    sys.path.insert(0, str(_SCRIPTS))
    try:
        from nvidia_models import rank_models
    finally:
        if str(_SCRIPTS) in sys.path:
            sys.path.remove(str(_SCRIPTS))

    ranked = rank_models([
        "meta/llama-3.1-8b-instruct",
        "nvidia/some-nemotron-super-49b",
    ])
    assert "nemotron" in ranked[0]


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
