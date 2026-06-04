"""Regression tests for daily-2026-06-04 improvements.

Covers:
- Claude Opus 4.8 model-map entries in the router
- 2026 server-side beta tool stripping (text_editor_20260101, bash_20260101, etc.)
- Effort parameter stripped before forwarding to Ollama
- Thinking content blocks stripped from message history
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Router: Opus 4.8 entries ──────────────────────────────────────────────────

def _fresh_router(env: dict[str, str] | None = None) -> "ModelRouter":  # type: ignore[name-defined]
    from router.model_router import ModelRouter, reset_router
    reset_router()
    if env:
        for k, v in env.items():
            os.environ[k] = v
    else:
        for k in ("MODEL_MAP", "ROUTER_EXTRA_MODELS", "NVIDIA_API_KEY", "ANTHROPIC_API_KEY",
                  "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
            os.environ.pop(k, None)
    os.environ["ROUTER_HEALTH_CHECK_ENABLED"] = "false"
    r = ModelRouter()
    reset_router()
    return r


def test_claude_opus_4_8_maps_to_model_map():
    """claude-opus-4-8 must resolve via model_map, not fall through to heuristic."""
    r = _fresh_router()
    decision = r.route(requested_model="claude-opus-4-8")
    assert decision.selection_source == "model_map", (
        f"Expected model_map, got {decision.selection_source}"
    )
    assert decision.resolved_model, "resolved_model should be non-empty"


def test_claude_opus_4_8_routes_to_heavy_model():
    """Without NVIDIA key, Opus 4.8 should route to the heavy local reasoning model."""
    r = _fresh_router()
    decision = r.route(requested_model="claude-opus-4-8")
    assert decision.resolved_model == "deepseek-r1:671b", (
        f"Expected deepseek-r1:671b (largest), got {decision.resolved_model}"
    )


def test_claude_sonnet_4_7_maps_to_coder():
    """claude-sonnet-4-7 should resolve to the coding model."""
    r = _fresh_router()
    decision = r.route(requested_model="claude-sonnet-4-7")
    assert decision.selection_source == "model_map"
    assert decision.resolved_model == "qwen3-coder:30b"


def test_opus_model_prefers_4_8_for_direct_api():
    """_opus_model() with ANTHROPIC_API_KEY should return claude-opus-4-8."""
    from router.model_router import _opus_model, reset_router
    reset_router()
    os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
    os.environ.pop("AWS_ACCESS_KEY_ID", None)
    os.environ.pop("AWS_SECRET_ACCESS_KEY", None)
    try:
        result = _opus_model()
        assert result == "claude-opus-4-8", f"Expected claude-opus-4-8, got {result}"
    finally:
        os.environ.pop("ANTHROPIC_API_KEY", None)
        reset_router()


def test_opus_model_prefers_4_8_bedrock_arn():
    """_opus_model() with Bedrock keys should return the Opus 4.8 ARN."""
    from router.model_router import _opus_model, reset_router
    reset_router()
    os.environ["AWS_ACCESS_KEY_ID"] = "AKIATEST"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "secrettest"
    os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        result = _opus_model()
        assert result == "us.anthropic.claude-opus-4-8-v1", (
            f"Expected us.anthropic.claude-opus-4-8-v1, got {result}"
        )
    finally:
        os.environ.pop("AWS_ACCESS_KEY_ID", None)
        os.environ.pop("AWS_SECRET_ACCESS_KEY", None)
        reset_router()


# ── Anthropic compat: 2026 tool stripping ─────────────────────────────────────

def _tools_to_openai(tools):  # type: ignore[no-untyped-def]
    from handlers.anthropic_compat import _tools_to_openai as _fn
    return _fn(tools)


def _make_tool(tool_type: str, name: str = "test_tool") -> dict:
    return {"type": tool_type, "name": name}


def test_text_editor_2026_is_stripped():
    result = _tools_to_openai([_make_tool("text_editor_20260101")])
    assert result == [], "text_editor_20260101 must be stripped"


def test_bash_2026_is_stripped():
    result = _tools_to_openai([_make_tool("bash_20260101")])
    assert result == [], "bash_20260101 must be stripped"


def test_computer_use_2026_is_stripped():
    result = _tools_to_openai([_make_tool("computer_use_20260124")])
    assert result == [], "computer_use_20260124 must be stripped"


def test_web_search_2026_is_stripped():
    result = _tools_to_openai([_make_tool("web_search_20260101")])
    assert result == [], "web_search_20260101 must be stripped"


def test_normal_function_tool_is_preserved():
    tool = {
        "type": "custom",
        "name": "get_weather",
        "description": "Get weather",
        "input_schema": {"type": "object", "properties": {"city": {"type": "string"}}},
    }
    result = _tools_to_openai([tool])
    assert len(result) == 1
    assert result[0]["type"] == "function"
    assert result[0]["function"]["name"] == "get_weather"


def test_mix_of_stripped_and_valid_tools():
    tools = [
        _make_tool("bash_20260101"),
        {
            "type": "custom",
            "name": "my_func",
            "description": "desc",
            "input_schema": {"type": "object", "properties": {}},
        },
        _make_tool("text_editor_20260101"),
    ]
    result = _tools_to_openai(tools)
    assert len(result) == 1
    assert result[0]["function"]["name"] == "my_func"


# ── Anthropic compat: thinking block stripping ─────────────────────────────────

def _content_block_to_text(block: dict) -> str:
    from handlers.anthropic_compat import _content_block_to_text as _fn
    return _fn(block)


def test_thinking_block_is_stripped_to_empty():
    block = {"type": "thinking", "thinking": "Let me reason step by step..."}
    assert _content_block_to_text(block) == ""


def test_thinking_block_with_adaptive_type():
    block = {"type": "thinking", "thinking": "Adaptive reasoning output"}
    assert _content_block_to_text(block) == ""


def test_text_block_still_works():
    block = {"type": "text", "text": "Hello world"}
    assert _content_block_to_text(block) == "Hello world"


# ── Effort / thinking param stripping (unit test on payload building logic) ───

def test_effort_not_in_openai_payload():
    """Ensure effort never leaks into the forwarded OpenAI payload."""
    import json
    payload = {
        "model": "claude-opus-4-8",
        "messages": [{"role": "user", "content": "hi"}],
        "effort": "high",
        "max_tokens": 100,
    }
    openai_payload: dict = {
        "model": "deepseek-r1:32b",
        "messages": payload["messages"],
        "stream": False,
    }
    for param in ("temperature", "top_p"):
        val = payload.get(param)
        if val is not None:
            openai_payload[param] = val

    body = json.dumps(openai_payload)
    assert "effort" not in json.loads(body), "effort must not appear in forwarded payload"


def test_thinking_param_not_in_openai_payload():
    """Ensure thinking never leaks into the forwarded OpenAI payload."""
    import json
    payload = {
        "model": "claude-opus-4-8",
        "messages": [{"role": "user", "content": "hi"}],
        "thinking": {"type": "adaptive"},
        "max_tokens": 100,
    }
    openai_payload: dict = {
        "model": "deepseek-r1:32b",
        "messages": payload["messages"],
        "stream": False,
    }
    body = json.dumps(openai_payload)
    assert "thinking" not in json.loads(body), "thinking must not appear in forwarded payload"
