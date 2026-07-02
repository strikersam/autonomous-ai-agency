"""Groq provider adapter — free, fast LLM (deepseek-r1-distill-llama-70b)."""
from __future__ import annotations
from packages.ai.provider import Provider, ChatResponse, HealthStatus, RateLimit
from packages.ai.stream_watchdog import guarded_stream
from packages.config import settings


class GroqProvider(Provider):
    @property
    def provider_id(self) -> str:
        return "groq"

    @property
    def priority(self) -> int:
        return 20

    @property
    def is_configured(self) -> bool:
        return bool(settings.groq_api_key)

    async def chat(self, messages, *, model=None, temperature=0.3, max_tokens=4096, **kwargs):
        import httpx
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"}
        payload = {"model": model or "deepseek-r1-distill-llama-70b", "messages": messages,
                   "temperature": temperature, "max_tokens": max_tokens, "stream": False}
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return ChatResponse(
            text=data["choices"][0]["message"]["content"],
            model=payload["model"], provider="groq",
            usage=data.get("usage", {}),
        )

    async def stream(self, messages, *, model=None, temperature=0.3, max_tokens=4096, **kwargs):
        import httpx, json
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"}
        payload = {"model": model or "deepseek-r1-distill-llama-70b", "messages": messages,
                   "temperature": temperature, "max_tokens": max_tokens, "stream": True}

        async def _raw():
            async with httpx.AsyncClient(timeout=300) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if line.startswith("data: ") and line != "data: [DONE]":
                            chunk = json.loads(line[6:])
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            if delta.get("content"):
                                yield delta["content"]

        async for chunk in guarded_stream(_raw()):
            yield chunk

    async def health(self) -> HealthStatus:
        return HealthStatus(healthy=self.is_configured)

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        return 0.0

    def limits(self) -> RateLimit:
        return RateLimit(requests_per_minute=30, tokens_per_minute=5000)
