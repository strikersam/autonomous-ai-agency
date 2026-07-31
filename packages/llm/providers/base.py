"""packages/llm/providers/base.py — the provider contract and the generic adapter.

``LLMProvider`` is the only interface the router knows. ``OpenAICompatible``
implements it for every endpoint that speaks the OpenAI REST shape — which is
most of them: OpenAI, Groq, Cerebras, NVIDIA NIM, OpenRouter, Together,
Fireworks, DeepInfra, Mistral, Azure, LM Studio, vLLM, LiteLLM, LocalAI, and
any other OpenAI-compatible server. Vendors with a different wire format get a
subclass in this package (Anthropic, Gemini, Ollama).

Errors are classified here, at the point where the HTTP status and body are
both in hand. Classification decides two things the router acts on: whether to
retry at all, and which scope to penalise (key, model, or provider).
"""
from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

import httpx

from packages.llm.config import ProviderConfig
from packages.llm.types import (
    LLMRequest,
    LLMResponse,
    PermanentError,
    StreamChunk,
    ToolCall,
    TransientError,
    Usage,
)

log = logging.getLogger("llm.provider")

# Statuses that can never succeed on retry, whatever we do.
PERMANENT_STATUSES = frozenset({400, 401, 403, 404, 405, 413, 414, 422, 451})
# Statuses that are worth another attempt, possibly elsewhere.
TRANSIENT_STATUSES = frozenset({408, 409, 425, 429, 500, 502, 503, 504, 529})

# Body fragments that mean "this model is gone", not "this provider is down".
_MODEL_SCOPED_HINTS = (
    "model_not_found", "unknown model", "no such model", "model does not exist",
    "invalid model", "model is not supported", "decommissioned", "model not found",
)
# Body fragments that mean the key's quota is spent, not merely bursting.
_QUOTA_HINTS = (
    "quota", "insufficient_quota", "credit", "billing", "exceeded your current",
    "out of credits", "payment required",
)


def classify_error(
    status: int | None, body: str, *, provider_id: str
) -> PermanentError | TransientError:
    """Turn an HTTP failure into a typed error with the narrowest blame scope.

    The scope matters more than the retry flag: marking a whole provider dead
    because one model was decommissioned is the exact failure mode that caused
    the NVIDIA 410 incident (CLAUDE.md §7).
    """
    lowered = (body or "").lower()
    prefix = f"{provider_id} HTTP {status}" if status else provider_id

    if status == 429:
        quota = any(hint in lowered for hint in _QUOTA_HINTS)
        return TransientError(
            f"{prefix}: rate limited{' (quota exhausted)' if quota else ''}",
            status=status,
            scope="key",
        )

    if status in {404, 400, 422} and any(hint in lowered for hint in _MODEL_SCOPED_HINTS):
        # A bad model name is permanent for this model but not for the
        # provider — the router retries the next model on the same provider.
        return TransientError(f"{prefix}: model unavailable", status=status, scope="model")

    if status == 410:
        return TransientError(f"{prefix}: endpoint gone", status=status, scope="model")

    if status in PERMANENT_STATUSES:
        return PermanentError(f"{prefix}: {body[:300]}", status=status)

    if status in TRANSIENT_STATUSES or status is None or status >= 500:
        return TransientError(f"{prefix}: {body[:300]}", status=status, scope="provider")

    return PermanentError(f"{prefix}: {body[:300]}", status=status)


def retry_after_seconds(headers: Any) -> float | None:
    """Parse ``Retry-After`` (and common vendor variants) into seconds."""
    if not headers:
        return None
    for name in ("retry-after", "x-ratelimit-reset-requests", "x-ratelimit-reset-tokens"):
        raw = headers.get(name) if hasattr(headers, "get") else None
        if not raw:
            continue
        text = str(raw).strip().lower()
        try:
            if text.endswith("ms"):
                return float(text[:-2]) / 1000.0
            if text.endswith("s"):
                return float(text[:-1])
            return float(text)
        except ValueError:
            continue
    return None


class LLMProvider(ABC):
    """Every provider adapter implements exactly this."""

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    @property
    def id(self) -> str:
        return self.config.id

    @property
    def tier(self) -> str:
        return self.config.tier

    @property
    def priority(self) -> int:
        return self.config.priority

    @abstractmethod
    async def chat(
        self, request: LLMRequest, *, model: str, api_key: str, client: httpx.AsyncClient
    ) -> LLMResponse:
        """Perform one completion. Raises ``PermanentError``/``TransientError``."""

    @abstractmethod
    def stream(
        self, request: LLMRequest, *, model: str, api_key: str, client: httpx.AsyncClient
    ) -> AsyncIterator[StreamChunk]:
        """Yield normalised chunks for one streaming completion."""

    @abstractmethod
    async def health(self, *, api_key: str, client: httpx.AsyncClient) -> dict[str, Any]:
        """Cheap liveness probe. Never raises — returns a status dict."""

    async def list_models(self, *, api_key: str, client: httpx.AsyncClient) -> list[str]:
        """Discover model ids. Providers that cannot enumerate return []."""
        return list(self.config.models)

    def cost(self, model: str, usage: Usage) -> float:
        """USD cost for one completion, from the model registry."""
        from packages.llm.registry import get_registry

        spec = get_registry().get(model)
        if spec is None:
            return 0.0
        return (
            usage.prompt_tokens * spec.input_cost_per_1m / 1_000_000.0
            + usage.completion_tokens * spec.output_cost_per_1m / 1_000_000.0
        )

    def limits(self) -> dict[str, int]:
        return {
            "requests_per_minute": self.config.requests_per_minute,
            "tokens_per_minute": self.config.tokens_per_minute,
            "concurrent_requests": self.config.max_concurrency,
        }

    def auth_headers(self, api_key: str) -> dict[str, str]:
        """Build auth headers according to the configured auth style."""
        headers = dict(self.config.extra_headers)
        if not api_key:
            return headers
        style = (self.config.auth_style or "bearer").lower()
        if self.config.auth_header:
            headers[self.config.auth_header] = api_key
        elif style == "bearer":
            headers["Authorization"] = f"Bearer {api_key}"
        elif style == "x-api-key":
            headers["x-api-key"] = api_key
        elif style == "api-key":
            headers["api-key"] = api_key
        return headers

    def _url(self, path: str) -> str:
        base = (self.config.base_url or "").rstrip("/")
        return f"{base}/{path.lstrip('/')}"


class OpenAICompatible(LLMProvider):
    """Adapter for any endpoint speaking the OpenAI chat-completions shape.

    Adding a vendor that speaks this protocol is a ``providers.yaml`` entry,
    never a new class (ADR-008 §2).
    """

    kind = "openai"

    def _chat_url(self) -> str:
        if self.config.api_version and self.config.deployment:
            # Azure OpenAI: deployment-scoped path plus a mandatory api-version.
            base = (self.config.base_url or "").rstrip("/")
            return (
                f"{base}/openai/deployments/{self.config.deployment}"
                f"/chat/completions?api-version={self.config.api_version}"
            )
        return self._url("chat/completions")

    def build_payload(self, request: LLMRequest, model: str) -> dict[str, Any]:
        """Translate an ``LLMRequest`` into an OpenAI request body.

        Tools, tool_choice, and response_format pass through untouched so
        function calling, JSON mode, and strict schemas keep working exactly
        as they do today.
        """
        payload: dict[str, Any] = {
            "model": model,
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.tools:
            payload["tools"] = request.tools
            if request.tool_choice is not None:
                payload["tool_choice"] = request.tool_choice
        if request.response_format:
            payload["response_format"] = request.response_format
        payload.update(request.extra)
        return payload

    async def chat(
        self, request: LLMRequest, *, model: str, api_key: str, client: httpx.AsyncClient
    ) -> LLMResponse:
        payload = self.build_payload(request, model)
        started = time.monotonic()
        response = await client.post(
            self._chat_url(),
            json=payload,
            headers={"Content-Type": "application/json", **self.auth_headers(api_key)},
            timeout=min(request.timeout_sec, self.config.timeout_sec),
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        if response.status_code >= 400:
            raise self._error(response)
        return self._parse(response.json(), model=model, latency_ms=latency_ms)

    def _error(self, response: httpx.Response) -> PermanentError | TransientError:
        error = classify_error(response.status_code, response.text, provider_id=self.id)
        if isinstance(error, TransientError):
            error.retry_after = retry_after_seconds(response.headers)
        return error

    def _parse(self, data: dict[str, Any], *, model: str, latency_ms: int) -> LLMResponse:
        choices = data.get("choices") or []
        message = (choices[0].get("message") if choices else None) or {}
        text = message.get("content") or ""
        if isinstance(text, list):
            # Some OpenAI-compatible servers return content parts.
            text = "".join(
                str(part.get("text", "")) for part in text if isinstance(part, dict)
            )

        tool_calls: list[ToolCall] = []
        for index, call in enumerate(message.get("tool_calls") or []):
            function = call.get("function") or {}
            tool_calls.append(ToolCall(
                id=str(call.get("id") or f"call_{index}"),
                name=str(function.get("name") or ""),
                arguments=str(function.get("arguments") or ""),
                index=index,
            ))

        raw_usage = data.get("usage") or {}
        details = raw_usage.get("prompt_tokens_details") or {}
        usage = Usage(
            prompt_tokens=int(raw_usage.get("prompt_tokens") or 0),
            completion_tokens=int(raw_usage.get("completion_tokens") or 0),
            cached_tokens=int(details.get("cached_tokens") or 0),
        )
        return LLMResponse(
            text=str(text),
            model=str(data.get("model") or model),
            provider=self.id,
            usage=usage,
            tool_calls=tool_calls,
            finish_reason=(choices[0].get("finish_reason") if choices else None),
            latency_ms=latency_ms,
            cost_usd=self.cost(model, usage),
            raw=data,
        )

    async def stream(  # type: ignore[override]
        self, request: LLMRequest, *, model: str, api_key: str, client: httpx.AsyncClient
    ) -> AsyncIterator[StreamChunk]:
        payload = self.build_payload(request, model)
        payload["stream"] = True
        payload.setdefault("stream_options", {"include_usage": True})
        async with client.stream(
            "POST",
            self._chat_url(),
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
                chunk = self._parse_sse_line(line, model=model)
                if chunk is not None:
                    yield chunk

    def _parse_sse_line(self, line: str, *, model: str) -> StreamChunk | None:
        if not line or not line.startswith("data:"):
            return None
        data = line[5:].strip()
        if not data or data == "[DONE]":
            return None
        try:
            event = json.loads(data)
        except json.JSONDecodeError:
            return None

        choices = event.get("choices") or []
        delta = (choices[0].get("delta") if choices else None) or {}
        finish = choices[0].get("finish_reason") if choices else None

        tool_call = None
        for call in delta.get("tool_calls") or []:
            function = call.get("function") or {}
            tool_call = ToolCall(
                id=str(call.get("id") or ""),
                name=str(function.get("name") or ""),
                arguments=str(function.get("arguments") or ""),
                index=int(call.get("index") or 0),
            )
            break

        raw_usage = event.get("usage") or {}
        usage = None
        if raw_usage:
            usage = Usage(
                prompt_tokens=int(raw_usage.get("prompt_tokens") or 0),
                completion_tokens=int(raw_usage.get("completion_tokens") or 0),
            )

        content = delta.get("content") or ""
        if not content and tool_call is None and finish is None and usage is None:
            return None
        return StreamChunk(
            text=str(content),
            tool_call=tool_call,
            finish_reason=finish,
            usage=usage,
            provider=self.id,
            model=str(event.get("model") or model),
        )

    async def health(self, *, api_key: str, client: httpx.AsyncClient) -> dict[str, Any]:
        started = time.monotonic()
        try:
            response = await client.get(
                self._url("models"),
                headers=self.auth_headers(api_key),
                timeout=10.0,
            )
            latency_ms = int((time.monotonic() - started) * 1000)
            return {
                "healthy": response.status_code < 400,
                "status": response.status_code,
                "latency_ms": latency_ms,
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
            body = response.json()
        except Exception:
            return list(self.config.models)
        entries = body.get("data") if isinstance(body, dict) else body
        ids: list[str] = []
        for entry in entries or []:
            if isinstance(entry, dict) and entry.get("id"):
                ids.append(str(entry["id"]))
            elif isinstance(entry, str):
                ids.append(entry)
        return ids or list(self.config.models)
