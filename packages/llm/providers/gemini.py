"""packages/llm/providers/gemini.py — Google Gemini generateContent adapter.

Gemini's REST API names things differently at every level: ``contents``
instead of ``messages``, ``parts`` instead of string content, ``model``/``user``
instead of ``assistant``/``user``, ``systemInstruction`` as a separate field,
``functionDeclarations`` for tools, and the API key in a query parameter.
The translation is confined to this file.
"""
from __future__ import annotations

import json
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
    StreamChunk,
    ToolCall,
    TransientError,
    Usage,
)


class GeminiProvider(LLMProvider):
    """Adapter for ``POST /models/{model}:generateContent``."""

    kind = "gemini"

    def auth_headers(self, api_key: str) -> dict[str, str]:
        headers = dict(self.config.extra_headers)
        if api_key:
            # Header auth avoids leaking the key into proxy access logs the way
            # a ?key= query parameter would.
            headers["x-goog-api-key"] = api_key
        return headers

    def build_payload(self, request: LLMRequest, model: str) -> dict[str, Any]:
        contents: list[dict[str, Any]] = []
        system_parts: list[str] = []
        for message in request.messages:
            role = message.get("role")
            content = message.get("content")

            if role == "system":
                system_parts.append(
                    content if isinstance(content, str) else self._flatten(content)
                )
                continue

            # Tool results: OpenAI's role="tool" becomes a functionResponse
            # part on a user turn. Dropping it left the second turn of a tool
            # conversation with no result for the call the model just made.
            if role == "tool":
                contents.append({
                    "role": "user",
                    "parts": [{"functionResponse": {
                        "name": str(message.get("name") or message.get("tool_call_id") or "tool"),
                        "response": {"content": content if isinstance(content, str)
                                     else self._flatten(content)},
                    }}],
                })
                continue

            parts: list[dict[str, Any]] = []
            if isinstance(content, str):
                if content:
                    parts.append({"text": content})
            else:
                parts.extend(self._content_parts(content))

            # Assistant turns that called tools become functionCall parts.
            for call in (message.get("tool_calls") or []):
                function = call.get("function") or {}
                raw_args = function.get("arguments")
                try:
                    arguments = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                except json.JSONDecodeError:
                    arguments = {}
                parts.append({"functionCall": {
                    "name": str(function.get("name") or ""), "args": arguments,
                }})

            contents.append({
                "role": "model" if role == "assistant" else "user",
                "parts": parts or [{"text": ""}],
            })

        generation: dict[str, Any] = {
            "temperature": request.temperature,
            "maxOutputTokens": request.max_tokens,
        }
        if request.requires_json():
            generation["responseMimeType"] = "application/json"
            schema = (request.response_format or {}).get("json_schema", {}).get("schema")
            if schema:
                generation["responseSchema"] = schema

        payload: dict[str, Any] = {
            "contents": contents or [{"role": "user", "parts": [{"text": ""}]}],
            "generationConfig": generation,
        }
        if system_parts:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
        if request.tools:
            payload["tools"] = [{
                "functionDeclarations": [self._convert_tool(t) for t in request.tools]
            }]
        payload.update(request.extra)
        return payload

    @staticmethod
    def _content_parts(content: Any) -> list[dict[str, Any]]:
        """Translate an OpenAI content array into Gemini parts.

        Image parts are carried through rather than dropped: the models
        declare ``supports_images: true``, so the router will route a vision
        request here and silently losing the image would produce a confident
        answer about nothing.
        """
        parts: list[dict[str, Any]] = []
        if not isinstance(content, list):
            text = "" if content is None else str(content)
            return [{"text": text}] if text else []

        for part in content:
            if not isinstance(part, dict):
                continue
            kind = part.get("type")
            if kind == "text" or "text" in part:
                text = str(part.get("text") or "")
                if text:
                    parts.append({"text": text})
                continue
            url = ""
            if kind == "image_url":
                url = str((part.get("image_url") or {}).get("url") or "")
            elif kind in {"image", "input_image"}:
                url = str(part.get("image_url") or part.get("url") or part.get("source") or "")
            if not url:
                continue
            if url.startswith("data:"):
                # data:<mime>;base64,<payload>
                header, _, payload = url.partition(",")
                mime = header[5:].split(";", 1)[0] or "image/png"
                parts.append({"inlineData": {"mimeType": mime, "data": payload}})
            else:
                parts.append({"fileData": {"fileUri": url}})
        return parts

    @staticmethod
    def _flatten(content: Any) -> str:
        if isinstance(content, list):
            return "".join(
                str(part.get("text", "")) for part in content if isinstance(part, dict)
            )
        return "" if content is None else str(content)

    @staticmethod
    def _convert_tool(tool: dict[str, Any]) -> dict[str, Any]:
        function = tool.get("function") or tool
        return {
            "name": function.get("name", ""),
            "description": function.get("description", ""),
            "parameters": function.get("parameters") or {"type": "object", "properties": {}},
        }

    def _generate_url(self, model: str, *, stream: bool) -> str:
        verb = "streamGenerateContent" if stream else "generateContent"
        url = self._url(f"models/{model}:{verb}")
        return f"{url}?alt=sse" if stream else url

    async def chat(
        self, request: LLMRequest, *, model: str, api_key: str, client: httpx.AsyncClient
    ) -> LLMResponse:
        started = time.monotonic()
        response = await client.post(
            self._generate_url(model, stream=False),
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
        candidates = data.get("candidates") or []
        parts = ((candidates[0].get("content") if candidates else None) or {}).get("parts") or []

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for index, part in enumerate(parts):
            if not isinstance(part, dict):
                continue
            if "text" in part:
                text_parts.append(str(part["text"]))
            elif "functionCall" in part:
                call = part["functionCall"] or {}
                tool_calls.append(ToolCall(
                    id=f"call_{index}",
                    name=str(call.get("name") or ""),
                    arguments=json.dumps(call.get("args") or {}),
                    index=index,
                ))

        raw_usage = data.get("usageMetadata") or {}
        usage = Usage(
            prompt_tokens=int(raw_usage.get("promptTokenCount") or 0),
            completion_tokens=int(raw_usage.get("candidatesTokenCount") or 0),
            cached_tokens=int(raw_usage.get("cachedContentTokenCount") or 0),
        )
        return LLMResponse(
            text="".join(text_parts),
            model=model,
            provider=self.id,
            usage=usage,
            tool_calls=tool_calls,
            finish_reason=(candidates[0].get("finishReason") if candidates else None),
            latency_ms=latency_ms,
            cost_usd=self.cost(model, usage),
            raw=data,
        )

    async def stream(  # type: ignore[override]
        self, request: LLMRequest, *, model: str, api_key: str, client: httpx.AsyncClient
    ) -> AsyncIterator[StreamChunk]:
        async with client.stream(
            "POST",
            self._generate_url(model, stream=True),
            json=self.build_payload(request, model),
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
                partial = self._parse(event, model=model, latency_ms=0)
                if partial.text or partial.tool_calls or partial.finish_reason:
                    yield StreamChunk(
                        text=partial.text,
                        tool_calls=partial.tool_calls,
                        finish_reason=partial.finish_reason,
                        usage=partial.usage if partial.usage.total_tokens else None,
                        provider=self.id,
                        model=model,
                    )

    async def health(self, *, api_key: str, client: httpx.AsyncClient) -> dict[str, Any]:
        started = time.monotonic()
        try:
            response = await client.get(
                self._url("models"), headers=self.auth_headers(api_key), timeout=10.0
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
                self._url("models"), headers=self.auth_headers(api_key), timeout=15.0
            )
            if response.status_code >= 400:
                return list(self.config.models)
            models = response.json().get("models") or []
        except Exception:
            return list(self.config.models)
        # Gemini returns fully-qualified names like "models/gemini-2.5-flash".
        return [
            str(m["name"]).split("/")[-1]
            for m in models
            if isinstance(m, dict) and m.get("name")
        ] or list(self.config.models)
