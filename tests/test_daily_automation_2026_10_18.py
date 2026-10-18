"""tests/test_daily_automation_2026_10_18.py — Daily automation 2026-10-18.

Changes shipped today:
- **NVIDIA Nemotron 3.5 Super VL declared** (``nvidia/nemotron-3.5-super-vl:free``
  via OpenRouter).
  Released 2026-10-16. NVIDIA's multimodal 120B MoE model (~12B active params).
  Accepts text, images, documents, GUI screenshots, and video.
  Context: 1,050,000 tokens. Max output: 8,192 tokens.
  Tool calling: not yet probed — declared ``false`` conservatively.
  Available via OpenRouter free tier ($0.00/$0.00 per MTok).
  Also served by Together AI, DeepInfra, Nebius, and Crusoe at paid rates.
  Priority: 68 (explicit-only in the OpenRouter free tier, behind Nemotron 3 Super
  at 65, Gemma 4 31B at 66, and Qwen 3.8 27B at 67).
  Source: openrouter.ai/nvidia/nemotron-3.5-super-vl, 2026-10-18.

Files changed:
  ``config/llm/models.yaml``, ``packages/ai/cost_tracker.py``,
  ``CHANGELOG.md``, ``docs/changelog.md``,
  ``tests/test_daily_automation_2026_10_18.py`` (this file).
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

MODEL_ID = "nvidia/nemotron-3.5-super-vl:free"


@pytest.fixture(scope="module")
def ct():
    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_10_18",
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
# Cost tracker — Nemotron 3.5 Super VL (free)
# ---------------------------------------------------------------------------

class TestNemotron35SuperVLCost:
    def test_input_cost_is_zero(self, ct):
        cost = ct.cost_for_tokens(MODEL_ID, 1_000_000, 0)
        assert cost == pytest.approx(0.0), (
            "nvidia/nemotron-3.5-super-vl:free input cost must be $0.00/MTok (free tier)"
        )

    def test_output_cost_is_zero(self, ct):
        cost = ct.cost_for_tokens(MODEL_ID, 0, 1_000_000)
        assert cost == pytest.approx(0.0), (
            "nvidia/nemotron-3.5-super-vl:free output cost must be $0.00/MTok (free tier)"
        )

    def test_combined_cost_is_zero(self, ct):
        cost = ct.cost_for_tokens(MODEL_ID, 500_000, 500_000)
        assert cost == pytest.approx(0.0)

    def test_cost_is_float(self, ct):
        cost = ct.cost_for_tokens(MODEL_ID, 100_000, 10_000)
        assert isinstance(cost, float)


# ---------------------------------------------------------------------------
# models.yaml — Nemotron 3.5 Super VL
# ---------------------------------------------------------------------------

class TestNemotron35SuperVLYaml:
    def test_entry_present(self, llm_models):
        models = llm_models.get("models", {})
        assert MODEL_ID in models, f"{MODEL_ID} not found in config/llm/models.yaml"

    def test_provider_openrouter(self, llm_models):
        entry = llm_models["models"][MODEL_ID]
        assert entry.get("provider") == "openrouter", "provider must be 'openrouter'"

    def test_context_window(self, llm_models):
        entry = llm_models["models"][MODEL_ID]
        assert entry.get("context_window") == 1_050_000, (
            "context_window must be 1050000 (1.05M)"
        )

    def test_supports_tools_false(self, llm_models):
        """Tool calling must be declared false until probed on this account."""
        entry = llm_models["models"][MODEL_ID]
        assert entry.get("supports_tools") is False, (
            "supports_tools must be false (not yet probed)"
        )

    def test_supports_images(self, llm_models):
        """Nemotron 3.5 Super VL is multimodal; supports_images must be true."""
        entry = llm_models["models"][MODEL_ID]
        assert entry.get("supports_images") is True

    def test_supports_streaming(self, llm_models):
        entry = llm_models["models"][MODEL_ID]
        assert entry.get("supports_streaming") is True

    def test_priority_explicit_only(self, llm_models):
        """Priority in the 60-75 range: explicit-only in the OpenRouter free tier."""
        entry = llm_models["models"][MODEL_ID]
        assert entry.get("priority") == 68

    def test_input_cost_zero(self, llm_models):
        entry = llm_models["models"][MODEL_ID]
        assert entry.get("input_cost_per_1m") == pytest.approx(0.0)

    def test_output_cost_zero(self, llm_models):
        entry = llm_models["models"][MODEL_ID]
        assert entry.get("output_cost_per_1m") == pytest.approx(0.0)

    def test_display_name_present(self, llm_models):
        entry = llm_models["models"][MODEL_ID]
        assert "display_name" in entry and entry["display_name"], (
            "display_name must be non-empty"
        )

    def test_not_in_recommended_priority_list(self, llm_models):
        """Free-tier OpenRouter model must not appear in the top recommended list."""
        recommended = llm_models.get("recommended_priority", [])
        assert MODEL_ID not in recommended, (
            f"{MODEL_ID} should not be in recommended_priority (free-tier fallback only)"
        )

    def test_priority_after_existing_free_openrouter_models(self, llm_models):
        """Nemotron 3.5 must sit after the existing three free OpenRouter models."""
        models = llm_models.get("models", {})
        existing_free = [
            "nvidia/nemotron-3-super-120b-a12b:free",
            "google/gemma-4-31b-it:free",
            "qwen/qwen3.8-27b:free",
        ]
        for existing_id in existing_free:
            if existing_id in models:
                existing_priority = models[existing_id].get("priority", 0)
                new_priority = models[MODEL_ID].get("priority", 0)
                assert new_priority > existing_priority, (
                    f"{MODEL_ID} priority {new_priority} must be higher number "
                    f"(lower preference) than {existing_id} at {existing_priority}"
                )
