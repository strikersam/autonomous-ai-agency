"""packages/ai/provider.py — Provider abstraction interface.

Every LLM provider implements this interface. The ProviderManager
(packages/ai/registry.py) uses these implementations to route calls,
handle failover, and manage health.

This is the target interface — existing providers in provider_router.py
will be migrated to implement this contract one at a time.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


@dataclass
class ChatResponse:
    """Standard response from a provider chat call."""
    text: str
    model: str
    provider: str
    usage: dict[str, int] = field(default_factory=dict)
    raw: Any = None


@dataclass
class HealthStatus:
    """Provider health check result."""
    healthy: bool
    latency_ms: float | None = None
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class RateLimit:
    """Provider rate limit info."""
    requests_per_minute: int | None = None
    tokens_per_minute: int | None = None
    concurrent_requests: int | None = None


class Provider(ABC):
    """Base interface every provider must implement.
    
    Implementations live in packages/ai/adapters/ (e.g. nvidia.py, cerebras.py).
    The ProviderManager routes calls to the appropriate adapter.
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique identifier (e.g. 'nvidia', 'cerebras')."""
        ...

    @property
    @abstractmethod
    def priority(self) -> int:
        """Lower = higher priority in the fallback chain."""
        ...

    @abstractmethod
    async def chat(self, messages: list[dict[str, str]], *, model: str | None = None,
                   temperature: float = 0.3, max_tokens: int = 4096,
                   **kwargs: Any) -> ChatResponse:
        """Send a chat completion request."""
        ...

    @abstractmethod
    async def stream(self, messages: list[dict[str, str]], *, model: str | None = None,
                     temperature: float = 0.3, max_tokens: int = 4096,
                     **kwargs: Any) -> AsyncIterator[str]:
        """Stream a chat completion response."""
        ...

    @abstractmethod
    async def health(self) -> HealthStatus:
        """Check provider health."""
        ...

    @abstractmethod
    def cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost in USD for the given token counts."""
        ...

    @abstractmethod
    def limits(self) -> RateLimit:
        """Return the provider's rate limits."""
        ...

    @property
    def is_configured(self) -> bool:
        """True when the provider has the required API key set."""
        return True  # Override in subclasses
