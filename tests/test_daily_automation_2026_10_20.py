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
    """Retired 2026-11-14: NVIDIA answered HTTP 410 Gone on catalogue-probe run
    43619238209, and the id is absent from the account's /v1/models (scheduled
    run 43598099666). It stayed priority-99 explicit-only until then; a live 410
    means it must not be routable at all."""

    def test_entry_removed(self, llm_models):
        models = llm_models.get("models", {})
        assert MODEL_ID not in models, (
            f"{MODEL_ID} answers 410 on NVIDIA NIM; do not re-add without a live probe"
        )

    def test_listed_as_retired(self):
        from tests.test_nvidia_default_model import RETIRED
        assert MODEL_ID in RETIRED

    def test_not_in_recommended_priority_list(self, llm_models):
        recommended = llm_models.get("recommended_priority", [])
        assert MODEL_ID not in recommended
