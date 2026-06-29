"""Ollama provider adapter — local LLM inference."""
from __future__ import annotations
from packages.ai.provider import Provider, ChatResponse, HealthStatus, RateLimit
from packages.config import settings


class OllamaProvider(Provider):
    @property
    def provider_id(self) -> str:
        return "ollama"

    @property
    def priority(self) -> int:
        return 40

    @property
    def is_configured(self) -> bool:
        return bool(settings.ollama_base)

    async def chat(self, messages, *, model=None, temperature=0.3, max_tokens=4096, **kwargs):
        import httpx
        url = f"{settings.ollama_base}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        payload = {"model": model or settings.ollama_model, "messages": messages,
                   "temperature": temperature, "max_tokens": max_tokens, "stream": False}
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return ChatResponse(
            text=data["choices"][0]["message"]["content"],
            model=payload["model"], provider="ollama",
            usage=data.get("usage", {}),
        )

    async def stream(self, messages, *, model=None, temperature=0.3, max_tokens=4096, **kwargs):
        import httpx, json
        url = f"{settings.ollama_base}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        payload = {"model": model or settings.ollama_model, "messages": messages,
                   "temperature": temperature, "max_tokens": max_tokens, "stream": True}
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        chunk = json.loads(line[6:])
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        if delta.get("content"):
                            yield delta["content"]

    async def health(self) -> HealthStatus:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{settings.ollama_base}/api/tags")
            return HealthStatus(healthy=resp.status_code == 200)
        except Exception as exc:
            return HealthStatus(healthy=False, error=str(exc))

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        return 0.0  # Local = free

    def limits(self) -> RateLimit:
        return RateLimit()  # No rate limits for local
