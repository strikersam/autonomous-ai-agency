"""tests/test_anthropic_adapter.py — unit tests for packages/ai/adapters/anthropic.py.

All tests use mock/fake objects — no real HTTP calls, no real API keys needed.
"""
from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.ai.adapters.anthropic import AnthropicProvider, _DEFAULT_MODEL, _resolve_model
from packages.ai.provider import ChatResponse, HealthStatus


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_provider(api_key: str = "sk-ant-test") -> AnthropicProvider:
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": api_key, "TESTING": "true"}):
        # Re-import settings so the patched env is picked up
        from packages.config import settings as s
        s.anthropic_api_key = api_key
        return AnthropicProvider()


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_provider_id():
    assert AnthropicProvider().provider_id == "anthropic"


def test_priority_is_after_free_providers():
    """Anthropic (paid) should have lower priority than free providers (10-40)."""
    assert AnthropicProvider().priority == 50


def test_is_configured_true_when_key_set():
    provider = _make_provider("sk-ant-test")
    assert provider.is_configured is True


def test_is_configured_false_when_key_missing():
    with patch.dict(os.environ, {"TESTING": "true"}):
        from packages.config import settings as s
        original = s.anthropic_api_key
        s.anthropic_api_key = ""
        try:
            provider = AnthropicProvider()
            assert provider.is_configured is False
        finally:
            s.anthropic_api_key = original


def test_resolve_model_uses_default_when_none():
    resolved = _resolve_model(None)
    assert resolved == _DEFAULT_MODEL


def test_resolve_model_respects_explicit_model():
    assert _resolve_model("claude-opus-4-8") == "claude-opus-4-8"


@pytest.mark.asyncio
async def test_chat_builds_correct_payload():
    """chat() sends the right JSON body and parses the Anthropic response."""
    fake_response_data = {
        "content": [{"type": "text", "text": "Hello from Claude!"}],
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value=fake_response_data)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    provider = _make_provider()

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await provider.chat(
            [{"role": "user", "content": "Hi"}],
            model="claude-sonnet-5",
        )

    assert isinstance(result, ChatResponse)
    assert result.text == "Hello from Claude!"
    assert result.provider == "anthropic"
    assert result.model == "claude-sonnet-5"
    assert result.usage["prompt_tokens"] == 10
    assert result.usage["completion_tokens"] == 5

    # Verify the payload was built correctly
    call_kwargs = mock_client.post.call_args[1]["json"]
    assert call_kwargs["model"] == "claude-sonnet-5"
    assert call_kwargs["messages"] == [{"role": "user", "content": "Hi"}]


@pytest.mark.asyncio
async def test_health_configured():
    provider = _make_provider("sk-ant-test")
    result = await provider.health()
    assert isinstance(result, HealthStatus)
    assert result.healthy is True


@pytest.mark.asyncio
async def test_health_unconfigured():
    with patch.dict(os.environ, {"TESTING": "true"}):
        from packages.config import settings as s
        original = s.anthropic_api_key
        s.anthropic_api_key = ""
        try:
            provider = AnthropicProvider()
            result = await provider.health()
            assert result.healthy is False
            assert "not set" in (result.error or "").lower()
        finally:
            s.anthropic_api_key = original


def test_cost_positive_for_tokens():
    provider = AnthropicProvider()
    cost = provider.cost(1_000_000, 1_000_000)
    # $3/1M input + $15/1M output = $18 for 1M each
    assert cost == pytest.approx(18.0)


def test_cost_zero_for_no_tokens():
    assert AnthropicProvider().cost(0, 0) == 0.0


def test_limits_defined():
    limits = AnthropicProvider().limits()
    assert limits.requests_per_minute is not None
    assert limits.tokens_per_minute is not None
