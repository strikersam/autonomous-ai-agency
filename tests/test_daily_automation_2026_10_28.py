"""tests/test_daily_automation_2026_10_28.py — Daily automation 2026-10-28.

Changes shipped today:
- **GPT-6.1 Terra declared in model catalogue** (``gpt-6.1-terra`` /
  ``openai/gpt-6.1-terra``, GA 2026-10-26). OpenAI's balanced mid-tier
  model in the GPT-6.1 family; 50 % cheaper than GPT-5.6 Terra and
  GPT-6.1 Sol. Context: 1,050,000 tokens. Max output: 128K tokens.
  Supports tool calling, function calling, JSON mode, streaming, and images.
  Pricing: $1.00/$5.00 per MTok.
  Cached input: $0.05/MTok (5 % of input rate).
  Priority 99 (explicit-only) — unprobed on this account; lower once
  ``catalogue-probe.yml`` sees a 200.
  Available via direct OpenAI API (``gpt-6.1-terra``) and
  OpenRouter (``openai/gpt-6.1-terra``).
  Sources: openai.com/index/introducing-gpt-6-1-terra/,
  openrouter.ai/openai/gpt-6.1-terra,
  ghacks.net/2026/10/27/openai-launches-gpt-6-1-terra-with-api-pricing-50-lower-than-gpt-5-6-terra/,
  2026-10-28.

Files changed:
  ``packages/ai/cost_tracker.py``,
  ``config/llm/models.yaml``,
  ``CHANGELOG.md``, ``docs/changelog.md``,
  ``tests/test_daily_automation_2026_10_28.py`` (this file).
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

GPT61_TERRA_OPENAI_ID = "gpt-6.1-terra"
GPT61_TERRA_OPENROUTER_ID = "openai/gpt-6.1-terra"
GPT61_TERRA_INPUT_COST = 1.0
GPT61_TERRA_OUTPUT_COST = 5.0
GPT61_TERRA_CACHE_FRACTION = 0.05  # $0.05 / $1.00 = 5 %


@pytest.fixture(scope="module")
def ct():
    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_10_28",
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
# Cost tracker — GPT-6.1 Terra OpenAI direct ID
# ---------------------------------------------------------------------------

class TestGpt61TerraOpenAICostTracker:
    def test_entry_exists(self, ct):
        cost = ct.cost_for_tokens(GPT61_TERRA_OPENAI_ID, 1_000_000, 0)
        assert cost is not None, f"{GPT61_TERRA_OPENAI_ID} must have a cost entry"

    def test_input_cost(self, ct):
        cost = ct.cost_for_tokens(GPT61_TERRA_OPENAI_ID, 1_000_000, 0)
        assert cost == pytest.approx(GPT61_TERRA_INPUT_COST), (
            f"{GPT61_TERRA_OPENAI_ID} input cost must be ${GPT61_TERRA_INPUT_COST}/MTok"
        )

    def test_output_cost(self, ct):
        cost = ct.cost_for_tokens(GPT61_TERRA_OPENAI_ID, 0, 1_000_000)
        assert cost == pytest.approx(GPT61_TERRA_OUTPUT_COST), (
            f"{GPT61_TERRA_OPENAI_ID} output cost must be ${GPT61_TERRA_OUTPUT_COST}/MTok"
        )

    def test_combined_cost(self, ct):
        cost = ct.cost_for_tokens(GPT61_TERRA_OPENAI_ID, 1_000_000, 1_000_000)
        assert cost == pytest.approx(GPT61_TERRA_INPUT_COST + GPT61_TERRA_OUTPUT_COST)

    def test_cost_is_float(self, ct):
        cost = ct.cost_for_tokens(GPT61_TERRA_OPENAI_ID, 500_000, 100_000)
        assert isinstance(cost, float)

    def test_cheaper_than_gpt61_sol(self, ct):
        """GPT-6.1 Terra must cost less than GPT-6.1 Sol for the same workload."""
        terra_cost = ct.cost_for_tokens(GPT61_TERRA_OPENAI_ID, 1_000_000, 1_000_000)
        sol_cost = ct.cost_for_tokens("gpt-6.1-sol", 1_000_000, 1_000_000)
        assert terra_cost < sol_cost, (
            f"GPT-6.1 Terra (${terra_cost}) must be cheaper than GPT-6.1 Sol (${sol_cost})"
        )

    def test_cache_fraction_is_5_percent(self, ct):
        fractions = {prefix: frac for prefix, frac in ct._CACHE_READ_FRACTIONS}
        assert GPT61_TERRA_OPENAI_ID in fractions, (
            f"{GPT61_TERRA_OPENAI_ID} must have an explicit cache-read fraction"
        )
        assert fractions[GPT61_TERRA_OPENAI_ID] == pytest.approx(
            GPT61_TERRA_CACHE_FRACTION
        ), (
            f"Cache fraction must be {GPT61_TERRA_CACHE_FRACTION} (5 %), "
            f"got {fractions[GPT61_TERRA_OPENAI_ID]}"
        )

    def test_cache_read_reduces_cost(self, ct):
        full_input = ct.cost_for_tokens(GPT61_TERRA_OPENAI_ID, 1_000_000, 0)
        with_cache = ct.cost_for_tokens(
            GPT61_TERRA_OPENAI_ID, 1_000_000, 0, cached_tokens=1_000_000
        )
        assert with_cache < full_input

    def test_cached_cost_is_5_percent_of_input(self, ct):
        """A fully-cached prompt should cost 5 % of the standard input rate."""
        full_input = ct.cost_for_tokens(GPT61_TERRA_OPENAI_ID, 1_000_000, 0)
        cached = ct.cost_for_tokens(
            GPT61_TERRA_OPENAI_ID, 1_000_000, 0, cached_tokens=1_000_000
        )
        assert cached == pytest.approx(full_input * GPT61_TERRA_CACHE_FRACTION)


# ---------------------------------------------------------------------------
# Cost tracker — GPT-6.1 Terra OpenRouter ID
# ---------------------------------------------------------------------------

class TestGpt61TerraOpenRouterCostTracker:
    def test_entry_exists(self, ct):
        cost = ct.cost_for_tokens(GPT61_TERRA_OPENROUTER_ID, 1_000_000, 0)
        assert cost is not None, f"{GPT61_TERRA_OPENROUTER_ID} must have a cost entry"

    def test_input_cost(self, ct):
        cost = ct.cost_for_tokens(GPT61_TERRA_OPENROUTER_ID, 1_000_000, 0)
        assert cost == pytest.approx(GPT61_TERRA_INPUT_COST)

    def test_output_cost(self, ct):
        cost = ct.cost_for_tokens(GPT61_TERRA_OPENROUTER_ID, 0, 1_000_000)
        assert cost == pytest.approx(GPT61_TERRA_OUTPUT_COST)

    def test_matches_openai_id(self, ct):
        openai_cost = ct.cost_for_tokens(GPT61_TERRA_OPENAI_ID, 500_000, 200_000)
        openrouter_cost = ct.cost_for_tokens(
            GPT61_TERRA_OPENROUTER_ID, 500_000, 200_000
        )
        assert openai_cost == pytest.approx(openrouter_cost), (
            "OpenAI and OpenRouter IDs must have identical pricing"
        )

    def test_openrouter_cache_fraction(self, ct):
        fractions = {prefix: frac for prefix, frac in ct._CACHE_READ_FRACTIONS}
        assert GPT61_TERRA_OPENROUTER_ID in fractions
        assert fractions[GPT61_TERRA_OPENROUTER_ID] == pytest.approx(
            GPT61_TERRA_CACHE_FRACTION
        )


# ---------------------------------------------------------------------------
# models.yaml — GPT-6.1 Terra
# ---------------------------------------------------------------------------

class TestGpt61TerraYaml:
    def test_entry_present(self, llm_models):
        models = llm_models.get("models", {})
        assert GPT61_TERRA_OPENAI_ID in models, (
            f"{GPT61_TERRA_OPENAI_ID} not found in config/llm/models.yaml"
        )

    def test_provider_openrouter(self, llm_models):
        entry = llm_models["models"][GPT61_TERRA_OPENAI_ID]
        assert entry.get("provider") == "openrouter", (
            "provider must be 'openrouter' (primary access via OpenRouter)"
        )

    def test_supports_tools(self, llm_models):
        entry = llm_models["models"][GPT61_TERRA_OPENAI_ID]
        assert entry.get("supports_tools") is True

    def test_supports_function_calling(self, llm_models):
        entry = llm_models["models"][GPT61_TERRA_OPENAI_ID]
        assert entry.get("supports_function_calling") is True

    def test_supports_streaming(self, llm_models):
        entry = llm_models["models"][GPT61_TERRA_OPENAI_ID]
        assert entry.get("supports_streaming") is True

    def test_supports_images(self, llm_models):
        entry = llm_models["models"][GPT61_TERRA_OPENAI_ID]
        assert entry.get("supports_images") is True

    def test_priority_explicit_only(self, llm_models):
        entry = llm_models["models"][GPT61_TERRA_OPENAI_ID]
        assert entry.get("priority") == 99, (
            f"{GPT61_TERRA_OPENAI_ID} must be priority 99 "
            "(explicit-only until catalogue-probe confirms it answers)"
        )

    def test_context_window(self, llm_models):
        entry = llm_models["models"][GPT61_TERRA_OPENAI_ID]
        assert entry.get("context_window") == 1_050_000, (
            "context_window must be 1,050,000 (1.05M)"
        )

    def test_max_output_tokens(self, llm_models):
        entry = llm_models["models"][GPT61_TERRA_OPENAI_ID]
        assert entry.get("max_output_tokens") == 128_000

    def test_display_name_present(self, llm_models):
        entry = llm_models["models"][GPT61_TERRA_OPENAI_ID]
        assert "display_name" in entry and entry["display_name"]

    def test_not_in_recommended_priority(self, llm_models):
        recommended = llm_models.get("recommended_priority", [])
        assert GPT61_TERRA_OPENAI_ID not in recommended, (
            f"{GPT61_TERRA_OPENAI_ID} must not be in recommended_priority (unprobed)"
        )

    def test_input_cost_matches_cost_tracker(self, llm_models):
        entry = llm_models["models"][GPT61_TERRA_OPENAI_ID]
        assert entry.get("input_cost_per_1m") == pytest.approx(GPT61_TERRA_INPUT_COST)

    def test_output_cost_matches_cost_tracker(self, llm_models):
        entry = llm_models["models"][GPT61_TERRA_OPENAI_ID]
        assert entry.get("output_cost_per_1m") == pytest.approx(GPT61_TERRA_OUTPUT_COST)


# ---------------------------------------------------------------------------
# Catalogue consistency — 86 declared IDs after this change
# ---------------------------------------------------------------------------

class TestCatalogueSize:
    def test_catalogue_has_86_ids(self, llm_models):
        """models.yaml should have 86 declared model entries after adding gpt-6.1-terra."""
        models = llm_models.get("models", {})
        assert len(models) == 86, (
            f"Expected 86 model IDs in models.yaml, got {len(models)}. "
            "If you added or removed other models, update this count."
        )


# ---------------------------------------------------------------------------
# Catalogue consistency — no new fuzzy collisions
# ---------------------------------------------------------------------------

class TestNoNewFuzzyCollisions:
    """gpt-6.1-terra / openai/gpt-6.1-terra must not fuzzy-collide with any free id."""

    TERRA_IDS = {GPT61_TERRA_OPENAI_ID, GPT61_TERRA_OPENROUTER_ID}

    def _is_zero_cost(self, ct, model_id: str) -> bool:
        inp, out = ct._DEFAULT_COST_TABLE.get(model_id, (0.0, 0.0))
        return inp == 0.0 and out == 0.0

    def test_openai_id_is_paid(self, ct):
        assert not self._is_zero_cost(ct, GPT61_TERRA_OPENAI_ID), (
            f"{GPT61_TERRA_OPENAI_ID} is a paid model and must not be in the zero-cost table"
        )

    def test_openrouter_id_is_paid(self, ct):
        assert not self._is_zero_cost(ct, GPT61_TERRA_OPENROUTER_ID), (
            f"{GPT61_TERRA_OPENROUTER_ID} is a paid model and must not be in the zero-cost table"
        )

    def test_no_undeclared_collision_with_free_models(self, ct):
        """No free model id should be a substring of the new Terra IDs, or vice-versa."""
        table = ct._DEFAULT_COST_TABLE
        zero_ids = {m for m, (i, o) in table.items() if i == 0.0 and o == 0.0}
        paid_ids = {m for m in table if m not in zero_ids}
        collisions = []
        for free_id in zero_ids:
            for paid_id in paid_ids:
                if free_id == paid_id:
                    continue
                if free_id in paid_id or paid_id in free_id:
                    if paid_id in self.TERRA_IDS or free_id in self.TERRA_IDS:
                        collisions.append((free_id, paid_id))
        assert not collisions, (
            f"New GPT-6.1 Terra IDs have undeclared fuzzy collisions: {collisions}"
        )
