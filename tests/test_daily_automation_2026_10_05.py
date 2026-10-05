"""tests/test_daily_automation_2026_10_05.py — Daily automation 2026-10-05.

``devstral-latest`` (Mistral's agentic coding model) is declared in
``config/llm/models.yaml`` and appended to ``PROVIDER_CANDIDATES['mistral']``.
The id is from docs.mistral.ai and unprobed on this account, so it is a
candidate only: the Mistral executor/verifier presets stay on
``mistral-small-latest``. Pixtral Large and Ministral 8B/3B were already
covered by #1644 (``tests/test_daily_automation_2026_10_03.py``) and are not
re-tested here.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ct():
    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_10_05",
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


@pytest.fixture(scope="module")
def brain_cfg():
    spec = importlib.util.spec_from_file_location(
        "brain_config_2026_10_05",
        REPO_ROOT / "packages" / "ai" / "brain_config.py",
    )
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# Devstral cost entry
# ---------------------------------------------------------------------------

class TestDevstralCostEntry:
    def test_devstral_input_cost(self, ct):
        cost = ct.cost_for_tokens("devstral-latest", 1_000_000, 0)
        assert cost == pytest.approx(0.10), "devstral-latest input must be $0.10/MTok"

    def test_devstral_output_cost(self, ct):
        cost = ct.cost_for_tokens("devstral-latest", 0, 1_000_000)
        assert cost == pytest.approx(0.30), "devstral-latest output must be $0.30/MTok"

    def test_devstral_cheaper_than_large(self, ct):
        devstral_in = ct.cost_for_tokens("devstral-latest", 1_000_000, 0)
        large_in = ct.cost_for_tokens("mistral-large-latest", 1_000_000, 0)
        assert devstral_in < large_in, "devstral should be cheaper than mistral-large-latest"

    def test_devstral_same_price_as_small(self, ct):
        devstral = ct.cost_for_tokens("devstral-latest", 1_000_000, 1_000_000)
        small = ct.cost_for_tokens("mistral-small-latest", 1_000_000, 1_000_000)
        assert devstral == pytest.approx(small), "devstral-latest estimated at same tier as mistral-small"


# ---------------------------------------------------------------------------
# models.yaml — devstral declared
# ---------------------------------------------------------------------------

class TestDevstralModelsYaml:
    def test_devstral_declared(self, llm_models):
        assert "devstral-latest" in llm_models, "devstral-latest must be in config/llm/models.yaml"

    def test_devstral_provider(self, llm_models):
        assert llm_models["devstral-latest"]["provider"] == "mistral"

    def test_devstral_supports_tools(self, llm_models):
        m = llm_models["devstral-latest"]
        assert m.get("supports_tools") is True, "devstral-latest must declare supports_tools: true"

    def test_devstral_supports_function_calling(self, llm_models):
        m = llm_models["devstral-latest"]
        assert m.get("supports_function_calling") is True

    def test_devstral_context_window(self, llm_models):
        m = llm_models["devstral-latest"]
        assert m["context_window"] >= 131072, "devstral-latest must have at least 128K context"

    def test_devstral_zero_cost_for_free_tier(self, llm_models):
        m = llm_models["devstral-latest"]
        assert m.get("input_cost_per_1m", -1) == 0.0, "free-tier deployment: cost must be 0.0"
        assert m.get("output_cost_per_1m", -1) == 0.0

    def test_devstral_priority_between_small_and_codestral(self, llm_models):
        devstral_p = llm_models["devstral-latest"]["priority"]
        small_p = llm_models["mistral-small-latest"]["priority"]
        codestral_p = llm_models["codestral-latest"]["priority"]
        # Lower priority number = higher routing priority
        assert small_p < devstral_p < codestral_p, (
            f"devstral priority ({devstral_p}) must be between "
            f"mistral-small ({small_p}) and codestral ({codestral_p})"
        )


# ---------------------------------------------------------------------------
# brain_config — devstral in candidates and presets
# ---------------------------------------------------------------------------

class TestDevstralBrainConfig:
    def test_devstral_in_mistral_candidates(self, brain_cfg):
        candidates = brain_cfg.PROVIDER_CANDIDATES.get("mistral", [])
        assert "devstral-latest" in candidates, (
            "devstral-latest must be in PROVIDER_CANDIDATES['mistral']"
        )

    def test_unprobed_devstral_is_not_a_preset_default(self, brain_cfg):
        """devstral-latest is unprobed: a wrong id as the default would fail every
        executor call, so the presets stay on the known-good mistral-small-latest."""
        preset = brain_cfg.PROVIDER_PRESETS.get("mistral", {})
        assert preset.get("executor") == "mistral-small-latest"
        assert preset.get("verifier") == "mistral-small-latest"

    def test_yaml_presets_mirror_brain_config(self):
        cfg = yaml.safe_load((REPO_ROOT / "config" / "models.yaml").read_text())
        presets = cfg["providers"]["mistral"]["role_presets"]
        assert presets["executor"] == presets["verifier"] == "mistral-small-latest"
        assert "devstral-latest" in cfg["providers"]["mistral"]["candidates"]

    def test_mistral_planner_still_large(self, brain_cfg):
        preset = brain_cfg.PROVIDER_PRESETS.get("mistral", {})
        assert preset.get("planner") == "mistral-large-latest", (
            "Mistral planner should remain mistral-large-latest"
        )

    def test_codestral_still_in_candidates(self, brain_cfg):
        """codestral-latest must stay in candidates — routing test in #1665 depends on it."""
        candidates = brain_cfg.PROVIDER_CANDIDATES.get("mistral", [])
        assert "codestral-latest" in candidates


# ---------------------------------------------------------------------------
# No duplicate declarations — a repeated dict key or YAML key silently wins
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
    """#1689 re-added three Mistral entries #1644 had already added; Python
    keeps the last one silently, so a later edit to the first would be lost."""
    assert _duplicate_dict_keys(REPO_ROOT / "packages" / "ai" / "cost_tracker.py") == []


def test_model_catalogue_has_no_duplicate_ids():
    import collections
    import re

    lines = (REPO_ROOT / "config" / "llm" / "models.yaml").read_text().splitlines()
    ids = [ln.strip()[:-1] for ln in lines if re.match(r"^  [A-Za-z0-9][^ :]*:\s*$", ln)]
    assert [k for k, n in collections.Counter(ids).items() if n > 1] == []
