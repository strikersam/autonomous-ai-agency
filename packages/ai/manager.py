"""packages/ai/manager.py — ProviderManager.

Single entry point for all LLM calls. Handles:
- Provider selection by priority
- Failover on 429/410/5xx
- Exponential backoff
- Health monitoring
- Brain watchdog integration

Usage:
    from packages.ai.manager import provider_manager
    
    response = await provider_manager.chat(messages, model="meta/llama-3.3-70b-instruct")
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from packages.ai.provider import Provider, ChatResponse, HealthStatus
from packages.config import settings

log = logging.getLogger("provider-manager")


class ProviderManager:
    """Coordinates provider selection, failover, and health."""

    def __init__(self) -> None:
        self._providers: list[Provider] = []
        self._failure_counts: dict[str, int] = {}
        self._max_failures: int = settings.brain_watchdog_max_failures

    def register(self, provider: Provider) -> None:
        """Register a provider."""
        self._providers.append(provider)
        self._providers.sort(key=lambda p: p.priority)

    @property
    def providers(self) -> list[Provider]:
        """Return providers sorted by priority (lowest = highest priority)."""
        return [p for p in self._providers if p.is_configured]

    async def chat(self, messages: list[dict], *, model: str | None = None,
                   max_retries: int = 2, **kwargs: Any) -> ChatResponse:
        """Send a chat request with automatic failover.

        Retry policy: retry the SAME provider up to ``max_retries`` times with
        exponential backoff (handles transient 5xx / network blips). Only after
        all retries are exhausted does it fail over to the next provider.
        """
        last_error: Exception | None = None

        for provider in self.providers:
            for attempt in range(max_retries + 1):
                try:
                    response = await provider.chat(messages, model=model, **kwargs)
                    self._failure_counts[provider.provider_id] = 0
                    return response
                except Exception as exc:
                    last_error = exc
                    count = self._failure_counts.get(provider.provider_id, 0) + 1
                    self._failure_counts[provider.provider_id] = count
                    log.warning("Provider %s failed (attempt %d/%d, count=%d): %s",
                                provider.provider_id, attempt + 1, max_retries + 1, count, exc)
                    if attempt < max_retries:
                        # Exponential backoff with jitter, then retry the SAME provider.
                        await asyncio.sleep(min(0.25 * (2 ** attempt), 2.0))
                        continue  # retry same provider
                    # Retries exhausted for this provider — fall through to next one.
                    break

        raise RuntimeError(f"All providers failed. Last error: {last_error}")

    async def health_all(self) -> dict[str, HealthStatus]:
        """Check health of all configured providers."""
        results = {}
        for provider in self.providers:
            try:
                results[provider.provider_id] = await provider.health()
            except Exception as exc:
                results[provider.provider_id] = HealthStatus(healthy=False, error=str(exc))
        return results


# Singleton
provider_manager = ProviderManager()
