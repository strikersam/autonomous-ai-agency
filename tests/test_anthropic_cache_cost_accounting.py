"""Anthropic cache reads must be costed, not clamped away.

Anthropic's ``usage.input_tokens`` excludes cache reads and writes. Passed
straight through as ``prompt_tokens``, ``cost_for_tokens`` clamped
``cached_tokens`` to that uncached remainder, so a call with 1M cache-read
tokens and 50 uncached tokens was costed at about $0.0002 instead of $0.20.
"""
from __future__ import annotations

import json

import httpx
import pytest

from packages.ai.cost_tracker import anthropic_prompt_tokens, cost_for_tokens
from packages.ai.router import ProviderRouter
from packages.llm.config import ProviderConfig
from packages.llm.providers.anthropic import AnthropicProvider

RAW_USAGE = {
    "input_tokens": 50,
    "output_tokens": 0,
    "cache_read_input_tokens": 1_000_000,
    "cache_creation_input_tokens": 0,
}
# Opus 5.5: $4/MTok input, cache reads at 0.05x -> $0.20 per 1M cached,
# plus 50 uncached tokens at $4/MTok.
EXPECTED_COST = 0.20 + 50 * 4.0 / 1_000_000


def test_prompt_count_includes_cache_reads_and_writes() -> None:
    usage = dict(RAW_USAGE, cache_creation_input_tokens=7)
    assert anthropic_prompt_tokens(usage) == 50 + 1_000_000 + 7


def test_provider_usage_keeps_cache_reads_inside_the_prompt_count() -> None:
    provider = AnthropicProvider(ProviderConfig(
        id="anthropic-test", kind="anthropic",
        base_url="https://api.anthropic.com", key_env=["ANTHROPIC_API_KEY"],
    ))
    data = {"content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn",
            "usage": RAW_USAGE}
    usage = provider._parse(data, model="claude-opus-5-5", latency_ms=0).usage
    assert usage.prompt_tokens == 1_000_050
    assert usage.cached_tokens == 1_000_000
    cost = cost_for_tokens("claude-opus-5-5", usage.prompt_tokens, 0, usage.cached_tokens)
    assert cost == pytest.approx(EXPECTED_COST)


def test_router_translated_usage_costs_cache_reads() -> None:
    body = {"id": "msg_1", "content": [{"type": "text", "text": "ok"}],
            "stop_reason": "end_turn", "usage": RAW_USAGE}
    resp = httpx.Response(200, content=json.dumps(body).encode(),
                          headers={"content-type": "application/json"})
    usage = ProviderRouter._anthropic_to_openai_response(resp, "claude-opus-5-5").json()["usage"]
    # The client-facing figure is unchanged ...
    assert usage["prompt_tokens"] == 50
    # ... while the count used for cost includes the cache reads.
    prompt = anthropic_prompt_tokens(usage)
    cost = cost_for_tokens("claude-opus-5-5", prompt, 0, usage["cache_read_input_tokens"])
    assert cost == pytest.approx(EXPECTED_COST)
