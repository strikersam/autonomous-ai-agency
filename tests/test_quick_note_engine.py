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
    text = (_SCRIPTS / "implement_agent.py").read_text()
    assert _before(text, "Using NVIDIA NIM as the primary engine", "Anthropic Claude Opus fallback")


def test_implement_agent_primary_model_is_a_coder() -> None:
    # Best-in-class coding engine: the first NVIDIA candidate should be a coder model.
    text = (_SCRIPTS / "implement_agent.py").read_text()
    start = text.index("NVIDIA_CANDIDATE_MODELS = [")
    first_entry = text[start:text.index("]", start)]
    assert "qwen/qwen3-coder" in first_entry.split("\n")[1]


def test_review_agent_nvidia_primary() -> None:
    text = (_SCRIPTS / "review_agent.py").read_text()
    assert _before(text, "# Primary: NVIDIA NIM", "# Optional fallback: Anthropic")


def test_apply_review_nvidia_primary() -> None:
    text = (_SCRIPTS / "apply_review.py").read_text()
    assert _before(text, "NVIDIA NIM — primary", "# Optional fallback: Claude Opus via Anthropic")
