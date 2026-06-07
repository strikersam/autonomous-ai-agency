from __future__ import annotations

import pytest

from runtimes.adapters.internal_agent import InternalAgentAdapter


def test_internal_agent_health_reports_unavailable_when_ollama_unreachable(monkeypatch):
    # Ensure NO cloud provider keys are present so the adapter falls through
    # to the Ollama probe.  The local machine may have OPENCODE_ZEN_API_KEY,
    # GROQ_API_KEY, etc. — clear them all so the test is deterministic.
    # NOTE: keep this list in sync with `_best_cloud_primary_base()` in
    # `runtimes/adapters/internal_agent.py` — every provider added there
    # must be cleared here to keep this test deterministic.
    for env_var in (
        "NVIDIA_API_KEY", "NVidiaApiKey",
        "OPENCODE_ZEN_API_KEY",
        "DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL",
        "GROQ_API_KEY",
        "DASHSCOPE_API_KEY", "QWEN_API_KEY",
        "OPENROUTER_API_KEY",
        "TOGETHER_API_KEY",
        "MISTRAL_API_KEY",
        "GOOGLE_API_KEY", "GEMINI_API_KEY",
        "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID",
        "HF_TOKEN", "HUGGINGFACE_API_TOKEN",
        "ZHIPU_API_KEY", "MINIMAX_API_KEY",
    ):
        monkeypatch.delenv(env_var, raising=False)

    # Point OLLAMA_BASE to a localhost URL that will not respond in tests
    monkeypatch.setenv("OLLAMA_BASE", "http://127.0.0.1:59999")

    # Force httpx.AsyncClient.get to raise to simulate unreachable service
    import httpx

    async def fake_get(self, url, **kwargs):
        raise httpx.ConnectError("failed to connect")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    adapter = InternalAgentAdapter(config={})
    import asyncio
    result = asyncio.run(adapter.health_check())
    assert result.available is False
    assert (result.error and "Ollama" in result.error) or (result.details is not None)
