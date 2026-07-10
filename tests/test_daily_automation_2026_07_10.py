"""tests/test_daily_automation_2026_07_10.py — Daily automation tests (2026-07-10).

Covers the three ecosystem updates applied today:
  1. services/brain_failover.py — Llama 4 models on Groq + NVIDIA NIM;
     Gemini 2.5 Flash/Pro on Google; latest Claude models on Anthropic provider.
  2. packages/ai/brain_config.py — Google added as BrainProvider;
     Anthropic + Aerolink presets updated to Claude Sonnet 5 / Opus 4.8;
     Groq preset updated to Llama 4 Maverick.
  3. packages/ai/registry.py — Llama 4 Maverick on Groq + NIM;
     Gemini 2.5 Flash registered.
"""
from __future__ import annotations

import importlib

import pytest


# ── brain_failover ────────────────────────────────────────────────────────────

class TestBrainFailoverModelUpdates:
    """Verify the provider registry in brain_failover contains the 2026 model set."""

    def _registry(self):
        import services.brain_failover as bf
        return bf._PROVIDER_REGISTRY

    def _by_id(self, pid: str) -> dict:
        return next(p for p in self._registry() if p["id"] == pid)

    def test_nvidia_nim_has_llama4_maverick(self):
        nvidia = self._by_id("nvidia")
        assert "meta/llama-4-maverick-17b-128e-instruct" in nvidia["models"]

    def test_nvidia_nim_has_llama4_scout(self):
        nvidia = self._by_id("nvidia")
        assert "meta/llama-4-scout-17b-16e-instruct" in nvidia["models"]

    def test_groq_has_llama4_maverick(self):
        groq = self._by_id("groq")
        assert "llama-4-maverick-17b-128e-instruct" in groq["models"]

    def test_groq_has_llama4_scout(self):
        groq = self._by_id("groq")
        assert "llama-4-scout-17b-16e-instruct" in groq["models"]

    def test_groq_no_longer_has_deprecated_mixtral(self):
        groq = self._by_id("groq")
        assert "mixtral-8x7b-32768" not in groq["models"]

    def test_google_default_is_gemini_25_flash(self):
        google = self._by_id("google")
        assert google["default_model"] == "gemini-2.5-flash"

    def test_google_has_gemini_25_pro(self):
        google = self._by_id("google")
        assert "gemini-2.5-pro" in google["models"]

    def test_google_has_gemini_25_flash(self):
        google = self._by_id("google")
        assert "gemini-2.5-flash" in google["models"]

    def test_google_still_has_gemini_20_flash_for_compat(self):
        google = self._by_id("google")
        assert "gemini-2.0-flash" in google["models"]

    def test_anthropic_default_is_claude_sonnet5(self):
        anthropic = self._by_id("anthropic")
        assert anthropic["default_model"] == "claude-sonnet-5"

    def test_anthropic_has_claude_fable5(self):
        anthropic = self._by_id("anthropic")
        assert "claude-fable-5" in anthropic["models"]

    def test_anthropic_has_claude_opus_48(self):
        anthropic = self._by_id("anthropic")
        assert "claude-opus-4-8" in anthropic["models"]

    def test_anthropic_has_claude_haiku_45(self):
        anthropic = self._by_id("anthropic")
        assert "claude-haiku-4-5-20251001" in anthropic["models"]

    def test_anthropic_still_has_sonnet46_for_compat(self):
        anthropic = self._by_id("anthropic")
        assert "claude-sonnet-4-6" in anthropic["models"]

    def test_anthropic_does_not_have_stale_oct2024_model(self):
        anthropic = self._by_id("anthropic")
        assert "claude-3-5-sonnet-20241022" not in anthropic["models"]


class TestBrainFailoverModelAliases:
    """Verify Llama 4 and Claude Sonnet 5 cross-provider aliases are registered."""

    def _aliases(self):
        import services.brain_failover as bf
        return bf._MODEL_ALIASES

    def test_llama4_maverick_groq_alias(self):
        aliases = self._aliases()
        assert "meta/llama-4-maverick-17b-128e-instruct" in aliases
        assert aliases["meta/llama-4-maverick-17b-128e-instruct"]["groq"] == "llama-4-maverick-17b-128e-instruct"

    def test_llama4_scout_groq_alias(self):
        aliases = self._aliases()
        assert "meta/llama-4-scout-17b-16e-instruct" in aliases
        assert aliases["meta/llama-4-scout-17b-16e-instruct"]["groq"] == "llama-4-scout-17b-16e-instruct"

    def test_llama4_maverick_nvidia_alias_is_identity(self):
        aliases = self._aliases()
        assert aliases["meta/llama-4-maverick-17b-128e-instruct"]["nvidia"] == "meta/llama-4-maverick-17b-128e-instruct"

    def test_claude_sonnet5_aerolink_alias(self):
        aliases = self._aliases()
        assert "claude-sonnet-5" in aliases
        assert aliases["claude-sonnet-5"]["aerolink"] == "claude-sonnet-5"


# ── brain_config ──────────────────────────────────────────────────────────────

class TestBrainConfigUpdates:
    """Verify brain_config.py changes: Google provider, updated presets."""

    def _bc(self):
        import packages.ai.brain_config as bc
        return bc

    def test_google_is_valid_brain_provider(self):
        from packages.ai.brain_config import BrainConfig
        cfg = BrainConfig(primary_provider="google", primary_model="gemini-2.5-flash")
        assert cfg.primary_provider == "google"

    def test_anthropic_is_valid_brain_provider(self):
        from packages.ai.brain_config import BrainConfig
        cfg = BrainConfig(primary_provider="anthropic", primary_model="claude-sonnet-5")
        assert cfg.primary_provider == "anthropic"

    def test_google_preset_exists(self):
        bc = self._bc()
        assert "google" in bc.PROVIDER_PRESETS

    def test_google_preset_uses_gemini25_pro_for_planner(self):
        bc = self._bc()
        assert bc.PROVIDER_PRESETS["google"]["planner"] == "gemini-2.5-pro"

    def test_google_preset_uses_gemini25_flash_for_executor(self):
        bc = self._bc()
        assert bc.PROVIDER_PRESETS["google"]["executor"] == "gemini-2.5-flash"

    def test_anthropic_preset_uses_claude_opus_for_planner(self):
        bc = self._bc()
        assert bc.PROVIDER_PRESETS["anthropic"]["planner"] == "claude-opus-4-8"

    def test_anthropic_preset_uses_claude_sonnet5_for_executor(self):
        bc = self._bc()
        assert bc.PROVIDER_PRESETS["anthropic"]["executor"] == "claude-sonnet-5"

    def test_aerolink_preset_updated_to_latest_claude(self):
        bc = self._bc()
        assert bc.PROVIDER_PRESETS["aerolink"]["executor"] == "claude-sonnet-5"

    def test_groq_preset_updated_to_llama4_maverick(self):
        bc = self._bc()
        assert bc.PROVIDER_PRESETS["groq"]["planner"] == "llama-4-maverick-17b-128e-instruct"

    def test_google_key_env_registered(self):
        bc = self._bc()
        assert bc.PROVIDER_KEY_ENV.get("google") == "GOOGLE_API_KEY"

    def test_google_base_url_registered(self):
        bc = self._bc()
        assert "google" in bc.PROVIDER_DEFAULT_BASE_URL
        assert "googleapis" in bc.PROVIDER_DEFAULT_BASE_URL["google"]


# ── model registry ────────────────────────────────────────────────────────────

class TestModelRegistryUpdates:
    """Verify new models are in the packages/ai/registry."""

    def _reg(self):
        import packages.ai.registry as reg
        return reg

    def test_llama4_maverick_groq_registered(self):
        reg = self._reg()
        model = reg.get("llama-4-maverick-17b-128e-instruct")
        assert model is not None
        assert model.provider_id == "groq"

    def test_llama4_maverick_groq_is_free(self):
        reg = self._reg()
        model = reg.get("llama-4-maverick-17b-128e-instruct")
        assert model.input_cost_per_1m == 0.0
        assert model.output_cost_per_1m == 0.0

    def test_llama4_maverick_groq_context_window(self):
        reg = self._reg()
        model = reg.get("llama-4-maverick-17b-128e-instruct")
        assert model.context_window == 131072

    def test_llama4_maverick_groq_supports_tools(self):
        reg = self._reg()
        model = reg.get("llama-4-maverick-17b-128e-instruct")
        assert model.supports_tools is True

    def test_llama4_maverick_nvidia_registered(self):
        reg = self._reg()
        model = reg.get("meta/llama-4-maverick-17b-128e-instruct")
        assert model is not None
        assert model.provider_id == "nvidia"

    def test_gemini25_flash_registered(self):
        reg = self._reg()
        model = reg.get("gemini-2.5-flash")
        assert model is not None
        assert model.provider_id == "google"

    def test_gemini25_flash_has_1m_context(self):
        reg = self._reg()
        model = reg.get("gemini-2.5-flash")
        assert model.context_window == 1048576

    def test_gemini25_flash_supports_vision(self):
        reg = self._reg()
        model = reg.get("gemini-2.5-flash")
        assert model.supports_vision is True

    def test_gemini25_flash_supports_tools(self):
        reg = self._reg()
        model = reg.get("gemini-2.5-flash")
        assert model.supports_tools is True

    def test_gemini25_flash_is_free(self):
        reg = self._reg()
        model = reg.get("gemini-2.5-flash")
        assert model.input_cost_per_1m == 0.0

    def test_best_model_for_vision_returns_gemini_or_capable(self):
        reg = self._reg()
        model = reg.best_model_for(require_vision=True)
        assert model is not None
        assert model.supports_vision is True

    def test_best_model_for_tools_returns_capable_model(self):
        reg = self._reg()
        model = reg.best_model_for(require_tools=True)
        assert model is not None
        assert model.supports_tools is True
