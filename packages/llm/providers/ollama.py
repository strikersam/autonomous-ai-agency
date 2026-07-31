"""packages/llm/providers/ollama.py — local Ollama adapter.

Ollama exposes both a native ``/api/chat`` endpoint and an OpenAI-compatible
``/v1`` surface. The native endpoint is used because it reports load state,
returns per-request timings, and supports ``keep_alive`` — all of which the
health tracker and the local-first strategy rely on.

LM Studio, vLLM, LocalAI, and LiteLLM are *not* handled here: they speak the
OpenAI protocol, so they are plain ``providers.yaml`` entries pointed at
``OpenAICompatible``.
"""
from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from packages.llm.providers.base import LLMProvider, classify_error
from packages.llm.types import (
    LLMRequest,
    LLMResponse,
    StreamChunk,
    ToolCall,
    TransientError,
    Usage,
)


class OllamaProvider(LLMProvider):
    """Adapter for the native Ollama ``/api/chat`` endpoint."""

    kind = "ollama"

    def auth_headers(self, api_key: str) -> dict[str, str]:
        # A local daemon needs no auth; a tunnelled one may sit behind a bearer.
        headers = dict(self.config.extra_headers)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def build_payload(self, request: LLMRequest, model: str) -> dict[str, Any]:
        options: dict[str, Any] = {
            "temperature": request.temperature,
            "num_predict": request.max_tokens,
        }
        payload: dict[str, Any] = {
            "model": model,
            "messages": request.messages,
            "stream": False,
            "options": options,
        }
        if request.requires_json():
            payload["format"] = "json"
        if request.tools:
            payload["tools"] = request.tools
        payload.update(request.extra)
        return payload

    async def chat(
        self, request: LLMRequest, *, model: str, api_key: str, client: httpx.AsyncClient
    ) -> LLMResponse:
        started = time.monotonic()
        response = await client.post(
            self._url("api/chat"),
            json=self.build_payload(request, model),
            headers={"Content-Type": "application/json", **self.auth_headers(api_key)},
            timeout=min(request.timeout_sec, self.config.timeout_sec),
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        if response.status_code >= 400:
            raise classify_error(response.status_code, response.text, provider_id=self.id)
        return self._parse(response.json(), model=model, latency_ms=latency_ms)

    def _parse(self, data: dict[str, Any], *, model: str, latency_ms: int) -> LLMResponse:
        message = data.get("message") or {}
        tool_calls: list[ToolCall] = []
        for index, call in enumerate(message.get("tool_calls") or []):
            function = call.get("function") or {}
            arguments = function.get("arguments")
            tool_calls.append(ToolCall(
                id=str(call.get("id") or f"call_{index}"),
                name=str(function.get("name") or ""),
                arguments=arguments if isinstance(arguments, str) else json.dumps(arguments or {}),
                index=index,
            ))

        usage = Usage(
            prompt_tokens=int(data.get("prompt_eval_count") or 0),
            completion_tokens=int(data.get("eval_count") or 0),
        )
        return LLMResponse(
            text=str(message.get("content") or ""),
            model=str(data.get("model") or model),
            provider=self.id,
            usage=usage,
            tool_calls=tool_calls,
            finish_reason=data.get("done_reason") or ("stop" if data.get("done") else None),
            latency_ms=latency_ms,
            cost_usd=0.0,  # local inference has no per-token price
            raw=data,
        )

    async def stream(  # type: ignore[override]
        self, request: LLMRequest, *, model: str, api_key: str, client: httpx.AsyncClient
    ) -> AsyncIterator[StreamChunk]:
        payload = self.build_payload(request, model)
        payload["stream"] = True
        async with client.stream(
            "POST",
            self._url("api/chat"),
            json=payload,
            headers={"Content-Type": "application/json", **self.auth_headers(api_key)},
            timeout=min(request.timeout_sec, self.config.timeout_sec),
        ) as response:
            if response.status_code >= 400:
                body = (await response.aread()).decode("utf-8", "replace")
                raise classify_error(response.status_code, body, provider_id=self.id)
            # Ollama streams NDJSON, one complete JSON object per line.
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                message = event.get("message") or {}
                done = bool(event.get("done"))
                usage = None
                if done:
                    usage = Usage(
                        prompt_tokens=int(event.get("prompt_eval_count") or 0),
                        completion_tokens=int(event.get("eval_count") or 0),
                    )
                text = str(message.get("content") or "")

                # Tool calls arrive on their own chunks with empty content.
                # Skipping text-less chunks removed streamed function calling
                # from this provider even though _parse handles it non-streamed.
                tool_calls: list[ToolCall] = []
                for index, call in enumerate(message.get("tool_calls") or []):
                    function = call.get("function") or {}
                    arguments = function.get("arguments")
                    tool_calls.append(ToolCall(
                        id=str(call.get("id") or f"call_{index}"),
                        name=str(function.get("name") or ""),
                        arguments=arguments if isinstance(arguments, str)
                        else json.dumps(arguments or {}),
                        index=index,
                    ))

                if not text and not tool_calls and not done:
                    continue
                yield StreamChunk(
                    text=text,
                    tool_calls=tool_calls,
                    finish_reason=(event.get("done_reason") or "stop") if done else None,
                    usage=usage,
                    provider=self.id,
                    model=str(event.get("model") or model),
                )

    async def health(self, *, api_key: str, client: httpx.AsyncClient) -> dict[str, Any]:
        started = time.monotonic()
        try:
            response = await client.get(
                self._url("api/tags"), headers=self.auth_headers(api_key), timeout=5.0
            )
            latency_ms = int((time.monotonic() - started) * 1000)
            models: list[str] = []
            if response.status_code < 400:
                models = [
                    str(m.get("name") or "")
                    for m in (response.json().get("models") or [])
                    if isinstance(m, dict)
                ]
            return {
                "healthy": response.status_code < 400,
                "status": response.status_code,
                "latency_ms": latency_ms,
                "models_loaded": len(models),
            }
        except Exception as exc:
            return {"healthy": False, "error": str(exc)[:200],
                    "latency_ms": int((time.monotonic() - started) * 1000)}

    async def list_models(self, *, api_key: str, client: httpx.AsyncClient) -> list[str]:
        try:
            response = await client.get(
                self._url("api/tags"), headers=self.auth_headers(api_key), timeout=10.0
            )
            if response.status_code >= 400:
                return list(self.config.models)
            entries = response.json().get("models") or []
        except Exception:
            return list(self.config.models)
        return [
            str(m["name"]) for m in entries if isinstance(m, dict) and m.get("name")
        ] or list(self.config.models)


__all__ = ["OllamaProvider", "TransientError"]
