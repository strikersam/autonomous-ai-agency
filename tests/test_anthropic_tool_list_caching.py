"""tests/test_anthropic_tool_list_caching.py — C6 extension: tool-list prompt caching.

``AnthropicProvider.build_payload`` marks the last entry of the ``tools`` array
with ``cache_control: {type: ephemeral}`` when ``prompt_caching`` is enabled
(the default). Anthropic then caches the full tool list up to that breakpoint,
reducing token costs on repeated agent calls where the tool list is unchanged.
System-message caching was already present; this closes the tool-list half.

Salvaged from PR #1230 — its other half (search_replace_file) was dropped as a
duplicate of the existing WorkspaceTools.edit_file (F1, already on master).
"""
from __future__ import annotations

import pytest


class TestAnthropicToolListCaching:
    """AnthropicProvider.build_payload caches the tool list when prompt_caching=True (C6)."""

    def _make_provider(self, prompt_caching: bool = True):
        from packages.llm.config import ProviderConfig
        from packages.llm.providers.anthropic import AnthropicProvider
        cfg = ProviderConfig(
            id="anthropic-test",
            kind="anthropic",
            base_url="https://api.anthropic.com",
            prompt_caching=prompt_caching,
        )
        return AnthropicProvider(cfg)

    def _make_request(self, tools: list[dict] | None = None):
        from packages.llm.types import LLMRequest
        return LLMRequest(
            messages=[{"role": "user", "content": "hello"}],
            model="claude-sonnet-4-6",
            tools=tools,
        )

    def test_last_tool_gets_cache_control_when_enabled(self):
        provider = self._make_provider(prompt_caching=True)
        tools = [
            {"name": "read_file", "description": "r", "input_schema": {"type": "object", "properties": {}}},
            {"name": "write_file", "description": "w", "input_schema": {"type": "object", "properties": {}}},
        ]
        request = self._make_request(tools=tools)
        payload = provider.build_payload(request, "claude-sonnet-4-6")
        assert "tools" in payload
        assert len(payload["tools"]) == 2
        last = payload["tools"][-1]
        assert last.get("cache_control") == {"type": "ephemeral"}, (
            "Last tool must have cache_control: {type: ephemeral}"
        )

    def test_non_last_tools_have_no_cache_control(self):
        provider = self._make_provider(prompt_caching=True)
        tools = [
            {"name": "read_file", "description": "r", "input_schema": {"type": "object"}},
            {"name": "search_code", "description": "s", "input_schema": {"type": "object"}},
            {"name": "write_file", "description": "w", "input_schema": {"type": "object"}},
        ]
        request = self._make_request(tools=tools)
        payload = provider.build_payload(request, "claude-sonnet-4-6")
        for tool in payload["tools"][:-1]:
            assert "cache_control" not in tool, (
                f"Only the last tool should have cache_control, found it on {tool.get('name')}"
            )

    def test_no_cache_control_when_prompt_caching_disabled(self):
        provider = self._make_provider(prompt_caching=False)
        tools = [{"name": "tool_a", "description": "a", "input_schema": {"type": "object"}}]
        request = self._make_request(tools=tools)
        payload = provider.build_payload(request, "claude-sonnet-4-6")
        assert "tools" in payload
        for tool in payload["tools"]:
            assert "cache_control" not in tool

    def test_single_tool_gets_cache_control(self):
        provider = self._make_provider(prompt_caching=True)
        tools = [{"name": "only_tool", "description": "o", "input_schema": {"type": "object"}}]
        request = self._make_request(tools=tools)
        payload = provider.build_payload(request, "claude-sonnet-4-6")
        assert payload["tools"][0].get("cache_control") == {"type": "ephemeral"}

    def test_no_tools_no_tools_key(self):
        provider = self._make_provider(prompt_caching=True)
        request = self._make_request(tools=None)
        payload = provider.build_payload(request, "claude-sonnet-4-6")
        assert "tools" not in payload

    def test_original_tool_dict_not_mutated(self):
        provider = self._make_provider(prompt_caching=True)
        original_tool = {"name": "t", "description": "d", "input_schema": {"type": "object"}}
        tools = [original_tool]
        request = self._make_request(tools=tools)
        provider.build_payload(request, "claude-sonnet-4-6")
        assert "cache_control" not in original_tool, (
            "build_payload must not mutate the caller's tool dicts"
        )

    def test_cache_control_type_is_ephemeral(self):
        provider = self._make_provider(prompt_caching=True)
        tools = [{"name": "x", "description": "x", "input_schema": {"type": "object"}}]
        request = self._make_request(tools=tools)
        payload = provider.build_payload(request, "claude-sonnet-4-6")
        cc = payload["tools"][-1].get("cache_control", {})
        assert cc.get("type") == "ephemeral"

    def test_tools_not_in_payload_without_request_tools(self):
        provider = self._make_provider(prompt_caching=True)
        request = self._make_request(tools=[])
        payload = provider.build_payload(request, "claude-sonnet-4-6")
        assert "tools" not in payload

    def test_native_anthropic_tool_format_preserved(self):
        """input_schema passthrough — native Anthropic tools should not be wrapped again."""
        provider = self._make_provider(prompt_caching=True)
        native_tool = {
            "name": "native",
            "description": "native tool",
            "input_schema": {"type": "object", "properties": {"x": {"type": "string"}}},
        }
        request = self._make_request(tools=[native_tool])
        payload = provider.build_payload(request, "claude-sonnet-4-6")
        built = payload["tools"][0]
        assert built["name"] == "native"
        assert "input_schema" in built
        assert built.get("cache_control") == {"type": "ephemeral"}
