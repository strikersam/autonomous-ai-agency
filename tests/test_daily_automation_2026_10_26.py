"""tests/test_daily_automation_2026_10_26.py — Daily automation 2026-10-26.

Changes shipped today:
- **Kimi K3.1 Pro declared in model catalogue** (``kimi-k3.1-pro`` /
  ``moonshotai/kimi-k3.1-pro``, released 2026-10-23). First model in Moonshot
  AI's new K3.1 series. Context: 1,048,576 tokens. Supports function calling,
  JSON mode, streaming, and thinking mode (always on; disabling it → HTTP 400).
  Pricing: $2.00/$10.00 per MTok; cached input $0.20/MTok (10 %).
  Highspeed variant (``kimi-k3.1-pro-highspeed``): $4.00/$20.00 per MTok;
  cached $0.20/MTok (5 %).
  Priority 99 (explicit-only) — unprobed on this account; lower once
  ``catalogue-probe.yml`` sees a 200.
  Available via Moonshot API (``kimi-k3.1-pro``, ``kimi-k3.1-pro-highspeed``)
  and OpenRouter (``moonshotai/kimi-k3.1-pro``).
  Sources: unite.ai/moonshot-ai-releases-kimi-k3-1-pro-first-model-in-new-k3-1-series/,
  openrouter.ai/moonshotai/kimi-k3.1-pro, 2026-10-26.

Files changed:
  ``packages/ai/cost_tracker.py``,
  ``config/llm/models.yaml``,
  ``CHANGELOG.md``, ``docs/changelog.md``,
  ``tests/test_daily_automation_2026_10_26.py`` (this file).
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

KIMI_K31_PRO_MOONSHOT_ID = "kimi-k3.1-pro"
KIMI_K31_PRO_HIGHSPEED_ID = "kimi-k3.1-pro-highspeed"
KIMI_K31_PRO_OPENROUTER_ID = "moonshotai/kimi-k3.1-pro"

KIMI_K31_PRO_INPUT_COST = 2.0
KIMI_K31_PRO_OUTPUT_COST = 10.0
KIMI_K31_PRO_CACHE_FRACTION = 0.10   # $0.20 / $2.00 = 10 %

KIMI_K31_PRO_HIGHSPEED_INPUT_COST = 4.0
KIMI_K31_PRO_HIGHSPEED_OUTPUT_COST = 20.0
KIMI_K31_PRO_HIGHSPEED_CACHE_FRACTION = 0.05  # $0.20 / $4.00 = 5 %


@pytest.fixture(scope="module")
def ct():
    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_10_26",
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
# Cost tracker — Kimi K3.1 Pro (Moonshot direct)
# ---------------------------------------------------------------------------

class TestKimiK31ProMoonshotCostTracker:
    def test_entry_exists(self, ct):
        cost = ct.cost_for_tokens(KIMI_K31_PRO_MOONSHOT_ID, 1_000_000, 0)
        assert cost is not None, f"{KIMI_K31_PRO_MOONSHOT_ID} must have a cost entry"

    def test_input_cost(self, ct):
        cost = ct.cost_for_tokens(KIMI_K31_PRO_MOONSHOT_ID, 1_000_000, 0)
        assert cost == pytest.approx(KIMI_K31_PRO_INPUT_COST), (
            f"{KIMI_K31_PRO_MOONSHOT_ID} input cost must be ${KIMI_K31_PRO_INPUT_COST}/MTok"
        )

    def test_output_cost(self, ct):
        cost = ct.cost_for_tokens(KIMI_K31_PRO_MOONSHOT_ID, 0, 1_000_000)
        assert cost == pytest.approx(KIMI_K31_PRO_OUTPUT_COST), (
            f"{KIMI_K31_PRO_MOONSHOT_ID} output cost must be ${KIMI_K31_PRO_OUTPUT_COST}/MTok"
        )

    def test_combined_cost(self, ct):
        cost = ct.cost_for_tokens(KIMI_K31_PRO_MOONSHOT_ID, 1_000_000, 1_000_000)
        assert cost == pytest.approx(
            KIMI_K31_PRO_INPUT_COST + KIMI_K31_PRO_OUTPUT_COST
        )

    def test_cost_is_float(self, ct):
        cost = ct.cost_for_tokens(KIMI_K31_PRO_MOONSHOT_ID, 500_000, 100_000)
        assert isinstance(cost, float)

    def test_cache_fraction_present(self, ct):
        fractions = {prefix: frac for prefix, frac in ct._CACHE_READ_FRACTIONS}
        assert KIMI_K31_PRO_MOONSHOT_ID in fractions, (
            f"{KIMI_K31_PRO_MOONSHOT_ID} must have an explicit cache-read fraction"
        )

    def test_cache_fraction_value(self, ct):
        fractions = {prefix: frac for prefix, frac in ct._CACHE_READ_FRACTIONS}
        assert fractions[KIMI_K31_PRO_MOONSHOT_ID] == pytest.approx(
            KIMI_K31_PRO_CACHE_FRACTION
        ), (
            f"Cache fraction must be {KIMI_K31_PRO_CACHE_FRACTION} (10 %), "
            f"got {fractions.get(KIMI_K31_PRO_MOONSHOT_ID)}"
        )

    def test_cache_read_reduces_cost(self, ct):
        full_input = ct.cost_for_tokens(KIMI_K31_PRO_MOONSHOT_ID, 1_000_000, 0)
        with_cache = ct.cost_for_tokens(
            KIMI_K31_PRO_MOONSHOT_ID, 1_000_000, 0, cached_tokens=1_000_000
        )
        assert with_cache < full_input

    def test_cached_cost_is_10_percent_of_input(self, ct):
        full_input = ct.cost_for_tokens(KIMI_K31_PRO_MOONSHOT_ID, 1_000_000, 0)
        cached = ct.cost_for_tokens(
            KIMI_K31_PRO_MOONSHOT_ID, 1_000_000, 0, cached_tokens=1_000_000
        )
        assert cached == pytest.approx(full_input * KIMI_K31_PRO_CACHE_FRACTION)

    def test_cheaper_than_kimi_k3(self, ct):
        """K3.1 Pro ($2 input) is cheaper than the original K3 ($3 input)."""
        k31_cost = ct.cost_for_tokens(KIMI_K31_PRO_MOONSHOT_ID, 1_000_000, 0)
        k3_cost = ct.cost_for_tokens("kimi-k3", 1_000_000, 0)
        assert k31_cost < k3_cost, "Kimi K3.1 Pro input must be cheaper than Kimi K3"


# ---------------------------------------------------------------------------
# Cost tracker — Kimi K3.1 Pro Highspeed
# ---------------------------------------------------------------------------

class TestKimiK31ProHighspeedCostTracker:
    def test_entry_exists(self, ct):
        cost = ct.cost_for_tokens(KIMI_K31_PRO_HIGHSPEED_ID, 1_000_000, 0)
        assert cost is not None, f"{KIMI_K31_PRO_HIGHSPEED_ID} must have a cost entry"

    def test_input_cost(self, ct):
        cost = ct.cost_for_tokens(KIMI_K31_PRO_HIGHSPEED_ID, 1_000_000, 0)
        assert cost == pytest.approx(KIMI_K31_PRO_HIGHSPEED_INPUT_COST), (
            f"{KIMI_K31_PRO_HIGHSPEED_ID} input cost must be "
            f"${KIMI_K31_PRO_HIGHSPEED_INPUT_COST}/MTok"
        )

    def test_output_cost(self, ct):
        cost = ct.cost_for_tokens(KIMI_K31_PRO_HIGHSPEED_ID, 0, 1_000_000)
        assert cost == pytest.approx(KIMI_K31_PRO_HIGHSPEED_OUTPUT_COST)

    def test_more_expensive_than_standard(self, ct):
        """Highspeed tier costs 2× more than standard."""
        standard_cost = ct.cost_for_tokens(KIMI_K31_PRO_MOONSHOT_ID, 1_000_000, 1_000_000)
        highspeed_cost = ct.cost_for_tokens(KIMI_K31_PRO_HIGHSPEED_ID, 1_000_000, 1_000_000)
        assert highspeed_cost == pytest.approx(standard_cost * 2.0)

    def test_highspeed_cache_fraction(self, ct):
        fractions = {prefix: frac for prefix, frac in ct._CACHE_READ_FRACTIONS}
        assert KIMI_K31_PRO_HIGHSPEED_ID in fractions, (
            f"{KIMI_K31_PRO_HIGHSPEED_ID} must have an explicit cache-read fraction"
        )
        assert fractions[KIMI_K31_PRO_HIGHSPEED_ID] == pytest.approx(
            KIMI_K31_PRO_HIGHSPEED_CACHE_FRACTION
        )

    def test_highspeed_fraction_before_standard(self, ct):
        """highspeed must appear before kimi-k3.1-pro in the fractions tuple (more specific first)."""
        prefixes = [prefix for prefix, _ in ct._CACHE_READ_FRACTIONS]
        assert KIMI_K31_PRO_HIGHSPEED_ID in prefixes
        assert KIMI_K31_PRO_MOONSHOT_ID in prefixes
        highspeed_pos = prefixes.index(KIMI_K31_PRO_HIGHSPEED_ID)
        standard_pos = prefixes.index(KIMI_K31_PRO_MOONSHOT_ID)
        assert highspeed_pos < standard_pos, (
            "kimi-k3.1-pro-highspeed must appear before kimi-k3.1-pro in fractions"
        )


# ---------------------------------------------------------------------------
# Cost tracker — Kimi K3.1 Pro OpenRouter ID
# ---------------------------------------------------------------------------

class TestKimiK31ProOpenRouterCostTracker:
    def test_entry_exists(self, ct):
        cost = ct.cost_for_tokens(KIMI_K31_PRO_OPENROUTER_ID, 1_000_000, 0)
        assert cost is not None, f"{KIMI_K31_PRO_OPENROUTER_ID} must have a cost entry"

    def test_input_cost_matches_moonshot(self, ct):
        moonshot_cost = ct.cost_for_tokens(KIMI_K31_PRO_MOONSHOT_ID, 1_000_000, 0)
        openrouter_cost = ct.cost_for_tokens(KIMI_K31_PRO_OPENROUTER_ID, 1_000_000, 0)
        assert moonshot_cost == pytest.approx(openrouter_cost), (
            "Moonshot and OpenRouter IDs must have identical input pricing"
        )

    def test_output_cost_matches_moonshot(self, ct):
        moonshot_cost = ct.cost_for_tokens(KIMI_K31_PRO_MOONSHOT_ID, 0, 1_000_000)
        openrouter_cost = ct.cost_for_tokens(KIMI_K31_PRO_OPENROUTER_ID, 0, 1_000_000)
        assert moonshot_cost == pytest.approx(openrouter_cost)

    def test_openrouter_cache_fraction(self, ct):
        fractions = {prefix: frac for prefix, frac in ct._CACHE_READ_FRACTIONS}
        assert KIMI_K31_PRO_OPENROUTER_ID in fractions
        assert fractions[KIMI_K31_PRO_OPENROUTER_ID] == pytest.approx(
            KIMI_K31_PRO_CACHE_FRACTION
        )


# ---------------------------------------------------------------------------
# models.yaml — Kimi K3.1 Pro
# ---------------------------------------------------------------------------

class TestKimiK31ProYaml:
    def test_entry_present(self, llm_models):
        models = llm_models.get("models", {})
        assert KIMI_K31_PRO_MOONSHOT_ID in models, (
            f"{KIMI_K31_PRO_MOONSHOT_ID} not found in config/llm/models.yaml"
        )

    def test_provider_moonshot(self, llm_models):
        entry = llm_models["models"][KIMI_K31_PRO_MOONSHOT_ID]
        assert entry.get("provider") == "moonshot", (
            "provider must be 'moonshot' (Moonshot AI direct API)"
        )

    def test_supports_tools(self, llm_models):
        entry = llm_models["models"][KIMI_K31_PRO_MOONSHOT_ID]
        assert entry.get("supports_tools") is True

    def test_supports_function_calling(self, llm_models):
        entry = llm_models["models"][KIMI_K31_PRO_MOONSHOT_ID]
        assert entry.get("supports_function_calling") is True

    def test_supports_streaming(self, llm_models):
        entry = llm_models["models"][KIMI_K31_PRO_MOONSHOT_ID]
        assert entry.get("supports_streaming") is True

    def test_supports_reasoning(self, llm_models):
        entry = llm_models["models"][KIMI_K31_PRO_MOONSHOT_ID]
        assert entry.get("supports_reasoning") is True, (
            "Kimi K3.1 Pro supports thinking mode (always on)"
        )

    def test_priority_explicit_only(self, llm_models):
        entry = llm_models["models"][KIMI_K31_PRO_MOONSHOT_ID]
        assert entry.get("priority") == 99, (
            f"{KIMI_K31_PRO_MOONSHOT_ID} must be priority 99 "
            "(explicit-only until catalogue-probe confirms it answers)"
        )

    def test_context_window(self, llm_models):
        entry = llm_models["models"][KIMI_K31_PRO_MOONSHOT_ID]
        assert entry.get("context_window") == 1_048_576, (
            "context_window must be 1,048,576 (1M)"
        )

    def test_display_name_present(self, llm_models):
        entry = llm_models["models"][KIMI_K31_PRO_MOONSHOT_ID]
        assert "display_name" in entry and entry["display_name"]

    def test_not_in_recommended_priority(self, llm_models):
        recommended = llm_models.get("recommended_priority", [])
        assert KIMI_K31_PRO_MOONSHOT_ID not in recommended, (
            f"{KIMI_K31_PRO_MOONSHOT_ID} must not be in recommended_priority (unprobed)"
        )

    def test_input_cost_matches_cost_tracker(self, llm_models):
        entry = llm_models["models"][KIMI_K31_PRO_MOONSHOT_ID]
        assert entry.get("input_cost_per_1m") == pytest.approx(KIMI_K31_PRO_INPUT_COST)

    def test_output_cost_matches_cost_tracker(self, llm_models):
        entry = llm_models["models"][KIMI_K31_PRO_MOONSHOT_ID]
        assert entry.get("output_cost_per_1m") == pytest.approx(KIMI_K31_PRO_OUTPUT_COST)

    def test_cheaper_than_kimi_k3_in_yaml(self, llm_models):
        """K3.1 Pro input cost ($2) must be less than Kimi K3 input cost ($3)."""
        k31 = llm_models["models"][KIMI_K31_PRO_MOONSHOT_ID]
        k3 = llm_models["models"].get("kimi-k3", {})
        assert k31.get("input_cost_per_1m", 0) < k3.get("input_cost_per_1m", 0), (
            "Kimi K3.1 Pro input cost must be lower than Kimi K3"
        )


# ---------------------------------------------------------------------------
# Catalogue size — 86 entries after adding kimi-k3.1-pro
# ---------------------------------------------------------------------------

class TestCatalogueSize:
    def test_catalogue_has_86_ids(self, llm_models):
        """models.yaml should have 86 declared model entries after adding kimi-k3.1-pro."""
        models = llm_models.get("models", {})
        assert len(models) == 86, (
            f"Expected 86 model IDs in models.yaml, got {len(models)}. "
            "If you added or removed other models, update this count."
        )


# ---------------------------------------------------------------------------
# No new fuzzy collisions
# ---------------------------------------------------------------------------

class TestNoNewFuzzyCollisions:
    """kimi-k3.1-pro / kimi-k3.1-pro-highspeed / moonshotai/kimi-k3.1-pro
    must not introduce undeclared substring collisions with free-tier ids."""

    NEW_IDS = {KIMI_K31_PRO_MOONSHOT_ID, KIMI_K31_PRO_HIGHSPEED_ID, KIMI_K31_PRO_OPENROUTER_ID}

    def _is_zero_cost(self, ct, model_id: str) -> bool:
        inp, out = ct._DEFAULT_COST_TABLE.get(model_id, (0.0, 0.0))
        return inp == 0.0 and out == 0.0

    def test_moonshot_id_is_paid(self, ct):
        assert not self._is_zero_cost(ct, KIMI_K31_PRO_MOONSHOT_ID)

    def test_highspeed_id_is_paid(self, ct):
        assert not self._is_zero_cost(ct, KIMI_K31_PRO_HIGHSPEED_ID)

    def test_openrouter_id_is_paid(self, ct):
        assert not self._is_zero_cost(ct, KIMI_K31_PRO_OPENROUTER_ID)

    def test_no_undeclared_collision_with_free_models(self, ct):
        """No free model id should be a substring of the new K3.1 IDs, or vice-versa."""
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
            f"New Kimi K3.1 Pro IDs have undeclared fuzzy collisions: {collisions}"
        )
