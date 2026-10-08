"""tests/test_daily_automation_2026_10_08.py — Daily automation 2026-10-08.

One model addition:

1. **Claude Haiku 5.5** (Anthropic, released 2026-10-07) — added to
   ``packages/ai/cost_tracker.py`` and ``config/llm/models.yaml``.
   Anthropic's cheapest and fastest Claude 5-generation model targeting
   high-volume, latency-sensitive work (classification, routing, extraction,
   subagents, browser use). 1M-token context, 128K max output, adaptive
   thinking via the effort parameter.
   Pricing: $0.10/$0.50 per MTok input/output (base rate, prompts ≤100K
   tokens); above 100K the input rate rises 5× to $0.50/MTok.
   Cache reads: $0.01/MTok (10 % of input rate — covered by the generic
   "claude-" prefix in ``_CACHE_READ_FRACTIONS``; no new override needed).
   Sources: platform.claude.com/docs/en/models/haiku-5-5/overview,
   openrouter.ai/anthropic/claude-haiku-5.5, marktechpost.com 2026-10-07.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ct():
    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_10_08",
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
    )["models"]


# ---------------------------------------------------------------------------
# Haiku 5.5 — cost entries
# ---------------------------------------------------------------------------

class TestHaiku55CostEntry:
    def test_haiku_55_input_cost(self, ct):
        cost = ct.cost_for_tokens("claude-haiku-5-5", 1_000_000, 0)
        assert cost == pytest.approx(0.10), (
            "claude-haiku-5-5 input must be $0.10/MTok"
        )

    def test_haiku_55_output_cost(self, ct):
        cost = ct.cost_for_tokens("claude-haiku-5-5", 0, 1_000_000)
        assert cost == pytest.approx(0.50), (
            "claude-haiku-5-5 output must be $0.50/MTok"
        )

    def test_haiku_55_versioned_input_cost(self, ct):
        cost = ct.cost_for_tokens("claude-haiku-5-5-20261007", 1_000_000, 0)
        assert cost == pytest.approx(0.10), (
            "claude-haiku-5-5-20261007 input must be $0.10/MTok"
        )

    def test_haiku_55_versioned_output_cost(self, ct):
        cost = ct.cost_for_tokens("claude-haiku-5-5-20261007", 0, 1_000_000)
        assert cost == pytest.approx(0.50), (
            "claude-haiku-5-5-20261007 output must be $0.50/MTok"
        )

    def test_haiku_55_cheaper_than_haiku_45_output(self, ct):
        """Haiku 5.5 output ($0.50/MTok) is cheaper than Haiku 4.5 ($5.00/MTok)."""
        h55 = ct.cost_for_tokens("claude-haiku-5-5", 0, 1_000_000)
        h45 = ct.cost_for_tokens("claude-haiku-4-5", 0, 1_000_000)
        assert h55 < h45, "Haiku 5.5 output must cost less than Haiku 4.5 output"

    def test_haiku_55_cheaper_than_sonnet_55_input(self, ct):
        """Haiku 5.5 ($0.10) is much cheaper than Sonnet 5.5 ($2.00) on input."""
        h55 = ct.cost_for_tokens("claude-haiku-5-5", 1_000_000, 0)
        s55 = ct.cost_for_tokens("claude-sonnet-5-5", 1_000_000, 0)
        assert h55 < s55, "Haiku 5.5 input must cost less than Sonnet 5.5 input"

    def test_haiku_55_cache_read_is_10_percent(self, ct):
        """Cache reads for claude-haiku-5-5 should be 10 % of input rate
        ($0.01/MTok), covered by the generic 'claude-' prefix."""
        frac = ct._cache_read_fraction("claude-haiku-5-5")
        assert frac == pytest.approx(0.10), (
            "claude-haiku-5-5 cache read fraction must be 0.10 (10 %)"
        )

    def test_haiku_55_cache_cost_computation(self, ct):
        """1M cached tokens should cost $0.01 (0.10 × 0.10 = 0.01)."""
        cost = ct.cost_for_tokens(
            "claude-haiku-5-5",
            prompt_tokens=1_000_000,
            completion_tokens=0,
            cached_tokens=1_000_000,
        )
        assert cost == pytest.approx(0.01), (
            "1M cached Haiku 5.5 tokens must cost $0.01"
        )

    def test_haiku_55_combined_input_output(self, ct):
        """100K in + 10K out = $0.01 + $0.005 = $0.015."""
        cost = ct.cost_for_tokens("claude-haiku-5-5", 100_000, 10_000)
        assert cost == pytest.approx(0.015), (
            "100K input + 10K output must cost $0.015 for Haiku 5.5"
        )


# ---------------------------------------------------------------------------
# Haiku 5.5 — models.yaml declaration
# ---------------------------------------------------------------------------

class TestHaiku55ModelsYaml:
    def test_haiku_55_declared(self, llm_models):
        assert "claude-haiku-5-5" in llm_models, (
            "claude-haiku-5-5 must be in config/llm/models.yaml"
        )

    def test_haiku_55_versioned_declared(self, llm_models):
        assert "claude-haiku-5-5-20261007" in llm_models, (
            "claude-haiku-5-5-20261007 must be in config/llm/models.yaml"
        )

    def test_haiku_55_provider(self, llm_models):
        assert llm_models["claude-haiku-5-5"]["provider"] == "anthropic"

    def test_haiku_55_context_window(self, llm_models):
        assert llm_models["claude-haiku-5-5"]["context_window"] == 1_048_576, (
            "claude-haiku-5-5 must have a 1M-token context window"
        )

    def test_haiku_55_max_output(self, llm_models):
        assert llm_models["claude-haiku-5-5"]["max_output_tokens"] == 128_000, (
            "claude-haiku-5-5 must support 128K output tokens"
        )

    def test_haiku_55_supports_tools(self, llm_models):
        assert llm_models["claude-haiku-5-5"].get("supports_tools") is True

    def test_haiku_55_supports_images(self, llm_models):
        assert llm_models["claude-haiku-5-5"].get("supports_images") is True

    def test_haiku_55_speed_tier_fast(self, llm_models):
        assert llm_models["claude-haiku-5-5"]["speed_tier"] == "fast"

    def test_haiku_55_bigger_context_than_haiku_45(self, llm_models):
        h55 = llm_models["claude-haiku-5-5"]["context_window"]
        h45 = llm_models["claude-haiku-4-5"]["context_window"]
        assert h55 > h45, (
            "Haiku 5.5 context window must exceed Haiku 4.5 (200K)"
        )

    def test_haiku_55_cheaper_input_than_haiku_45(self, llm_models):
        h55 = llm_models["claude-haiku-5-5"]["input_cost_per_1m"]
        h45 = llm_models["claude-haiku-4-5"]["input_cost_per_1m"]
        assert h55 < h45, (
            "Haiku 5.5 input cost per 1M must be less than Haiku 4.5"
        )

    def test_haiku_55_has_alias(self, llm_models):
        aliases = llm_models["claude-haiku-5-5"].get("aliases", [])
        assert "haiku5.5" in aliases, (
            "claude-haiku-5-5 must have 'haiku5.5' alias"
        )

    def test_haiku_55_versioned_same_context(self, llm_models):
        base = llm_models["claude-haiku-5-5"]["context_window"]
        dated = llm_models["claude-haiku-5-5-20261007"]["context_window"]
        assert base == dated, (
            "dated alias must have same context window as base model"
        )
