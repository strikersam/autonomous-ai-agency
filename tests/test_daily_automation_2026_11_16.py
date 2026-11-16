"""tests/test_daily_automation_2026_11_16.py — Daily automation 2026-11-16.

Changes shipped today:
- **Claude Fable 5.2 declared in model catalogue** (``claude-fable-5-2``).
  Anthropic's revised Fable 5 release, launched 2026-11-09. ~20 % cheaper than
  Fable 5.1 ($8/$40 vs $10/$50 per MTok). Same adaptive-thinking constraints
  (no temperature, no legacy extended-thinking budget). Cache reads: 2.5 % of
  the input rate ($0.20/MTok). Context: 1,048,576 tokens; max output: 131,072.
  OpenRouter ID: ``anthropic/claude-fable-5.2``.
  Sources: openrouter.ai/anthropic/claude-fable-5.2,
           models.litellm.ai/models/claude-fable-5-2,
           founderz.com/blog/claude-fable-5-2/, 2026-11-16.

- **Claude Mythos 5.2 declared in model catalogue** (``claude-mythos-5-2``).
  Same underlying model as Fable 5.2, available only to organisations verified
  through Anthropic's Cyber or Life Sciences programs; requires
  ``ROUTER_ALLOW_MYTHOS=1``. Identical pricing and capabilities.
  Sources: platform.claude.com/docs/en/models/mythos-5-2/overview.md,
           braindetox.kr/en/posts/claude_fable_mythos_52_release.html, 2026-11-16.

Files changed:
  ``config/llm/models.yaml``,
  ``packages/ai/cost_tracker.py``,
  ``packages/llm/providers/anthropic.py``,
  ``config/models.yaml``,
  ``packages/ai/brain_config.py``,
  ``CHANGELOG.md``, ``docs/changelog.md``,
  ``README.md``,
  ``tests/test_daily_automation_2026_11_16.py`` (this file).
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FABLE52_ID = "claude-fable-5-2"
FABLE52_INPUT_COST = 8.0
FABLE52_OUTPUT_COST = 40.0
FABLE52_CONTEXT = 1_048_576
FABLE52_MAX_OUTPUT = 131_072
FABLE52_CACHE_FRACTION = 0.025

MYTHOS52_ID = "claude-mythos-5-2"
MYTHOS52_INPUT_COST = 8.0
MYTHOS52_OUTPUT_COST = 40.0
MYTHOS52_CONTEXT = 1_048_576
MYTHOS52_MAX_OUTPUT = 131_072
MYTHOS52_CACHE_FRACTION = 0.025


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def ct():
    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_11_16",
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
def anthropic_provider_src():
    """Source text of anthropic.py — avoids importing httpx in a bare environment."""
    return (REPO_ROOT / "packages" / "llm" / "providers" / "anthropic.py").read_text()


# ---------------------------------------------------------------------------
# Claude Fable 5.2 — model catalogue
# ---------------------------------------------------------------------------


class TestFable52Catalogue:
    def test_present_in_llm_models(self, llm_models):
        models = llm_models.get("models", {})
        assert FABLE52_ID in models, f"{FABLE52_ID} not found in config/llm/models.yaml"

    def test_provider_is_anthropic(self, llm_models):
        entry = llm_models["models"][FABLE52_ID]
        assert entry["provider"] == "anthropic"

    def test_context_window(self, llm_models):
        entry = llm_models["models"][FABLE52_ID]
        assert entry["context_window"] == FABLE52_CONTEXT

    def test_max_output_tokens(self, llm_models):
        entry = llm_models["models"][FABLE52_ID]
        assert entry["max_output_tokens"] == FABLE52_MAX_OUTPUT

    def test_supports_tools(self, llm_models):
        entry = llm_models["models"][FABLE52_ID]
        assert entry.get("supports_tools") is True

    def test_supports_reasoning(self, llm_models):
        entry = llm_models["models"][FABLE52_ID]
        assert entry.get("supports_reasoning") is True

    def test_input_cost(self, llm_models):
        entry = llm_models["models"][FABLE52_ID]
        assert abs(entry["input_cost_per_1m"] - FABLE52_INPUT_COST) < 0.01

    def test_output_cost(self, llm_models):
        entry = llm_models["models"][FABLE52_ID]
        assert abs(entry["output_cost_per_1m"] - FABLE52_OUTPUT_COST) < 0.01

    def test_cheaper_than_fable51(self, llm_models):
        fable51 = llm_models["models"]["claude-fable-5-1"]
        fable52 = llm_models["models"][FABLE52_ID]
        assert fable52["input_cost_per_1m"] < fable51["input_cost_per_1m"], (
            "Fable 5.2 input cost must be lower than Fable 5.1"
        )

    def test_alias_fable52(self, llm_models):
        entry = llm_models["models"][FABLE52_ID]
        assert "fable5.2" in entry.get("aliases", [])


# ---------------------------------------------------------------------------
# Claude Fable 5.2 — cost tracker
# ---------------------------------------------------------------------------


class TestFable52CostTracker:
    def test_input_cost_per_token(self, ct):
        cost = ct.cost_for_tokens(FABLE52_ID, 1_000_000, 0)
        assert abs(cost - FABLE52_INPUT_COST) < 0.01

    def test_output_cost_per_token(self, ct):
        cost = ct.cost_for_tokens(FABLE52_ID, 0, 1_000_000)
        assert abs(cost - FABLE52_OUTPUT_COST) < 0.01

    def test_cache_read_fraction(self, ct):
        frac = ct._cache_read_fraction(FABLE52_ID)
        assert abs(frac - FABLE52_CACHE_FRACTION) < 0.001, (
            f"Expected cache read fraction ~{FABLE52_CACHE_FRACTION}, got {frac}"
        )

    def test_cache_reads_cheaper_than_fable51(self, ct):
        cost_52 = ct.cost_for_tokens(FABLE52_ID, 1_000_000, 0) * FABLE52_CACHE_FRACTION
        fable51_base = 10.0  # $10/MTok for Fable 5.1
        cost_51 = fable51_base * 0.025  # same fraction
        assert cost_52 < cost_51, "Fable 5.2 cache reads must cost less than Fable 5.1"


# ---------------------------------------------------------------------------
# Claude Fable 5.2 — adaptive thinking guard (source-level check)
# ---------------------------------------------------------------------------


class TestFable52AdaptiveThinking:
    def test_in_adaptive_thinking_models(self, anthropic_provider_src):
        assert '"claude-fable-5-2"' in anthropic_provider_src, (
            f"{FABLE52_ID} must appear in ADAPTIVE_THINKING_MODELS in anthropic.py"
        )


# ---------------------------------------------------------------------------
# Claude Mythos 5.2 — model catalogue
# ---------------------------------------------------------------------------


class TestMythos52Catalogue:
    def test_present_in_llm_models(self, llm_models):
        models = llm_models.get("models", {})
        assert MYTHOS52_ID in models, f"{MYTHOS52_ID} not found in config/llm/models.yaml"

    def test_provider_is_anthropic(self, llm_models):
        entry = llm_models["models"][MYTHOS52_ID]
        assert entry["provider"] == "anthropic"

    def test_context_window(self, llm_models):
        entry = llm_models["models"][MYTHOS52_ID]
        assert entry["context_window"] == MYTHOS52_CONTEXT

    def test_input_cost(self, llm_models):
        entry = llm_models["models"][MYTHOS52_ID]
        assert abs(entry["input_cost_per_1m"] - MYTHOS52_INPUT_COST) < 0.01

    def test_output_cost(self, llm_models):
        entry = llm_models["models"][MYTHOS52_ID]
        assert abs(entry["output_cost_per_1m"] - MYTHOS52_OUTPUT_COST) < 0.01

    def test_matches_fable52_pricing(self, llm_models):
        fable52 = llm_models["models"][FABLE52_ID]
        mythos52 = llm_models["models"][MYTHOS52_ID]
        assert fable52["input_cost_per_1m"] == mythos52["input_cost_per_1m"]
        assert fable52["output_cost_per_1m"] == mythos52["output_cost_per_1m"]

    def test_alias_mythos52(self, llm_models):
        entry = llm_models["models"][MYTHOS52_ID]
        assert "mythos5.2" in entry.get("aliases", [])


# ---------------------------------------------------------------------------
# Claude Mythos 5.2 — cost tracker
# ---------------------------------------------------------------------------


class TestMythos52CostTracker:
    def test_input_cost_per_token(self, ct):
        cost = ct.cost_for_tokens(MYTHOS52_ID, 1_000_000, 0)
        assert abs(cost - MYTHOS52_INPUT_COST) < 0.01

    def test_cache_read_fraction(self, ct):
        frac = ct._cache_read_fraction(MYTHOS52_ID)
        assert abs(frac - MYTHOS52_CACHE_FRACTION) < 0.001


# ---------------------------------------------------------------------------
# Claude Mythos 5.2 — adaptive thinking guard (source-level check)
# ---------------------------------------------------------------------------


class TestMythos52AdaptiveThinking:
    def test_in_adaptive_thinking_models(self, anthropic_provider_src):
        assert '"claude-mythos-5-2"' in anthropic_provider_src, (
            f"{MYTHOS52_ID} must appear in ADAPTIVE_THINKING_MODELS in anthropic.py"
        )


# ---------------------------------------------------------------------------
# Provider candidates — Fable 5.2 appears in anthropic + aerolink chains
# ---------------------------------------------------------------------------


class TestFable52ProviderCandidates:
    @pytest.fixture(scope="class")
    def models_yaml(self):
        return yaml.safe_load(
            (REPO_ROOT / "config" / "models.yaml").read_text()
        )

    @pytest.fixture(scope="class")
    def brain_config_src(self):
        """Source text of brain_config.py — avoids heavy transitive imports."""
        return (REPO_ROOT / "packages" / "ai" / "brain_config.py").read_text()

    def test_in_anthropic_candidates_yaml(self, models_yaml):
        candidates = models_yaml["providers"]["anthropic"]["candidates"]
        assert FABLE52_ID in candidates, (
            f"{FABLE52_ID} must appear in config/models.yaml anthropic candidates"
        )

    def test_in_aerolink_candidates_yaml(self, models_yaml):
        candidates = models_yaml["providers"]["aerolink"]["candidates"]
        assert FABLE52_ID in candidates, (
            f"{FABLE52_ID} must appear in config/models.yaml aerolink candidates"
        )

    def test_in_brain_config_source(self, brain_config_src):
        assert f'"{FABLE52_ID}"' in brain_config_src, (
            f"{FABLE52_ID} must appear in PROVIDER_CANDIDATES in brain_config.py"
        )

    def test_fable52_before_fable5_in_anthropic_yaml(self, models_yaml):
        candidates = models_yaml["providers"]["anthropic"]["candidates"]
        idx_52 = candidates.index(FABLE52_ID)
        idx_5 = candidates.index("claude-fable-5")
        assert idx_52 < idx_5, "Fable 5.2 should appear before Fable 5 in anthropic candidates"

    def test_fable52_before_fable5_in_brain_config(self, brain_config_src):
        idx_52 = brain_config_src.find(f'"{FABLE52_ID}"')
        idx_5 = brain_config_src.find('"claude-fable-5",')
        assert idx_52 != -1 and idx_5 != -1, "Both IDs must be in brain_config.py"
        assert idx_52 < idx_5, "Fable 5.2 should appear before Fable 5 in PROVIDER_CANDIDATES"


# ---------------------------------------------------------------------------
# Regression — Fable 5 and 5.1 entries unchanged
# ---------------------------------------------------------------------------


class TestFable5RegressionUnchanged:
    def test_fable5_still_present(self, llm_models):
        assert "claude-fable-5" in llm_models.get("models", {})

    def test_fable51_still_present(self, llm_models):
        assert "claude-fable-5-1" in llm_models.get("models", {})

    def test_fable5_cost_unchanged(self, ct):
        cost = ct.cost_for_tokens("claude-fable-5", 1_000_000, 0)
        assert abs(cost - 10.0) < 0.01, "Fable 5 input cost must remain $10/MTok"

    def test_fable51_cost_unchanged(self, ct):
        cost = ct.cost_for_tokens("claude-fable-5-1", 1_000_000, 0)
        assert abs(cost - 10.0) < 0.01, "Fable 5.1 input cost must remain $10/MTok"
