"""tests/test_daily_automation_2026_08_29.py — Daily automation tests (2026-08-29).

Covers the ecosystem updates applied today:
  1. config/llm/models.yaml — Cerebras Qwen3-235B-A22B-Instruct-2507 added.
     New 262k-context free-tier model running at ~1,500 tok/s on Cerebras
     wafer-scale hardware (officially GA on Cerebras inference cloud, confirmed
     in Cerebras docs and press release 2026-07).
  2. config/llm/models.yaml — Sonnet 5 pricing comment updated: planned
     September 2026 increase to $3/$15 per MTok was cancelled on 2026-08-10;
     $2/$10 is now the permanent standard rate. Numbers unchanged; only the
     comment describing them was wrong.
"""
from __future__ import annotations

import pytest


def _cfg():
    from packages.llm.config import load_config
    return load_config()


# ── Cerebras Qwen3-235B ───────────────────────────────────────────────────────

class TestCatalogQwen3_235B:
    """Verify the qwen-3-235b-a22b-instruct-2507 entry in config/llm/models.yaml."""

    def test_model_in_catalog(self) -> None:
        assert "qwen-3-235b-a22b-instruct-2507" in _cfg().models

    def test_provider_is_cerebras(self) -> None:
        assert _cfg().models["qwen-3-235b-a22b-instruct-2507"].provider == "cerebras"

    def test_display_name(self) -> None:
        m = _cfg().models["qwen-3-235b-a22b-instruct-2507"]
        assert "235" in m.display_name
        assert "Qwen" in m.display_name

    def test_context_window_262k(self) -> None:
        assert _cfg().models["qwen-3-235b-a22b-instruct-2507"].context_window == 262144

    def test_context_window_larger_than_480b_coder(self) -> None:
        """Qwen3-235B has a much larger context window than Qwen3-Coder-480B."""
        models = _cfg().models
        assert models["qwen-3-235b-a22b-instruct-2507"].context_window > models["qwen-3-coder-480b"].context_window

    def test_max_output_tokens(self) -> None:
        assert _cfg().models["qwen-3-235b-a22b-instruct-2507"].max_output_tokens == 16384

    def test_supports_tools(self) -> None:
        assert _cfg().models["qwen-3-235b-a22b-instruct-2507"].supports_tools is True

    def test_supports_function_calling(self) -> None:
        assert _cfg().models["qwen-3-235b-a22b-instruct-2507"].supports_function_calling is True

    def test_supports_json(self) -> None:
        assert _cfg().models["qwen-3-235b-a22b-instruct-2507"].supports_json is True

    def test_supports_streaming(self) -> None:
        assert _cfg().models["qwen-3-235b-a22b-instruct-2507"].supports_streaming is True

    def test_is_free_tier(self) -> None:
        """Must be classified as free so the free-brain failover chain uses it."""
        m = _cfg().models["qwen-3-235b-a22b-instruct-2507"]
        assert m.input_cost_per_1m == 0.0
        assert m.output_cost_per_1m == 0.0
        assert m.is_free is True

    def test_speed_tier_fast(self) -> None:
        assert _cfg().models["qwen-3-235b-a22b-instruct-2507"].speed_tier == "fast"

    def test_priority_higher_than_480b_coder(self) -> None:
        """235B instruct should be preferred over 480B coder in general routing (lower number = higher priority)."""
        models = _cfg().models
        assert models["qwen-3-235b-a22b-instruct-2507"].priority < models["qwen-3-coder-480b"].priority

    def test_reasoning_disabled_on_instruct_variant(self) -> None:
        """Non-thinking variant: supports_reasoning must be False to avoid extended-thinking overhead."""
        assert _cfg().models["qwen-3-235b-a22b-instruct-2507"].supports_reasoning is False

    def test_alias_qwen3_235b(self) -> None:
        aliases = _cfg().models["qwen-3-235b-a22b-instruct-2507"].aliases
        assert "qwen3-235b" in aliases

    def test_alias_cerebras_qwen3_235b(self) -> None:
        aliases = _cfg().models["qwen-3-235b-a22b-instruct-2507"].aliases
        assert "cerebras-qwen3-235b" in aliases

    def test_cerebras_now_has_two_models(self) -> None:
        models = _cfg().models
        cerebras = [k for k, v in models.items() if v.provider == "cerebras"]
        assert len(cerebras) == 2
        assert "qwen-3-235b-a22b-instruct-2507" in cerebras
        assert "qwen-3-coder-480b" in cerebras


# ── Claude Sonnet 5 permanent pricing ────────────────────────────────────────

class TestSonnet5PermanentPricing:
    """Verify Sonnet 5 pricing is still $2/$10 (permanent, not introductory)."""

    def test_sonnet5_in_catalog(self) -> None:
        assert "claude-sonnet-5" in _cfg().models

    def test_sonnet5_input_cost_2_per_mtok(self) -> None:
        assert _cfg().models["claude-sonnet-5"].input_cost_per_1m == 2.0

    def test_sonnet5_output_cost_10_per_mtok(self) -> None:
        assert _cfg().models["claude-sonnet-5"].output_cost_per_1m == 10.0

    def test_sonnet5_not_free(self) -> None:
        assert _cfg().models["claude-sonnet-5"].is_free is False

    def test_sonnet5_dated_alias_same_pricing(self) -> None:
        """Dated alias (2026-05-01) should also have the same $2/$10 pricing."""
        m = _cfg().models.get("claude-sonnet-5-20260501")
        if m is not None:
            assert m.input_cost_per_1m == 2.0
            assert m.output_cost_per_1m == 10.0

    def test_sonnet5_cheaper_than_sonnet4_6(self) -> None:
        """Sonnet 5 at $2 input is cheaper than the earlier Sonnet 4.6 ($3)."""
        models = _cfg().models
        if "claude-sonnet-4-6" in models:
            assert models["claude-sonnet-5"].input_cost_per_1m < models["claude-sonnet-4-6"].input_cost_per_1m
