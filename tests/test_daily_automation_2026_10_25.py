"""tests/test_daily_automation_2026_10_25.py — Daily automation 2026-10-25.

Changes shipped today:
- **Gemini 4 Argon declared in model catalogue** (``gemini-4-argon`` /
  ``google/gemini-4-argon``, GA 2026-10-13). Google's most capable production
  model; designed for complex multi-step tasks and long-context work.
  Context: 1,048,576 tokens. Supports tool calling, function calling,
  structured outputs, streaming, and thinking modes (low / medium / high).
  Pricing (introductory, through 2026-11-30): $2.00/$10.00 per MTok.
  Standard rate from 2026-12-01: $4.00/$20.00 per MTok.
  Cached input: $0.10/MTok (5 % of intro input rate).
  Priority 99 (explicit-only) — unprobed on this account; lower once
  ``catalogue-probe.yml`` sees a 200.
  Available via Google Gemini API (``gemini-4-argon``) and
  OpenRouter (``google/gemini-4-argon``).
  Sources: computingforgeeks.com/gemini-4-argon-released-features-benchmarks/,
  openrouter.ai/google/gemini-4-argon, eesel.ai/blog/gemini-4-argon-pricing,
  2026-10-25.

Files changed:
  ``packages/ai/cost_tracker.py``,
  ``config/llm/models.yaml``,
  ``CHANGELOG.md``, ``docs/changelog.md``,
  ``tests/test_daily_automation_2026_10_25.py`` (this file).
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

GEMINI_4_ARGON_GOOGLE_ID = "gemini-4-argon"
GEMINI_4_ARGON_OPENROUTER_ID = "google/gemini-4-argon"
GEMINI_4_ARGON_INPUT_COST = 2.0    # introductory price through 2026-11-30
GEMINI_4_ARGON_OUTPUT_COST = 10.0
GEMINI_4_ARGON_CACHE_FRACTION = 0.05  # $0.10 / $2.00 = 5 %


@pytest.fixture(scope="module")
def ct():
    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_10_25",
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
# Cost tracker — Gemini 4 Argon Google direct ID
# ---------------------------------------------------------------------------

class TestGemini4ArgonGoogleCostTracker:
    def test_entry_exists(self, ct):
        cost = ct.cost_for_tokens(GEMINI_4_ARGON_GOOGLE_ID, 1_000_000, 0)
        assert cost is not None, f"{GEMINI_4_ARGON_GOOGLE_ID} must have a cost entry"

    def test_input_cost(self, ct):
        cost = ct.cost_for_tokens(GEMINI_4_ARGON_GOOGLE_ID, 1_000_000, 0)
        assert cost == pytest.approx(GEMINI_4_ARGON_INPUT_COST), (
            f"{GEMINI_4_ARGON_GOOGLE_ID} input cost must be ${GEMINI_4_ARGON_INPUT_COST}/MTok"
        )

    def test_output_cost(self, ct):
        cost = ct.cost_for_tokens(GEMINI_4_ARGON_GOOGLE_ID, 0, 1_000_000)
        assert cost == pytest.approx(GEMINI_4_ARGON_OUTPUT_COST), (
            f"{GEMINI_4_ARGON_GOOGLE_ID} output cost must be ${GEMINI_4_ARGON_OUTPUT_COST}/MTok"
        )

    def test_combined_cost(self, ct):
        cost = ct.cost_for_tokens(GEMINI_4_ARGON_GOOGLE_ID, 1_000_000, 1_000_000)
        assert cost == pytest.approx(GEMINI_4_ARGON_INPUT_COST + GEMINI_4_ARGON_OUTPUT_COST)

    def test_cost_is_float(self, ct):
        cost = ct.cost_for_tokens(GEMINI_4_ARGON_GOOGLE_ID, 500_000, 100_000)
        assert isinstance(cost, float)

    def test_cache_fraction_overrides_generic_gemini(self, ct):
        """gemini-4-argon must use 5 % cache fraction, not the generic 25 % for gemini-."""
        fractions = {prefix: frac for prefix, frac in ct._CACHE_READ_FRACTIONS}
        assert GEMINI_4_ARGON_GOOGLE_ID in fractions, (
            f"{GEMINI_4_ARGON_GOOGLE_ID} must have an explicit cache-read fraction "
            f"(would otherwise get the generic 'gemini-' 25 % rate)"
        )
        assert fractions[GEMINI_4_ARGON_GOOGLE_ID] == pytest.approx(
            GEMINI_4_ARGON_CACHE_FRACTION
        ), (
            f"Cache fraction must be {GEMINI_4_ARGON_CACHE_FRACTION} (5 %), "
            f"got {fractions[GEMINI_4_ARGON_GOOGLE_ID]}"
        )

    def test_cache_read_reduces_cost(self, ct):
        full_input = ct.cost_for_tokens(GEMINI_4_ARGON_GOOGLE_ID, 1_000_000, 0)
        with_cache = ct.cost_for_tokens(
            GEMINI_4_ARGON_GOOGLE_ID, 1_000_000, 0, cached_tokens=1_000_000
        )
        assert with_cache < full_input

    def test_cached_cost_is_5_percent_of_input(self, ct):
        """A fully-cached prompt should cost 5 % of the standard input rate."""
        full_input = ct.cost_for_tokens(GEMINI_4_ARGON_GOOGLE_ID, 1_000_000, 0)
        cached = ct.cost_for_tokens(
            GEMINI_4_ARGON_GOOGLE_ID, 1_000_000, 0, cached_tokens=1_000_000
        )
        assert cached == pytest.approx(full_input * GEMINI_4_ARGON_CACHE_FRACTION)

    def test_cache_override_precedes_generic_gemini_prefix(self, ct):
        """The specific 'gemini-4-argon' entry must appear before 'gemini-' in the tuple."""
        prefixes = [prefix for prefix, _ in ct._CACHE_READ_FRACTIONS]
        assert GEMINI_4_ARGON_GOOGLE_ID in prefixes
        assert "gemini-" in prefixes
        argon_pos = prefixes.index(GEMINI_4_ARGON_GOOGLE_ID)
        generic_pos = prefixes.index("gemini-")
        assert argon_pos < generic_pos, (
            "gemini-4-argon override must appear before the generic 'gemini-' fallback"
        )


# ---------------------------------------------------------------------------
# Cost tracker — Gemini 4 Argon OpenRouter ID
# ---------------------------------------------------------------------------

class TestGemini4ArgonOpenRouterCostTracker:
    def test_entry_exists(self, ct):
        cost = ct.cost_for_tokens(GEMINI_4_ARGON_OPENROUTER_ID, 1_000_000, 0)
        assert cost is not None, f"{GEMINI_4_ARGON_OPENROUTER_ID} must have a cost entry"

    def test_input_cost(self, ct):
        cost = ct.cost_for_tokens(GEMINI_4_ARGON_OPENROUTER_ID, 1_000_000, 0)
        assert cost == pytest.approx(GEMINI_4_ARGON_INPUT_COST)

    def test_output_cost(self, ct):
        cost = ct.cost_for_tokens(GEMINI_4_ARGON_OPENROUTER_ID, 0, 1_000_000)
        assert cost == pytest.approx(GEMINI_4_ARGON_OUTPUT_COST)

    def test_matches_google_id(self, ct):
        google_cost = ct.cost_for_tokens(GEMINI_4_ARGON_GOOGLE_ID, 500_000, 200_000)
        openrouter_cost = ct.cost_for_tokens(
            GEMINI_4_ARGON_OPENROUTER_ID, 500_000, 200_000
        )
        assert google_cost == pytest.approx(openrouter_cost), (
            "Google and OpenRouter IDs must have identical pricing"
        )

    def test_openrouter_cache_fraction(self, ct):
        fractions = {prefix: frac for prefix, frac in ct._CACHE_READ_FRACTIONS}
        assert GEMINI_4_ARGON_OPENROUTER_ID in fractions
        assert fractions[GEMINI_4_ARGON_OPENROUTER_ID] == pytest.approx(
            GEMINI_4_ARGON_CACHE_FRACTION
        )


# ---------------------------------------------------------------------------
# models.yaml — Gemini 4 Argon
# ---------------------------------------------------------------------------

class TestGemini4ArgonYaml:
    def test_entry_present(self, llm_models):
        models = llm_models.get("models", {})
        assert GEMINI_4_ARGON_GOOGLE_ID in models, (
            f"{GEMINI_4_ARGON_GOOGLE_ID} not found in config/llm/models.yaml"
        )

    def test_provider_openrouter(self, llm_models):
        entry = llm_models["models"][GEMINI_4_ARGON_GOOGLE_ID]
        assert entry.get("provider") == "openrouter", (
            "provider must be 'openrouter' (primary access via OpenRouter)"
        )

    def test_supports_tools(self, llm_models):
        entry = llm_models["models"][GEMINI_4_ARGON_GOOGLE_ID]
        assert entry.get("supports_tools") is True

    def test_supports_function_calling(self, llm_models):
        entry = llm_models["models"][GEMINI_4_ARGON_GOOGLE_ID]
        assert entry.get("supports_function_calling") is True

    def test_supports_streaming(self, llm_models):
        entry = llm_models["models"][GEMINI_4_ARGON_GOOGLE_ID]
        assert entry.get("supports_streaming") is True

    def test_supports_reasoning(self, llm_models):
        entry = llm_models["models"][GEMINI_4_ARGON_GOOGLE_ID]
        assert entry.get("supports_reasoning") is True, (
            "Gemini 4 Argon supports thinking modes (low/medium/high)"
        )

    def test_priority_explicit_only(self, llm_models):
        entry = llm_models["models"][GEMINI_4_ARGON_GOOGLE_ID]
        assert entry.get("priority") == 99, (
            f"{GEMINI_4_ARGON_GOOGLE_ID} must be priority 99 "
            "(explicit-only until catalogue-probe confirms it answers)"
        )

    def test_context_window(self, llm_models):
        entry = llm_models["models"][GEMINI_4_ARGON_GOOGLE_ID]
        assert entry.get("context_window") == 1_048_576, (
            "context_window must be 1,048,576 (1M)"
        )

    def test_display_name_present(self, llm_models):
        entry = llm_models["models"][GEMINI_4_ARGON_GOOGLE_ID]
        assert "display_name" in entry and entry["display_name"]

    def test_not_in_recommended_priority(self, llm_models):
        recommended = llm_models.get("recommended_priority", [])
        assert GEMINI_4_ARGON_GOOGLE_ID not in recommended, (
            f"{GEMINI_4_ARGON_GOOGLE_ID} must not be in recommended_priority (unprobed)"
        )

    def test_input_cost_matches_cost_tracker(self, llm_models):
        entry = llm_models["models"][GEMINI_4_ARGON_GOOGLE_ID]
        assert entry.get("input_cost_per_1m") == pytest.approx(GEMINI_4_ARGON_INPUT_COST)

    def test_output_cost_matches_cost_tracker(self, llm_models):
        entry = llm_models["models"][GEMINI_4_ARGON_GOOGLE_ID]
        assert entry.get("output_cost_per_1m") == pytest.approx(GEMINI_4_ARGON_OUTPUT_COST)

    def test_max_output_tokens(self, llm_models):
        entry = llm_models["models"][GEMINI_4_ARGON_GOOGLE_ID]
        assert entry.get("max_output_tokens") == 65_536, (
            "max_output_tokens must be 65,536 (default; up to 1M with long-decode)"
        )


# ---------------------------------------------------------------------------
# Catalogue consistency — 100 declared IDs after this change
# ---------------------------------------------------------------------------

class TestCatalogueSize:
    def test_catalogue_has_at_least_85_ids_including_argon(self, llm_models):
        """gemini-4-argon brought the catalogue to 85 ids. The exact current
        total is pinned by the newest daily-automation test file; pinning it
        here too made every later model addition fail this older test."""
        models = llm_models.get("models", {})
        assert "gemini-4-argon" in models
        assert len(models) >= 85, (
            f"Expected at least 85 model IDs in models.yaml, got {len(models)}."
        )


# ---------------------------------------------------------------------------
# Catalogue consistency — no new fuzzy collisions
# ---------------------------------------------------------------------------

class TestNoNewFuzzyCollisions:
    """gemini-4-argon / google/gemini-4-argon must not fuzzy-collide with any free id."""

    ARGON_IDS = {GEMINI_4_ARGON_GOOGLE_ID, GEMINI_4_ARGON_OPENROUTER_ID}

    def _is_zero_cost(self, ct, model_id: str) -> bool:
        inp, out = ct._DEFAULT_COST_TABLE.get(model_id, (0.0, 0.0))
        return inp == 0.0 and out == 0.0

    def test_google_id_is_paid(self, ct):
        assert not self._is_zero_cost(ct, GEMINI_4_ARGON_GOOGLE_ID), (
            f"{GEMINI_4_ARGON_GOOGLE_ID} is a paid model and must not be in the zero-cost table"
        )

    def test_openrouter_id_is_paid(self, ct):
        assert not self._is_zero_cost(ct, GEMINI_4_ARGON_OPENROUTER_ID), (
            f"{GEMINI_4_ARGON_OPENROUTER_ID} is a paid model and must not be in the zero-cost table"
        )

    def test_no_undeclared_collision_with_free_models(self, ct):
        """No free model id should be a substring of the new Argon IDs, or vice-versa."""
        table = ct._DEFAULT_COST_TABLE
        zero_ids = {m for m, (i, o) in table.items() if i == 0.0 and o == 0.0}
        paid_ids = {m for m in table if m not in zero_ids}
        collisions = []
        for free_id in zero_ids:
            for paid_id in paid_ids:
                if free_id == paid_id:
                    continue
                if free_id in paid_id or paid_id in free_id:
                    if paid_id in self.ARGON_IDS or free_id in self.ARGON_IDS:
                        collisions.append((free_id, paid_id))
        assert not collisions, (
            f"New Gemini 4 Argon IDs have undeclared fuzzy collisions: {collisions}"
        )
