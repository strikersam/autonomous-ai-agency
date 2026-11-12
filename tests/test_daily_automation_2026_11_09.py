"""tests/test_daily_automation_2026_11_09.py — Daily automation 2026-11-09.

Changes shipped today:
- **Gemini Omni 1.2 Flash declared in model catalogue** (``gemini-omni-1.2-flash``
  / ``google/gemini-omni-1.2-flash``, released on OpenRouter 2026-11-05).
  Google's successor to Omni 1.1 Flash. Video-generation-only model (text,
  images and video in; text and video out) — not a chat/tool-call routing
  candidate (``supports_tools: false``, ``priority: 99``).
  Context: 131,072 tokens; max output: 65,536 tokens.
  Text pricing: $1.50 input / $9.00 output per MTok.
  Video billed separately per second by resolution (not tracked here).
  ~30 % lower per-second video pricing vs Omni 1.1.
  Sources: openrouter.ai/google/gemini-omni-1.2-flash,
           blog.google/innovation-and-ai/technology/developers-tools/
             introducing-gemini-omni-1-2-flash/, 2026-11-05.

Files changed:
  ``config/llm/models.yaml``,
  ``packages/ai/cost_tracker.py``,
  ``CHANGELOG.md``, ``docs/changelog.md``,
  ``tests/test_daily_automation_2026_11_09.py`` (this file).
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# Gemini Omni 1.2 Flash
OMNI12_DIRECT_ID = "gemini-omni-1.2-flash"
OMNI12_OPENROUTER_ID = "google/gemini-omni-1.2-flash"
OMNI12_INPUT_COST = 1.5
OMNI12_OUTPUT_COST = 9.0
OMNI12_CONTEXT_WINDOW = 131_072
OMNI12_MAX_OUTPUT = 65_536


@pytest.fixture(scope="module")
def ct():
    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_11_09",
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
# Gemini Omni 1.2 Flash — cost tracker (direct id)
# ---------------------------------------------------------------------------

class TestOmni12DirectCostTracker:
    def test_entry_exists(self, ct):
        cost = ct.cost_for_tokens(OMNI12_DIRECT_ID, 1_000_000, 0)
        assert cost is not None

    def test_input_cost(self, ct):
        cost = ct.cost_for_tokens(OMNI12_DIRECT_ID, 1_000_000, 0)
        assert abs(cost - OMNI12_INPUT_COST) < 0.01, (
            f"Expected ~${OMNI12_INPUT_COST} input cost, got ${cost}"
        )

    def test_output_cost(self, ct):
        cost = ct.cost_for_tokens(OMNI12_DIRECT_ID, 0, 1_000_000)
        assert abs(cost - OMNI12_OUTPUT_COST) < 0.01, (
            f"Expected ~${OMNI12_OUTPUT_COST} output cost, got ${cost}"
        )

    def test_combined_cost(self, ct):
        cost = ct.cost_for_tokens(OMNI12_DIRECT_ID, 100_000, 50_000)
        expected = OMNI12_INPUT_COST * 0.1 + OMNI12_OUTPUT_COST * 0.05
        assert abs(cost - expected) < 0.01


# ---------------------------------------------------------------------------
# Gemini Omni 1.2 Flash — cost tracker (OpenRouter id)
# ---------------------------------------------------------------------------

class TestOmni12OpenRouterCostTracker:
    def test_entry_exists(self, ct):
        cost = ct.cost_for_tokens(OMNI12_OPENROUTER_ID, 1_000_000, 0)
        assert cost is not None

    def test_input_cost(self, ct):
        cost = ct.cost_for_tokens(OMNI12_OPENROUTER_ID, 1_000_000, 0)
        assert abs(cost - OMNI12_INPUT_COST) < 0.01, (
            f"Expected ~${OMNI12_INPUT_COST} input cost, got ${cost}"
        )

    def test_output_cost(self, ct):
        cost = ct.cost_for_tokens(OMNI12_OPENROUTER_ID, 0, 1_000_000)
        assert abs(cost - OMNI12_OUTPUT_COST) < 0.01, (
            f"Expected ~${OMNI12_OUTPUT_COST} output cost, got ${cost}"
        )

    def test_ids_produce_same_cost(self, ct):
        cost_direct = ct.cost_for_tokens(OMNI12_DIRECT_ID, 500_000, 200_000)
        cost_openrouter = ct.cost_for_tokens(OMNI12_OPENROUTER_ID, 500_000, 200_000)
        assert abs(cost_direct - cost_openrouter) < 0.001, (
            f"Direct and OpenRouter costs should match: {cost_direct} vs {cost_openrouter}"
        )


# ---------------------------------------------------------------------------
# Gemini Omni 1.2 Flash — models.yaml entry
# ---------------------------------------------------------------------------

class TestOmni12ModelsYaml:
    def test_entry_present(self, llm_models):
        models = llm_models.get("models", {})
        assert OMNI12_DIRECT_ID in models, (
            f"Expected '{OMNI12_DIRECT_ID}' in config/llm/models.yaml"
        )

    def test_provider_is_openrouter(self, llm_models):
        entry = llm_models["models"][OMNI12_DIRECT_ID]
        assert entry["provider"] == "openrouter", (
            f"Expected provider 'openrouter', got '{entry.get('provider')}'"
        )

    def test_no_tools(self, llm_models):
        entry = llm_models["models"][OMNI12_DIRECT_ID]
        assert entry.get("supports_tools") is False, (
            "Gemini Omni 1.2 Flash does not support function calling"
        )
        assert entry.get("supports_function_calling") is False

    def test_context_window(self, llm_models):
        entry = llm_models["models"][OMNI12_DIRECT_ID]
        assert entry["context_window"] == OMNI12_CONTEXT_WINDOW, (
            f"Expected context_window={OMNI12_CONTEXT_WINDOW}, "
            f"got {entry.get('context_window')}"
        )

    def test_max_output_tokens(self, llm_models):
        entry = llm_models["models"][OMNI12_DIRECT_ID]
        assert entry["max_output_tokens"] == OMNI12_MAX_OUTPUT, (
            f"Expected max_output_tokens={OMNI12_MAX_OUTPUT}, "
            f"got {entry.get('max_output_tokens')}"
        )

    def test_priority_is_99(self, llm_models):
        entry = llm_models["models"][OMNI12_DIRECT_ID]
        assert entry["priority"] == 99, (
            "Omni 1.2 Flash should be priority 99 (explicit-only, not for routing)"
        )

    def test_input_cost(self, llm_models):
        entry = llm_models["models"][OMNI12_DIRECT_ID]
        assert abs(entry["input_cost_per_1m"] - OMNI12_INPUT_COST) < 0.01

    def test_output_cost(self, llm_models):
        entry = llm_models["models"][OMNI12_DIRECT_ID]
        assert abs(entry["output_cost_per_1m"] - OMNI12_OUTPUT_COST) < 0.01

    def test_supports_images(self, llm_models):
        entry = llm_models["models"][OMNI12_DIRECT_ID]
        assert entry.get("supports_images") is True

    def test_supports_streaming(self, llm_models):
        entry = llm_models["models"][OMNI12_DIRECT_ID]
        assert entry.get("supports_streaming") is True


# ---------------------------------------------------------------------------
# Regression: Omni 1.1 Flash entry still present and unchanged
# ---------------------------------------------------------------------------

class TestOmni11RegressionUnchanged:
    def test_omni11_still_present_in_yaml(self, llm_models):
        models = llm_models.get("models", {})
        assert "gemini-omni-1.1-flash" in models

    def test_omni11_still_zero_cost(self, ct):
        cost = ct.cost_for_tokens("gemini-omni-1.1-flash", 1_000_000, 1_000_000)
        assert cost == 0.0, "Omni 1.1 Flash pricing is still unconfirmed — must stay $0"
