"""Tests for Anthropic-specific router features.

Covers:
- Prompt caching (ANTHROPIC_PROMPT_CACHING): system-prompt cache_control injection,
  anthropic-beta header, and cache usage field surfacing in responses.
- Extended thinking (ANTHROPIC_THINKING_BUDGET): thinking parameter injection,
  interleaved-thinking beta header, temperature override.
"""

from __future__ import annotations

import json

import httpx
import pytest

from packages.ai.router import ProviderConfig, ProviderRouter


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_anthropic_provider(**kwargs) -> ProviderConfig:
    defaults = dict(
        provider_id="anthropic",
        type="anthropic",
        base_url="https://api.anthropic.com",
        api_key="test-key-123",
        default_model="claude-sonnet-4-6",
        priority=50,
    )
    defaults.update(kwargs)
    return ProviderConfig(**defaults)


def _payload(system: str = "", user: str = "Hello", **extra) -> dict:
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": user})
    return {"messages": msgs, **extra}


# ── auth_headers — prompt caching beta ────────────────────────────────────────


class TestAuthHeadersPromptCaching:
    def test_prompt_caching_beta_added_by_default(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_PROMPT_CACHING", raising=False)
        p = _make_anthropic_provider()
        assert "prompt-caching-2024-07-31" in p.auth_headers().get("anthropic-beta", "")

    def test_prompt_caching_beta_absent_when_disabled(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_PROMPT_CACHING", "false")
        p = _make_anthropic_provider()
        assert "prompt-caching-2024-07-31" not in p.auth_headers().get("anthropic-beta", "")

    def test_prompt_caching_off_values(self, monkeypatch):
        for val in ("0", "false", "no", "off", "False", "OFF"):
            monkeypatch.setenv("ANTHROPIC_PROMPT_CACHING", val)
            p = _make_anthropic_provider()
            assert "prompt-caching-2024-07-31" not in p.auth_headers().get("anthropic-beta", ""), val

    def test_no_anthropic_beta_header_for_openai_provider(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_PROMPT_CACHING", raising=False)
        p = ProviderConfig(
            provider_id="openai",
            type="openai",
            base_url="https://api.openai.com",
            api_key="sk-test",
            default_model="gpt-4o",
        )
        assert "anthropic-beta" not in p.auth_headers()

    def test_x_api_key_still_present_with_caching_on(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_PROMPT_CACHING", raising=False)
        p = _make_anthropic_provider()
        headers = p.auth_headers()
        assert headers.get("x-api-key") == "test-key-123"
        assert "anthropic-version" in headers


# ── auth_headers — extended thinking beta ─────────────────────────────────────


class TestAuthHeadersExtendedThinking:
    def test_thinking_beta_absent_when_budget_zero(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_THINKING_BUDGET", "0")
        p = _make_anthropic_provider()
        assert "interleaved-thinking" not in p.auth_headers().get("anthropic-beta", "")

    def test_thinking_beta_present_when_budget_positive(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_THINKING_BUDGET", "8000")
        monkeypatch.setenv("ANTHROPIC_PROMPT_CACHING", "false")
        p = _make_anthropic_provider()
        assert "interleaved-thinking-2025-05-14" in p.auth_headers().get("anthropic-beta", "")

    def test_both_betas_present_when_both_enabled(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_THINKING_BUDGET", "4000")
        monkeypatch.delenv("ANTHROPIC_PROMPT_CACHING", raising=False)
        p = _make_anthropic_provider()
        beta = p.auth_headers().get("anthropic-beta", "")
        assert "prompt-caching-2024-07-31" in beta
        assert "interleaved-thinking-2025-05-14" in beta

    def test_invalid_budget_does_not_raise(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_THINKING_BUDGET", "notanumber")
        p = _make_anthropic_provider()
        assert "interleaved-thinking" not in p.auth_headers().get("anthropic-beta", "")


# ── _anthropic_payload — prompt caching ───────────────────────────────────────


class TestAnthropicPayloadPromptCaching:
    def test_system_becomes_list_with_cache_control_by_default(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_PROMPT_CACHING", raising=False)
        monkeypatch.delenv("ANTHROPIC_THINKING_BUDGET", raising=False)
        out = ProviderRouter._anthropic_payload(_payload(system="You are helpful."))
        assert isinstance(out["system"], list)
        block = out["system"][0]
        assert block["type"] == "text"
        assert block["text"] == "You are helpful."
        assert block["cache_control"] == {"type": "ephemeral"}

    def test_system_is_plain_string_when_caching_disabled(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_PROMPT_CACHING", "false")
        monkeypatch.delenv("ANTHROPIC_THINKING_BUDGET", raising=False)
        out = ProviderRouter._anthropic_payload(_payload(system="You are helpful."))
        assert isinstance(out["system"], str)
        assert out["system"] == "You are helpful."

    def test_no_system_field_when_no_system_message(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_PROMPT_CACHING", raising=False)
        monkeypatch.delenv("ANTHROPIC_THINKING_BUDGET", raising=False)
        out = ProviderRouter._anthropic_payload({"messages": [{"role": "user", "content": "Hi"}]})
        assert out["system"] is None

    def test_multiple_system_messages_joined(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_PROMPT_CACHING", raising=False)
        monkeypatch.delenv("ANTHROPIC_THINKING_BUDGET", raising=False)
        msgs = [
            {"role": "system", "content": "Part 1"},
            {"role": "system", "content": "Part 2"},
            {"role": "user", "content": "Hello"},
        ]
        out = ProviderRouter._anthropic_payload({"messages": msgs})
        assert isinstance(out["system"], list)
        assert out["system"][0]["text"] == "Part 1\n\nPart 2"

    def test_user_messages_preserved(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_PROMPT_CACHING", raising=False)
        monkeypatch.delenv("ANTHROPIC_THINKING_BUDGET", raising=False)
        out = ProviderRouter._anthropic_payload(_payload(system="sys", user="user msg"))
        assert out["messages"] == [{"role": "user", "content": "user msg"}]


# ── _anthropic_payload — extended thinking ────────────────────────────────────


class TestAnthropicPayloadExtendedThinking:
    def test_thinking_param_added_when_budget_set(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_THINKING_BUDGET", "8000")
        monkeypatch.setenv("ANTHROPIC_PROMPT_CACHING", "false")
        out = ProviderRouter._anthropic_payload(_payload(user="Reason carefully."))
        assert out.get("thinking") == {"type": "enabled", "budget_tokens": 8000}

    def test_temperature_forced_to_1_when_thinking_enabled(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_THINKING_BUDGET", "4000")
        monkeypatch.setenv("ANTHROPIC_PROMPT_CACHING", "false")
        out = ProviderRouter._anthropic_payload(_payload(user="Think deeply."))
        assert out["temperature"] == 1

    def test_no_thinking_param_when_budget_zero(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_THINKING_BUDGET", "0")
        out = ProviderRouter._anthropic_payload(_payload(user="Hello."))
        assert "thinking" not in out

    def test_temperature_not_overridden_when_no_thinking(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_THINKING_BUDGET", "0")
        out = ProviderRouter._anthropic_payload(_payload(user="Hello.") | {"temperature": 0.7})
        assert out["temperature"] == pytest.approx(0.7)


# ── _anthropic_to_openai_response — cache usage fields ────────────────────────


class TestAnthropicToOpenAICacheUsage:
    def _make_anthropic_response(self, **usage_extra) -> httpx.Response:
        usage = {"input_tokens": 20, "output_tokens": 5, **usage_extra}
        body = {
            "id": "msg_abc",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Hi there!"}],
            "stop_reason": "end_turn",
            "usage": usage,
        }
        return httpx.Response(200, json=body)

    def test_cache_creation_tokens_surfaced(self):
        resp = self._make_anthropic_response(cache_creation_input_tokens=500)
        out = ProviderRouter._anthropic_to_openai_response(resp, "claude-sonnet-4-6")
        data = out.json()
        assert data["usage"]["cache_creation_input_tokens"] == 500

    def test_cache_read_tokens_surfaced(self):
        resp = self._make_anthropic_response(cache_read_input_tokens=1000)
        out = ProviderRouter._anthropic_to_openai_response(resp, "claude-sonnet-4-6")
        data = out.json()
        assert data["usage"]["cache_read_input_tokens"] == 1000

    def test_cache_fields_zero_when_not_in_anthropic_response(self):
        resp = self._make_anthropic_response()
        out = ProviderRouter._anthropic_to_openai_response(resp, "claude-sonnet-4-6")
        data = out.json()
        assert data["usage"]["cache_creation_input_tokens"] == 0
        assert data["usage"]["cache_read_input_tokens"] == 0

    def test_standard_usage_fields_still_correct(self):
        resp = self._make_anthropic_response()
        out = ProviderRouter._anthropic_to_openai_response(resp, "claude-sonnet-4-6")
        data = out.json()
        assert data["usage"]["prompt_tokens"] == 20
        assert data["usage"]["completion_tokens"] == 5
        assert data["usage"]["total_tokens"] == 25

    def test_response_content_extracted(self):
        resp = self._make_anthropic_response()
        out = ProviderRouter._anthropic_to_openai_response(resp, "claude-sonnet-4-6")
        data = out.json()
        assert data["choices"][0]["message"]["content"] == "Hi there!"
