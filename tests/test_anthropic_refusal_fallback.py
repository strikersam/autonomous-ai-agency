"""Tests for Anthropic server-side fallbacks and refusal logging.

Covers:
- fallbacks: {"mode": "default"} injected into payload when server_fallback=True
  (packages/llm/providers/anthropic.py + packages/llm/config.py)
- fallbacks: {"mode": "default"} injected by _anthropic_payload when
  ANTHROPIC_SERVER_FALLBACK_BETA is active (packages/ai/router.py)
- WARNING log emitted when stop_reason == "refusal" with stop_details surfaced
- fallbacks NOT injected when server_fallback / env var is disabled
"""
from __future__ import annotations

import json
import logging

import httpx
import pytest

from packages.llm.config import ProviderConfig
from packages.llm.providers.anthropic import AnthropicProvider
from packages.llm.types import LLMRequest


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_provider(**kwargs) -> AnthropicProvider:
    defaults = dict(
        id="anthropic-test",
        kind="anthropic",
        base_url="https://api.anthropic.com",
        key_env=["ANTHROPIC_API_KEY"],
    )
    defaults.update(kwargs)
    return AnthropicProvider(ProviderConfig(**defaults))


def _request(**kwargs) -> LLMRequest:
    defaults = dict(
        messages=[{"role": "user", "content": "hello"}],
        model="claude-sonnet-4-6",
        max_tokens=100,
    )
    defaults.update(kwargs)
    return LLMRequest(**defaults)


def _refusal_response(category: str | None = "cyber", explanation: str = "Test refusal") -> dict:
    """Anthropic API shape for a content refusal (HTTP 200, stop_reason=refusal)."""
    stop_details: dict = {"explanation": explanation}
    if category is not None:
        stop_details["category"] = category
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-4-6-20260101",
        "content": [],
        "stop_reason": "refusal",
        "stop_details": stop_details,
        "usage": {"input_tokens": 10, "output_tokens": 0},
    }


# ── server_fallback payload injection (packages/llm) ─────────────────────────


class TestServerFallbackPayload:
    def test_fallbacks_injected_when_server_fallback_true(self):
        provider = _make_provider(server_fallback=True)
        payload = provider.build_payload(_request(), "claude-sonnet-4-6")
        assert payload.get("fallbacks") == {"mode": "default"}, (
            "Expected fallbacks={mode:default} when server_fallback=True"
        )

    def test_fallbacks_absent_when_server_fallback_false(self):
        provider = _make_provider(server_fallback=False)
        payload = provider.build_payload(_request(), "claude-sonnet-4-6")
        assert "fallbacks" not in payload, (
            "fallbacks must not appear when server_fallback=False"
        )

    def test_fallbacks_absent_by_default(self):
        provider = _make_provider()
        payload = provider.build_payload(_request(), "claude-sonnet-4-6")
        assert "fallbacks" not in payload, (
            "fallbacks must be absent when server_fallback is not set (default False)"
        )

    def test_fallbacks_mode_is_default_not_custom(self):
        """Only "default" mode is sent — never a custom string."""
        provider = _make_provider(server_fallback=True)
        payload = provider.build_payload(_request(), "claude-sonnet-4-6")
        assert payload["fallbacks"]["mode"] == "default"

    def test_other_payload_fields_unaffected(self):
        provider = _make_provider(server_fallback=True)
        payload = provider.build_payload(_request(), "claude-sonnet-4-6")
        assert "model" in payload
        assert "messages" in payload
        assert "max_tokens" in payload


# ── refusal logging (packages/llm) ───────────────────────────────────────────


class TestRefusalLogging:
    def _parse(self, data: dict, model: str = "claude-sonnet-4-6") -> None:
        provider = _make_provider()
        provider._parse(data, model=model, latency_ms=0)

    def test_warning_logged_on_refusal(self, caplog):
        with caplog.at_level(logging.WARNING, logger="llm.providers.anthropic"):
            self._parse(_refusal_response(category="cyber"))
        assert any("refusal" in r.message.lower() for r in caplog.records), (
            "Expected a WARNING log containing 'refusal'"
        )

    def test_warning_includes_category(self, caplog):
        with caplog.at_level(logging.WARNING, logger="llm.providers.anthropic"):
            self._parse(_refusal_response(category="bio"))
        assert any("bio" in r.message for r in caplog.records), (
            "Expected the log to include the refusal category"
        )

    def test_warning_includes_null_category(self, caplog):
        with caplog.at_level(logging.WARNING, logger="llm.providers.anthropic"):
            self._parse(_refusal_response(category=None))
        assert any("unknown" in r.message for r in caplog.records), (
            "Expected 'unknown' when category is null"
        )

    def test_warning_includes_explanation(self, caplog):
        with caplog.at_level(logging.WARNING, logger="llm.providers.anthropic"):
            self._parse(_refusal_response(explanation="This request violates policy XYZ"))
        assert any("policy XYZ" in r.message for r in caplog.records), (
            "Expected explanation text in the log"
        )

    def test_no_warning_for_normal_stop(self, caplog):
        data = {
            "id": "msg_ok",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-4-6",
            "content": [{"type": "text", "text": "Hello!"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 5, "output_tokens": 3},
        }
        with caplog.at_level(logging.WARNING, logger="llm.providers.anthropic"):
            self._parse(data)
        refusal_logs = [r for r in caplog.records if "refusal" in r.message.lower()]
        assert not refusal_logs, "Must not emit refusal log for non-refusal stop"

    def test_finish_reason_is_refusal(self):
        provider = _make_provider()
        response = provider._parse(_refusal_response(), model="claude-sonnet-4-6", latency_ms=5)
        assert response.finish_reason == "refusal"

    def test_refusal_text_is_empty(self):
        provider = _make_provider()
        response = provider._parse(_refusal_response(), model="claude-sonnet-4-6", latency_ms=5)
        assert response.text == ""


# ── legacy ai/router _anthropic_payload (packages/ai) ────────────────────────


class TestLegacyRouterServerFallback:
    def _payload(self, **kwargs) -> dict:
        from packages.ai.router import ProviderRouter
        return ProviderRouter._anthropic_payload({
            "messages": [{"role": "user", "content": "hi"}],
            "model": "claude-sonnet-4-6",
            "max_tokens": 100,
            **kwargs,
        })

    def test_fallbacks_injected_when_env_on(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_SERVER_FALLBACK_BETA", "true")
        out = self._payload()
        assert out.get("fallbacks") == {"mode": "default"}, (
            "Expected fallbacks when ANTHROPIC_SERVER_FALLBACK_BETA=true"
        )

    def test_fallbacks_absent_when_env_off(self, monkeypatch):
        for val in ("0", "false", "no", "off", "False", "OFF"):
            monkeypatch.setenv("ANTHROPIC_SERVER_FALLBACK_BETA", val)
            out = self._payload()
            assert "fallbacks" not in out, (
                f"fallbacks must be absent when ANTHROPIC_SERVER_FALLBACK_BETA={val!r}"
            )

    def test_default_is_on(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_SERVER_FALLBACK_BETA", raising=False)
        out = self._payload()
        assert out.get("fallbacks") == {"mode": "default"}, (
            "fallbacks must be present by default (env var absent)"
        )
