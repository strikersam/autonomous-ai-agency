"""Tests for extended usage fields in the Anthropic compat handler.

Verifies that cache_read_input_tokens and cache_creation_input_tokens are
present in both non-streaming and streaming responses, keeping Claude Code CLI
and the Anthropic SDK happy when they read these fields from local-model responses.
"""

from __future__ import annotations

import json

import pytest

from handlers.anthropic_compat import (
    _build_anthropic_response,
    _sse_event,
)


# ── Non-streaming response builder ────────────────────────────────────────────────────────────────────────────

class TestBuildAnthropicResponse:
    def _sample_openai_resp(self, prompt_tokens: int = 10, completion_tokens: int = 5) -> dict:
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "Hello there."},
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
        }

    def test_usage_has_cache_read_input_tokens(self):
        resp = _build_anthropic_response(self._sample_openai_resp(), "claude-sonnet-4-6", "msg_abc")
        assert "cache_read_input_tokens" in resp["usage"]

    def test_usage_has_cache_creation_input_tokens(self):
        resp = _build_anthropic_response(self._sample_openai_resp(), "claude-sonnet-4-6", "msg_abc")
        assert "cache_creation_input_tokens" in resp["usage"]

    def test_cache_fields_are_zero_for_local_models(self):
        resp = _build_anthropic_response(self._sample_openai_resp(), "qwen3-coder:30b", "msg_xyz")
        assert resp["usage"]["cache_read_input_tokens"] == 0
        assert resp["usage"]["cache_creation_input_tokens"] == 0

    def test_standard_usage_fields_still_present(self):
        resp = _build_anthropic_response(self._sample_openai_resp(15, 8), "claude-haiku-4-5", "msg_001")
        assert resp["usage"]["input_tokens"] == 15
        assert resp["usage"]["output_tokens"] == 8

    def test_usage_on_empty_choices(self):
        resp = _build_anthropic_response({"choices": [], "usage": {}}, "claude-sonnet-4-6", "msg_002")
        assert resp["usage"]["cache_read_input_tokens"] == 0
        assert resp["usage"]["cache_creation_input_tokens"] == 0

    def test_response_structure_valid(self):
        resp = _build_anthropic_response(self._sample_openai_resp(), "claude-sonnet-4-6", "msg_003")
        assert resp["type"] == "message"
        assert resp["role"] == "assistant"
        assert "content" in resp
        assert "usage" in resp


# ── Streaming message_start event ─────────────────────────────────────────────────────────────────────────────

class TestStreamingUsageFields:
    def _parse_message_start_usage(self, event_bytes: bytes) -> dict:
        """Extract the usage dict from a message_start SSE event."""
        text = event_bytes.decode("utf-8")
        # Find the data: line
        for line in text.splitlines():
            if line.startswith("data:"):
                data = json.loads(line[5:].strip())
                return data["message"]["usage"]
        raise AssertionError("No data: line found in SSE event")

    def test_message_start_contains_cache_read_tokens(self):
        event = _sse_event("message_start", {
            "type": "message_start",
            "message": {
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "content": [],
                "model": "claude-sonnet-4-6",
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {
                    "input_tokens": 0,
                    "output_tokens": 1,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                },
            },
        })
        usage = self._parse_message_start_usage(event)
        assert "cache_read_input_tokens" in usage
        assert "cache_creation_input_tokens" in usage

    def test_message_start_cache_fields_are_zero(self):
        event = _sse_event("message_start", {
            "type": "message_start",
            "message": {
                "id": "msg_test2",
                "type": "message",
                "role": "assistant",
                "content": [],
                "model": "qwen3-coder:30b",
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {
                    "input_tokens": 0,
                    "output_tokens": 1,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                },
            },
        })
        usage = self._parse_message_start_usage(event)
        assert usage["cache_read_input_tokens"] == 0
        assert usage["cache_creation_input_tokens"] == 0


# ── Integration: field names match Anthropic API spec ─────────────────────────────────────────────────────────────────────\n
def test_usage_field_names_match_anthropic_spec():
    """Verify exact field names match the Anthropic Messages API spec (2024-06-20+)."""
    resp = _build_anthropic_response(
        {"choices": [{"finish_reason": "stop", "message": {"content": "ok"}}], "usage": {}},
        "claude-opus-4-8",
        "msg_spec",
    )
    # As per https://docs.anthropic.com/en/api/getting-started#response
    expected_fields = {"input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"}
    assert set(resp["usage"].keys()) >= expected_fields
