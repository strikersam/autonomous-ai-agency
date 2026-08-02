"""tests/test_daily_2026_08_02.py — Daily automation tests (2026-08-02).

Covers the ecosystem updates applied in this session:
  1. config/llm/models.yaml — Claude 5 family (Sonnet 5, Opus 4.8, Fable 5),
     Llama 4 Scout on Groq + NVIDIA NIM, Gemini 2.5 Pro;
     claude-haiku-4-5-20251001 alias on the existing haiku entry.
  2. packages/ai/registry.py — Llama 4 Scout (Groq + NVIDIA NIM), Gemini 2.5 Pro.
"""
from __future__ import annotations

import pytest


# ── 1. config/llm/models.yaml additions ──────────────────────────────────────


class TestModelsYamlNewEntries:
    """New models declared in config/llm/models.yaml must load cleanly."""

    @pytest.fixture(autouse=True)
    def _cfg(self, monkeypatch):
        monkeypatch.delenv("LLM_CONFIG_DIR", raising=False)
        from packages.llm import config as llm_config
        llm_config.reset()
        self._cfg_obj = llm_config.load_config()
        yield
        llm_config.reset()

    # ── Claude 5 / Opus 4.8 / Fable 5 ────────────────────────────────────

    def test_claude_sonnet_5_in_models(self):
        assert "claude-sonnet-5" in self._cfg_obj.models

    def test_claude_sonnet_5_context_window(self):
        m = self._cfg_obj.models["claude-sonnet-5"]
        assert m.context_window == 200000

    def test_claude_sonnet_5_supports_tools(self):
        m = self._cfg_obj.models["claude-sonnet-5"]
        assert m.supports_tools is True

    def test_claude_sonnet_5_supports_reasoning(self):
        m = self._cfg_obj.models["claude-sonnet-5"]
        assert m.supports_reasoning is True

    def test_claude_sonnet_5_is_paid(self):
        m = self._cfg_obj.models["claude-sonnet-5"]
        assert m.input_cost_per_1m > 0

    def test_claude_sonnet_5_priority_before_sonnet_46(self):
        s5 = self._cfg_obj.models["claude-sonnet-5"]
        s46 = self._cfg_obj.models["claude-sonnet-4-6"]
        assert s5.priority < s46.priority, "Sonnet 5 should have higher priority than Sonnet 4.6"

    def test_claude_opus_48_in_models(self):
        assert "claude-opus-4-8" in self._cfg_obj.models

    def test_claude_opus_48_supports_reasoning(self):
        m = self._cfg_obj.models["claude-opus-4-8"]
        assert m.supports_reasoning is True

    def test_claude_opus_48_is_expensive(self):
        m = self._cfg_obj.models["claude-opus-4-8"]
        assert m.input_cost_per_1m >= 15.0

    def test_claude_fable_5_in_models(self):
        assert "claude-fable-5" in self._cfg_obj.models

    def test_claude_fable_5_supports_tools(self):
        m = self._cfg_obj.models["claude-fable-5"]
        assert m.supports_tools is True

    def test_claude_fable_5_is_paid(self):
        m = self._cfg_obj.models["claude-fable-5"]
        assert m.input_cost_per_1m > 0

    # ── claude-haiku-4-5-20251001 alias ───────────────────────────────────

    def test_haiku_45_versioned_alias_resolves(self):
        """claude-haiku-4-5-20251001 must be an alias on the haiku-4-5 entry."""
        m = self._cfg_obj.models["claude-haiku-4-5"]
        assert "claude-haiku-4-5-20251001" in (m.aliases or [])

    # ── Llama 4 Scout on Groq ─────────────────────────────────────────────

    def test_llama4_scout_groq_in_models(self):
        assert "llama-4-scout-17b-16e-instruct" in self._cfg_obj.models

    def test_llama4_scout_groq_provider(self):
        m = self._cfg_obj.models["llama-4-scout-17b-16e-instruct"]
        assert m.provider == "groq"

    def test_llama4_scout_groq_is_free(self):
        m = self._cfg_obj.models["llama-4-scout-17b-16e-instruct"]
        assert m.input_cost_per_1m == 0.0

    def test_llama4_scout_groq_supports_tools(self):
        m = self._cfg_obj.models["llama-4-scout-17b-16e-instruct"]
        assert m.supports_tools is True

    def test_llama4_scout_groq_priority_before_maverick(self):
        scout = self._cfg_obj.models["llama-4-scout-17b-16e-instruct"]
        maverick = self._cfg_obj.models["llama-4-maverick-17b-128e-instruct"]
        assert scout.priority < maverick.priority, "Scout is faster; should have higher priority"

    # ── Llama 4 Scout on NVIDIA NIM ──────────────────────────────────────

    def test_llama4_scout_nvidia_in_models(self):
        assert "meta/llama-4-scout-17b-16e-instruct" in self._cfg_obj.models

    def test_llama4_scout_nvidia_provider(self):
        m = self._cfg_obj.models["meta/llama-4-scout-17b-16e-instruct"]
        assert m.provider == "nvidia"

    def test_llama4_scout_nvidia_is_free(self):
        m = self._cfg_obj.models["meta/llama-4-scout-17b-16e-instruct"]
        assert m.input_cost_per_1m == 0.0

    # ── Gemini 2.5 Pro ────────────────────────────────────────────────────

    def test_gemini_25_pro_in_models(self):
        assert "gemini-2.5-pro" in self._cfg_obj.models

    def test_gemini_25_pro_context_window(self):
        m = self._cfg_obj.models["gemini-2.5-pro"]
        assert m.context_window == 2097152

    def test_gemini_25_pro_supports_reasoning(self):
        m = self._cfg_obj.models["gemini-2.5-pro"]
        assert m.supports_reasoning is True

    def test_gemini_25_pro_is_free(self):
        m = self._cfg_obj.models["gemini-2.5-pro"]
        assert m.input_cost_per_1m == 0.0

    def test_gemini_25_pro_priority_below_flash(self):
        pro = self._cfg_obj.models["gemini-2.5-pro"]
        flash = self._cfg_obj.models["gemini-2.5-flash"]
        assert pro.priority > flash.priority, "Pro is slower; Flash should have higher priority"

    # ── Legacy entries must still load ────────────────────────────────────

    def test_claude_sonnet_46_still_present(self):
        assert "claude-sonnet-4-6" in self._cfg_obj.models

    def test_llama4_maverick_groq_still_present(self):
        assert "llama-4-maverick-17b-128e-instruct" in self._cfg_obj.models

    def test_gemini_25_flash_still_present(self):
        assert "gemini-2.5-flash" in self._cfg_obj.models


# ── 2. packages/ai/registry additions ────────────────────────────────────────


class TestRegistryNewEntries:
    """New models in packages/ai/registry.py must have correct capability declarations."""

    def _reg(self):
        import packages.ai.registry as reg
        return reg

    def test_llama4_scout_groq_registered(self):
        reg = self._reg()
        model = reg.get("llama-4-scout-17b-16e-instruct")
        assert model is not None
        assert model.provider_id == "groq"

    def test_llama4_scout_groq_is_free(self):
        reg = self._reg()
        model = reg.get("llama-4-scout-17b-16e-instruct")
        assert model.input_cost_per_1m == 0.0
        assert model.output_cost_per_1m == 0.0

    def test_llama4_scout_groq_context_window(self):
        reg = self._reg()
        model = reg.get("llama-4-scout-17b-16e-instruct")
        assert model.context_window == 131072

    def test_llama4_scout_groq_supports_tools(self):
        reg = self._reg()
        model = reg.get("llama-4-scout-17b-16e-instruct")
        assert model.supports_tools is True

    def test_llama4_scout_groq_priority_before_maverick(self):
        reg = self._reg()
        scout = reg.get("llama-4-scout-17b-16e-instruct")
        maverick = reg.get("llama-4-maverick-17b-128e-instruct")
        assert scout is not None and maverick is not None
        assert scout.priority < maverick.priority

    def test_llama4_scout_nvidia_registered(self):
        reg = self._reg()
        model = reg.get("meta/llama-4-scout-17b-16e-instruct")
        assert model is not None
        assert model.provider_id == "nvidia"

    def test_llama4_scout_nvidia_is_free(self):
        reg = self._reg()
        model = reg.get("meta/llama-4-scout-17b-16e-instruct")
        assert model.input_cost_per_1m == 0.0

    def test_gemini25_pro_registered(self):
        reg = self._reg()
        model = reg.get("gemini-2.5-pro")
        assert model is not None
        assert model.provider_id == "google"

    def test_gemini25_pro_has_2m_context(self):
        reg = self._reg()
        model = reg.get("gemini-2.5-pro")
        assert model.context_window == 2097152

    def test_gemini25_pro_supports_vision(self):
        reg = self._reg()
        model = reg.get("gemini-2.5-pro")
        assert model.supports_vision is True

    def test_gemini25_pro_supports_tools(self):
        reg = self._reg()
        model = reg.get("gemini-2.5-pro")
        assert model.supports_tools is True

    def test_gemini25_pro_is_free(self):
        reg = self._reg()
        model = reg.get("gemini-2.5-pro")
        assert model.input_cost_per_1m == 0.0

    def test_gemini25_pro_priority_below_flash(self):
        reg = self._reg()
        pro = reg.get("gemini-2.5-pro")
        flash = reg.get("gemini-2.5-flash")
        assert pro is not None and flash is not None
        assert pro.priority > flash.priority

    def test_best_model_for_tools_includes_new_models(self):
        reg = self._reg()
        models_with_tools = [m for m in reg.all_models() if m.supports_tools]
        model_ids = {m.model_id for m in models_with_tools}
        assert "llama-4-scout-17b-16e-instruct" in model_ids
        assert "gemini-2.5-pro" in model_ids

    def test_legacy_registry_entries_unaffected(self):
        reg = self._reg()
        assert reg.get("llama-4-maverick-17b-128e-instruct") is not None
        assert reg.get("gemini-2.5-flash") is not None
        assert reg.get("meta/llama-4-maverick-17b-128e-instruct") is not None
