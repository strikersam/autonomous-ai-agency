"""tests/test_daily_automation_2026_08_21.py — Daily automation tests (2026-08-21).

Covers the three ecosystem updates applied today:
  1. config/llm/models.yaml — claude-sonnet-5, claude-sonnet-5-20260501,
     claude-opus-5, and claude-haiku-4-5-20251001 added to the YAML model catalog.
  2. config/llm/providers.yaml + packages/llm/config.py — Anthropic default model
     updated from claude-sonnet-4-6 / claude-sonnet-4-5 to claude-sonnet-5.
  3. packages/llm/providers/anthropic.py — anthropic-workspace-id response header
     captured to debug log and surfaced in LLMResponse.raw for observability.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest


# ── YAML catalog — Claude 5 family ───────────────────────────────────────────

class TestCatalogClaude5Models:
    """Verify the new Claude 5 entries in config/llm/models.yaml."""

    def _cfg(self):
        from packages.llm.config import load_config
        return load_config()

    def test_claude_sonnet5_in_catalog(self) -> None:
        assert "claude-sonnet-5" in self._cfg().models

    def test_claude_sonnet5_dated_alias_in_catalog(self) -> None:
        assert "claude-sonnet-5-20260501" in self._cfg().models

    def test_claude_opus5_in_catalog(self) -> None:
        assert "claude-opus-5" in self._cfg().models

    def test_claude_haiku45_dated_alias_in_catalog(self) -> None:
        assert "claude-haiku-4-5-20251001" in self._cfg().models

    def test_sonnet5_has_1m_context_window(self) -> None:
        model = self._cfg().models["claude-sonnet-5"]
        assert model.context_window == 1_048_576

    def test_sonnet5_dated_alias_has_1m_context_window(self) -> None:
        model = self._cfg().models["claude-sonnet-5-20260501"]
        assert model.context_window == 1_048_576

    def test_sonnet5_introductory_pricing(self) -> None:
        model = self._cfg().models["claude-sonnet-5"]
        assert model.input_cost_per_1m == 2.0
        assert model.output_cost_per_1m == 10.0

    def test_sonnet5_cheaper_than_sonnet46(self) -> None:
        models = self._cfg().models
        s5 = models["claude-sonnet-5"]
        s46 = models["claude-sonnet-4-6"]
        assert s5.input_cost_per_1m < s46.input_cost_per_1m

    def test_opus5_provider_is_anthropic(self) -> None:
        model = self._cfg().models["claude-opus-5"]
        assert model.provider == "anthropic"

    def test_opus5_supports_tools(self) -> None:
        model = self._cfg().models["claude-opus-5"]
        assert model.supports_tools

    def test_opus5_supports_reasoning(self) -> None:
        model = self._cfg().models["claude-opus-5"]
        assert model.supports_reasoning

    def test_sonnet5_supports_images(self) -> None:
        model = self._cfg().models["claude-sonnet-5"]
        assert model.supports_images

    def test_haiku45_dated_alias_same_cost_as_undated(self) -> None:
        models = self._cfg().models
        haiku = models["claude-haiku-4-5"]
        haiku_dated = models["claude-haiku-4-5-20251001"]
        assert haiku_dated.input_cost_per_1m == haiku.input_cost_per_1m
        assert haiku_dated.output_cost_per_1m == haiku.output_cost_per_1m


# ── Anthropic default model ───────────────────────────────────────────────────

class TestAnthropicDefaultModel:
    """Verify the Anthropic provider default model was promoted to claude-sonnet-5."""

    def test_providers_yaml_default_is_sonnet5(self) -> None:
        from packages.llm.config import load_config
        cfg = load_config()
        p = cfg.providers.get("anthropic")
        assert p is not None, "anthropic provider must be present in providers.yaml"
        assert p.default_model == "claude-sonnet-5"

    def test_env_fallback_default_is_sonnet5(self) -> None:
        """packages/llm/config.py env-provider fallback must also use sonnet-5."""
        from packages.llm import config as llm_config
        for row in llm_config._ENV_PROVIDERS:
            pid, _kind, _base_env, _base_default, _key_prefix, _tier, _priority, model_env, model_default = row
            if pid == "anthropic":
                assert model_default == "claude-sonnet-5", (
                    f"anthropic env fallback is {model_default!r}, expected 'claude-sonnet-5'"
                )
                return
        pytest.fail("anthropic row not found in _ENV_PROVIDERS")


# ── anthropic-workspace-id header capture ─────────────────────────────────────

class TestAnthropicWorkspaceIdCapture:
    """Verify the workspace-id header is captured from Anthropic API responses."""

    def _make_provider(self):
        from packages.llm.providers.anthropic import AnthropicProvider
        from packages.llm.config import ProviderConfig
        cfg = ProviderConfig(
            id="anthropic",
            kind="anthropic",
            base_url="https://api.anthropic.com",
            key_env=["ANTHROPIC_API_KEY"],
            tier="premium",
            priority=64,
            timeout_sec=30.0,
            prompt_caching=False,
        )
        return AnthropicProvider(cfg)

    def _minimal_response_body(self) -> dict:
        return {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "hello"}],
            "model": "claude-sonnet-5",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 5, "output_tokens": 3},
        }

    def test_workspace_id_surfaced_in_raw_when_present(self) -> None:
        provider = self._make_provider()
        result = provider._parse(
            self._minimal_response_body(),
            model="claude-sonnet-5",
            latency_ms=50,
            workspace_id="ws_abc123",
        )
        assert result.raw.get("_anthropic_workspace_id") == "ws_abc123"

    def test_raw_unchanged_when_workspace_id_absent(self) -> None:
        provider = self._make_provider()
        result = provider._parse(
            self._minimal_response_body(),
            model="claude-sonnet-5",
            latency_ms=50,
            workspace_id=None,
        )
        assert "_anthropic_workspace_id" not in result.raw

    def test_workspace_id_default_is_none(self) -> None:
        """_parse must work without passing workspace_id (backwards compat)."""
        provider = self._make_provider()
        result = provider._parse(
            self._minimal_response_body(),
            model="claude-sonnet-5",
            latency_ms=50,
        )
        assert "_anthropic_workspace_id" not in result.raw

    @pytest.mark.asyncio
    async def test_chat_extracts_workspace_id_from_headers(self) -> None:
        """chat() must read anthrophic-workspace-id from the response headers."""
        provider = self._make_provider()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"anthropic-workspace-id": "ws_xyz789"}
        mock_response.json.return_value = self._minimal_response_body()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        from packages.llm.types import LLMRequest
        request = LLMRequest(
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=10,
        )
        result = await provider.chat(
            request, model="claude-sonnet-5", api_key="key", client=mock_client
        )
        assert result.raw.get("_anthropic_workspace_id") == "ws_xyz789"

    @pytest.mark.asyncio
    async def test_chat_omits_workspace_id_when_header_absent(self) -> None:
        provider = self._make_provider()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = self._minimal_response_body()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        from packages.llm.types import LLMRequest
        request = LLMRequest(
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=10,
        )
        result = await provider.chat(
            request, model="claude-sonnet-5", api_key="key", client=mock_client
        )
        assert "_anthropic_workspace_id" not in result.raw
