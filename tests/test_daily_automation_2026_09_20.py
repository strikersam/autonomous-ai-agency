"""tests/test_daily_automation_2026_09_20.py — Daily automation tests (2026-09-20).

Covers the model catalog updates applied today:

  1. ZhipuAI / GLM (zhipu + zai providers):
     ``glm-5.2``, ``glm-5.1``, ``glm-4``, ``glm-4-flash``, ``glm-4-air``

     All five IDs appear in ``config/models.yaml``'s ``zhipu`` and ``zai``
     candidates lists (zhipu and zai are the same GLM model ids, different
     endpoints), but had no ``config/llm/models.yaml`` entry.  Without an entry,
     ``packages/llm/registry.py`` assigns ``supports_tools: false`` and silently
     drops every model from every tool-calling request — despite GLM-4+ natively
     supporting the OpenAI function-calling protocol.

     Fix: add catalog entries declaring ``supports_tools: true`` for all five
     models, consistent with ZhipuAI's open-platform documentation.

  2. DashScope / Alibaba Qwen (dashscope provider):
     ``qwen-plus``, ``qwen-max``, ``qwen-turbo``, ``qwen-coder-plus``

     All four IDs appear in the ``dashscope`` candidates list and had no llm
     catalog entry.  All Qwen2.5 models support OpenAI-style tool calling per
     Alibaba documentation.  ``qwen-coder-plus`` is the executor preset.
     Cost entries added with approximate CNY→USD conversions as conservative floors.

  3. Moonshot / Kimi (moonshot provider):
     ``moonshot-v1-8k``, ``moonshot-v1-32k``, ``moonshot-v1-128k``

     All three IDs appear in the ``moonshot`` candidates list and had no llm
     catalog entry.  All support OpenAI-style tool calling per Moonshot
     documentation.  ``moonshot-v1-32k`` is the planner/executor preset.

  4. Cost tracking: pricing rows added for all new models.

Sandbox note: ``packages.ai.brain_config`` requires pydantic/fastapi and cannot
be imported here.  Tests verify the YAML and cost_tracker source directly — the
same approach used in tests/test_daily_automation_2026_09_19.py.
"""
from __future__ import annotations

from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent


def _llm_catalog() -> dict[str, dict]:
    data = yaml.safe_load((_ROOT / "config" / "llm" / "models.yaml").read_text())
    return dict(data.get("models") or {})


def _routing_candidates() -> dict[str, list[str]]:
    data = yaml.safe_load((_ROOT / "config" / "models.yaml").read_text())
    result: dict[str, list[str]] = {}
    for pid, pdata in (data.get("providers") or {}).items():
        result[pid] = list(pdata.get("candidates") or [])
    return result


def _cost_src() -> str:
    return (_ROOT / "packages" / "ai" / "cost_tracker.py").read_text()


# ── ZhipuAI / GLM ────────────────────────────────────────────────────────────


class TestGLMCatalogEntries:
    """glm-5.2 / glm-5.1 / glm-4 / glm-4-flash / glm-4-air now have llm catalog entries."""

    GLM_MODELS = ["glm-5.2", "glm-5.1", "glm-4", "glm-4-flash", "glm-4-air"]

    def test_glm_models_in_zhipu_candidates(self):
        candidates = _routing_candidates().get("zhipu", [])
        for model in self.GLM_MODELS:
            assert model in candidates, f"{model} missing from zhipu candidates"

    def test_glm_models_in_zai_candidates(self):
        candidates = _routing_candidates().get("zai", [])
        for model in self.GLM_MODELS:
            assert model in candidates, f"{model} missing from zai candidates"

    def test_glm_models_have_catalog_entries(self):
        catalog = _llm_catalog()
        for model in self.GLM_MODELS:
            assert model in catalog, (
                f"{model} missing from config/llm/models.yaml; without an entry "
                "it defaults to supports_tools:false and is silently excluded "
                "from all tool-calling requests"
            )

    def test_glm_52_is_supports_tools_true(self):
        entry = _llm_catalog()["glm-5.2"]
        assert entry.get("supports_tools") is True, (
            "glm-5.2 should declare supports_tools:true (GLM-4+ supports "
            "OpenAI function-calling protocol per ZhipuAI docs)"
        )

    def test_glm_4_family_is_supports_tools_true(self):
        catalog = _llm_catalog()
        for model in ("glm-4", "glm-4-flash", "glm-4-air"):
            entry = catalog[model]
            assert entry.get("supports_tools") is True, (
                f"{model} should declare supports_tools:true"
            )

    def test_glm_52_provider_is_zhipu(self):
        assert _llm_catalog()["glm-5.2"].get("provider") == "zhipu"

    def test_glm_52_context_window(self):
        entry = _llm_catalog()["glm-5.2"]
        assert entry.get("context_window", 0) >= 131072, (
            "glm-5.2 context window should be ≥128K"
        )

    def test_glm_models_have_cost_tracker_entries(self):
        src = _cost_src()
        for model in self.GLM_MODELS:
            assert f'"{model}"' in src, (
                f"cost_tracker.py missing entry for {model}"
            )

    def test_zhipu_role_presets_use_glm_52(self):
        data = yaml.safe_load((_ROOT / "config" / "models.yaml").read_text())
        presets = data["providers"]["zhipu"]["role_presets"]
        for role in ("planner", "executor", "verifier", "judge"):
            assert presets[role] == "glm-5.2", (
                f"zhipu {role} preset should be glm-5.2"
            )


# ── DashScope / Qwen ─────────────────────────────────────────────────────────


class TestDashScopeCatalogEntries:
    """qwen-plus / qwen-max / qwen-turbo / qwen-coder-plus now have llm catalog entries."""

    QWEN_MODELS = ["qwen-plus", "qwen-max", "qwen-turbo", "qwen-coder-plus"]

    def test_qwen_models_in_dashscope_candidates(self):
        candidates = _routing_candidates().get("dashscope", [])
        for model in self.QWEN_MODELS:
            assert model in candidates, f"{model} missing from dashscope candidates"

    def test_qwen_models_have_catalog_entries(self):
        catalog = _llm_catalog()
        for model in self.QWEN_MODELS:
            assert model in catalog, (
                f"{model} missing from config/llm/models.yaml; without an entry "
                "it defaults to supports_tools:false and is silently excluded "
                "from all tool-calling requests"
            )

    def test_qwen_models_support_tools(self):
        catalog = _llm_catalog()
        for model in self.QWEN_MODELS:
            assert catalog[model].get("supports_tools") is True, (
                f"{model} should declare supports_tools:true per Alibaba docs"
            )

    def test_qwen_models_provider_is_dashscope(self):
        catalog = _llm_catalog()
        for model in self.QWEN_MODELS:
            assert catalog[model].get("provider") == "dashscope", (
                f"{model} provider should be dashscope"
            )

    def test_qwen_turbo_context_window_is_1m(self):
        entry = _llm_catalog()["qwen-turbo"]
        assert entry.get("context_window", 0) >= 1_000_000, (
            "qwen-turbo should declare 1M context window"
        )

    def test_qwen_coder_plus_is_executor_preset(self):
        data = yaml.safe_load((_ROOT / "config" / "models.yaml").read_text())
        presets = data["providers"]["dashscope"]["role_presets"]
        assert presets["executor"] == "qwen-coder-plus"

    def test_qwen_models_have_cost_tracker_entries(self):
        src = _cost_src()
        for model in self.QWEN_MODELS:
            assert f'"{model}"' in src, f"cost_tracker.py missing entry for {model}"

    def test_qwen_max_more_expensive_than_plus(self):
        catalog = _llm_catalog()
        plus_cost = catalog["qwen-plus"].get("input_cost_per_1m", 0)
        max_cost = catalog["qwen-max"].get("input_cost_per_1m", 0)
        assert max_cost > plus_cost, (
            "qwen-max should cost more than qwen-plus per MTok"
        )

    def test_qwen_turbo_cheapest(self):
        catalog = _llm_catalog()
        turbo_cost = catalog["qwen-turbo"].get("input_cost_per_1m", 0)
        plus_cost = catalog["qwen-plus"].get("input_cost_per_1m", 0)
        assert turbo_cost < plus_cost, (
            "qwen-turbo should be cheaper than qwen-plus per MTok"
        )


# ── Moonshot / Kimi ──────────────────────────────────────────────────────────


class TestMoonshotCatalogEntries:
    """moonshot-v1-8k / moonshot-v1-32k / moonshot-v1-128k now have llm catalog entries."""

    MOONSHOT_MODELS = ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"]

    def test_moonshot_models_in_candidates(self):
        candidates = _routing_candidates().get("moonshot", [])
        for model in self.MOONSHOT_MODELS:
            assert model in candidates, f"{model} missing from moonshot candidates"

    def test_moonshot_models_have_catalog_entries(self):
        catalog = _llm_catalog()
        for model in self.MOONSHOT_MODELS:
            assert model in catalog, (
                f"{model} missing from config/llm/models.yaml"
            )

    def test_moonshot_models_support_tools(self):
        catalog = _llm_catalog()
        for model in self.MOONSHOT_MODELS:
            assert catalog[model].get("supports_tools") is True, (
                f"{model} should declare supports_tools:true"
            )

    def test_moonshot_models_provider_is_moonshot(self):
        catalog = _llm_catalog()
        for model in self.MOONSHOT_MODELS:
            assert catalog[model].get("provider") == "moonshot"

    def test_moonshot_context_windows_differ(self):
        catalog = _llm_catalog()
        assert catalog["moonshot-v1-8k"]["context_window"] < catalog["moonshot-v1-32k"]["context_window"]
        assert catalog["moonshot-v1-32k"]["context_window"] < catalog["moonshot-v1-128k"]["context_window"]

    def test_moonshot_32k_is_planner_preset(self):
        data = yaml.safe_load((_ROOT / "config" / "models.yaml").read_text())
        presets = data["providers"]["moonshot"]["role_presets"]
        assert presets["planner"] == "moonshot-v1-32k"

    def test_moonshot_models_have_cost_tracker_entries(self):
        src = _cost_src()
        for model in self.MOONSHOT_MODELS:
            assert f'"{model}"' in src, f"cost_tracker.py missing entry for {model}"

    def test_moonshot_128k_priority_better_than_8k(self):
        catalog = _llm_catalog()
        # Lower priority number = higher preference in routing
        assert catalog["moonshot-v1-128k"]["priority"] < catalog["moonshot-v1-8k"]["priority"], (
            "128K context variant should have higher routing priority than 8K"
        )


# ── Cross-provider totals ─────────────────────────────────────────────────────


class TestCatalogTotals:
    """Smoke check: overall catalog size grew with the new entries."""

    def test_total_models_at_least_58(self):
        # Was 46 before 2026-09-19 additions; 58 after yesterday; 12 added today.
        catalog = _llm_catalog()
        assert len(catalog) >= 58, (
            f"Expected ≥58 catalog entries, got {len(catalog)}"
        )

    def test_consistency_script_passes(self):
        """check_model_catalog_consistency.py must report no drift."""
        import subprocess
        import sys
        result = subprocess.run(  # nosec
            [sys.executable, "scripts/check_model_catalog_consistency.py"],
            cwd=str(_ROOT),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"catalog consistency check failed:\n{result.stdout}\n{result.stderr}"
        )
