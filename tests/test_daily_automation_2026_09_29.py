"""tests/test_daily_automation_2026_09_29.py — Daily automation 2026-09-29.

Changes shipped today:
- ``claude-sonnet-5-5`` (Claude Sonnet 5.5) added to the model registry
  (config/llm/models.yaml) and to the anthropic/aerolink provider candidate
  lists (config/models.yaml, packages/ai/brain_config.py).
- A dated alias ``claude-sonnet-5-5-20260929`` added alongside.
- executor/verifier role_presets on both the ``anthropic`` and ``aerolink``
  providers updated from ``claude-sonnet-5`` to ``claude-sonnet-5-5``
  (20% cheaper at the same capability tier, following the Opus 5→5.5 precedent
  from 2026-09-24/25).
"""
from __future__ import annotations

import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
LLM_MODELS_YAML = REPO_ROOT / "config" / "llm" / "models.yaml"
MODELS_YAML = REPO_ROOT / "config" / "models.yaml"
BRAIN_CONFIG = REPO_ROOT / "packages" / "ai" / "brain_config.py"


@pytest.fixture(scope="module")
def llm_models() -> dict:
    return yaml.safe_load(LLM_MODELS_YAML.read_text())


@pytest.fixture(scope="module")
def models_yaml() -> dict:
    return yaml.safe_load(MODELS_YAML.read_text())


# ── Sonnet 5.5 in config/llm/models.yaml ─────────────────────────────────────

class TestSonnet55InLLMModels:
    """claude-sonnet-5-5 and its dated alias must be declared in config/llm/models.yaml."""

    def test_sonnet_55_declared(self, llm_models):
        assert "claude-sonnet-5-5" in llm_models["models"], (
            "claude-sonnet-5-5 must be declared in config/llm/models.yaml"
        )

    def test_sonnet_55_provider_is_anthropic(self, llm_models):
        entry = llm_models["models"]["claude-sonnet-5-5"]
        assert entry["provider"] == "anthropic"

    def test_sonnet_55_same_input_price_as_sonnet_5(self, llm_models):
        s5_in = llm_models["models"]["claude-sonnet-5"]["input_cost_per_1m"]
        s55_in = llm_models["models"]["claude-sonnet-5-5"]["input_cost_per_1m"]
        assert s55_in == s5_in, (
            f"claude-sonnet-5-5 input cost ({s55_in}) should equal "
            f"claude-sonnet-5 ({s5_in})"
        )

    def test_sonnet_55_same_output_price_as_sonnet_5(self, llm_models):
        s5_out = llm_models["models"]["claude-sonnet-5"]["output_cost_per_1m"]
        s55_out = llm_models["models"]["claude-sonnet-5-5"]["output_cost_per_1m"]
        assert s55_out == s5_out

    def test_sonnet_55_same_context_window_as_sonnet_5(self, llm_models):
        s5_ctx = llm_models["models"]["claude-sonnet-5"]["context_window"]
        s55_ctx = llm_models["models"]["claude-sonnet-5-5"]["context_window"]
        assert s55_ctx == s5_ctx == 1048576

    def test_sonnet_55_supports_tools(self, llm_models):
        entry = llm_models["models"]["claude-sonnet-5-5"]
        assert entry["supports_tools"] is True
        assert entry["supports_streaming"] is True
        assert entry["supports_reasoning"] is True

    def test_sonnet_55_dated_alias_declared(self, llm_models):
        assert "claude-sonnet-5-5-20260929" in llm_models["models"], (
            "Dated alias claude-sonnet-5-5-20260929 must be in config/llm/models.yaml"
        )

    def test_dated_alias_same_cost_as_base(self, llm_models):
        base = llm_models["models"]["claude-sonnet-5-5"]
        dated = llm_models["models"]["claude-sonnet-5-5-20260929"]
        assert base["input_cost_per_1m"] == dated["input_cost_per_1m"]
        assert base["output_cost_per_1m"] == dated["output_cost_per_1m"]


# ── Anthropic provider: role presets and candidates ───────────────────────────

class TestAnthropicRolePresetsUpdated:
    """anthropic executor/verifier must use claude-sonnet-5-5."""

    def test_anthropic_executor_is_sonnet_55(self, models_yaml):
        preset = models_yaml["providers"]["anthropic"]["role_presets"]
        assert preset["executor"] == "claude-sonnet-5-5", (
            "anthropic executor should be claude-sonnet-5-5 (20% cheaper than Sonnet 5)"
        )

    def test_anthropic_verifier_is_sonnet_55(self, models_yaml):
        preset = models_yaml["providers"]["anthropic"]["role_presets"]
        assert preset["verifier"] == "claude-sonnet-5-5"

    def test_anthropic_planner_unchanged(self, models_yaml):
        preset = models_yaml["providers"]["anthropic"]["role_presets"]
        assert preset["planner"] == "claude-opus-5-5"

    def test_anthropic_judge_unchanged(self, models_yaml):
        preset = models_yaml["providers"]["anthropic"]["role_presets"]
        assert preset["judge"] == "claude-opus-5-5"

    def test_sonnet_55_in_anthropic_candidates(self, models_yaml):
        candidates = models_yaml["providers"]["anthropic"]["candidates"]
        assert "claude-sonnet-5-5" in candidates

    def test_sonnet_55_before_sonnet_5_in_anthropic_candidates(self, models_yaml):
        candidates = models_yaml["providers"]["anthropic"]["candidates"]
        assert candidates.index("claude-sonnet-5-5") < candidates.index("claude-sonnet-5"), (
            "claude-sonnet-5-5 should appear before claude-sonnet-5 in anthropic candidates "
            "(newer/cheaper model preferred)"
        )

    def test_sonnet_5_still_present_as_fallback(self, models_yaml):
        candidates = models_yaml["providers"]["anthropic"]["candidates"]
        assert "claude-sonnet-5" in candidates


# ── Aerolink provider: role presets and candidates ────────────────────────────

class TestAerolinkRolePresetsUpdated:
    """aerolink executor/verifier must use claude-sonnet-5-5, mirroring anthropic."""

    def test_aerolink_executor_is_sonnet_55(self, models_yaml):
        preset = models_yaml["providers"]["aerolink"]["role_presets"]
        assert preset["executor"] == "claude-sonnet-5-5", (
            "Aerolink executor should be claude-sonnet-5-5 (mirrors anthropic provider)"
        )

    def test_aerolink_verifier_is_sonnet_55(self, models_yaml):
        preset = models_yaml["providers"]["aerolink"]["role_presets"]
        assert preset["verifier"] == "claude-sonnet-5-5"

    def test_aerolink_planner_unchanged(self, models_yaml):
        preset = models_yaml["providers"]["aerolink"]["role_presets"]
        assert preset["planner"] == "claude-opus-5-5"

    def test_aerolink_judge_unchanged(self, models_yaml):
        preset = models_yaml["providers"]["aerolink"]["role_presets"]
        assert preset["judge"] == "claude-opus-5-5"

    def test_sonnet_55_in_aerolink_candidates(self, models_yaml):
        candidates = models_yaml["providers"]["aerolink"]["candidates"]
        assert "claude-sonnet-5-5" in candidates

    def test_aerolink_and_anthropic_presets_agree_on_executor(self, models_yaml):
        aerolink = models_yaml["providers"]["aerolink"]["role_presets"]["executor"]
        anthropic = models_yaml["providers"]["anthropic"]["role_presets"]["executor"]
        assert aerolink == anthropic, (
            f"Aerolink executor ({aerolink!r}) should match anthropic executor "
            f"({anthropic!r}) — both serve the same Claude models"
        )

    def test_aerolink_and_anthropic_presets_agree_on_verifier(self, models_yaml):
        aerolink = models_yaml["providers"]["aerolink"]["role_presets"]["verifier"]
        anthropic = models_yaml["providers"]["anthropic"]["role_presets"]["verifier"]
        assert aerolink == anthropic


# ── brain_config.py mirrors config/models.yaml ───────────────────────────────

class TestBrainConfigMirrorsYaml:
    """packages/ai/brain_config.py PROVIDER_ROLE_PRESETS and PROVIDER_CANDIDATES
    must stay reconciled with config/models.yaml (CLAUDE.md rule 4)."""

    def _brain_config_text(self) -> str:
        return BRAIN_CONFIG.read_text(encoding="utf-8")

    def test_brain_config_anthropic_executor_is_sonnet_55(self):
        text = self._brain_config_text()
        assert '"claude-sonnet-5-5"' in text, (
            "packages/ai/brain_config.py must reference claude-sonnet-5-5 "
            "for the anthropic executor/verifier role"
        )

    def test_brain_config_anthropic_candidates_include_sonnet_55(self):
        text = self._brain_config_text()
        anthropic_start = text.index('"anthropic": [')
        next_bracket = text.index('],', anthropic_start)
        anthropic_block = text[anthropic_start:next_bracket]
        assert '"claude-sonnet-5-5"' in anthropic_block, (
            "brain_config.py PROVIDER_CANDIDATES['anthropic'] should include "
            "'claude-sonnet-5-5'"
        )

    def test_brain_config_aerolink_candidates_include_sonnet_55(self):
        text = self._brain_config_text()
        aerolink_start = text.index('"aerolink": [')
        next_bracket = text.index('],', aerolink_start)
        aerolink_block = text[aerolink_start:next_bracket]
        assert '"claude-sonnet-5-5"' in aerolink_block, (
            "brain_config.py PROVIDER_CANDIDATES['aerolink'] should include "
            "'claude-sonnet-5-5'"
        )
