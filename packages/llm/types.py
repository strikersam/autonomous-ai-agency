"""packages/llm/types.py — the wire types every caller and provider shares.

One request shape, one response shape, one stream chunk shape. Providers
translate to and from their vendor formats; nothing above this layer ever
sees a vendor-specific dict.

Tool calls and structured outputs travel through untouched: ``tools``,
``tool_choice``, and ``response_format`` are passed to the provider verbatim
and returned in :class:`LLMResponse.tool_calls` without reinterpretation.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Priority(int, Enum):
    """Queue priority. Lower value = served first."""

    CRITICAL = 0     # interactive user chat
    HIGH = 10        # agent plan/execute steps
    NORMAL = 20      # default
    LOW = 30         # background loops, digests
    BULK = 40        # batch backfills


@dataclass
class ToolCall:
    """A single tool/function call emitted by a model."""

    id: str
    name: str
    arguments: str = ""          # raw JSON string, never re-serialised
    index: int = 0


@dataclass
class Usage:
    """Token accounting for one completion."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    cache_creation_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def as_dict(self) -> dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cached_tokens": self.cached_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class LLMRequest:
    """A provider-neutral chat request.

    ``model`` is a *hint*: the router may substitute an equivalent model on a
    different provider when the requested one is unavailable. Set
    ``pin_model=True`` to forbid substitution.
    """

    messages: list[dict[str, Any]]
    model: str | None = None
    temperature: float = 0.3
    max_tokens: int = 4096
    stream: bool = False

    # Capability requirements — used to filter the candidate set.
    tools: list[dict[str, Any]] | None = None
    tool_choice: Any = None
    response_format: dict[str, Any] | None = None

    # Routing controls.
    agent: str | None = None                 # per-agent policy lookup key
    workflow: str | None = None              # cost attribution bucket
    strategy: str | None = None              # override routing.yaml default
    priority: Priority = Priority.NORMAL
    pin_model: bool = False
    allow_paid: bool | None = None           # None = inherit policy
    providers: list[str] | None = None       # explicit allow-list
    exclude_providers: list[str] = field(default_factory=list)

    # Behaviour toggles.
    cacheable: bool = True
    timeout_sec: float = 120.0
    max_attempts: int | None = None          # None = routing.yaml default
    conversation_id: str | None = None       # enables context management
    extra: dict[str, Any] = field(default_factory=dict)

    def requires_tools(self) -> bool:
        return bool(self.tools)

    def requires_json(self) -> bool:
        fmt = (self.response_format or {}).get("type", "")
        return fmt in {"json_object", "json_schema"}

    def requires_vision(self) -> bool:
        for message in self.messages:
            content = message.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") in {
                        "image_url", "image", "input_image",
                    }:
                        return True
        return False

    def approx_prompt_tokens(self) -> int:
        """Cheap character-based token estimate (~4 chars/token).

        Deliberately dependency-free: a tokenizer per provider family would
        pull in three packages to refine a number only used for candidate
        filtering and budget pre-checks.
        """
        chars = 0
        for message in self.messages:
            content = message.get("content")
            if isinstance(content, str):
                chars += len(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        chars += len(str(part.get("text") or ""))
            chars += 8  # role + framing overhead
        if self.tools:
            chars += len(str(self.tools))
        return max(1, chars // 4)


@dataclass
class Attempt:
    """One provider/model/key attempt, successful or not."""

    provider: str
    model: str
    key_index: int = 0
    ok: bool = False
    status: int | None = None
    error: str | None = None
    latency_ms: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "key_index": self.key_index,
            "ok": self.ok,
            "status": self.status,
            "error": self.error,
            "latency_ms": self.latency_ms,
        }


@dataclass
class LLMResponse:
    """A completed chat response plus the routing audit trail."""

    text: str
    model: str
    provider: str
    usage: Usage = field(default_factory=Usage)
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None
    latency_ms: int = 0
    cost_usd: float = 0.0
    cached: bool = False
    attempts: list[Attempt] = field(default_factory=list)
    raw: Any = None
    created_at: float = field(default_factory=time.time)

    @property
    def fallback_count(self) -> int:
        """How many attempts failed before this one succeeded."""
        return max(0, len(self.attempts) - 1)

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "model": self.model,
            "provider": self.provider,
            "usage": self.usage.as_dict(),
            "tool_calls": [
                {"id": t.id, "name": t.name, "arguments": t.arguments}
                for t in self.tool_calls
            ],
            "finish_reason": self.finish_reason,
            "latency_ms": self.latency_ms,
            "cost_usd": self.cost_usd,
            "cached": self.cached,
            "attempts": [a.as_dict() for a in self.attempts],
        }


@dataclass
class StreamChunk:
    """One delta in a streaming response.

    Every provider's stream is normalised to this shape, so a caller can
    consume Anthropic SSE, Gemini's JSON stream, and Ollama's NDJSON with the
    same loop.
    """

    text: str = ""
    # A list, not a single call: models emit parallel tool calls in one delta,
    # and a scalar field forced every adapter to truncate all but the first.
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None
    usage: Usage | None = None
    provider: str = ""
    model: str = ""

    @property
    def done(self) -> bool:
        return self.finish_reason is not None

    @property
    def tool_call(self) -> ToolCall | None:
        """The first tool call, for callers that only ever expect one."""
        return self.tool_calls[0] if self.tool_calls else None


# ── Errors ───────────────────────────────────────────────────────────────────

class LLMError(RuntimeError):
    """Base class for every router-raised error."""


class PermanentError(LLMError):
    """The request will never succeed as written — do not retry.

    Auth failures, malformed requests, content-policy refusals, and unknown
    model names on a pinned model all land here.
    """

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class TransientError(LLMError):
    """A retryable failure (429, 5xx, timeout, connection reset)."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        retry_after: float | None = None,
        scope: str = "provider",
    ) -> None:
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after
        # "key" | "model" | "provider" — the narrowest scope that explains it.
        self.scope = scope


class RouterExhausted(LLMError):
    """Every candidate provider, model, and key was tried and failed."""

    def __init__(self, attempts: list[Attempt], reason: str = "") -> None:
        tried = ", ".join(f"{a.provider}/{a.model}" for a in attempts) or "none"
        super().__init__(
            f"All LLM candidates exhausted ({reason or 'no candidate succeeded'}). "
            f"Tried: {tried}"
        )
        self.attempts = attempts
        self.reason = reason


class BudgetExceeded(LLMError):
    """A configured spend or token budget would be breached by this request."""


class QueueFull(LLMError):
    """Backpressure: the request queue is at capacity."""
