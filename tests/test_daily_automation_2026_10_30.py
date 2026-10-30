"""tests/test_daily_automation_2026_10_30.py — Daily automation 2026-10-30.

Changes shipped today:
- **GPT-6.1 Terra declared in model catalogue** (``gpt-6.1-terra`` /
  ``openai/gpt-6.1-terra``, released 2026-10-26). OpenAI's cost-efficient
  tier model optimised for computer use and agentic work; substantial
  improvement over GPT-5.6 Terra. Context: 1,050,000 tokens. Max output: 128K.
  Pricing: $1.00/$5.00 per MTok (standard); cached input $0.05/MTok (5 %).
  Tool calling via the Responses API.
  Sources: openrouter.ai/openai/gpt-6.1-terra,
           requesty.ai/models/openai/gpt-6.1-terra, 2026-10-30.

- **Kimi K3.1 Pro declared in model catalogue** (``kimi-k3.1-pro`` /
  ``moonshotai/kimi-k3.1-pro``, released 2026-10-23). Moonshot AI's
  successor to Kimi K3; improved coding, reasoning, and long-context
  retrieval. Context: 1,048,576 tokens. Pricing: $2.00/$10.00 per MTok.
  API ID previously unconfirmed (deferred 2026-10-25); confirmed via
  openrouter.ai/moonshotai/kimi-k3.1-pro, 2026-10-30.

- **Inception Mercury 3 declared in model catalogue** (``inception/mercury-3``,
  released 2026-10-16 to 2026-10-19). Inception's third-gen diffusion-based
  language model. Context: 1,000,000 tokens; max output: 131,072.
  Pricing: $0.10/$0.35 per MTok; cached input ~90 % cheaper ($0.01/MTok =
  10 % of input rate).
  Sources: openrouter.ai/inception/mercury-3,
           mindstudio.ai/blog/mercury-3-pricing-api,
           computeprices.com/models/mercury-3, 2026-10-30.

Files changed:
  ``packages/ai/cost_tracker.py``,
  ``config/llm/models.yaml``,
  ``CHANGELOG.md``, ``docs/changelog.md``,
  ``tests/test_daily_automation_2026_10_30.py`` (this file).
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# GPT-6.1 Terra
GPT61_TERRA_OPENAI_ID = "gpt-6.1-terra"
GPT61_TERRA_OPENROUTER_ID = "openai/gpt-6.1-terra"
GPT61_TERRA_INPUT_COST = 1.0
GPT61_TERRA_OUTPUT_COST = 5.0
GPT61_TERRA_CACHE_FRACTION = 0.05  # $0.05 / $1.00 = 5 %

# Kimi K3.1 Pro
KIMI_K31_PRO_DIRECT_ID = "kimi-k3.1-pro"
KIMI_K31_PRO_OPENROUTER_ID = "moonshotai/kimi-k3.1-pro"
KIMI_K31_PRO_INPUT_COST = 2.0
KIMI_K31_PRO_OUTPUT_COST = 10.0

# Inception Mercury 3
MERCURY_3_OPENROUTER_ID = "inception/mercury-3"
MERCURY_3_INPUT_COST = 0.10
MERCURY_3_OUTPUT_COST = 0.35
MERCURY_3_CACHE_FRACTION = 0.10  # ~90 % discount → $0.01/$0.10 = 10 %


@pytest.fixture(scope="module")
def ct():
    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_10_30",
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
# GPT-6.1 Terra — cost tracker (OpenAI direct ID)
# ---------------------------------------------------------------------------

class TestGpt61TerraCostTracker:
    def test_entry_exists(self, ct):
        cost = ct.cost_for_tokens(GPT61_TERRA_OPENAI_ID, 1_000_000, 0)
        assert cost is not None

    def test_input_cost(self, ct):
        cost = ct.cost_for_tokens(GPT61_TERRA_OPENAI_ID, 1_000_000, 0)
        assert cost == pytest.approx(GPT61_TERRA_INPUT_COST), (
            f"{GPT61_TERRA_OPENAI_ID} input must be ${GPT61_TERRA_INPUT_COST}/MTok"
        )

    def test_output_cost(self, ct):
        cost = ct.cost_for_tokens(GPT61_TERRA_OPENAI_ID, 0, 1_000_000)
        assert cost == pytest.approx(GPT61_TERRA_OUTPUT_COST), (
            f"{GPT61_TERRA_OPENAI_ID} output must be ${GPT61_TERRA_OUTPUT_COST}/MTok"
        )

    def test_combined_cost(self, ct):
        cost = ct.cost_for_tokens(GPT61_TERRA_OPENAI_ID, 1_000_000, 1_000_000)
        assert cost == pytest.approx(GPT61_TERRA_INPUT_COST + GPT61_TERRA_OUTPUT_COST)

    def test_cache_fraction_explicit(self, ct):
        fractions = {prefix: frac for prefix, frac in ct._CACHE_READ_FRACTIONS}
        assert GPT61_TERRA_OPENAI_ID in fractions, (
            f"{GPT61_TERRA_OPENAI_ID} must have an explicit cache-read fraction"
        )
        assert fractions[GPT61_TERRA_OPENAI_ID] == pytest.approx(GPT61_TERRA_CACHE_FRACTION)

    def test_cache_read_reduces_cost(self, ct):
        full = ct.cost_for_tokens(GPT61_TERRA_OPENAI_ID, 1_000_000, 0)
        cached = ct.cost_for_tokens(
            GPT61_TERRA_OPENAI_ID, 1_000_000, 0, cached_tokens=1_000_000
        )
        assert cached < full

    def test_cached_cost_is_5_percent_of_input(self, ct):
        full = ct.cost_for_tokens(GPT61_TERRA_OPENAI_ID, 1_000_000, 0)
        cached = ct.cost_for_tokens(
            GPT61_TERRA_OPENAI_ID, 1_000_000, 0, cached_tokens=1_000_000
        )
        assert cached == pytest.approx(full * GPT61_TERRA_CACHE_FRACTION)

    def test_is_paid_model(self, ct):
        inp, out = ct._DEFAULT_COST_TABLE.get(GPT61_TERRA_OPENAI_ID, (0.0, 0.0))
        assert inp > 0.0 and out > 0.0, "gpt-6.1-terra must be a paid entry"


# ---------------------------------------------------------------------------
# GPT-6.1 Terra — cost tracker (OpenRouter ID)
# ---------------------------------------------------------------------------

class TestGpt61TerraOpenRouterCostTracker:
    def test_entry_exists(self, ct):
        cost = ct.cost_for_tokens(GPT61_TERRA_OPENROUTER_ID, 1_000_000, 0)
        assert cost is not None

    def test_input_cost(self, ct):
        cost = ct.cost_for_tokens(GPT61_TERRA_OPENROUTER_ID, 1_000_000, 0)
        assert cost == pytest.approx(GPT61_TERRA_INPUT_COST)

    def test_output_cost(self, ct):
        cost = ct.cost_for_tokens(GPT61_TERRA_OPENROUTER_ID, 0, 1_000_000)
        assert cost == pytest.approx(GPT61_TERRA_OUTPUT_COST)

    def test_matches_direct_id(self, ct):
        direct = ct.cost_for_tokens(GPT61_TERRA_OPENAI_ID, 500_000, 200_000)
        openrouter = ct.cost_for_tokens(GPT61_TERRA_OPENROUTER_ID, 500_000, 200_000)
        assert direct == pytest.approx(openrouter)

    def test_openrouter_cache_fraction(self, ct):
        fractions = {prefix: frac for prefix, frac in ct._CACHE_READ_FRACTIONS}
        assert GPT61_TERRA_OPENROUTER_ID in fractions
        assert fractions[GPT61_TERRA_OPENROUTER_ID] == pytest.approx(GPT61_TERRA_CACHE_FRACTION)


# ---------------------------------------------------------------------------
# GPT-6.1 Terra — models.yaml
# ---------------------------------------------------------------------------

class TestGpt61TerraYaml:
    def test_entry_present(self, llm_models):
        models = llm_models.get("models", {})
        assert GPT61_TERRA_OPENAI_ID in models

    def test_provider_openrouter(self, llm_models):
        entry = llm_models["models"][GPT61_TERRA_OPENAI_ID]
        assert entry.get("provider") == "openrouter"

    def test_supports_tools(self, llm_models):
        entry = llm_models["models"][GPT61_TERRA_OPENAI_ID]
        assert entry.get("supports_tools") is True

    def test_supports_streaming(self, llm_models):
        entry = llm_models["models"][GPT61_TERRA_OPENAI_ID]
        assert entry.get("supports_streaming") is True

    def test_priority_explicit_only(self, llm_models):
        entry = llm_models["models"][GPT61_TERRA_OPENAI_ID]
        assert entry.get("priority") == 99

    def test_context_window(self, llm_models):
        entry = llm_models["models"][GPT61_TERRA_OPENAI_ID]
        assert entry.get("context_window") == 1_050_000

    def test_max_output_tokens(self, llm_models):
        entry = llm_models["models"][GPT61_TERRA_OPENAI_ID]
        assert entry.get("max_output_tokens") == 128_000

    def test_input_cost_matches_tracker(self, llm_models):
        entry = llm_models["models"][GPT61_TERRA_OPENAI_ID]
        assert entry.get("input_cost_per_1m") == pytest.approx(GPT61_TERRA_INPUT_COST)

    def test_output_cost_matches_tracker(self, llm_models):
        entry = llm_models["models"][GPT61_TERRA_OPENAI_ID]
        assert entry.get("output_cost_per_1m") == pytest.approx(GPT61_TERRA_OUTPUT_COST)

    def test_not_in_recommended_priority(self, llm_models):
        recommended = llm_models.get("recommended_priority", [])
        assert GPT61_TERRA_OPENAI_ID not in recommended


# ---------------------------------------------------------------------------
# Kimi K3.1 Pro — cost tracker (Moonshot direct ID)
# ---------------------------------------------------------------------------

class TestKimiK31ProCostTracker:
    def test_entry_exists(self, ct):
        cost = ct.cost_for_tokens(KIMI_K31_PRO_DIRECT_ID, 1_000_000, 0)
        assert cost is not None

    def test_input_cost(self, ct):
        cost = ct.cost_for_tokens(KIMI_K31_PRO_DIRECT_ID, 1_000_000, 0)
        assert cost == pytest.approx(KIMI_K31_PRO_INPUT_COST)

    def test_output_cost(self, ct):
        cost = ct.cost_for_tokens(KIMI_K31_PRO_DIRECT_ID, 0, 1_000_000)
        assert cost == pytest.approx(KIMI_K31_PRO_OUTPUT_COST)

    def test_combined_cost(self, ct):
        cost = ct.cost_for_tokens(KIMI_K31_PRO_DIRECT_ID, 1_000_000, 1_000_000)
        assert cost == pytest.approx(KIMI_K31_PRO_INPUT_COST + KIMI_K31_PRO_OUTPUT_COST)

    def test_is_paid_model(self, ct):
        inp, out = ct._DEFAULT_COST_TABLE.get(KIMI_K31_PRO_DIRECT_ID, (0.0, 0.0))
        assert inp > 0.0 and out > 0.0


# ---------------------------------------------------------------------------
# Kimi K3.1 Pro — cost tracker (OpenRouter ID)
# ---------------------------------------------------------------------------

class TestKimiK31ProOpenRouterCostTracker:
    def test_entry_exists(self, ct):
        cost = ct.cost_for_tokens(KIMI_K31_PRO_OPENROUTER_ID, 1_000_000, 0)
        assert cost is not None

    def test_input_cost(self, ct):
        cost = ct.cost_for_tokens(KIMI_K31_PRO_OPENROUTER_ID, 1_000_000, 0)
        assert cost == pytest.approx(KIMI_K31_PRO_INPUT_COST)

    def test_output_cost(self, ct):
        cost = ct.cost_for_tokens(KIMI_K31_PRO_OPENROUTER_ID, 0, 1_000_000)
        assert cost == pytest.approx(KIMI_K31_PRO_OUTPUT_COST)

    def test_matches_direct_id(self, ct):
        direct = ct.cost_for_tokens(KIMI_K31_PRO_DIRECT_ID, 500_000, 200_000)
        openrouter = ct.cost_for_tokens(KIMI_K31_PRO_OPENROUTER_ID, 500_000, 200_000)
        assert direct == pytest.approx(openrouter)


# ---------------------------------------------------------------------------
# Kimi K3.1 Pro — models.yaml
# ---------------------------------------------------------------------------

class TestKimiK31ProYaml:
    def test_entry_present(self, llm_models):
        models = llm_models.get("models", {})
        assert KIMI_K31_PRO_DIRECT_ID in models

    def test_provider_openrouter(self, llm_models):
        entry = llm_models["models"][KIMI_K31_PRO_DIRECT_ID]
        assert entry.get("provider") == "openrouter"

    def test_supports_tools(self, llm_models):
        entry = llm_models["models"][KIMI_K31_PRO_DIRECT_ID]
        assert entry.get("supports_tools") is True

    def test_priority_explicit_only(self, llm_models):
        entry = llm_models["models"][KIMI_K31_PRO_DIRECT_ID]
        assert entry.get("priority") == 99

    def test_context_window(self, llm_models):
        entry = llm_models["models"][KIMI_K31_PRO_DIRECT_ID]
        assert entry.get("context_window") == 1_048_576

    def test_input_cost_matches_tracker(self, llm_models):
        entry = llm_models["models"][KIMI_K31_PRO_DIRECT_ID]
        assert entry.get("input_cost_per_1m") == pytest.approx(KIMI_K31_PRO_INPUT_COST)

    def test_output_cost_matches_tracker(self, llm_models):
        entry = llm_models["models"][KIMI_K31_PRO_DIRECT_ID]
        assert entry.get("output_cost_per_1m") == pytest.approx(KIMI_K31_PRO_OUTPUT_COST)

    def test_not_in_recommended_priority(self, llm_models):
        recommended = llm_models.get("recommended_priority", [])
        assert KIMI_K31_PRO_DIRECT_ID not in recommended


# ---------------------------------------------------------------------------
# Inception Mercury 3 — cost tracker
# ---------------------------------------------------------------------------

class TestMercury3CostTracker:
    def test_entry_exists(self, ct):
        cost = ct.cost_for_tokens(MERCURY_3_OPENROUTER_ID, 1_000_000, 0)
        assert cost is not None

    def test_input_cost(self, ct):
        cost = ct.cost_for_tokens(MERCURY_3_OPENROUTER_ID, 1_000_000, 0)
        assert cost == pytest.approx(MERCURY_3_INPUT_COST)

    def test_output_cost(self, ct):
        cost = ct.cost_for_tokens(MERCURY_3_OPENROUTER_ID, 0, 1_000_000)
        assert cost == pytest.approx(MERCURY_3_OUTPUT_COST)

    def test_combined_cost(self, ct):
        cost = ct.cost_for_tokens(MERCURY_3_OPENROUTER_ID, 1_000_000, 1_000_000)
        assert cost == pytest.approx(MERCURY_3_INPUT_COST + MERCURY_3_OUTPUT_COST)

    def test_is_paid_model(self, ct):
        inp, out = ct._DEFAULT_COST_TABLE.get(MERCURY_3_OPENROUTER_ID, (0.0, 0.0))
        assert inp > 0.0 and out > 0.0

    def test_cache_fraction_explicit(self, ct):
        fractions = {prefix: frac for prefix, frac in ct._CACHE_READ_FRACTIONS}
        assert MERCURY_3_OPENROUTER_ID in fractions, (
            "inception/mercury-3 must have an explicit cache-read fraction "
            "(~90 % cached discount = 10 % fraction)"
        )
        assert fractions[MERCURY_3_OPENROUTER_ID] == pytest.approx(MERCURY_3_CACHE_FRACTION)

    def test_cache_read_reduces_cost(self, ct):
        full = ct.cost_for_tokens(MERCURY_3_OPENROUTER_ID, 1_000_000, 0)
        cached = ct.cost_for_tokens(
            MERCURY_3_OPENROUTER_ID, 1_000_000, 0, cached_tokens=1_000_000
        )
        assert cached < full

    def test_cached_cost_is_10_percent_of_input(self, ct):
        full = ct.cost_for_tokens(MERCURY_3_OPENROUTER_ID, 1_000_000, 0)
        cached = ct.cost_for_tokens(
            MERCURY_3_OPENROUTER_ID, 1_000_000, 0, cached_tokens=1_000_000
        )
        assert cached == pytest.approx(full * MERCURY_3_CACHE_FRACTION)


# ---------------------------------------------------------------------------
# Inception Mercury 3 — models.yaml
# ---------------------------------------------------------------------------

class TestMercury3Yaml:
    def test_entry_present(self, llm_models):
        models = llm_models.get("models", {})
        assert MERCURY_3_OPENROUTER_ID in models

    def test_provider_openrouter(self, llm_models):
        entry = llm_models["models"][MERCURY_3_OPENROUTER_ID]
        assert entry.get("provider") == "openrouter"

    def test_supports_streaming(self, llm_models):
        entry = llm_models["models"][MERCURY_3_OPENROUTER_ID]
        assert entry.get("supports_streaming") is True

    def test_priority_explicit_only(self, llm_models):
        entry = llm_models["models"][MERCURY_3_OPENROUTER_ID]
        assert entry.get("priority") == 99

    def test_context_window(self, llm_models):
        entry = llm_models["models"][MERCURY_3_OPENROUTER_ID]
        assert entry.get("context_window") == 1_000_000

    def test_max_output_tokens(self, llm_models):
        entry = llm_models["models"][MERCURY_3_OPENROUTER_ID]
        assert entry.get("max_output_tokens") == 131_072

    def test_input_cost_matches_tracker(self, llm_models):
        entry = llm_models["models"][MERCURY_3_OPENROUTER_ID]
        assert entry.get("input_cost_per_1m") == pytest.approx(MERCURY_3_INPUT_COST)

    def test_output_cost_matches_tracker(self, llm_models):
        entry = llm_models["models"][MERCURY_3_OPENROUTER_ID]
        assert entry.get("output_cost_per_1m") == pytest.approx(MERCURY_3_OUTPUT_COST)

    def test_not_in_recommended_priority(self, llm_models):
        recommended = llm_models.get("recommended_priority", [])
        assert MERCURY_3_OPENROUTER_ID not in recommended


# ---------------------------------------------------------------------------
# Catalogue consistency — 88 declared IDs after this change
# ---------------------------------------------------------------------------

class TestCatalogueSize:
    def test_catalogue_has_88_models(self, llm_models):
        """models.yaml should have 88 declared model entries after adding 3 new models."""
        models = llm_models.get("models", {})
        assert len(models) == 88, (
            f"Expected 88 model IDs in models.yaml, got {len(models)}. "
            "If you added or removed other models, update this count."
        )


# ---------------------------------------------------------------------------
# No new fuzzy collisions introduced
# ---------------------------------------------------------------------------

class TestNoNewFuzzyCollisions:
    """New paid IDs must not fuzzy-collide with existing free-tier (zero-cost) IDs."""

    NEW_IDS = {
        GPT61_TERRA_OPENAI_ID,
        GPT61_TERRA_OPENROUTER_ID,
        KIMI_K31_PRO_DIRECT_ID,
        KIMI_K31_PRO_OPENROUTER_ID,
        MERCURY_3_OPENROUTER_ID,
    }

    def _is_zero_cost(self, ct, model_id: str) -> bool:
        inp, out = ct._DEFAULT_COST_TABLE.get(model_id, (0.0, 0.0))
        return inp == 0.0 and out == 0.0

    def test_new_ids_are_paid(self, ct):
        for mid in self.NEW_IDS:
            assert not self._is_zero_cost(ct, mid), (
                f"{mid} is a paid model and must not be in the zero-cost table"
            )

    def test_no_undeclared_collision_with_free_models(self, ct):
        table = ct._DEFAULT_COST_TABLE
        zero_ids = {m for m, (i, o) in table.items() if i == 0.0 and o == 0.0}
        paid_ids = {m for m in table if m not in zero_ids}
        collisions = []
        for free_id in zero_ids:
            for paid_id in paid_ids:
                if free_id == paid_id:
                    continue
                if free_id in paid_id or paid_id in free_id:
                    if paid_id in self.NEW_IDS or free_id in self.NEW_IDS:
                        collisions.append((free_id, paid_id))
        assert not collisions, (
            f"New model IDs have undeclared fuzzy collisions with free-tier entries: {collisions}"
        )
