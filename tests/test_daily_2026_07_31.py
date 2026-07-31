"""Daily automation tests — 2026-07-31.

Research: Anthropic's prompt caching (cache_control: ephemeral) reduces system-prompt
costs by ~90% for repeated agentic loops and is now the default for the Anthropic
adapter in the new LLM routing layer (packages/llm/).  These tests verify:

  C6-1  cache_control is injected on the system prompt content block
  C6-2  cache_control is placed on the last tool definition (tools breakpoint)
  C6-3  The anthropic-beta header is sent when caching is enabled
  C6-4  cache_creation_input_tokens is extracted into Usage.cache_creation_tokens
  C6-5  cache_read_input_tokens maps to Usage.cached_tokens (pre-existing, regression)
  C6-6  ANTHROPIC_PROMPT_CACHE=false disables the cache_control injection
  C6-7  Usage.cache_creation_tokens is included in as_dict() output
  C6-8  Metrics: record_tokens forwards cache_read and cache_creation to the registry
  C6-9  llm_prompt_cache_tokens_total appears in the Prometheus exposition
  C6-10 cache_creation_tokens defaults to 0 (no regression on pre-existing responses)
"""
from __future__ import annotations

import json
import importlib
import sys
import types
import unittest
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# C6-7 / C6-10  Usage dataclass
# ---------------------------------------------------------------------------

class TestUsageDataclass(unittest.TestCase):
    def _usage(self, **kwargs):
        from packages.llm.types import Usage
        return Usage(**kwargs)

    def test_cache_creation_tokens_defaults_to_zero(self):
        u = self._usage(prompt_tokens=100, completion_tokens=20)
        assert u.cache_creation_tokens == 0

    def test_cache_creation_tokens_in_as_dict(self):
        u = self._usage(prompt_tokens=100, completion_tokens=20, cache_creation_tokens=50)
        d = u.as_dict()
        assert "cache_creation_tokens" in d
        assert d["cache_creation_tokens"] == 50

    def test_cached_tokens_still_in_as_dict(self):
        u = self._usage(prompt_tokens=100, completion_tokens=20, cached_tokens=30)
        d = u.as_dict()
        assert d["cached_tokens"] == 30

    def test_total_tokens_excludes_cache_fields(self):
        u = self._usage(prompt_tokens=100, completion_tokens=20,
                        cached_tokens=30, cache_creation_tokens=50)
        assert u.total_tokens == 120


# ---------------------------------------------------------------------------
# Helper: build a minimal ProviderConfig + AnthropicProvider
# ---------------------------------------------------------------------------

def _make_anthropic(*, cache_enabled: bool = True):
    from packages.llm.config import ProviderConfig
    from packages.llm.providers.anthropic import AnthropicProvider
    import packages.llm.providers.anthropic as antmod
    # Patch the module-level flag for this test
    original = antmod._PROMPT_CACHE_ENABLED
    antmod._PROMPT_CACHE_ENABLED = cache_enabled
    cfg = ProviderConfig(id="anthropic-test", kind="anthropic", base_url="https://api.anthropic.com")
    provider = AnthropicProvider(cfg)
    return provider, antmod, original


def _restore(antmod, original):
    antmod._PROMPT_CACHE_ENABLED = original


def _req(**kwargs):
    from packages.llm.types import LLMRequest
    defaults = dict(messages=[], max_tokens=256, temperature=0.0)
    defaults.update(kwargs)
    return LLMRequest(**defaults)


# ---------------------------------------------------------------------------
# C6-1  System prompt gets cache_control block
# ---------------------------------------------------------------------------

class TestAnthropicCacheControlSystem(unittest.TestCase):
    def test_system_becomes_content_block_with_cache_control(self):
        provider, antmod, orig = _make_anthropic(cache_enabled=True)
        try:
            req = _req(messages=[
                {"role": "system", "content": "You are a helpful agent."},
                {"role": "user", "content": "Hi"},
            ])
            payload = provider.build_payload(req, "claude-sonnet-4-6")
            system = payload["system"]
            assert isinstance(system, list), "system should be a content block list when caching"
            assert len(system) == 1
            block = system[0]
            assert block["type"] == "text"
            assert block["text"] == "You are a helpful agent."
            assert block.get("cache_control") == {"type": "ephemeral"}
        finally:
            _restore(antmod, orig)

    def test_multiple_system_messages_are_joined(self):
        provider, antmod, orig = _make_anthropic(cache_enabled=True)
        try:
            req = _req(messages=[
                {"role": "system", "content": "First."},
                {"role": "system", "content": "Second."},
                {"role": "user", "content": "Hi"},
            ])
            payload = provider.build_payload(req, "claude-sonnet-4-6")
            system = payload["system"]
            assert isinstance(system, list)
            assert "First." in system[0]["text"]
            assert "Second." in system[0]["text"]
            assert system[0].get("cache_control") == {"type": "ephemeral"}
        finally:
            _restore(antmod, orig)


# ---------------------------------------------------------------------------
# C6-2  Tool definitions get cache_control on the last entry
# ---------------------------------------------------------------------------

class TestAnthropicCacheControlTools(unittest.TestCase):
    def _tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "search",
                    "description": "Search",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        ]

    def test_last_tool_gets_cache_control(self):
        provider, antmod, orig = _make_anthropic(cache_enabled=True)
        try:
            req = _req(
                messages=[{"role": "user", "content": "go"}],
                tools=self._tools(),
            )
            payload = provider.build_payload(req, "claude-sonnet-4-6")
            converted = payload["tools"]
            assert len(converted) == 2
            assert "cache_control" not in converted[0], "only the last tool gets the breakpoint"
            assert converted[-1].get("cache_control") == {"type": "ephemeral"}
        finally:
            _restore(antmod, orig)

    def test_single_tool_gets_cache_control(self):
        provider, antmod, orig = _make_anthropic(cache_enabled=True)
        try:
            req = _req(
                messages=[{"role": "user", "content": "go"}],
                tools=[self._tools()[0]],
            )
            payload = provider.build_payload(req, "claude-sonnet-4-6")
            assert payload["tools"][0].get("cache_control") == {"type": "ephemeral"}
        finally:
            _restore(antmod, orig)


# ---------------------------------------------------------------------------
# C6-3  Beta header is sent when caching is enabled
# ---------------------------------------------------------------------------

class TestAnthropicBetaHeader(unittest.TestCase):
    def test_beta_header_present_when_caching_enabled(self):
        provider, antmod, orig = _make_anthropic(cache_enabled=True)
        try:
            headers = provider.auth_headers("sk-test")
            assert "anthropic-beta" in headers
            assert "prompt-caching" in headers["anthropic-beta"]
        finally:
            _restore(antmod, orig)

    def test_beta_header_absent_when_caching_disabled(self):
        provider, antmod, orig = _make_anthropic(cache_enabled=False)
        try:
            headers = provider.auth_headers("sk-test")
            assert "anthropic-beta" not in headers
        finally:
            _restore(antmod, orig)


# ---------------------------------------------------------------------------
# C6-6  ANTHROPIC_PROMPT_CACHE=false disables cache_control injection
# ---------------------------------------------------------------------------

class TestAnthropicCacheDisabled(unittest.TestCase):
    def test_system_is_plain_string_when_disabled(self):
        provider, antmod, orig = _make_anthropic(cache_enabled=False)
        try:
            req = _req(messages=[
                {"role": "system", "content": "You are terse."},
                {"role": "user", "content": "Hi"},
            ])
            payload = provider.build_payload(req, "claude-sonnet-4-6")
            assert isinstance(payload["system"], str), "plain string when caching off"
            assert payload["system"] == "You are terse."
        finally:
            _restore(antmod, orig)

    def test_tools_have_no_cache_control_when_disabled(self):
        provider, antmod, orig = _make_anthropic(cache_enabled=False)
        try:
            req = _req(
                messages=[{"role": "user", "content": "go"}],
                tools=[{
                    "type": "function",
                    "function": {"name": "t", "description": "t",
                                 "parameters": {"type": "object", "properties": {}}},
                }],
            )
            payload = provider.build_payload(req, "claude-sonnet-4-6")
            for tool in payload["tools"]:
                assert "cache_control" not in tool
        finally:
            _restore(antmod, orig)


# ---------------------------------------------------------------------------
# C6-4 / C6-5  Response parsing extracts cache token fields
# ---------------------------------------------------------------------------

class TestAnthropicResponseParsing(unittest.TestCase):
    def _response_data(self, *, cache_read: int = 0, cache_creation: int = 0):
        return {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-4-6",
            "content": [{"type": "text", "text": "Hello!"}],
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 20,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_creation,
            },
        }

    def test_cache_read_maps_to_cached_tokens(self):
        provider, antmod, orig = _make_anthropic()
        try:
            resp = provider._parse(
                self._response_data(cache_read=80), model="claude-sonnet-4-6", latency_ms=42
            )
            assert resp.usage.cached_tokens == 80
        finally:
            _restore(antmod, orig)

    def test_cache_creation_maps_to_cache_creation_tokens(self):
        provider, antmod, orig = _make_anthropic()
        try:
            resp = provider._parse(
                self._response_data(cache_creation=95), model="claude-sonnet-4-6", latency_ms=42
            )
            assert resp.usage.cache_creation_tokens == 95
        finally:
            _restore(antmod, orig)

    def test_both_fields_zero_on_non_cached_response(self):
        provider, antmod, orig = _make_anthropic()
        try:
            resp = provider._parse(
                self._response_data(), model="claude-sonnet-4-6", latency_ms=42
            )
            assert resp.usage.cached_tokens == 0
            assert resp.usage.cache_creation_tokens == 0
        finally:
            _restore(antmod, orig)


# ---------------------------------------------------------------------------
# C6-8 / C6-9  Metrics layer
# ---------------------------------------------------------------------------

class TestMetricsPromptCache(unittest.TestCase):
    def _fresh_registry(self):
        from packages.llm.metrics import MetricsRegistry
        return MetricsRegistry()

    def test_record_tokens_with_cache_fields(self):
        reg = self._fresh_registry()
        reg.record_tokens(
            provider="anthropic", model="claude-sonnet-4-6",
            prompt=100, completion=20, cost_usd=0.005,
            cache_read=80, cache_creation=95,
        )
        # read tokens recorded
        read_key = tuple(sorted([("direction", "read"), ("model", "claude-sonnet-4-6"),
                                  ("provider", "anthropic")]))
        assert reg.prompt_cache_tokens.values.get(read_key, 0) == 80
        # write tokens recorded
        write_key = tuple(sorted([("direction", "write"), ("model", "claude-sonnet-4-6"),
                                   ("provider", "anthropic")]))
        assert reg.prompt_cache_tokens.values.get(write_key, 0) == 95

    def test_record_tokens_zero_cache_fields_emits_nothing(self):
        reg = self._fresh_registry()
        reg.record_tokens(
            provider="openai", model="gpt-4o",
            prompt=50, completion=10, cost_usd=0.001,
        )
        assert not reg.prompt_cache_tokens.values

    def test_prometheus_exposition_includes_prompt_cache_counter(self):
        reg = self._fresh_registry()
        reg.record_tokens(
            provider="anthropic", model="claude-sonnet-4-6",
            prompt=100, completion=20, cost_usd=0.0,
            cache_read=50, cache_creation=0,
        )
        exposition = reg.render()
        assert "llm_prompt_cache_tokens_total" in exposition
        assert "read" in exposition

    def test_snapshot_includes_prompt_cache_counter(self):
        reg = self._fresh_registry()
        reg.record_tokens(
            provider="anthropic", model="claude-sonnet-4-6",
            prompt=100, completion=20, cost_usd=0.0,
            cache_creation=30,
        )
        snap = reg.snapshot()
        assert any("prompt_cache" in k for k in snap.get("counters", {}))
