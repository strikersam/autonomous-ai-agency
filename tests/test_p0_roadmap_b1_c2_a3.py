from __future__ import annotations

"""Tests for B1 Nemotron Reward Scoring, C2 Function Calling, A3 Capability Registry."""

import json
import os
from typing import Any

import pytest

from agent.capability_registry import (
    ToolDef,
    ToolRegistry,
    get_tool_registry,
    _infer_parameters_from_func,
)
from services.reward_scorer import RewardScore, RewardScorer
from packages.orchestration.chat_handlers import (
    _parse_tool_calls_from_response,
    _normalize_tool_choice,
    _inject_tool_results_as_messages,
)


# ── B1: Nemotron Reward Model Scoring ─────────────────────────────────────────

class TestRewardScore:
    def test_default_values(self) -> None:
        rs = RewardScore()
        assert rs.score == 0.0
        assert rs.model_used is True
        assert rs.error == ""

    def test_high_score(self) -> None:
        rs = RewardScore(score=0.95, model="nvidia/nemotron-4-340b-reward")
        assert rs.score == 0.95
        assert rs.model == "nvidia/nemotron-4-340b-reward"

    def test_score_bounds(self) -> None:
        """Score must be between 0.0 and 1.0."""
        rs = RewardScore(score=0.5)
        assert 0.0 <= rs.score <= 1.0


class TestRewardScorer:
    def test_is_available_without_key(self, monkeypatch: Any) -> None:
        """Without NVIDIA_API_KEY, scorer should report unavailable."""
        monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
        monkeypatch.delenv("NVidiaApiKey", raising=False)
        scorer = RewardScorer()
        assert scorer.is_available is False

    def test_is_available_with_key(self, monkeypatch: Any) -> None:
        """With NVIDIA_API_KEY, scorer should report available."""
        monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
        scorer = RewardScorer()
        assert scorer.is_available is True

    def test_score_without_key_returns_fallback(self) -> None:
        """Score without API key should return model_used=False."""
        import asyncio
        scorer = RewardScorer()
        scorer._api_key = None
        scorer._available = False
        result = asyncio.run(scorer.score(prompt="test", response="test"))
        assert result.model_used is False
        assert result.score == 0.0
        assert "not configured" in result.error.lower()

    @pytest.mark.asyncio
    async def test_score_without_key_returns_fallback_async(self) -> None:
        scorer = RewardScorer()
        scorer._api_key = None
        scorer._available = False
        result = await scorer.score(prompt="test", response="test")
        assert result.model_used is False

    def test_parse_score_from_json(self) -> None:
        scorer = RewardScorer()
        score = scorer._parse_score('{"score": 0.85}')
        assert score == 0.85

    def test_parse_score_from_number(self) -> None:
        scorer = RewardScorer()
        score = scorer._parse_score("0.73")
        assert score == 0.73

    def test_parse_score_clamps_to_1(self) -> None:
        scorer = RewardScorer()
        score = scorer._parse_score("999.0")
        assert score == 1.0

    def test_parse_score_clamps_to_0(self) -> None:
        scorer = RewardScorer()
        score = scorer._parse_score("-5")
        assert score == 0.0

    def test_parse_score_invalid_returns_0(self) -> None:
        scorer = RewardScorer()
        score = scorer._parse_score("not a score")
        assert score == 0.0

    def test_get_reward_scorer_singleton(self) -> None:
        from services.reward_scorer import get_reward_scorer
        s1 = get_reward_scorer()
        s2 = get_reward_scorer()
        assert s1 is s2


# ── C2: Function Calling / Tool Use ───────────────────────────────────────────

class TestParseToolCalls:
    def test_direct_json_array(self) -> None:
        text = json.dumps([
            {"name": "read_file", "arguments": {"path": "main.py"}},
            {"name": "search_code", "arguments": {"query": "TODO"}},
        ])
        calls = _parse_tool_calls_from_response(text)
        assert len(calls) == 2
        assert calls[0]["function"]["name"] == "read_file"
        assert calls[1]["function"]["name"] == "search_code"

    def test_markdown_fenced_json(self) -> None:
        text = '```json\n[{"name": "read_file", "arguments": {"path": "x.py"}}]\n```'
        calls = _parse_tool_calls_from_response(text)
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "read_file"

    def test_function_call_format(self) -> None:
        text = 'read_file({"path": "main.py"})'
        calls = _parse_tool_calls_from_response(text)
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "read_file"

    def test_empty_response(self) -> None:
        calls = _parse_tool_calls_from_response("just some text")
        assert calls == []

    def test_invalid_json(self) -> None:
        calls = _parse_tool_calls_from_response("{not valid json}")
        assert calls == []


class TestNormalizeToolChoice:
    def test_none_tool_choice_returns_unchanged(self) -> None:
        payload = {"model": "qwen3-coder:30b", "messages": []}
        result = _normalize_tool_choice(payload, model=payload["model"])
        assert "tool_choice" not in result

    def test_auto_tool_choice_injects_instruction(self) -> None:
        payload = {
            "model": "qwen3-coder:30b",
            "messages": [{"role": "user", "content": "hello"}],
            "tool_choice": "auto",
        }
        result = _normalize_tool_choice(payload, model=payload["model"])
        assert "tool_choice" not in result
        assert "may call a tool" in result["messages"][0]["content"].lower()

    def test_required_tool_choice_injects_instruction(self) -> None:
        payload = {
            "model": "qwen3-coder:30b",
            "messages": [{"role": "system", "content": "You are helpful."}],
            "tool_choice": "required",
        }
        result = _normalize_tool_choice(payload, model=payload["model"])
        assert "tool_choice" not in result
        assert "must call a tool" in result["messages"][0]["content"].lower()

    def test_none_tool_choice(self) -> None:
        payload = {
            "model": "qwen3-coder:30b",
            "messages": [],
            "tool_choice": "none",
        }
        result = _normalize_tool_choice(payload, model=payload["model"])
        assert "tool_choice" not in result

    def test_specific_tool(self) -> None:
        payload = {
            "model": "qwen3-coder:30b",
            "messages": [{"role": "user", "content": "hi"}],
            "tool_choice": {"type": "function", "function": {"name": "read_file"}},
        }
        result = _normalize_tool_choice(payload, model=payload["model"])
        assert "tool_choice" not in result
        assert "read_file" in result["messages"][0]["content"]

    def test_cloud_model_passes_through(self) -> None:
        """Cloud models (with / in name) should keep tool_choice as-is."""
        payload = {
            "model": "meta/llama-3.3-70b-instruct",
            "messages": [{"role": "user", "content": "hi"}],
            "tool_choice": "auto",
        }
        result = _normalize_tool_choice(payload, model=payload["model"])
        assert result["tool_choice"] == "auto"


class TestInjectToolResults:
    def test_injects_assistant_and_tool_messages(self) -> None:
        payload = {
            "model": "qwen3-coder:30b",
            "messages": [{"role": "user", "content": "read main.py"}],
        }
        response_data = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_abc123",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": '{"path":"main.py"}'},
                    }],
                },
                "finish_reason": "tool_calls",
            }],
        }
        tool_results = [{"id": "call_abc123", "result": "print('hello')"}]
        result = _inject_tool_results_as_messages(payload, response_data, tool_results)
        msgs = result["messages"]
        assert len(msgs) == 3  # user, assistant, tool
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["tool_calls"][0]["id"] == "call_abc123"
        assert msgs[2]["role"] == "tool"
        assert msgs[2]["content"] == "print('hello')"


# ── A3: Capability Registry ───────────────────────────────────────────────────

class TestToolDef:
    def test_basic_definition(self) -> None:
        def handler(x: str) -> str:
            return x

        td = ToolDef(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object", "properties": {}},
            handler=handler,
            capabilities=["filesystem"],
        )
        assert td.name == "test_tool"
        assert td.capabilities == ["filesystem"]
        assert td.version == "1.0.0"

    def test_to_openai_tool(self) -> None:
        def handler() -> str:
            return "ok"

        td = ToolDef(
            name="test",
            description="desc",
            parameters={"type": "object", "properties": {"x": {"type": "string"}}},
            handler=handler,
        )
        openai_tool = td.to_openai_tool()
        assert openai_tool["type"] == "function"
        assert openai_tool["function"]["name"] == "test"
        assert openai_tool["function"]["description"] == "desc"

    def test_to_dict(self) -> None:
        def handler() -> str:
            return "ok"

        td = ToolDef(
            name="test",
            description="desc",
            parameters={},
            handler=handler,
            capabilities=["code"],
            version="2.0.0",
            cost_tier=2,
        )
        d = td.to_dict()
        assert d["name"] == "test"
        assert d["capabilities"] == ["code"]
        assert d["version"] == "2.0.0"
        assert d["cost_tier"] == 2


class TestToolRegistry:
    def test_register_and_get(self) -> None:
        registry = ToolRegistry()
        td = ToolDef(
            name="my_tool",
            description="desc",
            parameters={},
            handler=lambda: None,
            capabilities=["test"],
        )
        registry.register(td)
        assert registry.get("my_tool") is td
        assert registry.get("nonexistent") is None

    def test_find_by_capability(self) -> None:
        registry = ToolRegistry()
        td1 = ToolDef(name="t1", description="", parameters={}, handler=lambda: None, capabilities=["read"])
        td2 = ToolDef(name="t2", description="", parameters={}, handler=lambda: None, capabilities=["write"])
        td3 = ToolDef(name="t3", description="", parameters={}, handler=lambda: None, capabilities=["read", "write"])
        registry.register(td1)
        registry.register(td2)
        registry.register(td3)
        read_tools = registry.find_by_capability("read")
        assert len(read_tools) == 2
        assert {t.name for t in read_tools} == {"t1", "t3"}

    def test_find_by_capabilities(self) -> None:
        registry = ToolRegistry()
        td1 = ToolDef(name="t1", description="", parameters={}, handler=lambda: None, capabilities=["read"])
        td2 = ToolDef(name="t2", description="", parameters={}, handler=lambda: None, capabilities=["write"])
        registry.register(td1)
        registry.register(td2)
        tools = registry.find_by_capabilities(["read", "write"])
        assert len(tools) == 2

    def test_search(self) -> None:
        registry = ToolRegistry()
        registry.register(ToolDef(name="read_file", description="Read a file", parameters={}, handler=lambda: None))
        registry.register(ToolDef(name="write_file", description="Write to file", parameters={}, handler=lambda: None))
        results = registry.search("read")
        assert len(results) == 1
        assert results[0].name == "read_file"

    def test_unregister(self) -> None:
        registry = ToolRegistry()
        td = ToolDef(name="temp", description="", parameters={}, handler=lambda: None, capabilities=["x"])
        registry.register(td)
        assert registry.get("temp") is not None
        assert registry.unregister("temp") is True
        assert registry.get("temp") is None
        assert registry.unregister("nonexistent") is False

    def test_agent_tool_decorator(self) -> None:
        registry = ToolRegistry()

        @registry.agent_tool(
            name="greet",
            description="Greet someone",
            parameters={"type": "object", "properties": {"name": {"type": "string"}}},
            capabilities=["conversation"],
        )
        def greet(name: str) -> str:
            return f"Hello, {name}"

        tool = registry.get("greet")
        assert tool is not None
        assert tool.capabilities == ["conversation"]
        assert tool.handler("World") == "Hello, World"

    def test_capabilities_list(self) -> None:
        registry = ToolRegistry()
        registry.register(ToolDef(name="a", description="", parameters={}, handler=lambda: None, capabilities=["x", "y"]))
        registry.register(ToolDef(name="b", description="", parameters={}, handler=lambda: None, capabilities=["y", "z"]))
        caps = registry.capabilities()
        assert set(caps) == {"x", "y", "z"}

    def test_negotiate(self) -> None:
        registry = ToolRegistry()
        registry.register(ToolDef(name="a", description="", parameters={}, handler=lambda: None, capabilities=["read"]))
        result = registry.negotiate(["read", "write"])
        assert result["matched_count"] == 1
        assert "write" in result["missing_capabilities"]

    def test_to_openai_tools_filtered(self) -> None:
        registry = ToolRegistry()
        registry.register(ToolDef(name="a", description="", parameters={}, handler=lambda: None, capabilities=["read"]))
        registry.register(ToolDef(name="b", description="", parameters={}, handler=lambda: None, capabilities=["write"]))
        tools = registry.to_openai_tools(capabilities=["read"])
        assert len(tools) == 1
        assert tools[0]["function"]["name"] == "a"

    def test_singleton_has_builtin_tools(self) -> None:
        registry = get_tool_registry()
        assert registry.get("read_file") is not None
        assert registry.get("write_file") is not None
        assert registry.get("search_code") is not None
        assert registry.get("list_files") is not None
        assert registry.get("finish") is not None


class TestInferParameters:
    def test_infer_basic(self) -> None:
        def func(x: str, y: int = 0) -> str:
            return x

        schema = _infer_parameters_from_func(func)
        assert schema["type"] == "object"
        assert "x" in schema["properties"]
        assert schema["properties"]["x"]["type"] == "string"
        assert schema["properties"]["y"]["type"] == "integer"
        assert "x" in schema.get("required", [])
        assert "y" not in schema.get("required", [])

    def test_infer_no_annotations(self) -> None:
        def func(a, b):  # type: ignore
            return a

        schema = _infer_parameters_from_func(func)
        assert "a" in schema["properties"]
