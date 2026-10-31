"""tests/test_daily_automation_2026_10_24.py — Daily automation 2026-10-24.

Changes shipped today:
- **Meta Muse Wonder declared in model catalogue** (``muse-wonder-1.0`` /
  ``meta/muse-wonder``, released 2026-10-12). Meta's first pay-as-you-go
  frontier model, built for agentic coding: long tool-use chains, multi-step
  debugging, large-repository work. Served by Meta's Model API; reachable via
  OpenRouter as ``meta/muse-wonder``.
  Context: 1,048,576 tokens. Supports function calling, streaming, JSON mode.
  Pricing: $4.00/$20.00 per MTok; cached input $0.20/MTok (5 % of input rate).
  Priority 99 (explicit-only) — preview tier; Meta is the only OpenRouter host;
  lower once ``catalogue-probe.yml`` sees a 200 on this account.
  Sources: openrouter.ai/meta/muse-wonder,
  computeprices.com/providers/openrouter/models/muse-wonder,
  eesel.ai/blog/meta-muse-wonder, 2026-10-24.

Files changed:
  ``packages/ai/cost_tracker.py``,
  ``config/llm/models.yaml``,
  ``CHANGELOG.md``, ``docs/changelog.md``,
  ``tests/test_daily_automation_2026_10_24.py`` (this file).
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

MUSE_WONDER_CANONICAL_ID = "muse-wonder-1.0"
MUSE_WONDER_OPENROUTER_ID = "meta/muse-wonder"
MUSE_WONDER_INPUT_COST = 4.0
MUSE_WONDER_OUTPUT_COST = 20.0
MUSE_WONDER_CACHE_FRACTION = 0.05  # $0.20 / $4.00


@pytest.fixture(scope="module")
def ct():
    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_10_24",
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
# Cost tracker — Muse Wonder canonical ID
# ---------------------------------------------------------------------------

class TestMuseWonderCanonicalCostTracker:
    def test_entry_exists(self, ct):
        cost = ct.cost_for_tokens(MUSE_WONDER_CANONICAL_ID, 1_000_000, 0)
        assert cost is not None, f"{MUSE_WONDER_CANONICAL_ID} must have a cost entry"

    def test_input_cost(self, ct):
        cost = ct.cost_for_tokens(MUSE_WONDER_CANONICAL_ID, 1_000_000, 0)
        assert cost == pytest.approx(MUSE_WONDER_INPUT_COST), (
            f"{MUSE_WONDER_CANONICAL_ID} input cost must be ${MUSE_WONDER_INPUT_COST}/MTok"
        )

    def test_output_cost(self, ct):
        cost = ct.cost_for_tokens(MUSE_WONDER_CANONICAL_ID, 0, 1_000_000)
        assert cost == pytest.approx(MUSE_WONDER_OUTPUT_COST), (
            f"{MUSE_WONDER_CANONICAL_ID} output cost must be ${MUSE_WONDER_OUTPUT_COST}/MTok"
        )

    def test_combined_cost(self, ct):
        cost = ct.cost_for_tokens(MUSE_WONDER_CANONICAL_ID, 1_000_000, 1_000_000)
        assert cost == pytest.approx(MUSE_WONDER_INPUT_COST + MUSE_WONDER_OUTPUT_COST)

    def test_cost_is_float(self, ct):
        cost = ct.cost_for_tokens(MUSE_WONDER_CANONICAL_ID, 500_000, 100_000)
        assert isinstance(cost, float)

    def test_cache_read_fraction_applies(self, ct):
        """Cache reads are 5 % of input rate ($0.20/$4.00)."""
        full_input = ct.cost_for_tokens(MUSE_WONDER_CANONICAL_ID, 1_000_000, 0)
        with_cache = ct.cost_for_tokens(
            MUSE_WONDER_CANONICAL_ID, 1_000_000, 0, cached_tokens=1_000_000
        )
        # A cache hit on the full prompt should reduce cost below the full rate.
        assert with_cache < full_input

    def test_cache_fraction_value(self, ct):
        """Cache read fraction must be 0.05 (5 %)."""
        fractions = {prefix: frac for prefix, frac in ct._CACHE_READ_FRACTIONS}
        assert MUSE_WONDER_CANONICAL_ID in fractions, (
            f"{MUSE_WONDER_CANONICAL_ID} must have an explicit cache-read fraction"
        )
        assert fractions[MUSE_WONDER_CANONICAL_ID] == pytest.approx(
            MUSE_WONDER_CACHE_FRACTION
        )


# ---------------------------------------------------------------------------
# Cost tracker — Muse Wonder OpenRouter ID
# ---------------------------------------------------------------------------

class TestMuseWonderOpenRouterCostTracker:
    def test_entry_exists(self, ct):
        cost = ct.cost_for_tokens(MUSE_WONDER_OPENROUTER_ID, 1_000_000, 0)
        assert cost is not None, f"{MUSE_WONDER_OPENROUTER_ID} must have a cost entry"

    def test_input_cost(self, ct):
        cost = ct.cost_for_tokens(MUSE_WONDER_OPENROUTER_ID, 1_000_000, 0)
        assert cost == pytest.approx(MUSE_WONDER_INPUT_COST)

    def test_output_cost(self, ct):
        cost = ct.cost_for_tokens(MUSE_WONDER_OPENROUTER_ID, 0, 1_000_000)
        assert cost == pytest.approx(MUSE_WONDER_OUTPUT_COST)

    def test_matches_canonical(self, ct):
        canonical = ct.cost_for_tokens(MUSE_WONDER_CANONICAL_ID, 500_000, 200_000)
        openrouter = ct.cost_for_tokens(MUSE_WONDER_OPENROUTER_ID, 500_000, 200_000)
        assert canonical == pytest.approx(openrouter), (
            "Canonical and OpenRouter IDs must have identical pricing"
        )

    def test_openrouter_cache_fraction(self, ct):
        fractions = {prefix: frac for prefix, frac in ct._CACHE_READ_FRACTIONS}
        assert MUSE_WONDER_OPENROUTER_ID in fractions
        assert fractions[MUSE_WONDER_OPENROUTER_ID] == pytest.approx(
            MUSE_WONDER_CACHE_FRACTION
        )


# ---------------------------------------------------------------------------
# models.yaml — Muse Wonder canonical ID
# ---------------------------------------------------------------------------

class TestMuseWonderYaml:
    def test_entry_present(self, llm_models):
        models = llm_models.get("models", {})
        assert MUSE_WONDER_CANONICAL_ID in models, (
            f"{MUSE_WONDER_CANONICAL_ID} not found in config/llm/models.yaml"
        )

    def test_provider_openrouter(self, llm_models):
        entry = llm_models["models"][MUSE_WONDER_CANONICAL_ID]
        assert entry.get("provider") == "openrouter", (
            "provider must be 'openrouter'"
        )

    def test_supports_tools(self, llm_models):
        entry = llm_models["models"][MUSE_WONDER_CANONICAL_ID]
        assert entry.get("supports_tools") is True

    def test_supports_function_calling(self, llm_models):
        entry = llm_models["models"][MUSE_WONDER_CANONICAL_ID]
        assert entry.get("supports_function_calling") is True

    def test_supports_streaming(self, llm_models):
        entry = llm_models["models"][MUSE_WONDER_CANONICAL_ID]
        assert entry.get("supports_streaming") is True

    def test_priority_explicit_only(self, llm_models):
        entry = llm_models["models"][MUSE_WONDER_CANONICAL_ID]
        assert entry.get("priority") == 99, (
            f"{MUSE_WONDER_CANONICAL_ID} must be priority 99 (explicit-only until probed)"
        )

    def test_context_window(self, llm_models):
        entry = llm_models["models"][MUSE_WONDER_CANONICAL_ID]
        assert entry.get("context_window") == 1_048_576, (
            "context_window must be 1,048,576 (1M)"
        )

    def test_display_name_present(self, llm_models):
        entry = llm_models["models"][MUSE_WONDER_CANONICAL_ID]
        assert "display_name" in entry and entry["display_name"]

    def test_not_in_recommended_priority(self, llm_models):
        recommended = llm_models.get("recommended_priority", [])
        assert MUSE_WONDER_CANONICAL_ID not in recommended, (
            f"{MUSE_WONDER_CANONICAL_ID} must not be in recommended_priority (unprobed)"
        )

    def test_speed_tier_slow(self, llm_models):
        entry = llm_models["models"][MUSE_WONDER_CANONICAL_ID]
        assert entry.get("speed_tier") == "slow", (
            "speed_tier must be 'slow' — frontier model comparable to gpt-6-astra"
        )

    def test_input_cost_matches_cost_tracker(self, llm_models):
        entry = llm_models["models"][MUSE_WONDER_CANONICAL_ID]
        assert entry.get("input_cost_per_1m") == pytest.approx(MUSE_WONDER_INPUT_COST)

    def test_output_cost_matches_cost_tracker(self, llm_models):
        entry = llm_models["models"][MUSE_WONDER_CANONICAL_ID]
        assert entry.get("output_cost_per_1m") == pytest.approx(MUSE_WONDER_OUTPUT_COST)


# ---------------------------------------------------------------------------
# Catalogue consistency — no new collisions
# ---------------------------------------------------------------------------

class TestNoNewFuzzyCollisions:
    """muse-wonder-1.0 / meta/muse-wonder must not fuzzy-collide with any paid id."""

    MUSE_IDS = {MUSE_WONDER_CANONICAL_ID, MUSE_WONDER_OPENROUTER_ID}

    def _is_zero_cost(self, ct, model_id: str) -> bool:
        inp, out = ct._DEFAULT_COST_TABLE.get(model_id, (0.0, 0.0))
        return inp == 0.0 and out == 0.0

    def test_canonical_not_free(self, ct):
        assert not self._is_zero_cost(ct, MUSE_WONDER_CANONICAL_ID), (
            f"{MUSE_WONDER_CANONICAL_ID} is paid and must not be in the zero-cost table"
        )

    def test_openrouter_not_free(self, ct):
        assert not self._is_zero_cost(ct, MUSE_WONDER_OPENROUTER_ID), (
            f"{MUSE_WONDER_OPENROUTER_ID} is paid and must not be in the zero-cost table"
        )

    def test_no_undeclared_collision_with_paid_models(self, ct):
        """No free model id should be a substring of muse-wonder-1.0 or vice-versa."""
        known_allowlist = set()
        table = ct._DEFAULT_COST_TABLE
        zero_ids = {m for m, (i, o) in table.items() if i == 0.0 and o == 0.0}
        paid_ids = {m for m in table if m not in zero_ids}
        collisions = []
        for free_id in zero_ids:
            for paid_id in paid_ids:
                if free_id == paid_id:
                    continue
                if (free_id in paid_id or paid_id in free_id) and (
                    (free_id, paid_id) not in known_allowlist
                    and (paid_id, free_id) not in known_allowlist
                ):
                    # Only flag collisions that involve our new IDs
                    if free_id in self.MUSE_IDS or paid_id in self.MUSE_IDS:
                        collisions.append((free_id, paid_id))
        assert not collisions, (
            f"New muse-wonder IDs have undeclared fuzzy collisions: {collisions}"
        )
