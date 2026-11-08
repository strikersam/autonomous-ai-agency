"""tests/test_daily_automation_2026_11_06.py — Daily automation 2026-11-06.

Changes shipped today:
- **Mistral Large 4 context window and cache-read fraction** (2026-11-06).
  Two fixes to the ``mistral-large-4-0`` catalogue entry:

  1. **Context window corrected to 524288.** The entry was set to 131072
     (a conservative initial value). OpenRouter and TypingMind both expose the
     model at 524,288 tokens; Mistral's own docs note the model *supports* 1M
     but the API limit in preview is 524K. Updated in ``config/llm/models.yaml``.
     Sources: openrouter.ai/mistralai/mistral-large-4-0, custom.typingmind.com
     (2026-11-06).

  2. **Cache-read fraction added at 10 %.** Mistral Large 4 cache reads are
     billed at $0.14/MTok on a $1.36/MTok input rate ($0.14 / $1.36 ≈ 10.3 %).
     No entry existed in ``_CACHE_READ_FRACTIONS``, so cached tokens fell through
     to no discount (0 % fraction returned by the default branch). The fix adds
     ``("mistral-large-4-0", 0.10)`` before the generic fallbacks.
     Source: mistral.ai pricing page capture 2026-10-22, gradually.ai/en/ai-models/
     mistral-large-4 (2026-11-06).

  Additionally the comment on the ``mistral-large-4-0`` entry in
  ``_DEFAULT_COST_TABLE`` is updated to remove the "Preview" language and note
  the open-weights release (2026-10-29, Hugging Face, Mistral Ecosystem
  Open-Weight License).

Files changed:
  ``config/llm/models.yaml``,
  ``packages/ai/cost_tracker.py``,
  ``CHANGELOG.md``, ``docs/changelog.md``,
  ``tests/test_daily_automation_2026_11_06.py`` (this file).
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

MISTRAL_L4_ID = "mistral-large-4-0"
MISTRAL_L4_INPUT_COST = 1.36    # $1.36/MTok (standard, post-launch-sale)
MISTRAL_L4_OUTPUT_COST = 4.18   # $4.18/MTok
MISTRAL_L4_CACHE_FRACTION = 0.10  # 10 % — $0.14/MTok ÷ $1.36/MTok
MISTRAL_L4_CACHED_COST_PER_MTOKEN = round(1.36 * 0.10, 10)  # ≈ $0.136/MTok
MISTRAL_L4_CONTEXT_WINDOW = 524_288  # API-exposed limit (not the model's 1M max)


@pytest.fixture(scope="module")
def ct():
    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_11_06",
        REPO_ROOT / "packages" / "ai" / "cost_tracker.py",
    )
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture(scope="module")
def models_yaml():
    path = REPO_ROOT / "config" / "llm" / "models.yaml"
    with path.open() as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Cost table — pricing unchanged, comment updated
# ---------------------------------------------------------------------------

class TestMistralLarge4CostTable:
    def test_input_cost_unchanged(self, ct):
        cost = ct.cost_for_tokens(MISTRAL_L4_ID, 1_000_000, 0)
        assert cost == pytest.approx(MISTRAL_L4_INPUT_COST), (
            f"{MISTRAL_L4_ID} input cost must remain ${MISTRAL_L4_INPUT_COST}/MTok"
        )

    def test_output_cost_unchanged(self, ct):
        cost = ct.cost_for_tokens(MISTRAL_L4_ID, 0, 1_000_000)
        assert cost == pytest.approx(MISTRAL_L4_OUTPUT_COST), (
            f"{MISTRAL_L4_ID} output cost must remain ${MISTRAL_L4_OUTPUT_COST}/MTok"
        )

    def test_id_in_cost_table(self, ct):
        table = dict(ct._DEFAULT_COST_TABLE)
        assert MISTRAL_L4_ID in table, (
            f"{MISTRAL_L4_ID} must be present in _DEFAULT_COST_TABLE"
        )


# ---------------------------------------------------------------------------
# Cache-read fraction — the core change
# ---------------------------------------------------------------------------

class TestMistralLarge4CacheFraction:
    def test_explicit_override_exists(self, ct):
        """mistral-large-4-0 must have an explicit 10 % override."""
        fractions = {prefix: frac for prefix, frac in ct._CACHE_READ_FRACTIONS}
        assert MISTRAL_L4_ID in fractions, (
            f"{MISTRAL_L4_ID} must have an explicit cache-read fraction entry; "
            "without it cached tokens fall to 0 % (no discount applied)."
        )

    def test_cache_fraction_is_ten_percent(self, ct):
        fractions = {prefix: frac for prefix, frac in ct._CACHE_READ_FRACTIONS}
        assert fractions[MISTRAL_L4_ID] == pytest.approx(MISTRAL_L4_CACHE_FRACTION), (
            f"Cache fraction must be 0.10 (10 %), got {fractions[MISTRAL_L4_ID]}"
        )

    def test_cache_read_reduces_cost(self, ct):
        full_input = ct.cost_for_tokens(MISTRAL_L4_ID, 1_000_000, 0)
        with_cache = ct.cost_for_tokens(
            MISTRAL_L4_ID, 1_000_000, 0, cached_tokens=1_000_000
        )
        assert with_cache < full_input

    def test_cached_cost_is_ten_percent_of_input(self, ct):
        full_input = ct.cost_for_tokens(MISTRAL_L4_ID, 1_000_000, 0)
        cached = ct.cost_for_tokens(
            MISTRAL_L4_ID, 1_000_000, 0, cached_tokens=1_000_000
        )
        assert cached == pytest.approx(full_input * MISTRAL_L4_CACHE_FRACTION), (
            f"Expected {full_input * MISTRAL_L4_CACHE_FRACTION} (10 % of full input), "
            f"got {cached}"
        )

    def test_cached_cost_absolute_value(self, ct):
        """Fully-cached 1M tokens: 10 % × $1.36/MTok ≈ $0.136."""
        cached = ct.cost_for_tokens(
            MISTRAL_L4_ID, 1_000_000, 0, cached_tokens=1_000_000
        )
        assert cached == pytest.approx(MISTRAL_L4_CACHED_COST_PER_MTOKEN, rel=1e-3), (
            f"Expected ≈ $0.136/MTok cache-read cost, got ${cached}"
        )

    def test_not_zero(self, ct):
        """Regression: before the fix cached tokens had no discount (fell to 0%)."""
        cached = ct.cost_for_tokens(
            MISTRAL_L4_ID, 1_000_000, 0, cached_tokens=1_000_000
        )
        full = ct.cost_for_tokens(MISTRAL_L4_ID, 1_000_000, 0)
        # cached should be significantly less than full but not zero
        assert cached > 0, "Cached cost must not be zero"
        assert cached < full, "Cached cost must be less than full input cost"


# ---------------------------------------------------------------------------
# Context window in models.yaml — the second change
# ---------------------------------------------------------------------------

class TestMistralLarge4ContextWindow:
    def test_context_window_is_524288(self, models_yaml):
        entry = models_yaml.get("models", {}).get(MISTRAL_L4_ID)
        if entry is None:
            # Try top-level key (some YAML files have flat structure)
            entry = models_yaml.get(MISTRAL_L4_ID)
        assert entry is not None, (
            f"{MISTRAL_L4_ID} must be declared in config/llm/models.yaml"
        )
        ctx = entry.get("context_window")
        assert ctx == MISTRAL_L4_CONTEXT_WINDOW, (
            f"context_window must be {MISTRAL_L4_CONTEXT_WINDOW} (API-exposed limit); "
            f"got {ctx}. The model supports 1M tokens but the API preview serves 524K."
        )

    def test_context_window_not_old_value(self, models_yaml):
        entry = models_yaml.get("models", {}).get(MISTRAL_L4_ID)
        if entry is None:
            entry = models_yaml.get(MISTRAL_L4_ID)
        assert entry is not None
        ctx = entry.get("context_window")
        assert ctx != 131072, (
            "context_window must not be the old conservative value of 131072; "
            "it has been confirmed at 524288 via OpenRouter and TypingMind."
        )


# ---------------------------------------------------------------------------
# No regression on other Mistral models
# ---------------------------------------------------------------------------

class TestOtherMistralModelsUnchanged:
    def test_mistral_large_latest_cost(self, ct):
        cost = ct.cost_for_tokens("mistral-large-latest", 1_000_000, 0)
        assert cost == pytest.approx(3.00), "mistral-large-latest must remain $3.00/MTok"

    def test_mistral_small_latest_cost(self, ct):
        cost = ct.cost_for_tokens("mistral-small-latest", 1_000_000, 0)
        assert cost == pytest.approx(0.10), "mistral-small-latest must remain $0.10/MTok"

    def test_fractions_tuple_is_valid(self, ct):
        for prefix, frac in ct._CACHE_READ_FRACTIONS:
            assert isinstance(prefix, str) and len(prefix) > 0
            assert 0.0 < frac <= 1.0, (
                f"All cache fractions must be in (0, 1]; got {frac} for '{prefix}'"
            )
