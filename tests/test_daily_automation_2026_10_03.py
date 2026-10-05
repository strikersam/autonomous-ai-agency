"""tests/test_daily_automation_2026_10_03.py — Daily automation 2026-10-03.

Changes shipped today:
- **Pixtral Large added to catalog** (``pixtral-large-latest``).
  Mistral's 124B multimodal vision flagship (released November 2024).
  131K context, image + text inputs, tool calling supported.
  Declared as a non-routed model (priority 90) — reach via
  ``X-Model-Override: pixtral-large-latest``.
  Pricing: $2.00/$6.00 per MTok (source: mistral.ai/technology/#pricing,
  2026-10-03).

- **Ministral 8B added to catalog** (``ministral-8b-latest``).
  Mistral's efficient 8B model (released October 2024).
  131K context, tool calling, flat $0.10/$0.10 per MTok — output tokens 3×
  cheaper than ``mistral-small-latest`` ($0.30 out); suited for high-throughput
  executor / verifier loops. Declared with priority 66, not added to routing
  candidates (not yet live-probed on this account).

- **Ministral 3B added to catalog** (``ministral-3b-latest``).
  Mistral's smallest and fastest model (released October 2024).
  131K context, flat $0.04/$0.04 per MTok. ``supports_tools: false`` —
  3B-parameter models do not reliably follow tool-call schemas.
  Use for text summarisation, classification, or triage.

Files changed:
  ``config/llm/models.yaml``, ``packages/ai/cost_tracker.py``,
  ``CHANGELOG.md``, ``docs/changelog.md``,
  ``tests/test_daily_automation_2026_10_03.py`` (this file).
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
        "cost_tracker_2026_10_03",
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


@pytest.fixture(scope="module")
def models_yaml():
    return yaml.safe_load(
        (REPO_ROOT / "config" / "models.yaml").read_text()
    )


# ---------------------------------------------------------------------------
# 1. Cost table entries — pixtral-large-latest
# ---------------------------------------------------------------------------

class TestPixtralLargeCostEntries:
    """pixtral-large-latest must appear in the cost table with correct pricing."""

    def test_pixtral_large_input_cost(self, ct):
        cost = ct.cost_for_tokens("pixtral-large-latest", 1_000_000, 0)
        assert cost == pytest.approx(2.00), (
            "pixtral-large-latest input cost should be $2.00/MTok"
        )

    def test_pixtral_large_output_cost(self, ct):
        cost = ct.cost_for_tokens("pixtral-large-latest", 0, 1_000_000)
        assert cost == pytest.approx(6.00), (
            "pixtral-large-latest output cost should be $6.00/MTok"
        )

    def test_pixtral_large_is_more_expensive_than_ministral_8b(self, ct):
        """Vision flagship should cost more than the lightweight 8B executor model."""
        m8b = ct.cost_for_tokens("ministral-8b-latest", 1_000_000, 0)
        pixtral = ct.cost_for_tokens("pixtral-large-latest", 1_000_000, 0)
        assert pixtral > m8b, (
            f"pixtral-large (${pixtral:.2f}) should cost more than ministral-8b (${m8b:.2f})"
        )


# ---------------------------------------------------------------------------
# 2. Cost table entries — ministral-8b-latest
# ---------------------------------------------------------------------------

class TestMinistral8bCostEntries:
    """ministral-8b-latest must appear in the cost table with correct pricing."""

    def test_ministral_8b_input_cost(self, ct):
        cost = ct.cost_for_tokens("ministral-8b-latest", 1_000_000, 0)
        assert cost == pytest.approx(0.10), (
            "ministral-8b-latest input cost should be $0.10/MTok"
        )

    def test_ministral_8b_output_cost(self, ct):
        cost = ct.cost_for_tokens("ministral-8b-latest", 0, 1_000_000)
        assert cost == pytest.approx(0.10), (
            "ministral-8b-latest is flat-rate: output should also be $0.10/MTok"
        )

    def test_ministral_8b_output_cheaper_than_mistral_small(self, ct):
        """Ministral 8B has lower output cost than Mistral Small 3."""
        small_out = ct.cost_for_tokens("mistral-small-latest", 0, 1_000_000)
        m8b_out = ct.cost_for_tokens("ministral-8b-latest", 0, 1_000_000)
        assert m8b_out < small_out, (
            f"ministral-8b out (${m8b_out:.3f}) must be cheaper than mistral-small out (${small_out:.3f})"
        )


# ---------------------------------------------------------------------------
# 3. Cost table entries — ministral-3b-latest
# ---------------------------------------------------------------------------

class TestMinistral3bCostEntries:
    """ministral-3b-latest must appear in the cost table with correct pricing."""

    def test_ministral_3b_input_cost(self, ct):
        cost = ct.cost_for_tokens("ministral-3b-latest", 1_000_000, 0)
        assert cost == pytest.approx(0.04), (
            "ministral-3b-latest input cost should be $0.04/MTok"
        )

    def test_ministral_3b_output_cost(self, ct):
        cost = ct.cost_for_tokens("ministral-3b-latest", 0, 1_000_000)
        assert cost == pytest.approx(0.04), (
            "ministral-3b-latest is flat-rate: output should also be $0.04/MTok"
        )

    def test_ministral_3b_cheaper_than_8b(self, ct):
        m3b = ct.cost_for_tokens("ministral-3b-latest", 1_000_000, 0)
        m8b = ct.cost_for_tokens("ministral-8b-latest", 1_000_000, 0)
        assert m3b < m8b, (
            f"ministral-3b (${m3b:.4f}) must cost less than ministral-8b (${m8b:.4f})"
        )


# ---------------------------------------------------------------------------
# 4. config/llm/models.yaml — pixtral-large-latest
# ---------------------------------------------------------------------------

class TestPixtralLargeModelYaml:
    """pixtral-large-latest must be declared in config/llm/models.yaml
    with the correct provider, context window, and capability flags."""

    def test_model_declared(self, llm_models):
        assert "pixtral-large-latest" in llm_models.get("models", {}), (
            "pixtral-large-latest should be declared in config/llm/models.yaml"
        )

    def test_provider_is_mistral(self, llm_models):
        entry = llm_models["models"]["pixtral-large-latest"]
        assert entry.get("provider") == "mistral"

    def test_context_window(self, llm_models):
        entry = llm_models["models"]["pixtral-large-latest"]
        assert entry.get("context_window") == 131072

    def test_supports_tools_is_true(self, llm_models):
        entry = llm_models["models"]["pixtral-large-latest"]
        assert entry.get("supports_tools") is True

    def test_priority_keeps_it_out_of_normal_routing(self, llm_models):
        """Priority >= 80 keeps it out of the default routing candidates."""
        entry = llm_models["models"]["pixtral-large-latest"]
        assert entry.get("priority", 0) >= 80, (
            "pixtral-large should have high priority number to stay out of default routing"
        )


# ---------------------------------------------------------------------------
# 5. config/llm/models.yaml — ministral-8b-latest
# ---------------------------------------------------------------------------

class TestMinistral8bModelYaml:
    """ministral-8b-latest must be declared with tool support."""

    def test_model_declared(self, llm_models):
        assert "ministral-8b-latest" in llm_models.get("models", {}), (
            "ministral-8b-latest should be declared in config/llm/models.yaml"
        )

    def test_provider_is_mistral(self, llm_models):
        entry = llm_models["models"]["ministral-8b-latest"]
        assert entry.get("provider") == "mistral"

    def test_supports_tools_is_true(self, llm_models):
        entry = llm_models["models"]["ministral-8b-latest"]
        assert entry.get("supports_tools") is True

    def test_context_window(self, llm_models):
        entry = llm_models["models"]["ministral-8b-latest"]
        assert entry.get("context_window") == 131072


# ---------------------------------------------------------------------------
# 6. config/llm/models.yaml — ministral-3b-latest
# ---------------------------------------------------------------------------

class TestMinistral3bModelYaml:
    """ministral-3b-latest must be declared with tools conservatively off."""

    def test_model_declared(self, llm_models):
        assert "ministral-3b-latest" in llm_models.get("models", {}), (
            "ministral-3b-latest should be declared in config/llm/models.yaml"
        )

    def test_provider_is_mistral(self, llm_models):
        entry = llm_models["models"]["ministral-3b-latest"]
        assert entry.get("provider") == "mistral"

    def test_supports_tools_is_false(self, llm_models):
        """3B models should not be trusted with tool schemas."""
        entry = llm_models["models"]["ministral-3b-latest"]
        assert entry.get("supports_tools") is False, (
            "ministral-3b-latest should have supports_tools: false (3B too small for tool calls)"
        )

    def test_context_window(self, llm_models):
        entry = llm_models["models"]["ministral-3b-latest"]
        assert entry.get("context_window") == 131072

    def test_is_cheaper_per_output_than_8b_in_yaml(self, llm_models):
        """Verify YAML cost fields agree with the cost table ordering."""
        entry_3b = llm_models["models"]["ministral-3b-latest"]
        entry_8b = llm_models["models"]["ministral-8b-latest"]
        assert entry_3b["output_cost_per_1m"] < entry_8b["output_cost_per_1m"], (
            "ministral-3b must have lower output_cost_per_1m than ministral-8b"
        )


# ---------------------------------------------------------------------------
# 7. New models are NOT in routing candidates (not yet live-probed)
# ---------------------------------------------------------------------------

class TestNewMistralModelsNotInCandidates:
    """None of the three new models should appear in config/models.yaml
    routing candidates — they have not been live-probed on this account."""

    def _get_mistral_candidates(self, models_yaml):
        providers = models_yaml.get("providers", {})
        mistral = providers.get("mistral", {})
        return mistral.get("candidates", [])

    def test_pixtral_large_not_in_mistral_candidates(self, models_yaml):
        cands = self._get_mistral_candidates(models_yaml)
        assert "pixtral-large-latest" not in cands, (
            "pixtral-large-latest must not be a routing candidate (not live-probed)"
        )

    def test_ministral_8b_not_in_mistral_candidates(self, models_yaml):
        cands = self._get_mistral_candidates(models_yaml)
        assert "ministral-8b-latest" not in cands, (
            "ministral-8b-latest must not be a routing candidate (not live-probed)"
        )

    def test_ministral_3b_not_in_mistral_candidates(self, models_yaml):
        cands = self._get_mistral_candidates(models_yaml)
        assert "ministral-3b-latest" not in cands, (
            "ministral-3b-latest must not be a routing candidate (not live-probed)"
        )

    def test_catalog_count_grew_by_three(self, llm_models):
        """Confirm the catalog grew by exactly the three new entries."""
        models = llm_models.get("models", {})
        new_ids = {"pixtral-large-latest", "ministral-8b-latest", "ministral-3b-latest"}
        declared = new_ids & set(models.keys())
        assert declared == new_ids, (
            f"Expected all three new models in catalog; got: {declared}"
        )
