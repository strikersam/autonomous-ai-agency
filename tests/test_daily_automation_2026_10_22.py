"""tests/test_daily_automation_2026_10_22.py — Daily automation 2026-10-22.

Changes shipped today:
- **MiniMax M3.1 Flash declared** (``minimax/minimax-m3.1-flash:free`` via OpenRouter).
  Released 2026-10-19. MiniMax's fast frontier model with 1M-token context.
  Free via OpenRouter's ":free" tier; paid rate (MiniMax direct) $0.15/$0.60/MTok.
  Priority 69 in the OpenRouter free tier (after Nemotron 3.5 Super VL at 68).
  ``supports_tools: false`` conservatively until a tool_call probe returns green.
  Source: openrouter.ai/minimax/minimax-m3.1-flash:free, 2026-10-22.

Ecosystem research reviewed:
  - Claude Code v2.1.305 (idle compaction, Linux namespace sandbox, plugin hooks)
  - Codex CLI v0.163.0 (mid-response steering, searchable /config panel)
  - NVIDIA NIM catalog (deepseek-ai/deepseek-v4.1-flash still awaiting live probe)
  - OpenRouter free tier (MiniMax M3.1 Flash, released 2026-10-19, confirmed new)
  - Groq/Cerebras free tier changes (noted, no catalogue action needed today)

Files changed:
  ``config/llm/models.yaml``,
  ``packages/ai/cost_tracker.py``,
  ``CHANGELOG.md``, ``docs/changelog.md``,
  ``tests/test_daily_automation_2026_10_22.py`` (this file).
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

FREE_MODEL_ID = "minimax/minimax-m3.1-flash:free"
# MiniMax direct, priced under its native id since the 2026-10-23 entry.
PAID_MODEL_ID = "MiniMax-M3.1-Flash"


@pytest.fixture(scope="module")
def ct():
    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_10_22",
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
# Cost tracker — MiniMax M3.1 Flash free tier
# ---------------------------------------------------------------------------

class TestMiniMaxM31FlashFreeCost:
    def test_free_input_cost_is_zero(self, ct):
        cost = ct.cost_for_tokens(FREE_MODEL_ID, 1_000_000, 0)
        assert cost == pytest.approx(0.0), (
            f"{FREE_MODEL_ID} input cost must be $0.00 (OpenRouter free tier)"
        )

    def test_free_output_cost_is_zero(self, ct):
        cost = ct.cost_for_tokens(FREE_MODEL_ID, 0, 1_000_000)
        assert cost == pytest.approx(0.0), (
            f"{FREE_MODEL_ID} output cost must be $0.00 (OpenRouter free tier)"
        )

    def test_free_combined_cost_is_zero(self, ct):
        cost = ct.cost_for_tokens(FREE_MODEL_ID, 500_000, 500_000)
        assert cost == pytest.approx(0.0)

    def test_free_cost_is_float(self, ct):
        cost = ct.cost_for_tokens(FREE_MODEL_ID, 100_000, 10_000)
        assert isinstance(cost, float)


# ---------------------------------------------------------------------------
# Cost tracker — MiniMax M3.1 Flash paid tier
# ---------------------------------------------------------------------------

class TestMiniMaxM31FlashPaidCost:
    def test_paid_input_cost(self, ct):
        cost = ct.cost_for_tokens(PAID_MODEL_ID, 1_000_000, 0)
        assert cost == pytest.approx(0.15), (
            f"{PAID_MODEL_ID} input cost must be $0.15/MTok (MiniMax direct list)"
        )

    def test_paid_output_cost(self, ct):
        cost = ct.cost_for_tokens(PAID_MODEL_ID, 0, 1_000_000)
        assert cost == pytest.approx(0.60), (
            f"{PAID_MODEL_ID} output cost must be $0.60/MTok (MiniMax direct list)"
        )

    def test_paid_cost_is_float(self, ct):
        cost = ct.cost_for_tokens(PAID_MODEL_ID, 100_000, 10_000)
        assert isinstance(cost, float)


# ---------------------------------------------------------------------------
# models.yaml — MiniMax M3.1 Flash (free via OpenRouter)
# ---------------------------------------------------------------------------

class TestMiniMaxM31FlashYaml:
    def test_entry_present(self, llm_models):
        models = llm_models.get("models", {})
        assert FREE_MODEL_ID in models, (
            f"{FREE_MODEL_ID} not found in config/llm/models.yaml"
        )

    def test_provider_openrouter(self, llm_models):
        entry = llm_models["models"][FREE_MODEL_ID]
        assert entry.get("provider") == "openrouter", (
            "provider must be 'openrouter' (served via OpenRouter free tier)"
        )

    def test_supports_tools_false(self, llm_models):
        entry = llm_models["models"][FREE_MODEL_ID]
        assert entry.get("supports_tools") is False, (
            "supports_tools must be false (not yet probed on this account)"
        )

    def test_supports_streaming(self, llm_models):
        entry = llm_models["models"][FREE_MODEL_ID]
        assert entry.get("supports_streaming") is True

    def test_priority_69(self, llm_models):
        entry = llm_models["models"][FREE_MODEL_ID]
        assert entry.get("priority") == 69, (
            f"{FREE_MODEL_ID} must be at priority 69 (OpenRouter free tier slot)"
        )

    def test_context_window_1m(self, llm_models):
        entry = llm_models["models"][FREE_MODEL_ID]
        assert entry.get("context_window") == 1_000_000, (
            "context_window must be 1,000,000 tokens"
        )

    def test_speed_tier_fast(self, llm_models):
        entry = llm_models["models"][FREE_MODEL_ID]
        assert entry.get("speed_tier") == "fast"

    def test_display_name_present(self, llm_models):
        entry = llm_models["models"][FREE_MODEL_ID]
        assert "display_name" in entry and entry["display_name"], (
            "display_name must be non-empty"
        )

    def test_not_in_recommended_priority_list(self, llm_models):
        recommended = llm_models.get("recommended_priority", [])
        assert FREE_MODEL_ID not in recommended, (
            f"{FREE_MODEL_ID} should not be in recommended_priority (unprobed)"
        )

    def test_input_cost_zero(self, llm_models):
        entry = llm_models["models"][FREE_MODEL_ID]
        if "input_cost_per_1m" in entry:
            assert entry["input_cost_per_1m"] == pytest.approx(0.0)

    def test_output_cost_zero(self, llm_models):
        entry = llm_models["models"][FREE_MODEL_ID]
        if "output_cost_per_1m" in entry:
            assert entry["output_cost_per_1m"] == pytest.approx(0.0)

    def test_priority_higher_than_previous_free_model(self, llm_models):
        """MiniMax M3.1 Flash must be lower priority than Nemotron 3.5 Super VL."""
        models = llm_models.get("models", {})
        prev = models.get("nvidia/nemotron-3.5-super-vl:free", {})
        current = models.get(FREE_MODEL_ID, {})
        assert current.get("priority", 0) > prev.get("priority", 0), (
            "MiniMax M3.1 Flash priority must be lower priority than nemotron-3.5-super-vl:free "
            "(higher number = lower priority in this repo's convention)"
        )
