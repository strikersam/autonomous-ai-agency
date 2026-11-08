"""tests/test_daily_automation_2026_11_08.py — Daily automation 2026-11-08.

Changes shipped today:
- **DeepSeek V4 Flash 0731 on OpenRouter** (``deepseek/deepseek-v4-flash-0731``,
  released 2026-07-31; appeared on OpenRouter early November 2026).
  1,048,576-token context. Pricing: $0.090/$0.180 per MTok.
  Sources: openrouter.ai/deepseek/deepseek-v4-flash-0731,
           pi.dev/models/openrouter/deepseek-deepseek-v4-flash-0731, 2026-11-08.

- **Mistral Large 4 OpenRouter alias** (``mistralai/mistral-large-4-0``).
  OpenRouter router ID for the existing ``mistral-large-4-0`` Mistral API entry.
  Same pricing: $1.36/$4.18 per MTok.
  Source: openrouter.ai/mistralai/mistral-large-4-0, 2026-11-08.

- **Google Gemini Omni 1.2 Flash on OpenRouter** (``google/gemini-omni-1.2-flash``,
  released 2026-11-05). Multimodal video model — text+image+video input,
  text+video output. 131,072-token context. No tool/function calling support.
  Pricing: $1.50/$9.00 per MTok; cache reads at 25 % of input rate.
  Sources: openrouter.ai/google/gemini-omni-1.2-flash,
           letsdatascience.com/news/google-launches-gemini-omni-12-flash*, 2026-11-08.

Files changed:
  ``packages/ai/cost_tracker.py``,
  ``CHANGELOG.md``, ``docs/changelog.md``,
  ``tests/test_daily_automation_2026_11_08.py`` (this file).
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# DeepSeek V4 Flash 0731 (OpenRouter)
DEEPSEEK_V4_FLASH_ID = "deepseek/deepseek-v4-flash-0731"
DEEPSEEK_V4_FLASH_INPUT_COST = 0.090
DEEPSEEK_V4_FLASH_OUTPUT_COST = 0.180

# Mistral Large 4 (OpenRouter alias)
MISTRAL_LARGE_4_DIRECT_ID = "mistral-large-4-0"
MISTRAL_LARGE_4_OPENROUTER_ID = "mistralai/mistral-large-4-0"
MISTRAL_LARGE_4_INPUT_COST = 1.36
MISTRAL_LARGE_4_OUTPUT_COST = 4.18

# Gemini Omni 1.2 Flash (OpenRouter)
GEMINI_OMNI_12_ID = "google/gemini-omni-1.2-flash"
GEMINI_OMNI_12_INPUT_COST = 1.50
GEMINI_OMNI_12_OUTPUT_COST = 9.00
GEMINI_OMNI_12_CACHE_FRACTION = 0.25


@pytest.fixture(scope="module")
def ct():
    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_11_08",
        REPO_ROOT / "packages" / "ai" / "cost_tracker.py",
    )
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# DeepSeek V4 Flash 0731 — cost tracker
# ---------------------------------------------------------------------------

class TestDeepSeekV4Flash0731CostTracker:
    def test_entry_exists(self, ct):
        cost = ct.cost_for_tokens(DEEPSEEK_V4_FLASH_ID, 1_000_000, 0)
        assert cost is not None

    def test_input_cost(self, ct):
        cost = ct.cost_for_tokens(DEEPSEEK_V4_FLASH_ID, 1_000_000, 0)
        assert cost == pytest.approx(DEEPSEEK_V4_FLASH_INPUT_COST), (
            f"{DEEPSEEK_V4_FLASH_ID} input must be ${DEEPSEEK_V4_FLASH_INPUT_COST}/MTok"
        )

    def test_output_cost(self, ct):
        cost = ct.cost_for_tokens(DEEPSEEK_V4_FLASH_ID, 0, 1_000_000)
        assert cost == pytest.approx(DEEPSEEK_V4_FLASH_OUTPUT_COST), (
            f"{DEEPSEEK_V4_FLASH_ID} output must be ${DEEPSEEK_V4_FLASH_OUTPUT_COST}/MTok"
        )

    def test_is_paid_model(self, ct):
        inp, out = ct._DEFAULT_COST_TABLE.get(DEEPSEEK_V4_FLASH_ID, (0.0, 0.0))
        assert inp > 0.0 and out > 0.0, (
            f"{DEEPSEEK_V4_FLASH_ID} must be a paid cost-table entry"
        )

    def test_combined_cost(self, ct):
        cost = ct.cost_for_tokens(DEEPSEEK_V4_FLASH_ID, 500_000, 200_000)
        expected = (DEEPSEEK_V4_FLASH_INPUT_COST * 0.5) + (DEEPSEEK_V4_FLASH_OUTPUT_COST * 0.2)
        assert cost == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Mistral Large 4 OpenRouter alias — cost tracker
# ---------------------------------------------------------------------------

class TestMistralLarge4OpenRouterAlias:
    def test_entry_exists(self, ct):
        cost = ct.cost_for_tokens(MISTRAL_LARGE_4_OPENROUTER_ID, 1_000_000, 0)
        assert cost is not None

    def test_input_cost(self, ct):
        cost = ct.cost_for_tokens(MISTRAL_LARGE_4_OPENROUTER_ID, 1_000_000, 0)
        assert cost == pytest.approx(MISTRAL_LARGE_4_INPUT_COST), (
            f"{MISTRAL_LARGE_4_OPENROUTER_ID} input must be ${MISTRAL_LARGE_4_INPUT_COST}/MTok"
        )

    def test_output_cost(self, ct):
        cost = ct.cost_for_tokens(MISTRAL_LARGE_4_OPENROUTER_ID, 0, 1_000_000)
        assert cost == pytest.approx(MISTRAL_LARGE_4_OUTPUT_COST), (
            f"{MISTRAL_LARGE_4_OPENROUTER_ID} output must be ${MISTRAL_LARGE_4_OUTPUT_COST}/MTok"
        )

    def test_matches_direct_id(self, ct):
        direct = ct.cost_for_tokens(MISTRAL_LARGE_4_DIRECT_ID, 500_000, 200_000)
        openrouter = ct.cost_for_tokens(MISTRAL_LARGE_4_OPENROUTER_ID, 500_000, 200_000)
        assert direct == pytest.approx(openrouter), (
            "mistralai/mistral-large-4-0 must cost the same as mistral-large-4-0"
        )

    def test_is_paid_model(self, ct):
        inp, out = ct._DEFAULT_COST_TABLE.get(MISTRAL_LARGE_4_OPENROUTER_ID, (0.0, 0.0))
        assert inp > 0.0 and out > 0.0, (
            f"{MISTRAL_LARGE_4_OPENROUTER_ID} must be a paid cost-table entry"
        )

    def test_combined_cost(self, ct):
        cost = ct.cost_for_tokens(MISTRAL_LARGE_4_OPENROUTER_ID, 200_000, 50_000)
        expected = (MISTRAL_LARGE_4_INPUT_COST * 0.2) + (MISTRAL_LARGE_4_OUTPUT_COST * 0.05)
        assert cost == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Gemini Omni 1.2 Flash (OpenRouter) — cost tracker
# ---------------------------------------------------------------------------

class TestGeminiOmni12FlashCostTracker:
    def test_entry_exists(self, ct):
        cost = ct.cost_for_tokens(GEMINI_OMNI_12_ID, 1_000_000, 0)
        assert cost is not None

    def test_input_cost(self, ct):
        cost = ct.cost_for_tokens(GEMINI_OMNI_12_ID, 1_000_000, 0)
        assert cost == pytest.approx(GEMINI_OMNI_12_INPUT_COST), (
            f"{GEMINI_OMNI_12_ID} input must be ${GEMINI_OMNI_12_INPUT_COST}/MTok"
        )

    def test_output_cost(self, ct):
        cost = ct.cost_for_tokens(GEMINI_OMNI_12_ID, 0, 1_000_000)
        assert cost == pytest.approx(GEMINI_OMNI_12_OUTPUT_COST), (
            f"{GEMINI_OMNI_12_ID} output must be ${GEMINI_OMNI_12_OUTPUT_COST}/MTok"
        )

    def test_is_paid_model(self, ct):
        inp, out = ct._DEFAULT_COST_TABLE.get(GEMINI_OMNI_12_ID, (0.0, 0.0))
        assert inp > 0.0 and out > 0.0, (
            f"{GEMINI_OMNI_12_ID} must be a paid cost-table entry"
        )

    def test_cache_fraction(self, ct):
        fraction = ct._cache_read_fraction(GEMINI_OMNI_12_ID)
        assert fraction == pytest.approx(GEMINI_OMNI_12_CACHE_FRACTION), (
            f"{GEMINI_OMNI_12_ID} cache-read fraction must be {GEMINI_OMNI_12_CACHE_FRACTION}"
        )

    def test_combined_cost(self, ct):
        cost = ct.cost_for_tokens(GEMINI_OMNI_12_ID, 200_000, 50_000)
        expected = (GEMINI_OMNI_12_INPUT_COST * 0.2) + (GEMINI_OMNI_12_OUTPUT_COST * 0.05)
        assert cost == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Catalogue-level invariants
# ---------------------------------------------------------------------------

class TestCatalogueInvariants:
    def test_all_new_ids_present(self, ct):
        ids = set(ct._DEFAULT_COST_TABLE.keys())
        for model_id in (
            DEEPSEEK_V4_FLASH_ID,
            MISTRAL_LARGE_4_OPENROUTER_ID,
            GEMINI_OMNI_12_ID,
        ):
            assert model_id in ids, f"{model_id} missing from cost table"

    def test_new_paid_ids_not_zero_cost(self, ct):
        for model_id in (
            DEEPSEEK_V4_FLASH_ID,
            MISTRAL_LARGE_4_OPENROUTER_ID,
            GEMINI_OMNI_12_ID,
        ):
            inp, out = ct._DEFAULT_COST_TABLE.get(model_id, (0.0, 0.0))
            assert inp > 0.0 and out > 0.0, (
                f"{model_id} must not be a zero-cost (free) entry"
            )

    def test_no_new_fuzzy_collision(self, ct):
        """Verify no new fuzzy collisions were introduced for the new paid IDs."""
        new_paid = {
            DEEPSEEK_V4_FLASH_ID,
            MISTRAL_LARGE_4_OPENROUTER_ID,
            GEMINI_OMNI_12_ID,
        }
        zero_keys = [k for k, v in ct._DEFAULT_COST_TABLE.items() if v == (0.0, 0.0)]
        for nk in new_paid:
            nk_l = nk.lower()
            for zk in zero_keys:
                zk_l = zk.lower()
                if nk_l in zk_l or zk_l in nk_l:
                    pytest.fail(
                        f"New paid model '{nk}' has a fuzzy substring collision with "
                        f"free model '{zk}' — add to KNOWN_SAME_MODEL_DIFFERENT_PROVIDER "
                        f"if this is intentional."
                    )
