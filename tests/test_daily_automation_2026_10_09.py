"""tests/test_daily_automation_2026_10_09.py — Daily automation 2026-10-09.

One model addition:

1. **Mistral Large 4 ("Le Chonk")** (Mistral AI, released 2026-10-06) — added to
   ``packages/ai/cost_tracker.py``, ``config/llm/models.yaml``,
   ``config/models.yaml``, and ``packages/ai/brain_config.py``.
   Mistral's 1.05-trillion-parameter mixture-of-experts flagship model, with
   49 billion active parameters. Multimodal; native function calling and tool use;
   131 072-token context (API limit; the model supports up to 1M).
   Preview API list price: $1.36/$4.18 per MTok input/output. A 50 % launch
   discount was in effect at time of writing (~$0.68/$2.09).
   Available via api.mistral.ai and OpenRouter (``mistralai/mistral-large-4-0``).
   Open weights promised for approx. 2026-10-31.
   Not yet probed on this account; live health checks apply.
   Sources: techcrunch.com/2026/10/06/mistrals-new-1t-model-aims-to-leapfrog,
   openrouter.ai/mistralai/mistral-large-4-0, marktechpost.com 2026-10-06.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

MODEL_ID = "mistral-large-4-0"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ct():
    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_10_09",
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


@pytest.fixture(scope="module")
def routing_config():
    return yaml.safe_load(
        (REPO_ROOT / "config" / "models.yaml").read_text()
    )


@pytest.fixture(scope="module")
def brain_config():
    spec = importlib.util.spec_from_file_location(
        "brain_config_2026_10_09",
        REPO_ROOT / "packages" / "ai" / "brain_config.py",
    )
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# Mistral Large 4 — cost entries
# ---------------------------------------------------------------------------

class TestMistralLarge4CostEntry:
    def test_input_cost(self, ct):
        cost = ct.cost_for_tokens(MODEL_ID, 1_000_000, 0)
        assert cost == pytest.approx(1.36), (
            f"{MODEL_ID} input must be $1.36/MTok"
        )

    def test_output_cost(self, ct):
        cost = ct.cost_for_tokens(MODEL_ID, 0, 1_000_000)
        assert cost == pytest.approx(4.18), (
            f"{MODEL_ID} output must be $4.18/MTok"
        )

    def test_combined_cost(self, ct):
        """100K input + 20K output = $0.136 + $0.0836 = $0.2196."""
        cost = ct.cost_for_tokens(MODEL_ID, 100_000, 20_000)
        assert cost == pytest.approx(0.1360 + 0.0836, rel=1e-3), (
            "100K input + 20K output cost mismatch"
        )

    def test_cheaper_input_than_mistral_large_2(self, ct):
        """Large 4 input ($1.36) is cheaper than Large 2 ($3.00)."""
        large4 = ct.cost_for_tokens(MODEL_ID, 1_000_000, 0)
        large2 = ct.cost_for_tokens("mistral-large-latest", 1_000_000, 0)
        assert large4 < large2, (
            "Mistral Large 4 input must cost less than Mistral Large 2 per MTok"
        )

    def test_cheaper_output_than_mistral_large_2(self, ct):
        """Large 4 output ($4.18) is cheaper than Large 2 ($9.00)."""
        large4 = ct.cost_for_tokens(MODEL_ID, 0, 1_000_000)
        large2 = ct.cost_for_tokens("mistral-large-latest", 0, 1_000_000)
        assert large4 < large2, (
            "Mistral Large 4 output must cost less than Mistral Large 2 per MTok"
        )

    def test_more_expensive_than_mistral_small(self, ct):
        """Large 4 ($1.36 in) is more expensive than Small ($0.10 in)."""
        large4 = ct.cost_for_tokens(MODEL_ID, 1_000_000, 0)
        small = ct.cost_for_tokens("mistral-small-latest", 1_000_000, 0)
        assert large4 > small, (
            "Mistral Large 4 must cost more than Mistral Small on input"
        )


# ---------------------------------------------------------------------------
# Mistral Large 4 — config/llm/models.yaml declaration
# ---------------------------------------------------------------------------

class TestMistralLarge4ModelsYaml:
    def test_declared(self, llm_models):
        assert MODEL_ID in llm_models, (
            f"{MODEL_ID} must be declared in config/llm/models.yaml"
        )

    def test_provider(self, llm_models):
        assert llm_models[MODEL_ID]["provider"] == "mistral", (
            f"{MODEL_ID} must use the 'mistral' provider"
        )

    def test_context_window(self, llm_models):
        assert llm_models[MODEL_ID]["context_window"] == 131_072, (
            f"{MODEL_ID} context window must be 131072"
        )

    def test_supports_tools(self, llm_models):
        assert llm_models[MODEL_ID].get("supports_tools") is True, (
            f"{MODEL_ID} must declare supports_tools: true"
        )

    def test_supports_function_calling(self, llm_models):
        assert llm_models[MODEL_ID].get("supports_function_calling") is True

    def test_supports_json(self, llm_models):
        assert llm_models[MODEL_ID].get("supports_json") is True

    def test_supports_streaming(self, llm_models):
        assert llm_models[MODEL_ID].get("supports_streaming") is True

    def test_speed_tier_slow(self, llm_models):
        assert llm_models[MODEL_ID]["speed_tier"] == "slow", (
            f"{MODEL_ID} is a large MoE model and must have speed_tier 'slow'"
        )

    def test_display_name_set(self, llm_models):
        dn = llm_models[MODEL_ID].get("display_name", "")
        assert dn, f"{MODEL_ID} must have a display_name"
        assert "Large 4" in dn or "Chonk" in dn, (
            "display_name should reference Large 4 or Le Chonk"
        )


# ---------------------------------------------------------------------------
# Mistral Large 4 — config/models.yaml routing candidates
# ---------------------------------------------------------------------------

class TestMistralLarge4RoutingConfig:
    def test_in_mistral_candidates(self, routing_config):
        mistral = routing_config.get("providers", {}).get("mistral", {})
        candidates = mistral.get("candidates", [])
        assert MODEL_ID in candidates, (
            f"{MODEL_ID} must appear in config/models.yaml mistral candidates"
        )


# ---------------------------------------------------------------------------
# Mistral Large 4 — brain_config PROVIDER_CANDIDATES
# ---------------------------------------------------------------------------

class TestMistralLarge4BrainConfig:
    def test_in_provider_candidates(self, brain_config):
        candidates = brain_config.PROVIDER_CANDIDATES.get("mistral", [])
        assert MODEL_ID in candidates, (
            f"{MODEL_ID} must be in brain_config.PROVIDER_CANDIDATES['mistral']"
        )
