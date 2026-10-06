"""tests/test_daily_automation_2026_10_06.py — Daily automation 2026-10-06.

Two model additions:

1. **Grok 4.7** (xAI, released 2026-09-21) — added to ``packages/ai/cost_tracker.py``
   and ``config/llm/models.yaml`` (priority 99, explicit-only; no xAI gateway
   provider wired yet). Pricing: $2.00/$6.00 per MTok, 500K context.
   Sources: docs.x.ai/developers/grok-4-7, openrouter.ai/x-ai/grok-4.7.

2. **Nemotron 3.5 Lightning 30B-A3B** (NVIDIA NIM, free tier) — MoE + Mamba-2 +
   Attention hybrid; 30B total / 3B active params; 1M-token context. Added to
   ``packages/ai/cost_tracker.py`` (free, $0/$0) and ``config/llm/models.yaml``
   (priority 99, explicit-only; returned 404 on 2026-08-28 account probe).
   Source: build.nvidia.com/nvidia/nemotron-3.5-lightning-30b-a3b.
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
        "cost_tracker_2026_10_06",
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
# Grok 4.7 — cost entries
# ---------------------------------------------------------------------------

class TestGrok47CostEntry:
    def test_grok_47_input_cost(self, ct):
        cost = ct.cost_for_tokens("grok-4.7", 1_000_000, 0)
        assert cost == pytest.approx(2.0), "grok-4.7 input must be $2.00/MTok"

    def test_grok_47_output_cost(self, ct):
        cost = ct.cost_for_tokens("grok-4.7", 0, 1_000_000)
        assert cost == pytest.approx(6.0), "grok-4.7 output must be $6.00/MTok"

    def test_grok_47_openrouter_path_input_cost(self, ct):
        """x-ai/grok-4.7 is the OpenRouter model id — same pricing."""
        cost = ct.cost_for_tokens("x-ai/grok-4.7", 1_000_000, 0)
        assert cost == pytest.approx(2.0), "x-ai/grok-4.7 input must be $2.00/MTok"

    def test_grok_47_openrouter_path_output_cost(self, ct):
        cost = ct.cost_for_tokens("x-ai/grok-4.7", 0, 1_000_000)
        assert cost == pytest.approx(6.0), "x-ai/grok-4.7 output must be $6.00/MTok"

    def test_grok_47_more_expensive_than_grok_46_free(self, ct):
        """grok-4.7 is a paid model; the free tokenin proxy alias (myt/grok-4.6-free)
        must remain at $0 — they must not be confused."""
        paid = ct.cost_for_tokens("grok-4.7", 1_000_000, 1_000_000)
        free = ct.cost_for_tokens("myt/grok-4.6-free", 1_000_000, 1_000_000)
        assert paid > free, "paid grok-4.7 must cost more than the free myt alias"

    def test_grok_47_same_price_as_gpt_61_sol(self, ct):
        """Both released at the same price tier ($2/$6–$10 input), so grok-4.7
        should cost the same input rate as gpt-6.1-sol ($2/$10); they are in the
        same per-1M-input band."""
        grok_in = ct.cost_for_tokens("grok-4.7", 1_000_000, 0)
        sol_in = ct.cost_for_tokens("gpt-6.1-sol", 1_000_000, 0)
        assert grok_in == pytest.approx(sol_in), (
            "grok-4.7 and gpt-6.1-sol both cost $2.00/MTok input"
        )


# ---------------------------------------------------------------------------
# Grok 4.7 — models.yaml declaration
# ---------------------------------------------------------------------------

class TestGrok47ModelsYaml:
    def test_grok_47_declared(self, llm_models):
        assert "grok-4.7" in llm_models, "grok-4.7 must be in config/llm/models.yaml"

    def test_grok_47_provider(self, llm_models):
        assert llm_models["grok-4.7"]["provider"] == "openrouter"

    def test_grok_47_supports_tools(self, llm_models):
        m = llm_models["grok-4.7"]
        assert m.get("supports_tools") is True

    def test_grok_47_context_window(self, llm_models):
        m = llm_models["grok-4.7"]
        assert m["context_window"] >= 500_000, (
            "grok-4.7 has a 500K-token context window"
        )

    def test_grok_47_priority_explicit_only(self, llm_models):
        """priority 99 keeps it out of normal routing until xAI gateway is wired."""
        assert llm_models["grok-4.7"]["priority"] == 99

    def test_grok_47_input_cost(self, llm_models):
        assert llm_models["grok-4.7"]["input_cost_per_1m"] == pytest.approx(2.0)

    def test_grok_47_output_cost(self, llm_models):
        assert llm_models["grok-4.7"]["output_cost_per_1m"] == pytest.approx(6.0)


# ---------------------------------------------------------------------------
# Nemotron 3.5 Lightning — cost entry
# ---------------------------------------------------------------------------

class TestNemotron35LightningCostEntry:
    MODEL_ID = "nvidia/nemotron-3.5-lightning-30b-a3b"

    def test_nemotron_lightning_free_input(self, ct):
        cost = ct.cost_for_tokens(self.MODEL_ID, 1_000_000, 0)
        assert cost == pytest.approx(0.0), (
            "nemotron-3.5-lightning-30b-a3b is free on NVIDIA NIM"
        )

    def test_nemotron_lightning_free_output(self, ct):
        cost = ct.cost_for_tokens(self.MODEL_ID, 0, 1_000_000)
        assert cost == pytest.approx(0.0)

    def test_nemotron_lightning_cheaper_than_super(self, ct):
        """Both are free on NIM; the cost entry must not accidentally charge more
        than the default Nemotron 3 Super."""
        lightning = ct.cost_for_tokens(self.MODEL_ID, 1_000_000, 1_000_000)
        sup = ct.cost_for_tokens("nvidia/nemotron-3-super-120b-a12b", 1_000_000, 1_000_000)
        assert lightning <= sup, "Lightning NIM cost must not exceed Super NIM cost"


# ---------------------------------------------------------------------------
# Nemotron 3.5 Lightning — models.yaml declaration
# ---------------------------------------------------------------------------

class TestNemotron35LightningModelsYaml:
    MODEL_ID = "nvidia/nemotron-3.5-lightning-30b-a3b"

    def test_lightning_declared(self, llm_models):
        assert self.MODEL_ID in llm_models, (
            "nvidia/nemotron-3.5-lightning-30b-a3b must be in config/llm/models.yaml"
        )

    def test_lightning_provider(self, llm_models):
        assert llm_models[self.MODEL_ID]["provider"] == "nvidia"

    def test_lightning_context_window(self, llm_models):
        m = llm_models[self.MODEL_ID]
        assert m["context_window"] >= 1_000_000, (
            "Nemotron 3.5 Lightning has a 1M-token context window"
        )

    def test_lightning_priority_explicit_only(self, llm_models):
        """Returned 404 on 2026-08-28 probe; keep explicit-only until re-probed."""
        assert llm_models[self.MODEL_ID]["priority"] == 99

    def test_lightning_free_cost(self, llm_models):
        m = llm_models[self.MODEL_ID]
        assert m["input_cost_per_1m"] == pytest.approx(0.0)
        assert m["output_cost_per_1m"] == pytest.approx(0.0)

    def test_lightning_supports_tools(self, llm_models):
        assert llm_models[self.MODEL_ID].get("supports_tools") is True


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
