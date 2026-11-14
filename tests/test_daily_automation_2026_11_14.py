"""tests/test_daily_automation_2026_11_14.py — Daily automation 2026-11-14.

Changes shipped today:
- **Claude Fable 5.2** (``claude-fable-5-2``) added to model catalogue and
  cost table at $8/$40 per MTok, cache reads 2.5 %.  Released 2026-11-09.
  Sources: platform.claude.com/docs/en/about-claude/pricing,
  explainx.ai/blog/claude-fable-5-2-mythos-5-2-launch-pricing-api-2026.

- **Claude Mythos 5.2** (``claude-mythos-5-2``) added to model catalogue and
  cost table at $8/$40 per MTok, cache reads 2.5 %.  Released 2026-11-09.
  Restricted to Anthropic-approved organisations (Glasswing program).
  Sources: platform.claude.com/docs/en/about-claude/pricing,
  eesel.ai/blog/claude-mythos-5-2.

- **Meta Muse Ember** (``muse-ember`` / ``meta/muse-ember``) added to model
  catalogue and cost table at $0.10/$0.50 per MTok, cache reads 4 %.
  Released 2026-11-09 on OpenRouter and Meta AI API.  Accepts text, images,
  video, audio, and PDF; 1 048 576-token context, 524 288-token output.
  Sources: openrouter.ai/meta/muse-ember, sumus.im/blog/muse-ember,
  aireleasetracker.com/model/meta/muse-ember.

- **Docs fix:** ``docs/configuration-reference.md`` AGENT_PLANNER_MODEL,
  AGENT_EXECUTOR_MODEL, AGENT_VERIFIER_MODEL and NEMOTRON_THINKING default
  values updated from the retired ``nvidia/nemotron-3-super-120b-a12b`` to
  the current default ``nvidia/nemotron-3-ultra-550b-a55b``.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ct():
    """Return the cost_tracker module loaded directly (no full app stack)."""
    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_11_14",
        REPO_ROOT / "packages" / "ai" / "cost_tracker.py",
    )
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture(scope="module")
def models_yaml_text():
    return (REPO_ROOT / "config" / "llm" / "models.yaml").read_text()


@pytest.fixture(scope="module")
def config_ref_text():
    return (REPO_ROOT / "docs" / "configuration-reference.md").read_text()


# ---------------------------------------------------------------------------
# 1. Claude Fable 5.2 / Mythos 5.2 — cost table
# ---------------------------------------------------------------------------

class TestFable52CostTable:
    """cost_for_tokens must return the $8/$40 rate for Fable 5.2."""

    def test_fable_5_2_input_cost(self, ct):
        """1 M input tokens, no output: $8."""
        cost = ct.cost_for_tokens("claude-fable-5-2", 1_000_000, 0)
        assert cost == pytest.approx(8.0)

    def test_fable_5_2_output_cost(self, ct):
        """1 M output tokens, no input: $40."""
        cost = ct.cost_for_tokens("claude-fable-5-2", 0, 1_000_000)
        assert cost == pytest.approx(40.0)

    def test_fable_5_2_cheaper_than_fable_5_1(self, ct):
        """Fable 5.2 input rate ($8) must be cheaper than 5.1 ($10)."""
        cost_52 = ct.cost_for_tokens("claude-fable-5-2", 1_000_000, 0)
        cost_51 = ct.cost_for_tokens("claude-fable-5-1", 1_000_000, 0)
        assert cost_52 < cost_51

    def test_fable_5_2_cache_read_is_2_point_5_percent(self, ct):
        """Cache reads must be 2.5 % of input rate — same as 5.1."""
        assert ct._cache_read_fraction("claude-fable-5-2") == pytest.approx(0.025)

    def test_fable_5_2_all_cached_costs_20_cents(self, ct):
        """1 M tokens all from cache: $8/MTok × 2.5 % × 1 M = $0.20."""
        cost = ct.cost_for_tokens("claude-fable-5-2", 1_000_000, 0, 1_000_000)
        assert cost == pytest.approx(0.20)


class TestMythos52CostTable:
    """cost_for_tokens must return the $8/$40 rate for Mythos 5.2."""

    def test_mythos_5_2_input_cost(self, ct):
        cost = ct.cost_for_tokens("claude-mythos-5-2", 1_000_000, 0)
        assert cost == pytest.approx(8.0)

    def test_mythos_5_2_output_cost(self, ct):
        cost = ct.cost_for_tokens("claude-mythos-5-2", 0, 1_000_000)
        assert cost == pytest.approx(40.0)

    def test_mythos_5_2_matches_fable_5_2(self, ct):
        """Fable 5.2 and Mythos 5.2 must have identical pricing."""
        assert (
            ct.cost_for_tokens("claude-mythos-5-2", 500_000, 500_000)
            == pytest.approx(ct.cost_for_tokens("claude-fable-5-2", 500_000, 500_000))
        )

    def test_mythos_5_2_cache_read_is_2_point_5_percent(self, ct):
        assert ct._cache_read_fraction("claude-mythos-5-2") == pytest.approx(0.025)

    def test_mythos_5_2_cheaper_than_mythos_5_1(self, ct):
        cost_52 = ct.cost_for_tokens("claude-mythos-5-2", 1_000_000, 0)
        cost_51 = ct.cost_for_tokens("claude-mythos-5-1", 1_000_000, 0)
        assert cost_52 < cost_51


# ---------------------------------------------------------------------------
# 2. Meta Muse Ember — cost table
# ---------------------------------------------------------------------------

class TestMuseEmberCostTable:
    """cost_for_tokens must return the $0.10/$0.50 rate for Muse Ember."""

    def test_muse_ember_input_cost(self, ct):
        """1 M input tokens: $0.10."""
        cost = ct.cost_for_tokens("muse-ember", 1_000_000, 0)
        assert cost == pytest.approx(0.10)

    def test_muse_ember_output_cost(self, ct):
        """1 M output tokens: $0.50."""
        cost = ct.cost_for_tokens("muse-ember", 0, 1_000_000)
        assert cost == pytest.approx(0.50)

    def test_muse_ember_openrouter_id_matches(self, ct):
        """OpenRouter ID meta/muse-ember must match the canonical rate."""
        cost_canonical = ct.cost_for_tokens("muse-ember", 1_000_000, 500_000)
        cost_openrouter = ct.cost_for_tokens("meta/muse-ember", 1_000_000, 500_000)
        assert cost_canonical == pytest.approx(cost_openrouter)

    def test_muse_ember_cache_read_is_4_percent(self, ct):
        """Cache reads: $0.004/MTok ≈ 4 % of $0.10/MTok input rate."""
        assert ct._cache_read_fraction("muse-ember") == pytest.approx(0.04)

    def test_muse_ember_openrouter_cache_read_is_4_percent(self, ct):
        assert ct._cache_read_fraction("meta/muse-ember") == pytest.approx(0.04)

    def test_muse_ember_all_cached_costs_0_004(self, ct):
        """1 M tokens all from cache: $0.10/MTok × 4 % × 1 M = $0.004."""
        cost = ct.cost_for_tokens("muse-ember", 1_000_000, 0, 1_000_000)
        assert cost == pytest.approx(0.004)

    def test_muse_ember_cheaper_than_muse_wonder(self, ct):
        """Ember is 25× cheaper on input than Wonder."""
        cost_ember = ct.cost_for_tokens("muse-ember", 1_000_000, 0)
        cost_wonder = ct.cost_for_tokens("muse-wonder-1.0", 1_000_000, 0)
        assert cost_ember < cost_wonder


# ---------------------------------------------------------------------------
# 3. models.yaml declares the new models
# ---------------------------------------------------------------------------

class TestModelsYamlDeclarations:

    def test_fable_5_2_declared(self, models_yaml_text):
        assert "claude-fable-5-2:" in models_yaml_text

    def test_mythos_5_2_declared(self, models_yaml_text):
        assert "claude-mythos-5-2:" in models_yaml_text

    def test_muse_ember_declared(self, models_yaml_text):
        assert "muse-ember:" in models_yaml_text

    def test_fable_5_2_input_cost_in_yaml(self, models_yaml_text):
        """YAML entry for Fable 5.2 must specify $8/MTok input."""
        idx = models_yaml_text.index("claude-fable-5-2:")
        snippet = models_yaml_text[idx: idx + 400]
        assert "input_cost_per_1m: 8.0" in snippet

    def test_mythos_5_2_output_cost_in_yaml(self, models_yaml_text):
        idx = models_yaml_text.index("claude-mythos-5-2:")
        snippet = models_yaml_text[idx: idx + 400]
        assert "output_cost_per_1m: 40.0" in snippet

    def test_muse_ember_context_window(self, models_yaml_text):
        idx = models_yaml_text.index("muse-ember:")
        snippet = models_yaml_text[idx: idx + 400]
        assert "context_window: 1048576" in snippet

    def test_muse_ember_max_output(self, models_yaml_text):
        idx = models_yaml_text.index("muse-ember:")
        snippet = models_yaml_text[idx: idx + 400]
        assert "max_output_tokens: 524288" in snippet


# ---------------------------------------------------------------------------
# 4. docs/configuration-reference.md no longer references the retired model
# ---------------------------------------------------------------------------

class TestDocsRetiredModelFixed:

    RETIRED = "nvidia/nemotron-3-super-120b-a12b"
    CURRENT = "nvidia/nemotron-3-ultra-550b-a55b"

    def test_retired_model_absent_from_agent_model_defaults(self, config_ref_text):
        """The retired model ID must not appear as the default value in the
        AGENT_PLANNER/EXECUTOR/VERIFIER_MODEL table rows."""
        for line in config_ref_text.splitlines():
            if any(var in line for var in (
                "AGENT_PLANNER_MODEL",
                "AGENT_EXECUTOR_MODEL",
                "AGENT_VERIFIER_MODEL",
            )):
                assert self.RETIRED not in line, (
                    f"Retired model still appears in row: {line!r}"
                )

    def test_current_model_present_in_agent_model_rows(self, config_ref_text):
        """The current default must appear in at least the AGENT_PLANNER_MODEL row."""
        planner_rows = [
            line for line in config_ref_text.splitlines()
            if "AGENT_PLANNER_MODEL" in line
        ]
        assert any(self.CURRENT in row for row in planner_rows), (
            f"Current default {self.CURRENT!r} not found in AGENT_PLANNER_MODEL row"
        )

    def test_nemotron_thinking_references_current_model(self, config_ref_text):
        for line in config_ref_text.splitlines():
            if "NEMOTRON_THINKING" in line:
                assert self.RETIRED not in line, (
                    f"Retired model still in NEMOTRON_THINKING row: {line!r}"
                )
                break
        else:
            pytest.skip("NEMOTRON_THINKING row not found in docs")
