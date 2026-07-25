"""Daily automation tests — 2026-07-25.

Covers four improvements added in this session:
  1. claude-opus-5 added to the model cost table
     (packages/ai/cost_tracker.py)
  2. Multi-modal (image) content handling in _anthropic_payload
     (packages/ai/router.py — _oai_content_to_anthropic)
  3. OpenAI-format tools → Anthropic tools translation
     (packages/ai/router.py — _oai_tools_to_anthropic, _anthropic_payload)
  4. Tool-use blocks + finish_reason mapping in _anthropic_to_openai_response
     (packages/ai/router.py — _anthropic_to_openai_response)
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest


# ── 1. claude-opus-5 in cost tracker ─────────────────────────────────────────


class TestClaudeOpus5CostEntry:
    """claude-opus-5 must appear in the cost table at the premium tier."""

    def test_opus5_in_cost_table(self):
        from packages.ai.cost_tracker import _DEFAULT_COST_TABLE

        assert "claude-opus-5" in _DEFAULT_COST_TABLE

    def test_opus5_pricing_premium_tier(self):
        from packages.ai.cost_tracker import _DEFAULT_COST_TABLE

        input_price, output_price = _DEFAULT_COST_TABLE["claude-opus-5"]
        assert input_price >= 15.0, "Opus 5 input price should be at premium tier"
        assert output_price >= 75.0, "Opus 5 output price should be at premium tier"

    def test_haiku45_alias_in_cost_table(self):
        from packages.ai.cost_tracker import _DEFAULT_COST_TABLE

        assert "claude-haiku-4-5" in _DEFAULT_COST_TABLE
        assert _DEFAULT_COST_TABLE["claude-haiku-4-5"] == _DEFAULT_COST_TABLE[
            "claude-haiku-4-5-20251001"
        ], "Alias and full name must share the same pricing"


# ── 2. Multi-modal content handling ──────────────────────────────────────────


class TestOaiContentToAnthropic:
    """_oai_content_to_anthropic converts OpenAI content blocks to Anthropic format."""

    def _convert(self, content: Any) -> Any:
        from packages.ai.router import ProviderRouter

        return ProviderRouter._oai_content_to_anthropic(content)

    def test_string_passthrough(self):
        assert self._convert("hello") == "hello"

    def test_empty_string_passthrough(self):
        assert self._convert("") == ""

    def test_none_returns_none(self):
        assert self._convert(None) is None

    def test_int_returns_none(self):
        assert self._convert(42) is None

    def test_text_block_preserved(self):
        result = self._convert([{"type": "text", "text": "What's in this image?"}])
        assert result == [{"type": "text", "text": "What's in this image?"}]

    def test_image_url_base64_converted(self):
        content = [
            {
                "type": "image_url",
                "image_url": {"url": "data:image/jpeg;base64,/9j/abc123"},
            }
        ]
        result = self._convert(content)
        assert isinstance(result, list) and len(result) == 1
        block = result[0]
        assert block["type"] == "image"
        assert block["source"]["type"] == "base64"
        assert block["source"]["media_type"] == "image/jpeg"
        assert block["source"]["data"] == "/9j/abc123"

    def test_image_url_http_converted(self):
        content = [
            {
                "type": "image_url",
                "image_url": {"url": "https://example.com/photo.png"},
            }
        ]
        result = self._convert(content)
        assert isinstance(result, list) and len(result) == 1
        block = result[0]
        assert block["type"] == "image"
        assert block["source"]["type"] == "url"
        assert block["source"]["url"] == "https://example.com/photo.png"

    def test_mixed_text_and_image(self):
        content = [
            {"type": "text", "text": "Describe this image:"},
            {"type": "image_url", "image_url": {"url": "https://example.com/cat.jpg"}},
        ]
        result = self._convert(content)
        assert len(result) == 2
        assert result[0]["type"] == "text"
        assert result[1]["type"] == "image"

    def test_unknown_block_type_dropped(self):
        content = [
            {"type": "text", "text": "keep"},
            {"type": "file", "file_id": "file_abc"},  # unknown type → dropped
        ]
        result = self._convert(content)
        assert result == [{"type": "text", "text": "keep"}]

    def test_empty_list_returns_none(self):
        # Empty list produces no blocks → None (message should be skipped)
        result = self._convert([])
        assert result is None

    def test_image_with_missing_url_dropped(self):
        content = [{"type": "image_url", "image_url": {}}]
        result = self._convert(content)
        assert result is None  # no valid blocks

    def test_non_dict_blocks_skipped(self):
        content = ["plain string in list", {"type": "text", "text": "ok"}]
        result = self._convert(content)
        assert result == [{"type": "text", "text": "ok"}]

    def test_multimodal_messages_reach_anthropic_payload(self):
        """_anthropic_payload must not drop messages with list-format content."""
        from packages.ai.router import ProviderRouter

        payload = {
            "model": "claude-sonnet-5",
            "messages": [
                {"role": "user", "content": [
                    {"type": "text", "text": "Describe this:"},
                    {"type": "image_url", "image_url": {"url": "https://example.com/x.jpg"}},
                ]},
            ],
        }
        out = ProviderRouter._anthropic_payload(payload)
        assert len(out["messages"]) == 1
        assert out["messages"][0]["role"] == "user"
        blocks = out["messages"][0]["content"]
        assert isinstance(blocks, list)
        types = {b["type"] for b in blocks}
        assert "text" in types
        assert "image" in types


# ── 3. OpenAI tools → Anthropic tools translation ────────────────────────────


class TestOaiToolsToAnthropic:
    """_oai_tools_to_anthropic converts OpenAI function tools to Anthropic format."""

    def _translate(
        self, tools: list[Any], tool_choice: Any = None
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        from packages.ai.router import ProviderRouter

        return ProviderRouter._oai_tools_to_anthropic(tools, tool_choice)

    def test_empty_tools_returns_empty(self):
        tools, choice = self._translate([])
        assert tools == []
        assert choice is None

    def test_function_tool_translated(self):
        oai_tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get the current weather",
                    "parameters": {
                        "type": "object",
                        "properties": {"location": {"type": "string"}},
                        "required": ["location"],
                    },
                },
            }
        ]
        tools, _ = self._translate(oai_tools)
        assert len(tools) == 1
        t = tools[0]
        assert t["name"] == "get_weather"
        assert t["description"] == "Get the current weather"
        assert t["input_schema"]["type"] == "object"
        assert "location" in t["input_schema"]["properties"]

    def test_tool_choice_auto(self):
        oai_tools = [{"type": "function", "function": {"name": "fn", "description": ""}}]
        _, choice = self._translate(oai_tools, tool_choice="auto")
        assert choice == {"type": "auto"}

    def test_tool_choice_none(self):
        oai_tools = [{"type": "function", "function": {"name": "fn", "description": ""}}]
        _, choice = self._translate(oai_tools, tool_choice="none")
        assert choice == {"type": "none"}

    def test_tool_choice_specific_function(self):
        oai_tools = [{"type": "function", "function": {"name": "fn", "description": ""}}]
        _, choice = self._translate(
            oai_tools, tool_choice={"type": "function", "function": {"name": "fn"}}
        )
        assert choice == {"type": "tool", "name": "fn"}

    def test_tool_choice_null_defaults_to_auto(self):
        oai_tools = [{"type": "function", "function": {"name": "fn", "description": ""}}]
        _, choice = self._translate(oai_tools, tool_choice=None)
        assert choice == {"type": "auto"}

    def test_tool_without_name_dropped(self):
        oai_tools = [{"type": "function", "function": {"description": "no name"}}]
        tools, _ = self._translate(oai_tools)
        assert tools == []

    def test_non_dict_tool_skipped(self):
        oai_tools = ["not-a-dict", {"type": "function", "function": {"name": "valid"}}]
        tools, _ = self._translate(oai_tools)
        assert len(tools) == 1
        assert tools[0]["name"] == "valid"

    def test_tools_included_in_anthropic_payload(self):
        """_anthropic_payload must forward tools to the Anthropic request body."""
        from packages.ai.router import ProviderRouter

        payload = {
            "model": "claude-sonnet-5",
            "messages": [{"role": "user", "content": "What's the weather?"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get weather",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ],
            "tool_choice": "auto",
        }
        out = ProviderRouter._anthropic_payload(payload)
        assert "tools" in out
        assert out["tools"][0]["name"] == "get_weather"
        assert out["tool_choice"] == {"type": "auto"}

    def test_no_tools_in_payload_produces_no_tools_key(self):
        """When the caller sends no tools, the Anthropic payload must not include them."""
        from packages.ai.router import ProviderRouter

        payload = {
            "model": "claude-sonnet-5",
            "messages": [{"role": "user", "content": "Hello"}],
        }
        out = ProviderRouter._anthropic_payload(payload)
        assert "tools" not in out
        assert "tool_choice" not in out


# ── 4. Anthropic response → OpenAI format ────────────────────────────────────


class TestAnthropicToOpenAIResponse:
    """_anthropic_to_openai_response handles tool_use blocks and finish_reason."""

    def _make_response(self, body: dict[str, Any]) -> Any:
        import httpx

        return httpx.Response(200, json=body)

    def _convert(self, body: dict[str, Any], model: str = "claude-sonnet-5") -> dict[str, Any]:
        from packages.ai.router import ProviderRouter

        raw = self._make_response(body)
        translated = ProviderRouter._anthropic_to_openai_response(raw, model)
        return translated.json()

    def _ant_body(
        self,
        content: list[dict[str, Any]],
        stop_reason: str = "end_turn",
        usage: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        return {
            "id": "msg_test",
            "content": content,
            "stop_reason": stop_reason,
            "usage": usage or {"input_tokens": 10, "output_tokens": 20},
        }

    def test_text_response_preserved(self):
        out = self._convert(self._ant_body([{"type": "text", "text": "Hello!"}]))
        assert out["choices"][0]["message"]["content"] == "Hello!"
        assert out["choices"][0]["finish_reason"] == "stop"

    def test_stop_reason_end_turn_maps_to_stop(self):
        out = self._convert(self._ant_body([], stop_reason="end_turn"))
        assert out["choices"][0]["finish_reason"] == "stop"

    def test_stop_reason_max_tokens_maps_to_length(self):
        out = self._convert(self._ant_body(
            [{"type": "text", "text": "cut off"}], stop_reason="max_tokens"
        ))
        assert out["choices"][0]["finish_reason"] == "length"

    def test_stop_reason_tool_use_maps_to_tool_calls(self):
        content = [
            {
                "type": "tool_use",
                "id": "toolu_abc",
                "name": "get_weather",
                "input": {"location": "SF"},
            }
        ]
        out = self._convert(self._ant_body(content, stop_reason="tool_use"))
        assert out["choices"][0]["finish_reason"] == "tool_calls"

    def test_tool_use_block_converted_to_oai_tool_call(self):
        content = [
            {
                "type": "tool_use",
                "id": "toolu_abc",
                "name": "get_weather",
                "input": {"location": "San Francisco"},
            }
        ]
        out = self._convert(self._ant_body(content, stop_reason="tool_use"))
        tool_calls = out["choices"][0]["message"].get("tool_calls") or []
        assert len(tool_calls) == 1
        tc = tool_calls[0]
        assert tc["id"] == "toolu_abc"
        assert tc["type"] == "function"
        assert tc["function"]["name"] == "get_weather"
        args = json.loads(tc["function"]["arguments"])
        assert args["location"] == "San Francisco"

    def test_tool_use_content_field_is_none(self):
        content = [
            {"type": "tool_use", "id": "t1", "name": "fn", "input": {}}
        ]
        out = self._convert(self._ant_body(content, stop_reason="tool_use"))
        assert out["choices"][0]["message"]["content"] is None

    def test_thinking_block_preserved_in_thinking_field(self):
        content = [
            {"type": "thinking", "thinking": "Let me think step by step..."},
            {"type": "text", "text": "The answer is 42."},
        ]
        out = self._convert(self._ant_body(content))
        msg = out["choices"][0]["message"]
        assert msg["content"] == "The answer is 42."
        assert msg.get("thinking") == "Let me think step by step..."

    def test_thinking_block_does_not_appear_in_text_content(self):
        content = [
            {"type": "thinking", "thinking": "Private reasoning..."},
            {"type": "text", "text": "Final answer."},
        ]
        out = self._convert(self._ant_body(content))
        assert "Private reasoning" not in out["choices"][0]["message"]["content"]

    def test_no_thinking_field_when_no_thinking_block(self):
        out = self._convert(self._ant_body([{"type": "text", "text": "Hello"}]))
        assert "thinking" not in out["choices"][0]["message"]

    def test_usage_fields_preserved(self):
        out = self._convert(self._ant_body(
            [{"type": "text", "text": "x"}],
            usage={"input_tokens": 100, "output_tokens": 50,
                   "cache_creation_input_tokens": 30, "cache_read_input_tokens": 20},
        ))
        u = out["usage"]
        assert u["prompt_tokens"] == 100
        assert u["completion_tokens"] == 50
        assert u["cache_creation_input_tokens"] == 30
        assert u["cache_read_input_tokens"] == 20

    def test_multiple_tool_use_blocks(self):
        content = [
            {"type": "tool_use", "id": "t1", "name": "fn1", "input": {"a": 1}},
            {"type": "tool_use", "id": "t2", "name": "fn2", "input": {"b": 2}},
        ]
        out = self._convert(self._ant_body(content, stop_reason="tool_use"))
        tool_calls = out["choices"][0]["message"]["tool_calls"]
        assert len(tool_calls) == 2
        names = {tc["function"]["name"] for tc in tool_calls}
        assert names == {"fn1", "fn2"}

    def test_text_and_tool_use_combined(self):
        content = [
            {"type": "text", "text": "I'll call the function."},
            {"type": "tool_use", "id": "t1", "name": "fn", "input": {}},
        ]
        out = self._convert(self._ant_body(content, stop_reason="tool_use"))
        msg = out["choices"][0]["message"]
        # text content preserved alongside tool_calls when both present
        assert msg.get("content") == "I'll call the function."
        assert len(msg["tool_calls"]) == 1
