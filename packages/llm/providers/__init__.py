"""packages/llm/providers — adapter factory.

Four adapter kinds cover every supported endpoint:

    openai      any OpenAI-compatible REST API — OpenAI, Groq, Cerebras,
                NVIDIA NIM, OpenRouter, Together, Fireworks, DeepInfra,
                Mistral, Azure, LM Studio, vLLM, LiteLLM, LocalAI, and the
                long tail of self-hosted servers
    anthropic   the Messages API
    gemini      Google generateContent
    ollama      the native local daemon API

Aliases exist so ``providers.yaml`` can say ``kind: lmstudio`` for
readability while still using the generic adapter.
"""
from __future__ import annotations

import logging

from packages.llm.config import ProviderConfig
from packages.llm.providers.anthropic import AnthropicProvider
from packages.llm.providers.base import (
    LLMProvider,
    OpenAICompatible,
    classify_error,
    retry_after_seconds,
)
from packages.llm.providers.gemini import GeminiProvider
from packages.llm.providers.ollama import OllamaProvider

log = logging.getLogger("llm.providers")

_ADAPTERS: dict[str, type[LLMProvider]] = {
    "openai": OpenAICompatible,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
    "google": GeminiProvider,
    "ollama": OllamaProvider,
}

# Readability aliases — all OpenAI-compatible under the hood.
_ALIASES = {
    "openai-compatible": "openai",
    "openai_compat": "openai",
    "openai_compatible": "openai",
    "azure": "openai",
    "azure-openai": "openai",
    "groq": "openai",
    "cerebras": "openai",
    "nvidia": "openai",
    "nim": "openai",
    "openrouter": "openai",
    "together": "openai",
    "fireworks": "openai",
    "deepinfra": "openai",
    "mistral": "openai",
    "lmstudio": "openai",
    "lm-studio": "openai",
    "vllm": "openai",
    "localai": "openai",
    "litellm": "openai",
    "claude": "anthropic",
}


def resolve_kind(kind: str) -> str:
    """Normalise a configured ``kind`` to an adapter key."""
    normalised = (kind or "openai").strip().lower()
    return _ALIASES.get(normalised, normalised)


def build_provider(config: ProviderConfig) -> LLMProvider:
    """Instantiate the adapter for one provider config.

    Unknown kinds fall back to the OpenAI-compatible adapter with a warning
    rather than failing startup — a typo in YAML should degrade one provider,
    not take the platform down.
    """
    kind = resolve_kind(config.kind)
    adapter = _ADAPTERS.get(kind)
    if adapter is None:
        log.warning(
            "llm.providers: unknown kind %r for provider %r — using the "
            "OpenAI-compatible adapter",
            config.kind, config.id,
        )
        adapter = OpenAICompatible
    return adapter(config)


def register_adapter(kind: str, adapter: type[LLMProvider]) -> None:
    """Register a custom adapter kind (extension point for plugins)."""
    _ADAPTERS[kind.strip().lower()] = adapter


__all__ = [
    "LLMProvider",
    "OpenAICompatible",
    "AnthropicProvider",
    "GeminiProvider",
    "OllamaProvider",
    "build_provider",
    "register_adapter",
    "resolve_kind",
    "classify_error",
    "retry_after_seconds",
]
