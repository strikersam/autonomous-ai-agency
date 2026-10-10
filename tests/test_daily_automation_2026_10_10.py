"""tests/test_daily_automation_2026_10_10.py — Daily automation 2026-10-10.

One model addition:

1. **GPT-6.1 Sol** (OpenAI, released 2026-09-29) — added to
   ``packages/ai/cost_tracker.py`` and ``config/llm/models.yaml``
   (priority 99, explicit-only; no direct OpenAI gateway wired).
   Pricing: $2.00/$10.00 per MTok; cached input $0.10/MTok (5 % fraction).
   Context: 1,050,000 tokens; 128K max output.
   OpenRouter id: openai/gpt-6.1-sol.
   Sources: openrouter.ai/openai/gpt-6.1-sol,
            aicybr.com/blog/openai-gpt-6-1-sol-pricing-benchmarks-api,
            2026-10-10.

"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ct():
    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_10_10",
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


# ---------------------------------------------------------------------------
# GPT-6.1 Sol — cost entries
# ---------------------------------------------------------------------------

class TestGpt61SolCostEntry:
    def test_gpt_61_sol_input_cost(self, ct):
        cost = ct.cost_for_tokens("gpt-6.1-sol", 1_000_000, 0)
        assert cost == pytest.approx(2.0), "gpt-6.1-sol input must be $2.00/MTok"

    def test_gpt_61_sol_output_cost(self, ct):
        cost = ct.cost_for_tokens("gpt-6.1-sol", 0, 1_000_000)
        assert cost == pytest.approx(10.0), "gpt-6.1-sol output must be $10.00/MTok"

    def test_gpt_61_sol_openrouter_alias_input_cost(self, ct):
        """openai/gpt-6.1-sol is the OpenRouter model id — same pricing."""
        cost = ct.cost_for_tokens("openai/gpt-6.1-sol", 1_000_000, 0)
        assert cost == pytest.approx(2.0), "openai/gpt-6.1-sol input must be $2.00/MTok"

    def test_gpt_61_sol_openrouter_alias_output_cost(self, ct):
        cost = ct.cost_for_tokens("openai/gpt-6.1-sol", 0, 1_000_000)
        assert cost == pytest.approx(10.0), "openai/gpt-6.1-sol output must be $10.00/MTok"

    def test_gpt_61_sol_cached_input_is_discounted(self, ct):
        """Cache reads at $0.10/MTok = 5 % of the $2.00/MTok input rate."""
        full = ct.cost_for_tokens("gpt-6.1-sol", 1_000_000, 0, cached_tokens=0)
        cached = ct.cost_for_tokens("gpt-6.1-sol", 1_000_000, 0, cached_tokens=1_000_000)
        assert cached == pytest.approx(full * 0.05, rel=1e-3), (
            "gpt-6.1-sol cached input must be 5 % of the standard input rate"
        )

    def test_gpt_61_sol_openrouter_cached_matches_direct(self, ct):
        """Both ids must produce identical cache-discounted cost."""
        direct = ct.cost_for_tokens("gpt-6.1-sol", 500_000, 0, cached_tokens=500_000)
        via_or = ct.cost_for_tokens("openai/gpt-6.1-sol", 500_000, 0, cached_tokens=500_000)
        assert direct == pytest.approx(via_or)

    def test_gpt_61_sol_more_expensive_than_gpt6_luna(self, ct):
        """GPT-6 Luna is the cheap variant ($0.10/$0.50); Sol is higher quality."""
        sol = ct.cost_for_tokens("gpt-6.1-sol", 1_000_000, 1_000_000)
        luna = ct.cost_for_tokens("gpt-6-luna", 1_000_000, 1_000_000)
        assert sol > luna, "gpt-6.1-sol must cost more than gpt-6-luna"

    def test_gpt_61_sol_cheaper_than_gpt6_astra(self, ct):
        """GPT-6 Astra is the frontier model ($10/$50); Sol is the mid-range."""
        sol = ct.cost_for_tokens("gpt-6.1-sol", 1_000_000, 1_000_000)
        astra = ct.cost_for_tokens("gpt-6-astra", 1_000_000, 1_000_000)
        assert sol < astra, "gpt-6.1-sol must be cheaper than gpt-6-astra"

    def test_gpt_61_sol_same_input_price_as_grok_47(self, ct):
        """Both models cost $2.00/MTok input — same price tier."""
        sol_in = ct.cost_for_tokens("gpt-6.1-sol", 1_000_000, 0)
        grok_in = ct.cost_for_tokens("grok-4.7", 1_000_000, 0)
        assert sol_in == pytest.approx(grok_in), (
            "gpt-6.1-sol and grok-4.7 both cost $2.00/MTok input"
        )


# ---------------------------------------------------------------------------
# GPT-6.1 Sol — config/llm/models.yaml declaration
# ---------------------------------------------------------------------------

class TestGpt61SolModelsYaml:
    def test_gpt_61_sol_declared(self, llm_models):
        assert "gpt-6.1-sol" in llm_models, (
            "gpt-6.1-sol must be in config/llm/models.yaml"
        )

    def test_gpt_61_sol_provider(self, llm_models):
        assert llm_models["gpt-6.1-sol"]["provider"] == "openrouter"

    def test_gpt_61_sol_supports_tools(self, llm_models):
        m = llm_models["gpt-6.1-sol"]
        assert m.get("supports_tools") is True

    def test_gpt_61_sol_context_window(self, llm_models):
        m = llm_models["gpt-6.1-sol"]
        assert m["context_window"] >= 1_000_000, (
            "gpt-6.1-sol has a 1M-token context window"
        )

    def test_gpt_61_sol_max_output(self, llm_models):
        m = llm_models["gpt-6.1-sol"]
        assert m.get("max_output_tokens", 0) >= 128_000, (
            "gpt-6.1-sol supports at least 128K max output tokens"
        )

    def test_gpt_61_sol_priority_explicit_only(self, llm_models):
        """priority 99 keeps it out of normal routing until the OpenAI gateway is wired."""
        assert llm_models["gpt-6.1-sol"]["priority"] == 99

    def test_gpt_61_sol_input_cost(self, llm_models):
        assert llm_models["gpt-6.1-sol"]["input_cost_per_1m"] == pytest.approx(2.0)

    def test_gpt_61_sol_output_cost(self, llm_models):
        assert llm_models["gpt-6.1-sol"]["output_cost_per_1m"] == pytest.approx(10.0)

    def test_gpt_61_sol_supports_images(self, llm_models):
        assert llm_models["gpt-6.1-sol"].get("supports_images") is True


# ---------------------------------------------------------------------------
# No duplicate model ids introduced
# ---------------------------------------------------------------------------

def _duplicate_dict_keys(path: pathlib.Path) -> list[str]:
    import ast
    import collections

    dupes: list[str] = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Dict):
            keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
            dupes += [k for k, n in collections.Counter(keys).items() if n > 1]
    return dupes


def test_cost_table_has_no_duplicate_model_ids():
    assert _duplicate_dict_keys(REPO_ROOT / "packages" / "ai" / "cost_tracker.py") == []


def test_model_catalogue_has_no_duplicate_ids():
    import collections
    import re

    lines = (REPO_ROOT / "config" / "llm" / "models.yaml").read_text().splitlines()
    ids = [ln.strip()[:-1] for ln in lines if re.match(r"^  [A-Za-z0-9][^ :]*:\s*$", ln)]
    assert [k for k, n in collections.Counter(ids).items() if n > 1] == []
