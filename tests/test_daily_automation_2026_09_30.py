"""tests/test_daily_automation_2026_09_30.py — Daily automation 2026-09-30.

Changes shipped today:
- **Per-model Anthropic cache-read fractions** corrected in
  ``packages/ai/cost_tracker._CACHE_READ_FRACTIONS``.  The table previously
  used a flat 10 % for every ``claude-`` prefix, but:
    - ``claude-fable-5-1`` / ``claude-mythos-5-1`` bill cache reads at 2.5 %
      of the input rate ($0.25/MTok on a $10/MTok base).
    - ``claude-opus-5-5`` (and its dated alias ``claude-opus-5-5-20260922``)
      bills at 5 % ($0.20/MTok on a $4/MTok base).
  The 10 % generic fallback for all other ``claude-`` models is unchanged.
  Source: platform.claude.com/docs/en/about-claude/pricing, 2026-09-30.

- **GPT-6 family cost table entries** added (``gpt-6-astra``,
  ``gpt-6-luna``, ``gpt-6.1-sol``).  These are not added to any provider's
  candidate list (NVIDIA NIM availability unconfirmed); entries enable cost
  attribution if the models are reached via OpenRouter or a configured
  OpenAI provider.
  Source: platform.openai.com/docs/models, 2026-09-30.
"""
from __future__ import annotations

import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Helpers — import the functions under test without the full app stack.
# ---------------------------------------------------------------------------

def _load_fraction_fn():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "cost_tracker",
        REPO_ROOT / "packages" / "ai" / "cost_tracker.py",
    )
    mod = importlib.util.load_from_spec(spec)  # type: ignore[attr-defined]
    return mod


@pytest.fixture(scope="module")
def ct():
    """Return the cost_tracker module."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_09_30",
        REPO_ROOT / "packages" / "ai" / "cost_tracker.py",
    )
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# 1. Per-model Anthropic cache-read fractions
# ---------------------------------------------------------------------------

class TestAnthropicCacheReadFractions:
    """_cache_read_fraction must return the correct per-model value."""

    def test_fable_5_1_is_2_point_5_percent(self, ct):
        assert ct._cache_read_fraction("claude-fable-5-1") == pytest.approx(0.025)

    def test_fable_5_1_dated_alias_is_2_point_5_percent(self, ct):
        assert ct._cache_read_fraction("claude-fable-5-1-20260901") == pytest.approx(0.025)

    def test_mythos_5_1_is_2_point_5_percent(self, ct):
        assert ct._cache_read_fraction("claude-mythos-5-1") == pytest.approx(0.025)

    def test_opus_5_5_is_5_percent(self, ct):
        assert ct._cache_read_fraction("claude-opus-5-5") == pytest.approx(0.05)

    def test_opus_5_5_dated_alias_is_5_percent(self, ct):
        assert ct._cache_read_fraction("claude-opus-5-5-20260922") == pytest.approx(0.05)

    def test_sonnet_5_5_is_10_percent(self, ct):
        """Sonnet 5.5 uses the generic 10 % fallback — unchanged."""
        assert ct._cache_read_fraction("claude-sonnet-5-5") == pytest.approx(0.10)

    def test_sonnet_5_5_dated_alias_is_10_percent(self, ct):
        assert ct._cache_read_fraction("claude-sonnet-5-5-20260929") == pytest.approx(0.10)

    def test_sonnet_5_is_10_percent(self, ct):
        assert ct._cache_read_fraction("claude-sonnet-5") == pytest.approx(0.10)

    def test_haiku_4_5_is_10_percent(self, ct):
        assert ct._cache_read_fraction("claude-haiku-4-5") == pytest.approx(0.10)

    def test_opus_5_is_10_percent(self, ct):
        """Opus 5 (not 5.5) uses the generic fallback — unchanged."""
        assert ct._cache_read_fraction("claude-opus-5") == pytest.approx(0.10)

    def test_fable_5_is_10_percent(self, ct):
        """Fable 5 (not 5.1) uses the generic fallback."""
        assert ct._cache_read_fraction("claude-fable-5") == pytest.approx(0.10)

    def test_gemini_is_25_percent(self, ct):
        """Gemini cache fraction must be unchanged."""
        assert ct._cache_read_fraction("gemini-2.5-flash") == pytest.approx(0.25)


class TestCacheReadCostCalculations:
    """cost_for_tokens must reflect the per-model fractions above."""

    def test_fable_5_1_all_cached_costs_quarter_percent_of_input(self, ct):
        """1 M tokens all from cache: $10/MTok × 2.5 % × 1 M = $0.25."""
        cost = ct.cost_for_tokens("claude-fable-5-1", 1_000_000, 0, 1_000_000)
        assert cost == pytest.approx(0.25)

    def test_fable_5_1_old_rate_was_higher(self, ct):
        """Regression: old flat 10 % would have returned $1.00, not $0.25."""
        cost = ct.cost_for_tokens("claude-fable-5-1", 1_000_000, 0, 1_000_000)
        assert cost < 1.00, (
            f"cost ${cost:.4f} should be < $1.00 (old flat-10% rate was $1.00 for 1M cached)"
        )

    def test_mythos_5_1_all_cached_matches_fable_5_1(self, ct):
        c_fable = ct.cost_for_tokens("claude-fable-5-1", 1_000_000, 0, 1_000_000)
        c_mythos = ct.cost_for_tokens("claude-mythos-5-1", 1_000_000, 0, 1_000_000)
        assert c_fable == pytest.approx(c_mythos)

    def test_opus_5_5_all_cached_costs_5_percent_of_input(self, ct):
        """1 M tokens all from cache: $4/MTok × 5 % × 1 M = $0.20."""
        cost = ct.cost_for_tokens("claude-opus-5-5", 1_000_000, 0, 1_000_000)
        assert cost == pytest.approx(0.20)

    def test_opus_5_5_old_rate_was_higher(self, ct):
        """Regression: old flat 10 % would have returned $0.40, not $0.20."""
        cost = ct.cost_for_tokens("claude-opus-5-5", 1_000_000, 0, 1_000_000)
        assert cost < 0.40

    def test_sonnet_5_5_all_cached_uses_10_percent(self, ct):
        """Sonnet 5.5 at $1.6/MTok: 1M cached = $1.6 × 10 % = $0.16."""
        cost = ct.cost_for_tokens("claude-sonnet-5-5", 1_000_000, 0, 1_000_000)
        assert cost == pytest.approx(0.16)

    def test_non_cached_fable_5_1_unchanged(self, ct):
        """Non-cached input is billed at the full input rate."""
        cost = ct.cost_for_tokens("claude-fable-5-1", 1_000_000, 0, 0)
        assert cost == pytest.approx(10.0)

    def test_fractions_are_ordered_specific_before_generic(self, ct):
        """Per-model entries must appear before the generic 'claude-' fallback."""
        entries = ct._CACHE_READ_FRACTIONS
        prefixes = [p for p, _ in entries]
        claude_idx = prefixes.index("claude-")
        for specific in ("claude-fable-5-1", "claude-mythos-5-1", "claude-opus-5-5"):
            sp_idx = prefixes.index(specific)
            assert sp_idx < claude_idx, (
                f"'{specific}' (idx {sp_idx}) must appear before 'claude-' (idx {claude_idx})"
            )


# ---------------------------------------------------------------------------
# 2. GPT-6 family cost table entries
# ---------------------------------------------------------------------------

class TestGpt6FamilyCostEntries:
    """GPT-6 models must be present in the cost table with correct pricing."""

    def test_gpt_6_astra_in_cost_table(self, ct):
        cost = ct.cost_for_tokens("gpt-6-astra", 1_000_000, 0)
        assert cost == pytest.approx(10.0), (
            "gpt-6-astra input cost should be $10/MTok"
        )

    def test_gpt_6_astra_output_cost(self, ct):
        cost = ct.cost_for_tokens("gpt-6-astra", 0, 1_000_000)
        assert cost == pytest.approx(50.0)

    def test_gpt_6_luna_in_cost_table(self, ct):
        cost = ct.cost_for_tokens("gpt-6-luna", 1_000_000, 0)
        assert cost == pytest.approx(0.1), (
            "gpt-6-luna input cost should be $0.1/MTok"
        )

    def test_gpt_6_luna_output_cost(self, ct):
        cost = ct.cost_for_tokens("gpt-6-luna", 0, 1_000_000)
        assert cost == pytest.approx(0.5)

    def test_gpt_6_1_sol_in_cost_table(self, ct):
        cost = ct.cost_for_tokens("gpt-6.1-sol", 1_000_000, 0)
        assert cost == pytest.approx(2.0), (
            "gpt-6.1-sol input cost should be $2/MTok"
        )

    def test_gpt_6_1_sol_output_cost(self, ct):
        cost = ct.cost_for_tokens("gpt-6.1-sol", 0, 1_000_000)
        assert cost == pytest.approx(10.0)

    def test_gpt_6_models_not_in_provider_candidates(self):
        """GPT-6 models must NOT appear in config/models.yaml candidates
        (NVIDIA NIM availability unconfirmed as of 2026-09-30)."""
        import yaml
        models_yaml = yaml.safe_load(
            (REPO_ROOT / "config" / "models.yaml").read_text()
        )
        all_candidates: list[str] = []
        for p_data in models_yaml.get("providers", {}).values():
            all_candidates.extend(p_data.get("candidates", []))
        for gpt6 in ("gpt-6-astra", "gpt-6-luna", "gpt-6.1-sol"):
            assert gpt6 not in all_candidates, (
                f"'{gpt6}' should not be in provider candidates until NIM availability confirmed"
            )

    def test_gpt_6_astra_is_more_expensive_than_gpt_5_6_sol(self, ct):
        """Sanity: Astra > Sol in input cost."""
        astra = ct.cost_for_tokens("gpt-6-astra", 1_000_000, 0)
        sol = ct.cost_for_tokens("gpt-5.6-sol", 1_000_000, 0)
        assert astra > sol

    def test_gpt_6_luna_is_cheaper_than_gpt_5_6_luna(self, ct):
        """GPT-6 Luna ($0.1/MTok) is cheaper than GPT-5.6 Luna ($0.5/MTok)."""
        luna6 = ct.cost_for_tokens("gpt-6-luna", 1_000_000, 0)
        luna56 = ct.cost_for_tokens("gpt-5.6-luna", 1_000_000, 0)
        assert luna6 < luna56
