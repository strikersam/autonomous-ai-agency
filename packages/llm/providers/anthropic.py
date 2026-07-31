"""packages/llm/providers/anthropic.py — Anthropic Messages API adapter.

Anthropic differs from the OpenAI shape in four ways that matter here: the
system prompt is a top-level field rather than a message, tools use
``input_schema`` instead of a nested ``function`` object, tool results come
back as content blocks, and streaming is a typed SSE event sequence rather
than uniform deltas. Everything else is shared with the base adapter.

Prompt caching (C6): when ANTHROPIC_PROMPT_CACHE is not "false", the system
prompt and tool definitions are marked with cache_control so Anthropic stores
them for 5 minutes.  On cache hit the prompt tokens are re-charged at 10% of
the normal rate, saving ~90% on the system-prompt cost for repetitive agentic
loops.  Requires claude-3-5-* or later; silently no-ops on older models.
"""
from __future__ import annotations

import json
import os
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from packages.llm.providers.base import (
    LLMProvider,
    classify_error,
    retry_after_seconds,
)
from packages.llm.types import (
    LLMRequest,
    LLMResponse,
    PermanentError,
    StreamChunk,
    ToolCall,
    TransientError,
    Usage,
)

DEFAULT_API_VERSION = "2023-06-01"
_CACHE_CONTROL = {"type": "ephemeral"}
_PROMPT_CACHE_ENABLED = os.environ.get("ANTHROPIC_PROMPT_CACHE", "true").strip().lower() not in (
    "false", "0", "no", "off"
)


class AnthropicProvider(LLMProvider):
    """Adapter for ``POST /v1/messages``."""

    kind = "anthropic"

    def auth_headers(self, api_key: str) -> dict[str, str]:
        headers = dict(self.config.extra_headers)
        headers["anthropic-version"] = self.config.api_version or DEFAULT_API_VERSION
        if api_key:
            headers["x-api-key"] = api_key
        if _PROMPT_CACHE_ENABLED:
            # Prompt caching graduated to GA for claude-3-5-* and later, but
            # including the beta header on all requests is harmless and ensures
            # it activates on older model IDs that still require the header.
            headers.setdefault("anthropic-beta", "prompt-caching-2024-07-31")
        return headers

    def build_payload(self, request: LLMRequest, model: str) -> dict[str, Any]:
        system_parts: list[str] = []
        messages: list[dict[str, Any]] = []
        for message in request.messages:
            role = message.get("role")
            content = message.get("content")

            if role == "system":
                system_parts.append(
                    content if isinstance(content, str) else json.dumps(content)
                )
                continue

            # A tool result. OpenAI carries these as role="tool" with a
            # tool_call_id; Anthropic needs a tool_result block on a user turn.
            # Without this the second turn of any tool conversation arrives
            # missing the block Anthropic requires and the request fails.
            if role == "tool":
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": str(message.get("tool_call_id") or ""),
                        "content": content if isinstance(content, str) else json.dumps(content),
                    }],
                })
                continue

            # An assistant turn that called tools. OpenAI puts them alongside
            # the text; Anthropic needs tool_use blocks in the content array.
            tool_calls = message.get("tool_calls") or []
            if role == "assistant" and tool_calls:
                blocks: list[dict[str, Any]] = []
                if isinstance(content, str) and content:
                    blocks.append({"type": "text", "text": content})
                for call in tool_calls:
                    function = call.get("function") or {}
                    raw_args = function.get("arguments")
                    try:
                        arguments = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                    except json.JSONDecodeError:
                        arguments = {}
                    blocks.append({
                        "type": "tool_use",
                        "id": str(call.get("id") or ""),
                        "name": str(function.get("name") or ""),
                        "input": arguments,
                    })
                messages.append({"role": "assistant", "content": blocks})
                continue

            messages.append({
                "role": "assistant" if role == "assistant" else "user",
                "content": content,
            })

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages or [{"role": "user", "content": ""}],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if system_parts:
            system_text = "\n\n".join(system_parts)
            if _PROMPT_CACHE_ENABLED:
                # Cache the system prompt as a structured content block. Anthropic
                # stores it for 5 minutes; subsequent requests with the same text pay
                # 10% of normal input-token cost (cache_read_input_tokens field).
                payload["system"] = [
                    {"type": "text", "text": system_text, "cache_control": _CACHE_CONTROL}
                ]
            else:
                payload["system"] = system_text
        if request.tools:
            converted = [self._convert_tool(t) for t in request.tools]
            if _PROMPT_CACHE_ENABLED and converted:
                # Mark the last tool definition as the cache breakpoint.  Anthropic
                # caches everything up to and including the first content block that
                # carries cache_control, so placing it on the last tool covers the
                # entire tool-definition block in one breakpoint.
                converted[-1] = dict(converted[-1], cache_control=_CACHE_CONTROL)
            payload["tools"] = converted
            if request.tool_choice is not None:
                payload["tool_choice"] = self._convert_tool_choice(request.tool_choice)
        payload.update(request.extra)
        return payload

    @staticmethod
    def _convert_tool(tool: dict[str, Any]) -> dict[str, Any]:
        """Accept both OpenAI and native Anthropic tool declarations."""
        if "input_schema" in tool:
            return tool
        function = tool.get("function") or tool
        return {
            "name": function.get("name", ""),
            "description": function.get("description", ""),
            "input_schema": function.get("parameters") or {"type": "object", "properties": {}},
        }

    @staticmethod
    def _convert_tool_choice(choice: Any) -> Any:
        if isinstance(choice, str):
            if choice == "required":
                return {"type": "any"}
            if choice == "none":
                # Anthropic supports {"type": "none"}. Mapping it to "auto"
                # let the model emit tool_use blocks the caller forbade.
                return {"type": "none"}
            return {"type": "auto"}
        if isinstance(choice, dict) and choice.get("type") == "function":
            name = (choice.get("function") or {}).get("name")
            if name:
                return {"type": "tool", "name": name}
        return choice

    async def chat(
        self, request: LLMRequest, *, model: str, api_key: str, client: httpx.AsyncClient
    ) -> LLMResponse:
        started = time.monotonic()
        response = await client.post(
            self._url("v1/messages"),
            json=self.build_payload(request, model),
            headers={"Content-Type": "application/json", **self.auth_headers(api_key)},
            timeout=min(request.timeout_sec, self.config.timeout_sec),
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        if response.status_code >= 400:
            error = classify_error(response.status_code, response.text, provider_id=self.id)
            if isinstance(error, TransientError):
                error.retry_after = retry_after_seconds(response.headers)
            raise error
        return self._parse(response.json(), model=model, latency_ms=latency_ms)

    def _parse(self, data: dict[str, Any], *, model: str, latency_ms: int) -> LLMResponse:
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for index, block in enumerate(data.get("content") or []):
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                text_parts.append(str(block.get("text") or ""))
            elif block.get("type") == "tool_use":
                tool_calls.append(ToolCall(
                    id=str(block.get("id") or f"call_{index}"),
                    name=str(block.get("name") or ""),
                    arguments=json.dumps(block.get("input") or {}),
                    index=index,
                ))

        raw_usage = data.get("usage") or {}
        usage = Usage(
            prompt_tokens=int(raw_usage.get("input_tokens") or 0),
            completion_tokens=int(raw_usage.get("output_tokens") or 0),
            cached_tokens=int(raw_usage.get("cache_read_input_tokens") or 0),
            cache_creation_tokens=int(raw_usage.get("cache_creation_input_tokens") or 0),
        )
        return LLMResponse(
            text="".join(text_parts),
            model=str(data.get("model") or model),
            provider=self.id,
            usage=usage,
            tool_calls=tool_calls,
            finish_reason=data.get("stop_reason"),
            latency_ms=latency_ms,
            cost_usd=self.cost(model, usage),
            raw=data,
        )

    async def stream(  # type: ignore[override]
        self, request: LLMRequest, *, model: str, api_key: str, client: httpx.AsyncClient
    ) -> AsyncIterator[StreamChunk]:
        payload = self.build_payload(request, model)
        payload["stream"] = True
        tool_names: dict[int, str] = {}
        tool_ids: dict[int, str] = {}
        async with client.stream(
            "POST",
            self._url("v1/messages"),
            json=payload,
            headers={"Content-Type": "application/json", **self.auth_headers(api_key)},
            timeout=min(request.timeout_sec, self.config.timeout_sec),
        ) as response:
            if response.status_code >= 400:
                body = (await response.aread()).decode("utf-8", "replace")
                error = classify_error(response.status_code, body, provider_id=self.id)
                if isinstance(error, TransientError):
                    error.retry_after = retry_after_seconds(response.headers)
                raise error
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if not raw:
                    continue
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                chunk = self._parse_event(event, model=model, tool_names=tool_names,
                                          tool_ids=tool_ids)
                if chunk is not None:
                    yield chunk

    def _parse_event(
        self,
        event: dict[str, Any],
        *,
        model: str,
        tool_names: dict[int, str],
        tool_ids: dict[int, str],
    ) -> StreamChunk | None:
        kind = event.get("type")
        index = int(event.get("index") or 0)

        if kind == "content_block_start":
            block = event.get("content_block") or {}
            if block.get("type") == "tool_use":
                tool_names[index] = str(block.get("name") or "")
                tool_ids[index] = str(block.get("id") or "")
            return None

        if kind == "content_block_delta":
            delta = event.get("delta") or {}
            if delta.get("type") == "text_delta":
                return StreamChunk(text=str(delta.get("text") or ""),
                                   provider=self.id, model=model)
            if delta.get("type") == "input_json_delta":
                return StreamChunk(
                    tool_calls=[ToolCall(
                        id=tool_ids.get(index, ""),
                        name=tool_names.get(index, ""),
                        arguments=str(delta.get("partial_json") or ""),
                        index=index,
                    )],
                    provider=self.id,
                    model=model,
                )
            return None

        if kind == "message_delta":
            delta = event.get("delta") or {}
            raw_usage = event.get("usage") or {}
            return StreamChunk(
                finish_reason=delta.get("stop_reason") or "stop",
                usage=Usage(completion_tokens=int(raw_usage.get("output_tokens") or 0)),
                provider=self.id,
                model=model,
            )
        return None

    async def health(self, *, api_key: str, client: httpx.AsyncClient) -> dict[str, Any]:
        started = time.monotonic()
        try:
            response = await client.get(
                self._url("v1/models"), headers=self.auth_headers(api_key), timeout=10.0
            )
            return {
                "healthy": response.status_code < 400,
                "status": response.status_code,
                "latency_ms": int((time.monotonic() - started) * 1000),
            }
        except Exception as exc:
            return {"healthy": False, "error": str(exc)[:200],
                    "latency_ms": int((time.monotonic() - started) * 1000)}

    async def list_models(self, *, api_key: str, client: httpx.AsyncClient) -> list[str]:
        try:
            response = await client.get(
                self._url("v1/models"), headers=self.auth_headers(api_key), timeout=15.0
            )
            if response.status_code >= 400:
                return list(self.config.models)
            data = response.json().get("data") or []
        except Exception:
            return list(self.config.models)
        return [str(m["id"]) for m in data if isinstance(m, dict) and m.get("id")] or list(
            self.config.models
        )


__all__ = ["AnthropicProvider", "PermanentError"]
