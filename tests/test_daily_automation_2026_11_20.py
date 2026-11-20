"""tests/test_daily_automation_2026_11_20.py — Daily automation 2026-11-20.

Changes shipped today:

- **Claude Haiku 5.5 added to provider candidate lists** (``claude-haiku-5-5``,
  ``claude-haiku-5-5-20261007``). The model was released 2026-10-07 and already
  present in ``cost_tracker._DEFAULT_COST_TABLE`` and ``config/llm/models.yaml``
  but was not yet offered as a failover candidate in ``config/models.yaml``
  (anthropic + aerolink providers) or ``brain_config.PROVIDER_CANDIDATES``.
  Haiku 5.5 is significantly cheaper than Haiku 4.5 ($0.10/$0.50 vs
  $1.00/$5.00 per MTok) with 1M-token context.

- **GPT-6 Cyber added to cost table** (``gpt-6-cyber``,
  ``openai/gpt-6-cyber``). Released 2026-11-05; restricted to organisations
  approved for Daybreak Red. Priced at $20.00/$100.00 per MTok input/output
  (2× GPT-6 Astra). Context: 1,100,000 tokens.
  Sources: developers.openai.com/api/docs/models/gpt-6-cyber,
           tokencost.app/models/gpt-6-cyber, 2026-11-20.

- **docs/configuration-reference.md** corrected: ``AGENT_PLANNER_MODEL``,
  ``AGENT_EXECUTOR_MODEL``, ``AGENT_VERIFIER_MODEL`` and ``NEMOTRON_THINKING``
  now reference the current default ``nvidia/nemotron-3-ultra-550b-a55b``
  instead of the retired ``nvidia/nemotron-3-super-120b-a12b``.

Files changed:
  ``config/models.yaml``,
  ``packages/ai/brain_config.py``,
  ``packages/ai/cost_tracker.py``,
  ``docs/configuration-reference.md``,
  ``CHANGELOG.md``, ``docs/changelog.md``,
  ``tests/test_daily_automation_2026_11_20.py`` (this file).
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

HAIKU55_ID = "claude-haiku-5-5"
HAIKU55_DATED_ID = "claude-haiku-5-5-20261007"
HAIKU55_INPUT_COST = 0.10
HAIKU55_OUTPUT_COST = 0.50

GPT6_CYBER_ID = "gpt-6-cyber"
GPT6_CYBER_OPENROUTER_ID = "openai/gpt-6-cyber"
GPT6_CYBER_INPUT_COST = 20.0
GPT6_CYBER_OUTPUT_COST = 100.0
GPT6_CYBER_CONTEXT = 1_100_000

RETIRED_DEFAULT = "nvidia/nemotron-3-super-120b-a12b"
CURRENT_DEFAULT = "nvidia/nemotron-3-ultra-550b-a55b"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def ct():
    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_11_20",
        REPO_ROOT / "packages" / "ai" / "cost_tracker.py",
    )
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture(scope="module")
def models_yaml():
    return yaml.safe_load(
        (REPO_ROOT / "config" / "models.yaml").read_text()
    )


@pytest.fixture(scope="module")
def brain_config_src():
    return (REPO_ROOT / "packages" / "ai" / "brain_config.py").read_text()


@pytest.fixture(scope="module")
def config_ref_src():
    return (REPO_ROOT / "docs" / "configuration-reference.md").read_text()


# ---------------------------------------------------------------------------
# Claude Haiku 5.5 — provider candidates
# ---------------------------------------------------------------------------


class TestHaiku55ProviderCandidates:
    def test_in_anthropic_candidates_yaml(self, models_yaml):
        candidates = models_yaml["providers"]["anthropic"]["candidates"]
        assert HAIKU55_ID in candidates, (
            f"{HAIKU55_ID} must appear in config/models.yaml anthropic candidates"
        )

    def test_dated_in_anthropic_candidates_yaml(self, models_yaml):
        candidates = models_yaml["providers"]["anthropic"]["candidates"]
        assert HAIKU55_DATED_ID in candidates, (
            f"{HAIKU55_DATED_ID} must appear in config/models.yaml anthropic candidates"
        )

    def test_in_aerolink_candidates_yaml(self, models_yaml):
        candidates = models_yaml["providers"]["aerolink"]["candidates"]
        assert HAIKU55_ID in candidates, (
            f"{HAIKU55_ID} must appear in config/models.yaml aerolink candidates"
        )

    def test_dated_in_aerolink_candidates_yaml(self, models_yaml):
        candidates = models_yaml["providers"]["aerolink"]["candidates"]
        assert HAIKU55_DATED_ID in candidates, (
            f"{HAIKU55_DATED_ID} must appear in config/models.yaml aerolink candidates"
        )

    def test_in_brain_config_source(self, brain_config_src):
        assert f'"{HAIKU55_ID}"' in brain_config_src, (
            f"{HAIKU55_ID} must appear in PROVIDER_CANDIDATES in brain_config.py"
        )

    def test_haiku55_before_haiku45_in_anthropic_yaml(self, models_yaml):
        candidates = models_yaml["providers"]["anthropic"]["candidates"]
        idx_55 = candidates.index(HAIKU55_ID)
        idx_45 = candidates.index("claude-haiku-4-5-20251001")
        assert idx_55 < idx_45, "Haiku 5.5 should appear before Haiku 4.5 in anthropic candidates"

    def test_haiku55_before_haiku45_in_aerolink_yaml(self, models_yaml):
        candidates = models_yaml["providers"]["aerolink"]["candidates"]
        idx_55 = candidates.index(HAIKU55_ID)
        idx_45 = candidates.index("claude-haiku-4-5-20251001")
        assert idx_55 < idx_45, "Haiku 5.5 should appear before Haiku 4.5 in aerolink candidates"


# ---------------------------------------------------------------------------
# Claude Haiku 5.5 — cost table
# ---------------------------------------------------------------------------


class TestHaiku55CostTracker:
    def test_input_cost(self, ct):
        cost = ct.cost_for_tokens(HAIKU55_ID, 1_000_000, 0)
        assert abs(cost - HAIKU55_INPUT_COST) < 0.001, (
            f"Haiku 5.5 input cost must be ${HAIKU55_INPUT_COST}/MTok"
        )

    def test_output_cost(self, ct):
        cost = ct.cost_for_tokens(HAIKU55_ID, 0, 1_000_000)
        assert abs(cost - HAIKU55_OUTPUT_COST) < 0.001, (
            f"Haiku 5.5 output cost must be ${HAIKU55_OUTPUT_COST}/MTok"
        )

    def test_dated_id_input_cost(self, ct):
        cost = ct.cost_for_tokens(HAIKU55_DATED_ID, 1_000_000, 0)
        assert abs(cost - HAIKU55_INPUT_COST) < 0.001

    def test_haiku55_cheaper_than_haiku45(self, ct):
        cost_55 = ct.cost_for_tokens(HAIKU55_ID, 1_000_000, 0)
        cost_45 = ct.cost_for_tokens("claude-haiku-4-5", 1_000_000, 0)
        assert cost_55 < cost_45, "Haiku 5.5 must be cheaper per input MTok than Haiku 4.5"


# ---------------------------------------------------------------------------
# GPT-6 Cyber — cost table
# ---------------------------------------------------------------------------


class TestGpt6CyberCostTracker:
    def test_direct_input_cost(self, ct):
        cost = ct.cost_for_tokens(GPT6_CYBER_ID, 1_000_000, 0)
        assert abs(cost - GPT6_CYBER_INPUT_COST) < 0.01, (
            f"gpt-6-cyber input cost must be ${GPT6_CYBER_INPUT_COST}/MTok"
        )

    def test_direct_output_cost(self, ct):
        cost = ct.cost_for_tokens(GPT6_CYBER_ID, 0, 1_000_000)
        assert abs(cost - GPT6_CYBER_OUTPUT_COST) < 0.01, (
            f"gpt-6-cyber output cost must be ${GPT6_CYBER_OUTPUT_COST}/MTok"
        )

    def test_openrouter_input_cost(self, ct):
        cost = ct.cost_for_tokens(GPT6_CYBER_OPENROUTER_ID, 1_000_000, 0)
        assert abs(cost - GPT6_CYBER_INPUT_COST) < 0.01

    def test_openrouter_output_cost(self, ct):
        cost = ct.cost_for_tokens(GPT6_CYBER_OPENROUTER_ID, 0, 1_000_000)
        assert abs(cost - GPT6_CYBER_OUTPUT_COST) < 0.01

    def test_cyber_pricier_than_astra(self, ct):
        cyber_cost = ct.cost_for_tokens(GPT6_CYBER_ID, 1_000_000, 0)
        astra_cost = ct.cost_for_tokens("gpt-6-astra", 1_000_000, 0)
        assert cyber_cost > astra_cost, "GPT-6 Cyber must cost more than GPT-6 Astra"

    def test_cyber_exactly_twice_astra(self, ct):
        cyber_cost = ct.cost_for_tokens(GPT6_CYBER_ID, 1_000_000, 0)
        astra_cost = ct.cost_for_tokens("gpt-6-astra", 1_000_000, 0)
        assert abs(cyber_cost / astra_cost - 2.0) < 0.001, (
            "GPT-6 Cyber is priced at exactly 2× GPT-6 Astra ($20 vs $10/MTok)"
        )


# ---------------------------------------------------------------------------
# Configuration reference doc — stale model ID removed
# ---------------------------------------------------------------------------


class TestConfigRefDocUpdated:
    def test_retired_model_id_absent(self, config_ref_src):
        assert RETIRED_DEFAULT not in config_ref_src, (
            f"docs/configuration-reference.md must not reference the retired "
            f"{RETIRED_DEFAULT!r} as a default"
        )

    def test_current_model_id_present_as_default(self, config_ref_src):
        assert CURRENT_DEFAULT in config_ref_src, (
            f"docs/configuration-reference.md must reference the current "
            f"default {CURRENT_DEFAULT!r}"
        )


# ---------------------------------------------------------------------------
# Regression — Haiku 4.5 still present (not removed, only superseded)
# ---------------------------------------------------------------------------


class TestHaiku45RegressionUnchanged:
    def test_haiku45_still_in_anthropic_yaml(self, models_yaml):
        candidates = models_yaml["providers"]["anthropic"]["candidates"]
        assert "claude-haiku-4-5-20251001" in candidates

    def test_haiku45_still_in_aerolink_yaml(self, models_yaml):
        candidates = models_yaml["providers"]["aerolink"]["candidates"]
        assert "claude-haiku-4-5-20251001" in candidates

    def test_haiku45_cost_unchanged(self, ct):
        cost = ct.cost_for_tokens("claude-haiku-4-5", 1_000_000, 0)
        assert abs(cost - 1.0) < 0.01, "Haiku 4.5 input cost must remain $1/MTok"
