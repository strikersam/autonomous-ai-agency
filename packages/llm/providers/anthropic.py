"""packages/llm/providers/anthropic.py — Anthropic Messages API adapter.

Anthropic differs from the OpenAI shape in four ways that matter here: the
system prompt is a top-level field rather than a message, tools use
``input_schema`` instead of a nested ``function`` object, tool results come
back as content blocks, and streaming is a typed SSE event sequence rather
than uniform deltas. Everything else is shared with the base adapter.
"""
from __future__ import annotations

import json
import logging
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

log = logging.getLogger("llm.providers.anthropic")

DEFAULT_API_VERSION = "2023-06-01"

# Anthropic's extended-thinking floor: a request with a budget below this is
# rejected outright, so an invalid one must never be sent.
_MIN_THINKING_BUDGET_TOKENS = 1024

# Claude Sonnet 5 and Fable 5 enforce adaptive thinking; sending temperature /
# top_p / top_k at a non-default value returns HTTP 400.  Strip those fields
# from the payload for every model in this set.
_NO_TEMPERATURE_MODELS: frozenset[str] = frozenset({
    "claude-sonnet-5",
    "claude-fable-5",
    "claude-mythos-5",
    "claude-mythos-preview",
})

# These models use adaptive thinking and do NOT support the legacy
# thinking.type="enabled" budget parameter — sending it returns HTTP 400.
_NO_EXTENDED_THINKING_MODELS: frozenset[str] = frozenset({
    "claude-fable-5",
    "claude-mythos-5",
    "claude-mythos-preview",
    "claude-opus-5",
    "claude-sonnet-5",
    "claude-opus-4-8",
    "claude-opus-4-7",
})

# Valid effort levels accepted by output_config.effort.
_VALID_EFFORT_LEVELS: frozenset[str] = frozenset({
    "low", "medium", "high", "xhigh", "max",
})


class AnthropicProvider(LLMProvider):
    """Adapter for ``POST /v1/messages``."""

    kind = "anthropic"

    def auth_headers(self, api_key: str) -> dict[str, str]:
        headers = dict(self.config.extra_headers)
        headers["anthropic-version"] = self.config.api_version or DEFAULT_API_VERSION
        if api_key:
            headers["x-api-key"] = api_key
        # Merge with whatever anthropic-beta value extra_headers already
        # configured rather than overwriting it — an operator-configured beta
        # (e.g. a different experimental capability) must survive alongside
        # the ones this adapter turns on for prompt_caching/thinking_budget.
        betas: list[str] = []
        for value in (headers.get("anthropic-beta") or "").split(","):
            value = value.strip()
            if value and value not in betas:
                betas.append(value)
        if self.config.prompt_caching and "prompt-caching-2024-07-31" not in betas:
            betas.append("prompt-caching-2024-07-31")
        if self.config.thinking_budget > 0 and "interleaved-thinking-2025-05-14" not in betas:
            betas.append("interleaved-thinking-2025-05-14")
        if betas:
            headers["anthropic-beta"] = ",".join(betas)
        return headers

    def build_payload(self, request: LLMRequest, model: str) -> dict[str, Any]:
        system_parts, messages = self._convert_messages(request.messages)
        no_temperature = model in _NO_TEMPERATURE_MODELS

        # Anthropic's API doesn't accept response_format.  When JSON mode is
        # requested, inject the constraint as a system-prompt instruction so the
        # model still honours it.  This mirrors what the legacy router does via
        # packages/ai/structured_output.py — kept inline here to avoid coupling
        # packages/llm to packages/ai.
        if request.response_format:
            instr = self._json_instruction(request.response_format)
            if instr:
                system_parts.append(instr)

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages or [{"role": "user", "content": ""}],
            "max_tokens": request.max_tokens,
        }
        # Claude Sonnet 5, Fable 5, and Mythos 5 reject non-default temperature/
        # top_p/top_k with HTTP 400 — their adaptive thinking layer handles
        # sampling internally.  Skip the field for those models entirely.
        if not no_temperature:
            payload["temperature"] = request.temperature

        if system_parts:
            payload["system"] = self._build_system(system_parts)
        if request.tools:
            converted_tools = [self._convert_tool(t) for t in request.tools]
            # Prompt-cache the tool list (C6): mark the last tool with
            # cache_control so Anthropic caches everything up to and including
            # the tool definitions.  This saves ~50–80% of tool-list tokens on
            # every subsequent call in the same session, at negligible overhead.
            # Guarded by the same prompt_caching flag that controls system
            # caching, so operators can disable it via ANTHROPIC_PROMPT_CACHING=off.
            if self.config.prompt_caching and converted_tools:
                last = dict(converted_tools[-1])
                last["cache_control"] = {"type": "ephemeral"}
                converted_tools = converted_tools[:-1] + [last]
            payload["tools"] = converted_tools
            if request.tool_choice is not None:
                payload["tool_choice"] = self._convert_tool_choice(request.tool_choice)

        # request.extra is merged before the provider-enforced fields below,
        # not after: extended thinking requires temperature=1, and applying
        # extra afterwards let a caller-supplied temperature (or a stray
        # "thinking" key) silently defeat that requirement.
        # Also strip temperature/top_p/top_k from extra for no-temperature models.
        extra = dict(request.extra)
        if no_temperature:
            extra.pop("temperature", None)
            extra.pop("top_p", None)
            extra.pop("top_k", None)
        payload.update(extra)

        # Legacy extended thinking: only for models that still support it.
        # Newer adaptive-thinking models (Opus 5, Sonnet 5, Fable 5, Opus 4.7/4.8)
        # return HTTP 400 when thinking.type="enabled" is sent.
        if model not in _NO_EXTENDED_THINKING_MODELS:
            thinking = self._thinking_config(request)
            if thinking is not None:
                payload["thinking"] = thinking
                payload["temperature"] = 1  # required for extended thinking

        # output_config.effort: the new per-request thinking-depth control for
        # adaptive-thinking models (Fable 5, Opus 5, Sonnet 5, Opus 4.7/4.8…).
        # Request-level effort takes priority over the provider default.
        effort = request.effort or self.config.default_effort
        if effort and effort in _VALID_EFFORT_LEVELS:
            payload["output_config"] = {"effort": effort}

        return payload

    @classmethod
    def _convert_messages(
        cls, messages: list[dict[str, Any]],
    ) -> tuple[list[str], list[dict[str, Any]]]:
        """Translate OpenAI-shaped messages into Anthropic's system/turn split."""
        system_parts: list[str] = []
        converted: list[dict[str, Any]] = []
        for message in messages:
            role = message.get("role")
            content = message.get("content")

            if role == "system":
                system_parts.append(
                    content if isinstance(content, str) else json.dumps(content)
                )
                continue

            if role == "tool":
                converted.append(cls._convert_tool_result(message))
                continue

            tool_calls = message.get("tool_calls") or []
            if role == "assistant" and tool_calls:
                converted.append(cls._convert_assistant_tool_calls(content, tool_calls))
                continue

            converted.append({
                "role": "assistant" if role == "assistant" else "user",
                "content": content,
            })
        return system_parts, converted

    @staticmethod
    def _convert_tool_result(message: dict[str, Any]) -> dict[str, Any]:
        """OpenAI carries a tool result as role="tool" with a tool_call_id;
        Anthropic needs a tool_result block on a user turn. Without this the
        second turn of any tool conversation arrives missing the block
        Anthropic requires and the request fails.
        """
        content = message.get("content")
        return {
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": str(message.get("tool_call_id") or ""),
                "content": content if isinstance(content, str) else json.dumps(content),
            }],
        }

    @staticmethod
    def _convert_assistant_tool_calls(
        content: Any, tool_calls: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """OpenAI puts a tool call alongside the assistant's text; Anthropic
        needs tool_use blocks in the content array instead.
        """
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
        return {"role": "assistant", "content": blocks}

    def _build_system(self, system_parts: list[str]) -> str | list[dict[str, Any]]:
        system_text = "\n\n".join(system_parts)
        if not self.config.prompt_caching:
            return system_text
        return [{"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}]

    def _thinking_config(self, request: LLMRequest) -> dict[str, Any] | None:
        """Anthropic's extended-thinking constraints on ``budget_tokens``:
        at least 1024, and less than ``max_tokens`` unless the request uses
        tools (interleaved thinking lets the budget span every thinking
        block in the turn, so it may exceed max_tokens there). A budget that
        violates either is dropped instead of sent, since sending it 400s
        every request rather than just the misconfigured ones.
        """
        budget = self.config.thinking_budget
        if budget <= 0:
            return None
        if budget < _MIN_THINKING_BUDGET_TOKENS:
            log.warning(
                "Anthropic thinking_budget=%d is below the %d-token minimum — "
                "disabling extended thinking for this request",
                budget, _MIN_THINKING_BUDGET_TOKENS,
            )
            return None
        if not request.tools and budget >= request.max_tokens:
            log.warning(
                "Anthropic thinking_budget=%d >= max_tokens=%d with no tools — "
                "disabling extended thinking for this request (would 400)",
                budget, request.max_tokens,
            )
            return None
        return {"type": "enabled", "budget_tokens": budget}

    @staticmethod
    def _json_instruction(response_format: dict[str, Any]) -> str | None:
        """Return a system-prompt instruction that enforces JSON output.

        Anthropic's Messages API does not support ``response_format`` in the
        request body; the constraint must travel as part of the system prompt.
        Returns ``None`` for unknown or non-JSON format types so callers can
        skip the append safely.
        """
        fmt_type = response_format.get("type", "")
        _base = (
            "You MUST respond with a single valid JSON object only. "
            "Do not include any text, explanation, or markdown outside the JSON."
        )
        if fmt_type == "json_object":
            return _base
        if fmt_type == "json_schema":
            schema_body = response_format.get("json_schema") or {}
            name = schema_body.get("name", "")
            schema = schema_body.get("schema")
            if schema:
                try:
                    schema_str = json.dumps(schema, indent=2)
                    label = f"'{name}' " if name else ""
                    return (
                        f"You MUST respond with a single valid JSON object matching "
                        f"the {label}schema:\n{schema_str}\n\n{_base}"
                    )
                except (TypeError, ValueError):
                    pass
            return _base
        return None

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
        workspace_id = response.headers.get("anthropic-workspace-id")
        if workspace_id:
            log.debug("anthropic workspace-id: %s", workspace_id)
        return self._parse(response.json(), model=model, latency_ms=latency_ms, workspace_id=workspace_id)

    def _parse(
        self,
        data: dict[str, Any],
        *,
        model: str,
        latency_ms: int,
        workspace_id: str | None = None,
    ) -> LLMResponse:
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
            thinking_tokens=int(raw_usage.get("thinking_tokens") or 0),
        )
        raw = {**data}
        if workspace_id:
            raw["_anthropic_workspace_id"] = workspace_id
        return LLMResponse(
            text="".join(text_parts),
            model=str(data.get("model") or model),
            provider=self.id,
            usage=usage,
            tool_calls=tool_calls,
            finish_reason=data.get("stop_reason"),
            latency_ms=latency_ms,
            cost_usd=self.cost(model, usage),
            raw=raw,
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

        if kind == "message_start":
            # The message_start event carries all input-side usage counts, including
            # prompt cache read/creation tokens. Capture them here so streaming
            # responses get accurate prompt-token accounting (otherwise prompt_tokens
            # stays at 0 for the whole stream).
            message = event.get("message") or {}
            raw_usage = message.get("usage") or {}
            return StreamChunk(
                usage=Usage(
                    prompt_tokens=int(raw_usage.get("input_tokens") or 0),
                    cached_tokens=int(raw_usage.get("cache_read_input_tokens") or 0),
                    cache_creation_tokens=int(raw_usage.get("cache_creation_input_tokens") or 0),
                ),
                provider=self.id,
                model=model,
            )

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
                usage=Usage(
                    completion_tokens=int(raw_usage.get("output_tokens") or 0),
                    thinking_tokens=int(raw_usage.get("thinking_tokens") or 0),
                ),
                provider=self.id,
                model=model,
            )
        return None

    def cost(self, model: str, usage: Usage) -> float:
        """USD cost for one completion, accounting for Anthropic-specific billing.

        Three token categories each have distinct rates:
          - Regular prompt tokens: base input rate
          - Cache creation tokens: 1.25× the base input rate (25% surcharge)
          - Thinking tokens: billed at the output token rate (same as completion tokens)
        Cache read tokens are NOT added here because they're already included in
        ``usage.prompt_tokens`` from the API and are billed at 0.1× input rate —
        using the base rate for them slightly overcounts, but the error is small and
        treating them specially would require a separate rate field in the registry.
        """
        from packages.llm.registry import get_registry

        spec = get_registry().get(model)
        if spec is None:
            return 0.0
        input_per_m = spec.input_cost_per_1m
        output_per_m = spec.output_cost_per_1m
        base = (usage.prompt_tokens * input_per_m + usage.completion_tokens * output_per_m) / 1_000_000.0
        cache_creation_premium = usage.cache_creation_tokens * input_per_m * 0.25 / 1_000_000.0
        thinking_cost = usage.thinking_tokens * output_per_m / 1_000_000.0
        return base + cache_creation_premium + thinking_cost

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
