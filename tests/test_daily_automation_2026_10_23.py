"""tests/test_daily_automation_2026_10_23.py — Daily automation 2026-10-23.

Changes shipped today:
- **Qwen3.6 27B declared on Groq** (``qwen/qwen3.6-27b``, released 2026-10-21).
  Dense 27B model (successor to Qwen 3.8 27B MoE). Supports vision, tool calling,
  and reasoning/non-reasoning switching on Groq LPU (~464 t/s).
  Context: 131,072 tokens. Pricing: $0.60/$3.00 per MTok.
  Priority: 99 (explicit-only) — Groq provider is wired, model unprobed on
  this account; lower priority after a live probe confirms it answers.
  Groq 50 % cache discount applies via the existing ``("qwen/", 0.50)`` fraction.

- **MiniMax M3.1 Flash cost entry** (``MiniMax-M3.1-Flash``, released 2026-10-19,
  weights open-sourced 2026-10-23). Lighter/cheaper successor to MiniMax M3.
  1M context, tool calling, no JSON mode. Pricing: $0.15/$0.60 per MTok.
  Cost-tracker entry only — MiniMax provider not yet wired as a failover backend.

Also verified today:
- GPT model deprecations (2026-10-23): ``gpt-3.5-turbo-0125``, ``gpt-4-0613``,
  ``gpt-4-1106-preview`` were retired by OpenAI today. Confirmed: none of these
  IDs appear in ``packages/ai/cost_tracker.py``, ``config/llm/models.yaml``, or
  ``packages/ai/brain_config.py`` — no action required.

Files changed:
  ``packages/ai/cost_tracker.py``,
  ``config/llm/models.yaml``,
  ``CHANGELOG.md``, ``docs/changelog.md``,
  ``tests/test_daily_automation_2026_10_23.py`` (this file).
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

QWEN36_ID = "qwen/qwen3.6-27b"
MINIMAX_M31_FLASH_ID = "MiniMax-M3.1-Flash"
DEPRECATED_IDS = [
    "gpt-3.5-turbo-0125",
    "gpt-4-0613",
    "gpt-4-1106-preview",
]


@pytest.fixture(scope="module")
def ct():
    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_10_23",
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
# Cost tracker — Qwen3.6 27B on Groq
# ---------------------------------------------------------------------------

class TestQwen36CostTracker:
    def test_entry_exists(self, ct):
        cost = ct.cost_for_tokens(QWEN36_ID, 1_000_000, 0)
        assert cost is not None, f"{QWEN36_ID} must have a cost entry"

    def test_input_cost(self, ct):
        cost = ct.cost_for_tokens(QWEN36_ID, 1_000_000, 0)
        assert cost == pytest.approx(0.60), (
            f"{QWEN36_ID} input cost must be $0.60/MTok"
        )

    def test_output_cost(self, ct):
        cost = ct.cost_for_tokens(QWEN36_ID, 0, 1_000_000)
        assert cost == pytest.approx(3.00), (
            f"{QWEN36_ID} output cost must be $3.00/MTok"
        )

    def test_combined_cost(self, ct):
        cost = ct.cost_for_tokens(QWEN36_ID, 1_000_000, 1_000_000)
        assert cost == pytest.approx(0.60 + 3.00)

    def test_cost_is_float(self, ct):
        cost = ct.cost_for_tokens(QWEN36_ID, 100_000, 10_000)
        assert isinstance(cost, float)

    def test_cache_read_fraction_applies(self, ct):
        """Groq qwen/ prefix gets a 50 % cache-read discount."""
        base = ct.cost_for_tokens(QWEN36_ID, 1_000_000, 0)
        cached = ct.cost_for_tokens(QWEN36_ID, 1_000_000, 0, cached_tokens=1_000_000)
        # cached cost must be ≤ full cost (the fraction reduces it)
        assert cached <= base


# ---------------------------------------------------------------------------
# models.yaml — Qwen3.6 27B on Groq
# ---------------------------------------------------------------------------

class TestQwen36Yaml:
    def test_entry_present(self, llm_models):
        models = llm_models.get("models", {})
        assert QWEN36_ID in models, f"{QWEN36_ID} not found in config/llm/models.yaml"

    def test_provider_groq(self, llm_models):
        entry = llm_models["models"][QWEN36_ID]
        assert entry.get("provider") == "groq", (
            "provider must be 'groq'"
        )

    def test_supports_tools(self, llm_models):
        entry = llm_models["models"][QWEN36_ID]
        assert entry.get("supports_tools") is True

    def test_supports_streaming(self, llm_models):
        entry = llm_models["models"][QWEN36_ID]
        assert entry.get("supports_streaming") is True

    def test_supports_reasoning(self, llm_models):
        entry = llm_models["models"][QWEN36_ID]
        assert entry.get("supports_reasoning") is True

    def test_priority_explicit_only(self, llm_models):
        entry = llm_models["models"][QWEN36_ID]
        assert entry.get("priority") == 99, (
            f"{QWEN36_ID} must be at priority 99 (explicit-only until probed)"
        )

    def test_context_window(self, llm_models):
        entry = llm_models["models"][QWEN36_ID]
        assert entry.get("context_window") == 131072

    def test_display_name_present(self, llm_models):
        entry = llm_models["models"][QWEN36_ID]
        assert "display_name" in entry and entry["display_name"]

    def test_not_in_recommended_priority(self, llm_models):
        recommended = llm_models.get("recommended_priority", [])
        assert QWEN36_ID not in recommended, (
            f"{QWEN36_ID} must not be in recommended_priority (unprobed)"
        )

    def test_speed_tier_fast(self, llm_models):
        entry = llm_models["models"][QWEN36_ID]
        assert entry.get("speed_tier") == "fast"


# ---------------------------------------------------------------------------
# Cost tracker — MiniMax M3.1 Flash
# ---------------------------------------------------------------------------

class TestMiniMaxM31FlashCostTracker:
    def test_entry_exists(self, ct):
        cost = ct.cost_for_tokens(MINIMAX_M31_FLASH_ID, 1_000_000, 0)
        assert cost is not None, f"{MINIMAX_M31_FLASH_ID} must have a cost entry"

    def test_input_cost(self, ct):
        cost = ct.cost_for_tokens(MINIMAX_M31_FLASH_ID, 1_000_000, 0)
        assert cost == pytest.approx(0.15), (
            f"{MINIMAX_M31_FLASH_ID} input cost must be $0.15/MTok"
        )

    def test_output_cost(self, ct):
        cost = ct.cost_for_tokens(MINIMAX_M31_FLASH_ID, 0, 1_000_000)
        assert cost == pytest.approx(0.60), (
            f"{MINIMAX_M31_FLASH_ID} output cost must be $0.60/MTok"
        )

    def test_combined_cost(self, ct):
        cost = ct.cost_for_tokens(MINIMAX_M31_FLASH_ID, 1_000_000, 1_000_000)
        assert cost == pytest.approx(0.15 + 0.60)

    def test_cost_is_float(self, ct):
        cost = ct.cost_for_tokens(MINIMAX_M31_FLASH_ID, 100_000, 10_000)
        assert isinstance(cost, float)


# ---------------------------------------------------------------------------
# Deprecated GPT models — must NOT appear in the catalogue
# ---------------------------------------------------------------------------

class TestDeprecatedGptModelsAbsent:
    """OpenAI retired gpt-3.5-turbo-0125, gpt-4-0613, gpt-4-1106-preview
    on 2026-10-23.  These IDs must not appear in routing or cost tables."""

    def test_not_in_cost_tracker(self, ct):
        table = ct._DEFAULT_COST_TABLE
        for model_id in DEPRECATED_IDS:
            assert model_id not in table, (
                f"{model_id} was retired by OpenAI on 2026-10-23 "
                "and must not appear in _DEFAULT_COST_TABLE"
            )

    def test_not_in_llm_models_yaml(self, llm_models):
        models = llm_models.get("models", {})
        for model_id in DEPRECATED_IDS:
            assert model_id not in models, (
                f"{model_id} was retired by OpenAI on 2026-10-23 "
                "and must not appear in config/llm/models.yaml"
            )
