"""tests/test_daily_automation_2026_10_19.py — Daily automation 2026-10-19.

Changes shipped today:
- **GLM-5.3 declared** (``glm-5.3`` via zhipu provider).
  Released 2026-08-14; API published 2026-08-18.
  Z.ai / ZhipuAI's current flagship GLM generation.
  1,000,000-token context (up from 131K in GLM-5.2); 128K max output.
  Supports function calling, JSON mode, streaming.
  Free-credits trial plan active — billed at $0.00 (list: $1.40/$4.40/MTok).
  Sources: requesty.ai/models/zai/glm-5.3,
           cloudprice.net/models/zhipu-glm-5-3, 2026-10-19.

- **GLM-5.3-Flash declared** (``glm-5.3-flash`` via zhipu provider).
  Faster/cheaper variant of GLM-5.3; same 1M-token context.
  Free-credits trial plan — billed at $0.00 (list: $0.15/$0.50/MTok).
  Source: felloai.com/glm-pricing/, 2026-10-19.

- **Kimi K3 declared** (``kimi-k3`` via moonshot provider).
  Moonshot AI MoE flagship. API released 2026-07-16.
  2.8T total parameters / 104B active. Context: 1,048,576 tokens.
  Max output: 131,072 tokens. Supports function calling, JSON mode, streaming.
  Pricing: $3.00/$15.00 per MTok (Moonshot official list, 2026-10-19).
  Sources: benchlm.ai/moonshot/api-pricing,
           openrouter.ai/moonshotai/kimi-k3, 2026-10-19.

Files changed:
  ``config/llm/models.yaml``, ``packages/ai/cost_tracker.py``,
  ``CHANGELOG.md``, ``docs/changelog.md``,
  ``tests/test_daily_automation_2026_10_19.py`` (this file).
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def ct():
    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_10_19",
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
# Cost tracker — GLM-5.3 (free-credits trial, $0.00)
# ---------------------------------------------------------------------------

class TestGlm53Cost:
    def test_input_cost_is_zero(self, ct):
        cost = ct.cost_for_tokens("glm-5.3", 1_000_000, 0)
        assert cost == pytest.approx(0.0), (
            "glm-5.3 input cost must be $0.00 (free-credits trial plan)"
        )

    def test_output_cost_is_zero(self, ct):
        cost = ct.cost_for_tokens("glm-5.3", 0, 1_000_000)
        assert cost == pytest.approx(0.0), (
            "glm-5.3 output cost must be $0.00 (free-credits trial plan)"
        )

    def test_combined_cost_is_zero(self, ct):
        cost = ct.cost_for_tokens("glm-5.3", 500_000, 500_000)
        assert cost == pytest.approx(0.0)

    def test_cost_is_float(self, ct):
        cost = ct.cost_for_tokens("glm-5.3", 100_000, 10_000)
        assert isinstance(cost, float)


# ---------------------------------------------------------------------------
# Cost tracker — GLM-5.3-Flash (free-credits trial, $0.00)
# ---------------------------------------------------------------------------

class TestGlm53FlashCost:
    def test_input_cost_is_zero(self, ct):
        cost = ct.cost_for_tokens("glm-5.3-flash", 1_000_000, 0)
        assert cost == pytest.approx(0.0), (
            "glm-5.3-flash input cost must be $0.00 (free-credits trial plan)"
        )

    def test_output_cost_is_zero(self, ct):
        cost = ct.cost_for_tokens("glm-5.3-flash", 0, 1_000_000)
        assert cost == pytest.approx(0.0), (
            "glm-5.3-flash output cost must be $0.00 (free-credits trial plan)"
        )

    def test_cost_is_float(self, ct):
        cost = ct.cost_for_tokens("glm-5.3-flash", 100_000, 10_000)
        assert isinstance(cost, float)


# ---------------------------------------------------------------------------
# Cost tracker — Kimi K3 ($3.00/$15.00 per MTok)
# ---------------------------------------------------------------------------

class TestKimiK3Cost:
    def test_input_cost(self, ct):
        cost = ct.cost_for_tokens("kimi-k3", 1_000_000, 0)
        assert cost == pytest.approx(3.0), (
            "kimi-k3 input cost must be $3.00/MTok (Moonshot official)"
        )

    def test_output_cost(self, ct):
        cost = ct.cost_for_tokens("kimi-k3", 0, 1_000_000)
        assert cost == pytest.approx(15.0), (
            "kimi-k3 output cost must be $15.00/MTok (Moonshot official)"
        )

    def test_combined_cost(self, ct):
        cost = ct.cost_for_tokens("kimi-k3", 100_000, 50_000)
        expected = (100_000 * 3.0 + 50_000 * 15.0) / 1_000_000
        assert cost == pytest.approx(expected)

    def test_cost_is_float(self, ct):
        cost = ct.cost_for_tokens("kimi-k3", 100_000, 10_000)
        assert isinstance(cost, float)


# ---------------------------------------------------------------------------
# models.yaml — GLM-5.3
# ---------------------------------------------------------------------------

class TestGlm53Yaml:
    def test_entry_present(self, llm_models):
        models = llm_models.get("models", {})
        assert "glm-5.3" in models, "glm-5.3 not found in config/llm/models.yaml"

    def test_provider_zhipu(self, llm_models):
        entry = llm_models["models"]["glm-5.3"]
        assert entry.get("provider") == "zhipu", "provider must be 'zhipu'"

    def test_context_window(self, llm_models):
        entry = llm_models["models"]["glm-5.3"]
        assert entry.get("context_window") == 1_000_000, (
            "context_window must be 1000000 (1M)"
        )

    def test_max_output_tokens(self, llm_models):
        entry = llm_models["models"]["glm-5.3"]
        assert entry.get("max_output_tokens") == 128_000

    def test_supports_tools(self, llm_models):
        entry = llm_models["models"]["glm-5.3"]
        assert entry.get("supports_tools") is True

    def test_supports_streaming(self, llm_models):
        entry = llm_models["models"]["glm-5.3"]
        assert entry.get("supports_streaming") is True

    def test_priority_above_glm52(self, llm_models):
        """GLM-5.3 must have lower priority number than GLM-5.2 (i.e. preferred first)."""
        models = llm_models.get("models", {})
        if "glm-5.2" in models:
            glm52_pri = models["glm-5.2"].get("priority", 999)
            glm53_pri = models["glm-5.3"].get("priority", 999)
            assert glm53_pri < glm52_pri, (
                f"glm-5.3 priority {glm53_pri} must be lower than "
                f"glm-5.2 priority {glm52_pri} (lower = more preferred)"
            )

    def test_display_name_present(self, llm_models):
        entry = llm_models["models"]["glm-5.3"]
        assert "display_name" in entry and entry["display_name"]

    def test_not_in_recommended_priority(self, llm_models):
        recommended = llm_models.get("recommended_priority", [])
        assert "glm-5.3" not in recommended, (
            "glm-5.3 should not be in recommended_priority (secondary provider)"
        )


# ---------------------------------------------------------------------------
# models.yaml — GLM-5.3-Flash
# ---------------------------------------------------------------------------

class TestGlm53FlashYaml:
    def test_entry_present(self, llm_models):
        models = llm_models.get("models", {})
        assert "glm-5.3-flash" in models, "glm-5.3-flash not found in config/llm/models.yaml"

    def test_provider_zhipu(self, llm_models):
        entry = llm_models["models"]["glm-5.3-flash"]
        assert entry.get("provider") == "zhipu"

    def test_context_window(self, llm_models):
        entry = llm_models["models"]["glm-5.3-flash"]
        assert entry.get("context_window") == 1_000_000

    def test_speed_tier_fast(self, llm_models):
        """Flash variant must be declared fast (for routing classification)."""
        entry = llm_models["models"]["glm-5.3-flash"]
        assert entry.get("speed_tier") == "fast", (
            "speed_tier must be 'fast' for the Flash variant"
        )

    def test_supports_tools(self, llm_models):
        entry = llm_models["models"]["glm-5.3-flash"]
        assert entry.get("supports_tools") is True

    def test_display_name_present(self, llm_models):
        entry = llm_models["models"]["glm-5.3-flash"]
        assert "display_name" in entry and entry["display_name"]


# ---------------------------------------------------------------------------
# models.yaml — Kimi K3
# ---------------------------------------------------------------------------

class TestKimiK3Yaml:
    def test_entry_present(self, llm_models):
        models = llm_models.get("models", {})
        assert "kimi-k3" in models, "kimi-k3 not found in config/llm/models.yaml"

    def test_provider_moonshot(self, llm_models):
        entry = llm_models["models"]["kimi-k3"]
        assert entry.get("provider") == "moonshot", "provider must be 'moonshot'"

    def test_context_window(self, llm_models):
        entry = llm_models["models"]["kimi-k3"]
        assert entry.get("context_window") == 1_048_576, (
            "context_window must be 1048576 (1M)"
        )

    def test_max_output_tokens(self, llm_models):
        entry = llm_models["models"]["kimi-k3"]
        assert entry.get("max_output_tokens") == 131_072

    def test_supports_tools(self, llm_models):
        entry = llm_models["models"]["kimi-k3"]
        assert entry.get("supports_tools") is True

    def test_supports_streaming(self, llm_models):
        entry = llm_models["models"]["kimi-k3"]
        assert entry.get("supports_streaming") is True

    def test_input_cost(self, llm_models):
        entry = llm_models["models"]["kimi-k3"]
        assert entry.get("input_cost_per_1m") == pytest.approx(3.0), (
            "input_cost_per_1m must be 3.0 ($3/MTok Moonshot official)"
        )

    def test_output_cost(self, llm_models):
        entry = llm_models["models"]["kimi-k3"]
        assert entry.get("output_cost_per_1m") == pytest.approx(15.0), (
            "output_cost_per_1m must be 15.0 ($15/MTok Moonshot official)"
        )

    def test_priority_below_moonshot_flagship(self, llm_models):
        """Kimi K3 must have lower number than moonshot-v1-128k (preferred first)."""
        models = llm_models.get("models", {})
        if "moonshot-v1-128k" in models:
            k3_pri = models["kimi-k3"].get("priority", 999)
            msv1_pri = models["moonshot-v1-128k"].get("priority", 999)
            assert k3_pri < msv1_pri, (
                f"kimi-k3 priority {k3_pri} must be lower than "
                f"moonshot-v1-128k priority {msv1_pri}"
            )

    def test_speed_tier_slow(self, llm_models):
        """Large MoE model; declared slow for routing classification."""
        entry = llm_models["models"]["kimi-k3"]
        assert entry.get("speed_tier") == "slow"

    def test_display_name_present(self, llm_models):
        entry = llm_models["models"]["kimi-k3"]
        assert "display_name" in entry and entry["display_name"]

    def test_not_in_recommended_priority(self, llm_models):
        recommended = llm_models.get("recommended_priority", [])
        assert "kimi-k3" not in recommended, (
            "kimi-k3 should not be in recommended_priority (secondary provider)"
        )
