"""tests/test_anthropic_conversation_caching.py — Rolling conversation cache breakpoints.

``AnthropicProvider._add_conversation_cache_breakpoints`` marks the most-recent
stable message with ``cache_control: {type: ephemeral}`` so Anthropic caches the
growing conversation history prefix on multi-turn agent calls.  Each subsequent
turn pays only for the new trailing messages rather than re-processing the full
history.

This is the third cache slot used by the provider:
  1. System prompt   — ``_build_system`` (existing)
  2. Tool list       — ``payload["tools"]`` block (existing, C6)
  3. Conversation    — ``_add_conversation_cache_breakpoints`` (this change)

Anthropic allows four cache_control breakpoints per request; three are now in
use, leaving one spare for future use.

Best-practice reference: rolling breakpoints with a 5-minute server-side TTL
that refreshes on each access, so a 50-turn agent loop pays the prefix cost
exactly once per cache miss rather than on every turn.
2026-08-30 daily automation — tracks the 2026 Anthropic prompt-caching guidance.
"""
from __future__ import annotations

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_provider(prompt_caching: bool = True):
    from packages.llm.config import ProviderConfig
    from packages.llm.providers.anthropic import AnthropicProvider
    cfg = ProviderConfig(
        id="anthropic-test",
        kind="anthropic",
        base_url="https://api.anthropic.com",
        prompt_caching=prompt_caching,
    )
    return AnthropicProvider(cfg)


def _make_request(messages: list[dict], tools: list[dict] | None = None):
    from packages.llm.types import LLMRequest
    return LLMRequest(messages=messages, model="claude-sonnet-4-6", tools=tools)


def _msgs(*pairs: tuple[str, str]) -> list[dict]:
    """Build a message list from (role, content) pairs."""
    return [{"role": role, "content": content} for role, content in pairs]


def _breakpoint_at(payload_messages: list[dict], idx: int) -> dict | None:
    """Return the cache_control of message[idx], or None if absent."""
    msg = payload_messages[idx]
    content = msg.get("content")
    if isinstance(content, list) and content:
        return content[-1].get("cache_control")
    return None


# ── Static method unit tests ──────────────────────────────────────────────────

class TestAddConversationCacheBreakpoints:
    """Unit tests for ``_add_conversation_cache_breakpoints`` in isolation."""

    def _fn(self, messages, **kw):
        from packages.llm.providers.anthropic import AnthropicProvider
        return AnthropicProvider._add_conversation_cache_breakpoints(messages, **kw)

    def test_marks_penultimate_message_with_string_content(self):
        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
            {"role": "user", "content": "again"},
        ]
        result = self._fn(msgs)
        # messages[-2] = msgs[1] should have cache_control
        assert result[1]["content"] == [
            {"type": "text", "text": "world", "cache_control": {"type": "ephemeral"}}
        ]

    def test_last_message_never_gets_cache_control(self):
        msgs = [
            {"role": "user", "content": "a"},
            {"role": "assistant", "content": "b"},
            {"role": "user", "content": "c"},
        ]
        result = self._fn(msgs)
        # messages[-1] = msgs[2] must not have cache_control
        content = result[-1]["content"]
        if isinstance(content, list):
            for block in content:
                assert "cache_control" not in block
        else:
            assert isinstance(content, str)

    def test_block_array_content_annotates_last_block(self):
        msgs = [
            {"role": "user", "content": "q"},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "thinking..."},
                    {"type": "text", "text": "answer"},
                ],
            },
            {"role": "user", "content": "next"},
        ]
        result = self._fn(msgs)
        blocks = result[1]["content"]
        # Only the last block gets cache_control
        assert blocks[-1].get("cache_control") == {"type": "ephemeral"}
        assert "cache_control" not in blocks[0]

    def test_short_conversation_unchanged(self):
        """Fewer than stable_back+1 messages → no breakpoint added."""
        msgs = [{"role": "user", "content": "hi"}]
        result = self._fn(msgs)
        assert result == msgs

    def test_exactly_threshold_length_gets_breakpoint(self):
        """Exactly stable_back+1 messages → breakpoint IS added."""
        msgs = [
            {"role": "user", "content": "a"},
            {"role": "assistant", "content": "b"},
            {"role": "user", "content": "c"},
        ]
        result = self._fn(msgs)  # stable_back=2, len=3 → threshold met
        # messages[-2] should now have cache_control
        content = result[1]["content"]
        assert isinstance(content, list)
        assert content[-1].get("cache_control") == {"type": "ephemeral"}

    def test_caller_list_not_mutated(self):
        original = [
            {"role": "user", "content": "u"},
            {"role": "assistant", "content": "a"},
            {"role": "user", "content": "u2"},
        ]
        original_copy = [dict(m) for m in original]
        self._fn(original)
        assert original == original_copy

    def test_caller_message_dicts_not_mutated(self):
        inner = {"role": "assistant", "content": "reply"}
        msgs = [
            {"role": "user", "content": "q"},
            inner,
            {"role": "user", "content": "q2"},
        ]
        self._fn(msgs)
        assert "cache_control" not in inner
        assert inner["content"] == "reply"

    def test_none_content_message_skipped(self):
        msgs = [
            {"role": "user", "content": "u"},
            {"role": "assistant"},  # no content key
            {"role": "user", "content": "u2"},
        ]
        result = self._fn(msgs)
        # Target message has no content → original returned unchanged
        assert result == msgs

    def test_empty_string_content_skipped(self):
        msgs = [
            {"role": "user", "content": "u"},
            {"role": "assistant", "content": ""},
            {"role": "user", "content": "u2"},
        ]
        result = self._fn(msgs)
        assert result == msgs

    def test_custom_stable_back(self):
        """stable_back=3 means messages[-3] gets the breakpoint."""
        msgs = [
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "u2"},
            {"role": "assistant", "content": "a2"},
            {"role": "user", "content": "u3"},
        ]
        result = self._fn(msgs, stable_back=3)
        # messages[-3] = msgs[2] should have breakpoint
        content = result[2]["content"]
        assert isinstance(content, list)
        assert content[-1].get("cache_control") == {"type": "ephemeral"}
        # messages[-2] and messages[-1] must not
        assert _breakpoint_at(result, -1) is None
        assert _breakpoint_at(result, -2) is None

    def test_tool_result_block_annotated(self):
        """Tool-result content arrays (role=user) get cache_control on last block."""
        msgs = [
            {"role": "user", "content": "q"},
            {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "x", "content": "ok"}],
            },
            {"role": "user", "content": "followup"},
        ]
        result = self._fn(msgs)
        blocks = result[1]["content"]
        assert blocks[-1].get("cache_control") == {"type": "ephemeral"}


# ── Integration: build_payload wires the breakpoints ─────────────────────────

class TestBuildPayloadConversationCaching:
    """Verify that build_payload propagates conversation cache breakpoints."""

    def test_three_message_conversation_gets_breakpoint(self):
        provider = _make_provider(prompt_caching=True)
        request = _make_request(_msgs(
            ("user", "hello"),
            ("assistant", "hi"),
            ("user", "bye"),
        ))
        payload = provider.build_payload(request, "claude-sonnet-4-6")
        msgs = payload["messages"]
        # messages[-2] (assistant turn "hi") should be cached
        assert _breakpoint_at(msgs, -2) == {"type": "ephemeral"}
        # messages[-1] (current user turn) must not be cached
        assert _breakpoint_at(msgs, -1) is None

    def test_disabled_caching_no_conversation_breakpoints(self):
        provider = _make_provider(prompt_caching=False)
        request = _make_request(_msgs(
            ("user", "u"),
            ("assistant", "a"),
            ("user", "u2"),
        ))
        payload = provider.build_payload(request, "claude-sonnet-4-6")
        for msg in payload["messages"]:
            content = msg.get("content")
            if isinstance(content, list):
                for block in content:
                    assert "cache_control" not in block

    def test_short_conversation_no_breakpoint(self):
        provider = _make_provider(prompt_caching=True)
        request = _make_request(_msgs(("user", "only one")))
        payload = provider.build_payload(request, "claude-sonnet-4-6")
        msgs = payload["messages"]
        for msg in msgs:
            content = msg.get("content")
            if isinstance(content, list):
                for block in content:
                    assert "cache_control" not in block

    def test_conversation_and_tool_caching_coexist(self):
        """Both the tool list and the conversation can be cached simultaneously."""
        provider = _make_provider(prompt_caching=True)
        tools = [
            {"name": "read_file", "description": "r", "input_schema": {"type": "object"}},
        ]
        request = _make_request(
            _msgs(("user", "u"), ("assistant", "a"), ("user", "u2")),
            tools=tools,
        )
        payload = provider.build_payload(request, "claude-sonnet-4-6")
        # Tool list cache
        assert payload["tools"][-1].get("cache_control") == {"type": "ephemeral"}
        # Conversation cache on messages[-2]
        assert _breakpoint_at(payload["messages"], -2) == {"type": "ephemeral"}

    def test_system_message_excluded_from_messages(self):
        """System messages are extracted to the system field; only turns are in messages."""
        provider = _make_provider(prompt_caching=True)
        request = _make_request([
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "u"},
            {"role": "assistant", "content": "a"},
            {"role": "user", "content": "u2"},
        ])
        payload = provider.build_payload(request, "claude-sonnet-4-6")
        # System must be top-level, not in messages
        assert "system" in payload
        # Remaining 3 messages; messages[-2] = assistant turn
        msgs = payload["messages"]
        assert len(msgs) == 3
        assert _breakpoint_at(msgs, -2) == {"type": "ephemeral"}

    def test_cache_control_type_is_always_ephemeral(self):
        provider = _make_provider(prompt_caching=True)
        request = _make_request(_msgs(
            ("user", "u1"),
            ("assistant", "a1"),
            ("user", "u2"),
        ))
        payload = provider.build_payload(request, "claude-sonnet-4-6")
        cc = _breakpoint_at(payload["messages"], -2)
        assert cc is not None
        assert cc.get("type") == "ephemeral"
