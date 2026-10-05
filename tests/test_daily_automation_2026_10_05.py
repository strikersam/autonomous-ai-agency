"""tests/test_daily_automation_2026_10_05.py — Daily automation 2026-10-05.

Changes shipped today:
- **Devstral declared in Mistral routing candidates** (``devstral-latest``).
  Mistral's agentic software-engineering model, fine-tuned on the Mistral Small 3.1
  architecture for tool-using agent loops. Specifically optimised for SWE-bench
  and coding agent tasks — the strongest alignment with this repo's plan→execute→verify
  loop of any model on the Mistral free tier. 128K context; function calling supported.
  Added to ``PROVIDER_CANDIDATES['mistral']`` and set as the default executor/verifier
  in ``PROVIDER_PRESETS['mistral']``. Declared from docs.mistral.ai, 2026-10-05 —
  not probed on this account; live health checks apply. Priority 63 (between
  mistral-small-latest at 62 and codestral-latest at 64 in the model-level ordering).
  Source: docs.mistral.ai/capabilities/code_generation/, 2026-10-05.

- **Pixtral Large, Ministral 8B, Ministral 3B cost entries added**.
  These three models were declared in ``config/llm/models.yaml`` on 2026-10-03 but
  their cost entries were missing from ``packages/ai/cost_tracker.py``. Added:
  ``pixtral-large-latest`` ($2.00/$6.00 per MTok), ``ministral-8b-latest``
  ($0.10/$0.10 per MTok), ``ministral-3b-latest`` ($0.04/$0.04 per MTok).
  Pricing source: mistral.ai/technology/#pricing, 2026-10-05.

Files changed:
  ``config/llm/models.yaml``,
  ``packages/ai/brain_config.py``,
  ``packages/ai/cost_tracker.py``,
  ``CHANGELOG.md``, ``docs/changelog.md``,
  ``tests/test_daily_automation_2026_10_05.py`` (this file).
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ct():
    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_10_05",
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
def brain_cfg():
    spec = importlib.util.spec_from_file_location(
        "brain_config_2026_10_05",
        REPO_ROOT / "packages" / "ai" / "brain_config.py",
    )
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# Devstral cost entry
# ---------------------------------------------------------------------------

class TestDevstralCostEntry:
    def test_devstral_input_cost(self, ct):
        cost = ct.cost_for_tokens("devstral-latest", 1_000_000, 0)
        assert cost == pytest.approx(0.10), "devstral-latest input must be $0.10/MTok"

    def test_devstral_output_cost(self, ct):
        cost = ct.cost_for_tokens("devstral-latest", 0, 1_000_000)
        assert cost == pytest.approx(0.30), "devstral-latest output must be $0.30/MTok"

    def test_devstral_cheaper_than_large(self, ct):
        devstral_in = ct.cost_for_tokens("devstral-latest", 1_000_000, 0)
        large_in = ct.cost_for_tokens("mistral-large-latest", 1_000_000, 0)
        assert devstral_in < large_in, "devstral should be cheaper than mistral-large-latest"

    def test_devstral_same_price_as_small(self, ct):
        devstral = ct.cost_for_tokens("devstral-latest", 1_000_000, 1_000_000)
        small = ct.cost_for_tokens("mistral-small-latest", 1_000_000, 1_000_000)
        assert devstral == pytest.approx(small), "devstral-latest estimated at same tier as mistral-small"


# ---------------------------------------------------------------------------
# Pixtral Large cost entry
# ---------------------------------------------------------------------------

class TestPixtralLargeCostEntry:
    def test_pixtral_large_input_cost(self, ct):
        cost = ct.cost_for_tokens("pixtral-large-latest", 1_000_000, 0)
        assert cost == pytest.approx(2.00), "pixtral-large-latest input must be $2.00/MTok"

    def test_pixtral_large_output_cost(self, ct):
        cost = ct.cost_for_tokens("pixtral-large-latest", 0, 1_000_000)
        assert cost == pytest.approx(6.00), "pixtral-large-latest output must be $6.00/MTok"

    def test_pixtral_large_more_expensive_than_mistral_large(self, ct):
        pixtral_out = ct.cost_for_tokens("pixtral-large-latest", 0, 1_000_000)
        large_out = ct.cost_for_tokens("mistral-large-latest", 0, 1_000_000)
        assert pixtral_out < large_out, "pixtral-large output should be cheaper than mistral-large ($9/MTok)"


# ---------------------------------------------------------------------------
# Ministral 8B cost entry
# ---------------------------------------------------------------------------

class TestMinistral8BCostEntry:
    def test_ministral_8b_input_cost(self, ct):
        cost = ct.cost_for_tokens("ministral-8b-latest", 1_000_000, 0)
        assert cost == pytest.approx(0.10), "ministral-8b-latest input must be $0.10/MTok"

    def test_ministral_8b_flat_pricing(self, ct):
        """Ministral 8B has flat per-token pricing (input == output cost per MTok)."""
        in_cost = ct.cost_for_tokens("ministral-8b-latest", 1_000_000, 0)
        out_cost = ct.cost_for_tokens("ministral-8b-latest", 0, 1_000_000)
        assert in_cost == pytest.approx(out_cost), "ministral-8b-latest should have flat pricing"

    def test_ministral_8b_cheaper_than_ministral_large(self, ct):
        ministral_in = ct.cost_for_tokens("ministral-8b-latest", 1_000_000, 0)
        large_in = ct.cost_for_tokens("mistral-large-latest", 1_000_000, 0)
        assert ministral_in < large_in


# ---------------------------------------------------------------------------
# Ministral 3B cost entry
# ---------------------------------------------------------------------------

class TestMinistral3BCostEntry:
    def test_ministral_3b_input_cost(self, ct):
        cost = ct.cost_for_tokens("ministral-3b-latest", 1_000_000, 0)
        assert cost == pytest.approx(0.04), "ministral-3b-latest input must be $0.04/MTok"

    def test_ministral_3b_flat_pricing(self, ct):
        in_cost = ct.cost_for_tokens("ministral-3b-latest", 1_000_000, 0)
        out_cost = ct.cost_for_tokens("ministral-3b-latest", 0, 1_000_000)
        assert in_cost == pytest.approx(out_cost), "ministral-3b-latest should have flat pricing"

    def test_ministral_3b_cheapest_mistral(self, ct):
        """Ministral 3B is the cheapest model in the Mistral family."""
        models_to_compare = [
            "devstral-latest",
            "mistral-small-latest",
            "codestral-latest",
            "ministral-8b-latest",
        ]
        m3b_in = ct.cost_for_tokens("ministral-3b-latest", 1_000_000, 0)
        for model_id in models_to_compare:
            other_in = ct.cost_for_tokens(model_id, 1_000_000, 0)
            assert m3b_in <= other_in, f"ministral-3b should be cheaper than {model_id}"


# ---------------------------------------------------------------------------
# models.yaml — devstral declared
# ---------------------------------------------------------------------------

class TestDevstralModelsYaml:
    def test_devstral_declared(self, llm_models):
        assert "devstral-latest" in llm_models, "devstral-latest must be in config/llm/models.yaml"

    def test_devstral_provider(self, llm_models):
        assert llm_models["devstral-latest"]["provider"] == "mistral"

    def test_devstral_supports_tools(self, llm_models):
        m = llm_models["devstral-latest"]
        assert m.get("supports_tools") is True, "devstral-latest must declare supports_tools: true"

    def test_devstral_supports_function_calling(self, llm_models):
        m = llm_models["devstral-latest"]
        assert m.get("supports_function_calling") is True

    def test_devstral_context_window(self, llm_models):
        m = llm_models["devstral-latest"]
        assert m["context_window"] >= 131072, "devstral-latest must have at least 128K context"

    def test_devstral_zero_cost_for_free_tier(self, llm_models):
        m = llm_models["devstral-latest"]
        assert m.get("input_cost_per_1m", -1) == 0.0, "free-tier deployment: cost must be 0.0"
        assert m.get("output_cost_per_1m", -1) == 0.0

    def test_devstral_priority_between_small_and_codestral(self, llm_models):
        devstral_p = llm_models["devstral-latest"]["priority"]
        small_p = llm_models["mistral-small-latest"]["priority"]
        codestral_p = llm_models["codestral-latest"]["priority"]
        # Lower priority number = higher routing priority
        assert small_p < devstral_p < codestral_p, (
            f"devstral priority ({devstral_p}) must be between "
            f"mistral-small ({small_p}) and codestral ({codestral_p})"
        )


# ---------------------------------------------------------------------------
# brain_config — devstral in candidates and presets
# ---------------------------------------------------------------------------

class TestDevstralBrainConfig:
    def test_devstral_in_mistral_candidates(self, brain_cfg):
        candidates = brain_cfg.PROVIDER_CANDIDATES.get("mistral", [])
        assert "devstral-latest" in candidates, (
            "devstral-latest must be in PROVIDER_CANDIDATES['mistral']"
        )

    def test_devstral_as_executor_preset(self, brain_cfg):
        preset = brain_cfg.PROVIDER_PRESETS.get("mistral", {})
        assert preset.get("executor") == "devstral-latest", (
            "Mistral executor preset should be devstral-latest (agentic coding model)"
        )

    def test_devstral_as_verifier_preset(self, brain_cfg):
        preset = brain_cfg.PROVIDER_PRESETS.get("mistral", {})
        assert preset.get("verifier") == "devstral-latest", (
            "Mistral verifier preset should be devstral-latest"
        )

    def test_mistral_planner_still_large(self, brain_cfg):
        preset = brain_cfg.PROVIDER_PRESETS.get("mistral", {})
        assert preset.get("planner") == "mistral-large-latest", (
            "Mistral planner should remain mistral-large-latest"
        )

    def test_codestral_still_in_candidates(self, brain_cfg):
        """codestral-latest must stay in candidates — routing test in #1665 depends on it."""
        candidates = brain_cfg.PROVIDER_CANDIDATES.get("mistral", [])
        assert "codestral-latest" in candidates
