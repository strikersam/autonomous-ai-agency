"""Two review findings left after #1952 and #1953.

1. The Anthropic response translator still used a bare ``int()`` on provider token counts, so a
   malformed count (a string, ``inf``) raised before the cost hook ran: the finished request
   looked like a provider failure and its cost, user-token and agent-spend recording was lost.
2. ``LLMRouter.stream()`` charged the retry budget before the post-slot Bedrock recheck, so a
   candidate skipped because the kill switch flipped while it queued still used up an attempt;
   with a one-attempt budget that stopped the fallback provider from being tried.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
from types import SimpleNamespace

import httpx
import pytest

from packages.ai.router import ProviderRouter


def _translate(usage):
    body = {"id": "m1", "content": [{"type": "text", "text": "hi"}], "stop_reason": "end_turn",
            "usage": usage}
    # Raw bytes, not json=: httpx refuses to serialise inf, but a provider can send `Infinity`.
    raw = httpx.Response(200, content=json.dumps(body).encode(),
                         headers={"content-type": "application/json"})
    out = ProviderRouter._anthropic_to_openai_response(raw, "claude")
    return out.json()["usage"]


@pytest.mark.parametrize("bad", ["many", None, [], {"x": 1}, -5, 1e999, "NaN"])
def test_a_malformed_cache_count_does_not_abort_the_translation(bad):
    usage = _translate({"input_tokens": 10, "output_tokens": 4,
                        "cache_read_input_tokens": bad, "cache_creation_input_tokens": bad})
    assert usage["cache_read_input_tokens"] >= 0
    assert usage["cache_creation_input_tokens"] >= 0
    assert (usage["prompt_tokens"], usage["completion_tokens"], usage["total_tokens"]) == (10, 4, 14)


def test_malformed_input_and_output_counts_read_as_zero_not_an_error():
    usage = _translate({"input_tokens": "lots", "output_tokens": float("inf")})
    assert (usage["prompt_tokens"], usage["completion_tokens"], usage["total_tokens"]) == (0, 0, 0)


def test_well_formed_usage_is_unchanged():
    usage = _translate({"input_tokens": 7, "output_tokens": 3,
                        "cache_read_input_tokens": 100, "cache_creation_input_tokens": 20})
    assert usage == {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10,
                     "cache_creation_input_tokens": 20, "cache_read_input_tokens": 100}


def test_stream_still_tries_the_fallback_when_a_blocked_candidate_is_skipped(monkeypatch):
    from packages.llm.retry import RetryBudget
    from packages.llm.router import LLMRouter
    from packages.llm.types import LLMRequest

    bedrock_cfg = SimpleNamespace(
        id="bedrock", kind="openai", key_env=[],
        base_url="https://bedrock-mantle.us-east-1.api.aws/v1")
    other_cfg = SimpleNamespace(
        id="groq", kind="openai", key_env=[], base_url="https://api.groq.com/openai/v1")
    called: list[str] = []

    class _Provider:
        def __init__(self, name):
            self.name = name

        async def stream(self, *_a, **_k):
            called.append(self.name)
            yield SimpleNamespace(delta="ok")

    @contextlib.asynccontextmanager
    async def _slot(pid, timeout=0):
        if pid == "bedrock":  # the switch goes ON while this candidate waits for its slot
            monkeypatch.delenv("BEDROCK_DISABLED", raising=False)
        yield True

    async def _http():
        return None

    router = LLMRouter.__new__(LLMRouter)
    router._providers = {"bedrock": _Provider("bedrock"), "groq": _Provider("groq")}
    router._bulkhead = SimpleNamespace(slot=_slot)
    router._health = SimpleNamespace(is_available=lambda _p: True,
                                     record_success=lambda *_a, **_k: None)
    router._keys = SimpleNamespace(acquire=lambda *_a, **_k: ("k", 0),
                                   record_success=lambda *_a, **_k: None)
    router._metrics = SimpleNamespace(record_request=lambda **_k: None)
    router._http = _http
    router._apply_policy = lambda r: r
    router._candidates = lambda _r: [
        SimpleNamespace(provider=bedrock_cfg, model=SimpleNamespace(id="m")),
        SimpleNamespace(provider=other_cfg, model=SimpleNamespace(id="m")),
    ]
    router._retry_budget = lambda _r: RetryBudget(max_attempts=1, deadline_sec=30.0)  # REAL budget
    router._penalise = lambda *_a, **_k: None
    monkeypatch.setenv("BEDROCK_DISABLED", "false")  # off when the candidates were built

    async def _drain():
        return [c async for c in router.stream(LLMRequest(
            messages=[{"role": "user", "content": "x"}]))]

    chunks = asyncio.run(_drain())
    assert called == ["groq"], f"fallback not reached; providers called: {called}"
    assert len(chunks) == 1
