"""Anthropic provider adapter — Claude 5/4 family via native Messages API.

Implements the Provider interface so the ProviderManager can route calls to
Anthropic alongside the free providers (Cerebras, Groq, NVIDIA NIM, Ollama).

Model priority is 50 — after all free providers — so paid calls only happen
when ALLOW_PAID_BRAIN=true or when explicitly requested by model name.

Streaming uses Anthropic's server-sent-events format (content_block_delta /
text_delta events), not the OpenAI SSE format.
"""
from __future__ import annotations

import json
import logging

from packages.ai.provider import Provider, ChatResponse, HealthStatus, RateLimit
from packages.config import settings

log = logging.getLogger(__name__)

_DEFAULT_MODEL = "claude-sonnet-5"
_API_BASE = "https://api.anthropic.com"
_ANTHROPIC_VERSION = "2023-06-01"


def _headers() -> dict[str, str]:
    return {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": _ANTHROPIC_VERSION,
        "content-type": "application/json",
    }


def _resolve_model(model: str | None) -> str:
    return model or getattr(settings, "anthropic_default_model", "") or _DEFAULT_MODEL


class AnthropicProvider(Provider):
    """Anthropic Claude provider — supports Claude 5, 4, and Haiku families."""

    @property
    def provider_id(self) -> str:
        return "anthropic"

    @property
    def priority(self) -> int:
        return 50

    @property
    def is_configured(self) -> bool:
        return bool(settings.anthropic_api_key)

    async def chat(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        **kwargs,
    ) -> ChatResponse:
        import httpx

        resolved = _resolve_model(model)
        payload: dict = {
            "model": resolved,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if temperature != 1.0:
            payload["temperature"] = temperature

        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                f"{_API_BASE}/v1/messages",
                json=payload,
                headers=_headers(),
            )
        resp.raise_for_status()
        data = resp.json()

        text = "".join(
            b["text"]
            for b in data.get("content", [])
            if b.get("type") == "text"
        )
        usage = data.get("usage", {})
        return ChatResponse(
            text=text,
            model=resolved,
            provider="anthropic",
            usage={
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
            },
            raw=data,
        )

    async def stream(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        **kwargs,
    ):
        import httpx

        resolved = _resolve_model(model)
        payload: dict = {
            "model": resolved,
            "max_tokens": max_tokens,
            "messages": messages,
            "stream": True,
        }
        if temperature != 1.0:
            payload["temperature"] = temperature

        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream(
                "POST",
                f"{_API_BASE}/v1/messages",
                json=payload,
                headers=_headers(),
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        event = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    if event.get("type") == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            yield delta.get("text", "")

    async def health(self) -> HealthStatus:
        if not self.is_configured:
            return HealthStatus(healthy=False, error="ANTHROPIC_API_KEY not set")
        return HealthStatus(healthy=True)

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        # claude-sonnet-5 pricing: $3/1M input, $15/1M output (USD)
        return (input_tokens * 3.0 + output_tokens * 15.0) / 1_000_000

    def limits(self) -> RateLimit:
        return RateLimit(requests_per_minute=50, tokens_per_minute=40_000)
