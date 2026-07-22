"""Regression test: HTTP 413 (Payload Too Large) must fail over to the next
PROVIDER immediately, not retry the same oversized payload against a
different model on the same provider.

Confirmed in production logs: a task was blocked after 5 dispatch attempts,
all of them Groq 413s, because the loop retried the same payload against up
to 3 models on Groq before ever trying a different provider — burning every
attempt on a failure mode retrying could never fix (the payload is too large
for that provider's endpoint regardless of which model on it is asked).
"""
from __future__ import annotations

import asyncio
from typing import ClassVar

import pytest

from agent.loop import AgentRunner
from services.brain_failover import reset_failover_manager


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in [
        "NVIDIA_API_KEY", "GROQ_API_KEY", "CEREBRAS_API_KEY", "ZHIPU_API_KEY",
        "DEEPSEEK_API_KEY", "TOGETHER_API_KEY", "DASHSCOPE_API_KEY",
        "MOONSHOT_API_KEY", "OPENROUTER_API_KEY", "MINIMAX_API_KEY",
        "GOOGLE_API_KEY", "ANTHROPIC_API_KEY", "ALLOW_PAID_BRAIN",
    ]:
        monkeypatch.delenv(k, raising=False)
    reset_failover_manager()
    yield
    reset_failover_manager()


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError("error", request=None, response=self)  # type: ignore[arg-type]

    def json(self):
        return self._payload


class _FakeAsyncClient:
    """Returns 413 for every call to a Groq URL, success for anything else."""

    calls: ClassVar[list[str]] = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None, headers=None, **kwargs):
        _FakeAsyncClient.calls.append(url)
        if "groq.com" in url:
            return _FakeResponse(413, text="Request too large")
        return _FakeResponse(200, {"choices": [{"message": {"content": "ok-from-fallback"}}]})


@pytest.fixture
def _two_provider_env(monkeypatch):
    """Groq (will 413) + Cerebras (will succeed) both configured, NVIDIA
    deliberately excluded — it's ordered ahead of Groq in the provider
    registry and would otherwise succeed before Groq is ever attempted,
    defeating the point of this test."""
    monkeypatch.setenv("GROQ_API_KEY", "gsk-TESTKEY")
    monkeypatch.setenv("CEREBRAS_API_KEY", "csk-TESTKEY")
    _FakeAsyncClient.calls = []


def test_413_fails_over_to_next_provider_after_one_attempt(_two_provider_env, monkeypatch):
    import agent.loop as loop_mod
    monkeypatch.setattr(loop_mod.httpx, "AsyncClient", _FakeAsyncClient)

    runner = AgentRunner(ollama_base="http://localhost:11434")
    out = asyncio.run(runner._chat_text("some-model", [{"role": "user", "content": "hi"}]))

    assert out == "ok-from-fallback"
    groq_calls = [c for c in _FakeAsyncClient.calls if "groq.com" in c]
    # Exactly one attempt against Groq — not up to 3 models retried against
    # the same oversized payload before moving to a different provider.
    assert len(groq_calls) == 1, f"expected exactly 1 Groq attempt, got {len(groq_calls)}: {groq_calls}"
