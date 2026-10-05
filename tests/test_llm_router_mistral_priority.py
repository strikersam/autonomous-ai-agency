"""Regression: a configured Mistral key must actually be reached on tool calls.

Production (2026-10-02 → 10-04) loaded the Mistral key but logged zero
``attempt mistral/...`` lines: at priority 48 it sat sixth in the tool-call
candidate list behind groq/nvidia/google, all of which were rate-limited, so the
six-attempt budget was gone before Mistral's turn.
"""
from __future__ import annotations

import pytest

import packages.llm.router as router_mod
from packages.llm.router import LLMRouter
from packages.llm.types import LLMRequest

_KEYS = {
    "AWS_BEARER_TOKEN_BEDROCK": "test",
    "CEREBRAS_API_KEY": "test",
    "GEMINI_API_KEY": "test",
    "GROQ_API_KEY": "test",
    "MISTRAL_API_KEY": "test",
    "NVIDIA_API_KEY": "test",
    "OPENROUTER_API_KEY": "test",
}

_TOOLS = [{
    "type": "function",
    "function": {"name": "noop", "parameters": {"type": "object", "properties": {}}},
}]


@pytest.fixture
def router(monkeypatch: pytest.MonkeyPatch) -> LLMRouter:
    for key, value in _KEYS.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(router_mod, "disabled_provider_ids", lambda: frozenset())
    return LLMRouter()


def test_mistral_codestral_leads_tool_calls_on_cold_health(router: LLMRouter) -> None:
    request = LLMRequest(messages=[{"role": "user", "content": "hi"}], tools=_TOOLS)
    order = [f"{c.provider.id}/{c.model.id}" for c in router._candidates(request)]
    assert order[0] == "mistral/codestral-latest", order

