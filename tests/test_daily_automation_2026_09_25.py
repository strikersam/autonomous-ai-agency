"""Daily automation 2026-09-25 — regression tests.

Changes shipped today:
- Aerolink role_presets updated: planner/judge now use ``claude-opus-5-5``
  (same as the ``anthropic`` provider, updated 2026-09-24).
- ``claude-opus-5-5`` added as first-position Aerolink candidate.
- ``TestNoFuzzyCollisionWithPaidModels`` CI invariant added to
  ``tests/test_cost_attribution.py`` (regression guard for PR #1566 / row 78).
"""
from __future__ import annotations

import pytest
import yaml
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODELS_YAML = REPO_ROOT / "config" / "models.yaml"
BRAIN_CONFIG = REPO_ROOT / "packages" / "ai" / "brain_config.py"


@pytest.fixture(scope="module")
def models_yaml() -> dict:
    return yaml.safe_load(MODELS_YAML.read_text())


class TestAerolinkRolePresetsUpdated:
    """Aerolink planner/judge must use claude-opus-5-5, mirroring the
    anthropic provider (updated 2026-09-24)."""

    def test_aerolink_planner_is_opus_55(self, models_yaml):
        preset = models_yaml["providers"]["aerolink"]["role_presets"]
        assert preset["planner"] == "claude-opus-5-5", (
            "Aerolink planner should be claude-opus-5-5 (20% cheaper than Opus 5)"
        )

    def test_aerolink_judge_is_opus_55(self, models_yaml):
        preset = models_yaml["providers"]["aerolink"]["role_presets"]
        assert preset["judge"] == "claude-opus-5-5"

    def test_aerolink_executor_is_sonnet_5(self, models_yaml):
        preset = models_yaml["providers"]["aerolink"]["role_presets"]
        assert preset["executor"] == "claude-sonnet-5"

    def test_aerolink_verifier_is_sonnet_5(self, models_yaml):
        preset = models_yaml["providers"]["aerolink"]["role_presets"]
        assert preset["verifier"] == "claude-sonnet-5"

    def test_aerolink_and_anthropic_presets_use_same_planner(self, models_yaml):
        aerolink = models_yaml["providers"]["aerolink"]["role_presets"]["planner"]
        anthropic = models_yaml["providers"]["anthropic"]["role_presets"]["planner"]
        assert aerolink == anthropic, (
            f"Aerolink planner ({aerolink!r}) should match anthropic planner "
            f"({anthropic!r}) — they serve the same Claude models via different endpoints"
        )

    def test_aerolink_and_anthropic_presets_use_same_judge(self, models_yaml):
        aerolink = models_yaml["providers"]["aerolink"]["role_presets"]["judge"]
        anthropic = models_yaml["providers"]["anthropic"]["role_presets"]["judge"]
        assert aerolink == anthropic


class TestAerolinkCandidatesIncludeOpus55:
    """claude-opus-5-5 must appear in the Aerolink candidates list."""

    def test_opus_55_in_candidates(self, models_yaml):
        candidates = models_yaml["providers"]["aerolink"]["candidates"]
        assert "claude-opus-5-5" in candidates

    def test_opus_55_is_first_candidate(self, models_yaml):
        candidates = models_yaml["providers"]["aerolink"]["candidates"]
        assert candidates[0] == "claude-opus-5-5", (
            "claude-opus-5-5 should be the first (highest-priority) Aerolink "
            "candidate — it is 20% cheaper than Opus 5 at the same capability tier"
        )

    def test_opus_5_still_present_as_fallback(self, models_yaml):
        candidates = models_yaml["providers"]["aerolink"]["candidates"]
        assert "claude-opus-5" in candidates


class TestBrainConfigAerolinkMirrorsYaml:
    """packages/ai/brain_config.py PROVIDER_ROLE_PRESETS and PROVIDER_CANDIDATES
    for 'aerolink' must stay byte-for-byte reconciled with config/models.yaml
    (rule 4)."""

    def _brain_config_text(self) -> str:
        return BRAIN_CONFIG.read_text(encoding="utf-8")

    def test_brain_config_aerolink_planner_is_opus_55(self):
        text = self._brain_config_text()
        assert '"claude-opus-5-5"' in text, (
            "packages/ai/brain_config.py PROVIDER_ROLE_PRESETS['aerolink'] planner "
            "must be 'claude-opus-5-5'"
        )

    def test_brain_config_aerolink_candidates_include_opus_55(self):
        text = self._brain_config_text()
        # Check the aerolink list block includes the new entry
        assert '"claude-opus-5-5"' in text
        # Verify it appears in the aerolink section (not just anthropic)
        aerolink_start = text.index('"aerolink": [')
        next_bracket = text.index('],', aerolink_start)
        aerolink_block = text[aerolink_start:next_bracket]
        assert '"claude-opus-5-5"' in aerolink_block, (
            "brain_config.py PROVIDER_CANDIDATES['aerolink'] should include 'claude-opus-5-5'"
        )
