"""tests/test_daily_automation_2026_10_20.py — Daily automation 2026-10-20.

Changes shipped today:
- **DeepSeek V4 Pro declared** (``deepseek-ai/deepseek-v4-pro`` via NVIDIA NIM).
  Available on NVIDIA NIM since Aug 2026 (free tier).
  Heavy/Pro variant of the DeepSeek V4 generation.
  Also reachable via TokenIn as ``myt/deepseek-v4-pro-free`` (already wired in
  ``packages/ai/brain_config.py`` as the planner/judge for the tokenin provider).
  Cost: $0.00 via NIM free tier.
  Priority: 99 (explicit-only) — no completion probe on this account yet; the
  V4.1-Flash lesson showed that a NIM-listed id can time out in production.
  ``supports_tools: false`` conservatively until a tool_call probe returns green.
  Sources: ``packages/ai/cost_tracker.py`` comment (live in NIM catalog Aug 2026),
           NVIDIA NIM model catalog, 2026-10-20.

Files changed:
  ``config/llm/models.yaml``,
  ``CHANGELOG.md``, ``docs/changelog.md``,
  ``tests/test_daily_automation_2026_10_20.py`` (this file).
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

MODEL_ID = "deepseek-ai/deepseek-v4-pro"


@pytest.fixture(scope="module")
def ct():
    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_10_20",
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
# Cost tracker — DeepSeek V4 Pro (free via NIM)
# ---------------------------------------------------------------------------

class TestDeepSeekV4ProCost:
    def test_input_cost_is_zero(self, ct):
        cost = ct.cost_for_tokens(MODEL_ID, 1_000_000, 0)
        assert cost == pytest.approx(0.0), (
            f"{MODEL_ID} input cost must be $0.00 (NVIDIA NIM free tier)"
        )

    def test_output_cost_is_zero(self, ct):
        cost = ct.cost_for_tokens(MODEL_ID, 0, 1_000_000)
        assert cost == pytest.approx(0.0), (
            f"{MODEL_ID} output cost must be $0.00 (NVIDIA NIM free tier)"
        )

    def test_combined_cost_is_zero(self, ct):
        cost = ct.cost_for_tokens(MODEL_ID, 500_000, 500_000)
        assert cost == pytest.approx(0.0)

    def test_cost_is_float(self, ct):
        cost = ct.cost_for_tokens(MODEL_ID, 100_000, 10_000)
        assert isinstance(cost, float)


# ---------------------------------------------------------------------------
# models.yaml — DeepSeek V4 Pro
# ---------------------------------------------------------------------------

class TestDeepSeekV4ProYaml:
    def test_entry_present(self, llm_models):
        models = llm_models.get("models", {})
        assert MODEL_ID in models, f"{MODEL_ID} not found in config/llm/models.yaml"

    def test_provider_nvidia(self, llm_models):
        entry = llm_models["models"][MODEL_ID]
        assert entry.get("provider") == "nvidia", (
            "provider must be 'nvidia' (served via NVIDIA NIM free tier)"
        )

    def test_supports_tools_false(self, llm_models):
        """Tool calling must be declared false until a tool_call probe returns green."""
        entry = llm_models["models"][MODEL_ID]
        assert entry.get("supports_tools") is False, (
            "supports_tools must be false (not yet probed on this account)"
        )

    def test_supports_streaming(self, llm_models):
        entry = llm_models["models"][MODEL_ID]
        assert entry.get("supports_streaming") is True

    def test_priority_explicit_only(self, llm_models):
        """Unprobed NIM model must sit at priority 99 (explicit-only)."""
        entry = llm_models["models"][MODEL_ID]
        assert entry.get("priority") == 99, (
            f"{MODEL_ID} must be at priority 99 (explicit-only) until probed"
        )

    def test_speed_tier_slow(self, llm_models):
        """Pro/heavy model; declared slow for routing classification."""
        entry = llm_models["models"][MODEL_ID]
        assert entry.get("speed_tier") == "slow"

    def test_display_name_present(self, llm_models):
        entry = llm_models["models"][MODEL_ID]
        assert "display_name" in entry and entry["display_name"], (
            "display_name must be non-empty"
        )

    def test_not_in_recommended_priority_list(self, llm_models):
        """Unprobed model must not appear in the recommended_priority list."""
        recommended = llm_models.get("recommended_priority", [])
        assert MODEL_ID not in recommended, (
            f"{MODEL_ID} should not be in recommended_priority (unprobed)"
        )

    def test_input_cost_zero(self, llm_models):
        entry = llm_models["models"][MODEL_ID]
        # cost_per_1m fields are optional when the cost_tracker carries them;
        # if present, must be zero (free NIM tier).
        if "input_cost_per_1m" in entry:
            assert entry["input_cost_per_1m"] == pytest.approx(0.0)

    def test_output_cost_zero(self, llm_models):
        entry = llm_models["models"][MODEL_ID]
        if "output_cost_per_1m" in entry:
            assert entry["output_cost_per_1m"] == pytest.approx(0.0)
