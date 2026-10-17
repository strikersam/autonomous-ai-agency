"""tests/test_daily_automation_2026_10_17.py — Daily automation 2026-10-17.

Changes shipped today:
- **Meta Muse Spark Open declared** (``meta-models/muse-spark-open`` on Groq).
  Released 2026-10-15. Meta's largest MoE open-weight reasoning model:
  816B total parameters, 42B active per request.
  Context: 131,072 tokens on Groq LPU. Max output: 131,072 tokens.
  Designed for coding and agentic tasks. Supports reasoning, tool calling, and
  streaming. Groq limited preview — requires contacting Groq sales for access.
  Market rate (Together AI / Fireworks AI): $1.25 input / $4.25 output per MTok.
  Priority: 99 (explicit-only; not in routing candidates until probed on this account).
  Source: console.groq.com/docs/model/meta-models/muse-spark-open, 2026-10-17.

Files changed:
  ``config/llm/models.yaml``, ``packages/ai/cost_tracker.py``,
  ``CHANGELOG.md``, ``docs/changelog.md``,
  ``tests/test_daily_automation_2026_10_17.py`` (this file).
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

MODEL_ID = "meta-models/muse-spark-open"


@pytest.fixture(scope="module")
def ct():
    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_10_17",
        REPO_ROOT / "packages" / "ai" / "cost_tracker.py",
    )
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture(scope="module")
def llm_models():
    return yaml.safe_load(
        (REPO_ROOT / "config" / "llm" / "models.yaml").read_text()
    )


# ---------------------------------------------------------------------------
# Cost tracker — Muse Spark Open
# ---------------------------------------------------------------------------

class TestMuseSparkOpenCost:
    def test_input_cost_declared(self, ct):
        cost = ct.cost_for_tokens(MODEL_ID, 1_000_000, 0)
        assert cost == pytest.approx(1.25), (
            "meta-models/muse-spark-open input cost must be $1.25/MTok (market rate)"
        )

    def test_output_cost_declared(self, ct):
        cost = ct.cost_for_tokens(MODEL_ID, 0, 1_000_000)
        assert cost == pytest.approx(4.25), (
            "meta-models/muse-spark-open output cost must be $4.25/MTok (market rate)"
        )

    def test_output_more_expensive_than_input(self, ct):
        in_cost = ct.cost_for_tokens(MODEL_ID, 1_000_000, 0)
        out_cost = ct.cost_for_tokens(MODEL_ID, 0, 1_000_000)
        assert out_cost > in_cost, "output should cost more than input per token"

    def test_paid_model(self, ct):
        """Sanity: Muse Spark Open is a paid model (not free)."""
        cost = ct.cost_for_tokens(MODEL_ID, 100, 100)
        assert cost > 0.0, "must have non-zero cost"

    def test_input_cost_is_float(self, ct):
        cost = ct.cost_for_tokens(MODEL_ID, 500_000, 0)
        assert isinstance(cost, float)

    def test_proportional_billing(self, ct):
        cost_half = ct.cost_for_tokens(MODEL_ID, 500_000, 0)
        cost_full = ct.cost_for_tokens(MODEL_ID, 1_000_000, 0)
        assert cost_full == pytest.approx(cost_half * 2, rel=1e-6)


# ---------------------------------------------------------------------------
# models.yaml — Muse Spark Open
# ---------------------------------------------------------------------------

class TestMuseSparkOpenYaml:
    def test_entry_present(self, llm_models):
        models = llm_models.get("models", {})
        assert MODEL_ID in models, f"{MODEL_ID} not found in config/llm/models.yaml"

    def test_provider_groq(self, llm_models):
        entry = llm_models["models"][MODEL_ID]
        assert entry.get("provider") == "groq", "provider must be 'groq'"

    def test_context_window(self, llm_models):
        entry = llm_models["models"][MODEL_ID]
        assert entry.get("context_window") == 131072, "context_window must be 131072"

    def test_max_output_tokens(self, llm_models):
        entry = llm_models["models"][MODEL_ID]
        assert entry.get("max_output_tokens") == 131072

    def test_supports_tools(self, llm_models):
        entry = llm_models["models"][MODEL_ID]
        assert entry.get("supports_tools") is True

    def test_supports_reasoning(self, llm_models):
        entry = llm_models["models"][MODEL_ID]
        assert entry.get("supports_reasoning") is True

    def test_supports_streaming(self, llm_models):
        entry = llm_models["models"][MODEL_ID]
        assert entry.get("supports_streaming") is True

    def test_priority_explicit_only(self, llm_models):
        entry = llm_models["models"][MODEL_ID]
        assert entry.get("priority") == 99, (
            "priority must be 99 (explicit-only; limited preview not yet probed)"
        )

    def test_input_cost(self, llm_models):
        entry = llm_models["models"][MODEL_ID]
        assert entry.get("input_cost_per_1m") == pytest.approx(1.25)

    def test_output_cost(self, llm_models):
        entry = llm_models["models"][MODEL_ID]
        assert entry.get("output_cost_per_1m") == pytest.approx(4.25)

    def test_display_name_present(self, llm_models):
        entry = llm_models["models"][MODEL_ID]
        assert "display_name" in entry and entry["display_name"], (
            "display_name must be non-empty"
        )

    def test_not_in_recommended_priority_list(self, llm_models):
        """Limited-preview model must not appear in the top recommended list."""
        recommended = llm_models.get("recommended_priority", [])
        assert MODEL_ID not in recommended, (
            f"{MODEL_ID} should not be in recommended_priority (limited preview)"
        )
