"""packages/llm — the multi-provider LLM routing layer.

Every LLM call in this platform goes through :class:`~packages.llm.router.LLMRouter`.
Agents never talk to OpenAI, Anthropic, Gemini, Ollama, or anything else
directly; the router owns provider selection, retries, failover, key rotation,
caching, queueing, context management, budgets, and observability.

    from packages.llm import LLMRequest, get_router

    response = await get_router().chat(LLMRequest(
        messages=[{"role": "user", "content": "hello"}],
        agent="planner",
    ))

See ``docs/adr/008-llm-router-multi-provider.md`` for the design rationale and
``docs/llm-router/`` for the operator guides.
"""
from __future__ import annotations

from packages.llm.config import (
    LLMConfig,
    ModelConfig,
    ProviderConfig,
    get_config,
    reload_config,
    router_enabled,
)
from packages.llm.router import LLMRouter, get_router
from packages.llm.types import (
    Attempt,
    BudgetExceeded,
    LLMError,
    LLMRequest,
    LLMResponse,
    PermanentError,
    Priority,
    QueueFull,
    RouterExhausted,
    StreamChunk,
    ToolCall,
    TransientError,
    Usage,
)

__all__ = [
    "Attempt",
    "BudgetExceeded",
    "LLMConfig",
    "LLMError",
    "LLMRequest",
    "LLMResponse",
    "LLMRouter",
    "ModelConfig",
    "PermanentError",
    "Priority",
    "ProviderConfig",
    "QueueFull",
    "RouterExhausted",
    "StreamChunk",
    "ToolCall",
    "TransientError",
    "Usage",
    "get_config",
    "get_router",
    "reload_config",
    "router_enabled",
]
