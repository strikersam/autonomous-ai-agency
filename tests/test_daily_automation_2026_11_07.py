"""tests/test_daily_automation_2026_11_07.py — Daily automation 2026-11-07.

Changes shipped today:
- **Tencent Hy4 declared in model catalogue** (``tencent/hy4-preview``,
  released 2026-08-28). Tencent's 770B MoE open-weight model; served via
  OpenRouter on 7+ backend providers. Context: 1,048,576 tokens.
  Pricing: $0.83/$2.50 per MTok; cached input ~$0.042/MTok (≈5 %).
  Supports function calling, streaming, JSON mode.
  Sources: openrouter.ai/tencent/hy4-preview,
           eesel.ai/blog/tencent-hy4-pricing,
           llmreference.com/model/hy4-preview/openrouter, 2026-11-07.

- **``google/gemini-3.1-pro-preview`` OpenRouter ID added** (alias for
  existing ``gemini-3.1-pro`` at $2.00/$12.00 per MTok).  Gemini 3.1 Pro
  Preview was released 2026-02-19 and is reachable via OpenRouter under the
  ``google/gemini-3.1-pro-preview`` slug; the direct Google AI API continues
  to use ``gemini-3.1-pro``.
  Sources: openrouter.ai/google/gemini-3.1-pro-preview,
           typingmind.com/guide/openrouter/gemini-3.1-pro-preview, 2026-11-07.

Files changed:
  ``packages/ai/cost_tracker.py``,
  ``config/llm/models.yaml``,
  ``CHANGELOG.md``, ``docs/changelog.md``,
  ``tests/test_daily_automation_2026_11_07.py`` (this file).
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# Tencent Hy4
HY4_OPENROUTER_ID = "tencent/hy4-preview"
HY4_INPUT_COST = 0.83
HY4_OUTPUT_COST = 2.50
HY4_CACHE_FRACTION = 0.05  # ~$0.042 / $0.83 ≈ 5 %

# Gemini 3.1 Pro Preview (OpenRouter alias)
GEMINI_31_PRO_DIRECT_ID = "gemini-3.1-pro"
GEMINI_31_PRO_OPENROUTER_ID = "google/gemini-3.1-pro-preview"
GEMINI_31_PRO_INPUT_COST = 2.0
GEMINI_31_PRO_OUTPUT_COST = 12.0


@pytest.fixture(scope="module")
def ct():
    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_11_07",
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
# Tencent Hy4 — cost tracker
# ---------------------------------------------------------------------------

class TestHy4CostTracker:
    def test_entry_exists(self, ct):
        cost = ct.cost_for_tokens(HY4_OPENROUTER_ID, 1_000_000, 0)
        assert cost is not None

    def test_input_cost(self, ct):
        cost = ct.cost_for_tokens(HY4_OPENROUTER_ID, 1_000_000, 0)
        assert cost == pytest.approx(HY4_INPUT_COST), (
            f"{HY4_OPENROUTER_ID} input must be ${HY4_INPUT_COST}/MTok"
        )

    def test_output_cost(self, ct):
        cost = ct.cost_for_tokens(HY4_OPENROUTER_ID, 0, 1_000_000)
        assert cost == pytest.approx(HY4_OUTPUT_COST), (
            f"{HY4_OPENROUTER_ID} output must be ${HY4_OUTPUT_COST}/MTok"
        )

    def test_combined_cost(self, ct):
        cost = ct.cost_for_tokens(HY4_OPENROUTER_ID, 500_000, 500_000)
        expected = (HY4_INPUT_COST * 0.5) + (HY4_OUTPUT_COST * 0.5)
        assert cost == pytest.approx(expected)

    def test_is_paid_model(self, ct):
        inp, out = ct._DEFAULT_COST_TABLE.get(HY4_OPENROUTER_ID, (0.0, 0.0))
        assert inp > 0.0 and out > 0.0, f"{HY4_OPENROUTER_ID} must be a paid entry"

    def test_cache_fraction_explicit(self, ct):
        fractions = {prefix: frac for prefix, frac in ct._CACHE_READ_FRACTIONS}
        assert HY4_OPENROUTER_ID in fractions, (
            f"{HY4_OPENROUTER_ID} must have an explicit cache-read fraction"
        )
        assert fractions[HY4_OPENROUTER_ID] == pytest.approx(HY4_CACHE_FRACTION)

    def test_cache_read_reduces_cost(self, ct):
        full = ct.cost_for_tokens(HY4_OPENROUTER_ID, 1_000_000, 0)
        cached = ct.cost_for_tokens(
            HY4_OPENROUTER_ID, 1_000_000, 0, cached_tokens=1_000_000
        )
        assert cached < full

    def test_cached_cost_is_5_percent_of_input(self, ct):
        full = ct.cost_for_tokens(HY4_OPENROUTER_ID, 1_000_000, 0)
        cached = ct.cost_for_tokens(
            HY4_OPENROUTER_ID, 1_000_000, 0, cached_tokens=1_000_000
        )
        assert cached == pytest.approx(full * HY4_CACHE_FRACTION)


# ---------------------------------------------------------------------------
# Tencent Hy4 — models.yaml
# ---------------------------------------------------------------------------

class TestHy4ModelsYaml:
    def test_entry_exists(self, llm_models):
        models = llm_models.get("models", {})
        assert HY4_OPENROUTER_ID in models, (
            f"{HY4_OPENROUTER_ID} must be declared in config/llm/models.yaml"
        )

    def test_provider_is_openrouter(self, llm_models):
        entry = llm_models["models"][HY4_OPENROUTER_ID]
        assert entry.get("provider") == "openrouter"

    def test_context_window(self, llm_models):
        entry = llm_models["models"][HY4_OPENROUTER_ID]
        assert entry.get("context_window") == 1048576

    def test_input_cost_matches_tracker(self, llm_models):
        entry = llm_models["models"][HY4_OPENROUTER_ID]
        assert entry.get("input_cost_per_1m") == pytest.approx(HY4_INPUT_COST)

    def test_output_cost_matches_tracker(self, llm_models):
        entry = llm_models["models"][HY4_OPENROUTER_ID]
        assert entry.get("output_cost_per_1m") == pytest.approx(HY4_OUTPUT_COST)

    def test_priority_is_99(self, llm_models):
        entry = llm_models["models"][HY4_OPENROUTER_ID]
        assert entry.get("priority") == 99, (
            f"{HY4_OPENROUTER_ID} must be priority=99 (explicit-only) until probed"
        )

    def test_supports_tools(self, llm_models):
        entry = llm_models["models"][HY4_OPENROUTER_ID]
        assert entry.get("supports_tools") is True

    def test_supports_streaming(self, llm_models):
        entry = llm_models["models"][HY4_OPENROUTER_ID]
        assert entry.get("supports_streaming") is True


# ---------------------------------------------------------------------------
# Gemini 3.1 Pro Preview (OpenRouter ID) — cost tracker
# ---------------------------------------------------------------------------

class TestGemini31ProPreviewOpenRouterCostTracker:
    def test_entry_exists(self, ct):
        cost = ct.cost_for_tokens(GEMINI_31_PRO_OPENROUTER_ID, 1_000_000, 0)
        assert cost is not None

    def test_input_cost(self, ct):
        cost = ct.cost_for_tokens(GEMINI_31_PRO_OPENROUTER_ID, 1_000_000, 0)
        assert cost == pytest.approx(GEMINI_31_PRO_INPUT_COST), (
            f"{GEMINI_31_PRO_OPENROUTER_ID} input must be ${GEMINI_31_PRO_INPUT_COST}/MTok"
        )

    def test_output_cost(self, ct):
        cost = ct.cost_for_tokens(GEMINI_31_PRO_OPENROUTER_ID, 0, 1_000_000)
        assert cost == pytest.approx(GEMINI_31_PRO_OUTPUT_COST), (
            f"{GEMINI_31_PRO_OPENROUTER_ID} output must be ${GEMINI_31_PRO_OUTPUT_COST}/MTok"
        )

    def test_matches_direct_id(self, ct):
        direct = ct.cost_for_tokens(GEMINI_31_PRO_DIRECT_ID, 500_000, 200_000)
        openrouter = ct.cost_for_tokens(GEMINI_31_PRO_OPENROUTER_ID, 500_000, 200_000)
        assert direct == pytest.approx(openrouter), (
            "google/gemini-3.1-pro-preview must cost the same as gemini-3.1-pro"
        )

    def test_is_paid_model(self, ct):
        inp, out = ct._DEFAULT_COST_TABLE.get(GEMINI_31_PRO_OPENROUTER_ID, (0.0, 0.0))
        assert inp > 0.0 and out > 0.0, (
            f"{GEMINI_31_PRO_OPENROUTER_ID} must be a paid cost-table entry"
        )

    def test_combined_cost(self, ct):
        cost = ct.cost_for_tokens(GEMINI_31_PRO_OPENROUTER_ID, 200_000, 50_000)
        expected = (GEMINI_31_PRO_INPUT_COST * 0.2) + (GEMINI_31_PRO_OUTPUT_COST * 0.05)
        assert cost == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Catalogue-level invariants
# ---------------------------------------------------------------------------

class TestCatalogueInvariants:
    def test_catalogue_total_increases(self, ct):
        """Model catalogue must grow by at least the two new entries."""
        ids = set(ct._DEFAULT_COST_TABLE.keys())
        assert HY4_OPENROUTER_ID in ids
        assert GEMINI_31_PRO_OPENROUTER_ID in ids

    def test_new_ids_not_zero_cost(self, ct):
        for model_id in (HY4_OPENROUTER_ID, GEMINI_31_PRO_OPENROUTER_ID):
            inp, out = ct._DEFAULT_COST_TABLE.get(model_id, (0.0, 0.0))
            assert inp > 0.0 and out > 0.0, (
                f"{model_id} must not be a zero-cost (free) entry"
            )

    def test_yaml_models_still_parseable(self, llm_models):
        assert "models" in llm_models
        assert len(llm_models["models"]) > 0
