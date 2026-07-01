"""NVIDIA NIM provider adapter — wraps the existing provider_router logic.

This is a thin adapter that delegates to provider_router.ProviderRouter
for the actual HTTP calls. As the migration progresses, the HTTP logic
will move here directly and provider_router will be retired.
"""
from __future__ import annotations

from packages.ai.provider import Provider, ChatResponse, HealthStatus, RateLimit
from packages.config import settings


class NvidiaProvider(Provider):
    """NVIDIA NIM — free LLM provider (meta/llama-3.3-70b-instruct)."""

    @property
    def provider_id(self) -> str:
        return "nvidia"

    @property
    def priority(self) -> int:
        return 30

    @property
    def is_configured(self) -> bool:
        return bool(settings.nvidia_api_key)

    async def chat(self, messages, *, model=None, temperature=0.3, max_tokens=4096, **kwargs):
        # Delegate to existing provider_router (will be migrated in full later)
        from packages.ai.router import ProviderRouter, ProviderConfig
        router = ProviderRouter([
            ProviderConfig(
                "nvidia", "openai-compatible",
                settings.nvidia_base_url,
                api_key=settings.nvidia_api_key,
                default_model=model or settings.nvidia_default_model,
                priority=0,
            )
        ])
        result = await router.chat_completion(
            {"model": model or settings.nvidia_default_model, "messages": messages,
             "temperature": temperature, "max_tokens": max_tokens, "stream": False},
            max_retries=2,
        )
        from packages.ai.router import extract_openai_text
        return ChatResponse(
            text=extract_openai_text(result.response.json()),
            model=result.model,
            provider="nvidia",
        )

    async def stream(self, messages, *, model=None, temperature=0.3, max_tokens=4096, **kwargs):
        # Streaming delegates to existing httpx-based streaming
        import httpx
        url = f"{settings.nvidia_base_url}/v1/chat/completions"
        headers = {"Authorization": f"Bearer {settings.nvidia_api_key}", "Content-Type": "application/json"}
        payload = {"model": model or settings.nvidia_default_model, "messages": messages,
                   "temperature": temperature, "max_tokens": max_tokens, "stream": True}
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        import json
                        chunk = json.loads(line[6:])
                        if chunk.get("choices", [{}])[0].get("delta", {}).get("content"):
                            yield chunk["choices"][0]["delta"]["content"]

    async def health(self) -> HealthStatus:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{settings.nvidia_base_url}/v1/models",
                    headers={"Authorization": f"Bearer {settings.nvidia_api_key}"},
                )
            # Only 2xx is healthy — 4xx (auth failure) is NOT healthy.
            return HealthStatus(healthy=200 <= resp.status_code < 300, details={"status_code": resp.status_code})
        except Exception as exc:
            return HealthStatus(healthy=False, error=str(exc))

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        return 0.0  # Free tier

    def limits(self) -> RateLimit:
        return RateLimit(requests_per_minute=40, tokens_per_minute=10000)
