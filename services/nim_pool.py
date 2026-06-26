from __future__ import annotations

"""NIM API Connection Pooling + Circuit Breaker (B5 roadmap item).

Optimised NVIDIA NIM API integration with persistent httpx.AsyncClient pool,
state-machine circuit breaker per provider, exponential backoff with jitter,
and connection health monitoring.

Replaces ad-hoc per-request httpx.AsyncClient creation with a managed pool
that reuses connections, enforces timeouts, and handles transient failures
with intelligent retry logic.

Usage::

    pool = get_nim_pool()

    # Make a request through the managed pool
    async with pool.session() as session:
        resp = await session.post(url, json=payload)

    # Or with automatic retry
    result = await pool.request_with_retry(
        method="POST",
        url="https://integrate.api.nvidia.com/v1/chat/completions",
        json=payload,
    )
"""

import asyncio
import logging
import os
import random
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator

import httpx

log = logging.getLogger("qwen-proxy")

# ── Configuration ──────────────────────────────────────────────────────────────

_POOL_SIZE = int(os.environ.get("NIM_POOL_SIZE", "20"))
_POOL_MAX_KEEPALIVE = int(os.environ.get("NIM_POOL_MAX_KEEPALIVE", "30"))
_REQUEST_TIMEOUT = float(os.environ.get("NIM_REQUEST_TIMEOUT", "60.0"))
_CONNECT_TIMEOUT = float(os.environ.get("NIM_CONNECT_TIMEOUT", "10.0"))

# Circuit breaker
_CB_FAILURE_THRESHOLD = int(os.environ.get("NIM_CB_FAILURE_THRESHOLD", "5"))
_CB_RECOVERY_TIMEOUT = float(os.environ.get("NIM_CB_RECOVERY_SEC", "30.0"))
_CB_HALF_OPEN_LIMIT = int(os.environ.get("NIM_CB_HALF_OPEN_LIMIT", "3"))

# Retry with backoff
_MAX_RETRIES = int(os.environ.get("NIM_MAX_RETRIES", "3"))
_BACKOFF_BASE = float(os.environ.get("NIM_BACKOFF_BASE", "1.0"))
_BACKOFF_MAX = float(os.environ.get("NIM_BACKOFF_MAX", "30.0"))


class CircuitState(Enum):
    CLOSED = "closed"          # Normal operation
    OPEN = "open"              # Failing, no requests allowed
    HALF_OPEN = "half_open"    # Testing recovery


@dataclass
class ProviderCircuit:
    """Per-provider circuit breaker state machine."""

    provider: str
    state: CircuitState = CircuitState.CLOSED
    failures: int = 0
    successes: int = 0
    last_failure: float = 0.0
    opened_at: float = 0.0
    half_open_attempts: int = 0
    total_requests: int = 0
    total_failures: int = 0
    total_successes: int = 0

    def record_success(self) -> None:
        self.total_requests += 1
        self.total_successes += 1
        if self.state == CircuitState.HALF_OPEN:
            self.successes += 1
            if self.successes >= _CB_HALF_OPEN_LIMIT:
                self.state = CircuitState.CLOSED
                self.failures = 0
                self.half_open_attempts = 0
                log.info("Circuit CLOSED for provider %s (recovered)", self.provider)
        else:
            self.failures = 0

    def record_failure(self) -> None:
        self.total_requests += 1
        self.total_failures += 1
        self.failures += 1
        self.last_failure = time.monotonic()
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_attempts += 1
            if self.half_open_attempts >= _CB_HALF_OPEN_LIMIT:
                self.state = CircuitState.OPEN
                self.opened_at = time.monotonic()
                log.warning("Circuit OPEN for provider %s (half-open failures exhausted)", self.provider)
        elif self.failures >= _CB_FAILURE_THRESHOLD:
            self.state = CircuitState.OPEN
            self.opened_at = time.monotonic()
            log.warning("Circuit OPEN for provider %s after %d failures", self.provider, self.failures)

    def try_half_open(self) -> bool:
        """Attempt to move from OPEN to HALF_OPEN after recovery timeout."""
        if self.state != CircuitState.OPEN:
            return False
        if time.monotonic() - self.opened_at >= _CB_RECOVERY_TIMEOUT:
            self.state = CircuitState.HALF_OPEN
            self.successes = 0
            self.half_open_attempts = 0
            log.info("Circuit HALF_OPEN for provider %s (attempting recovery)", self.provider)
            return True
        return False

    def can_request(self) -> bool:
        """Check if a request can be made through this circuit."""
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            return self.try_half_open()
        return True  # HALF_OPEN

    def stats(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "state": self.state.value,
            "failures": self.failures,
            "total_requests": self.total_requests,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "success_rate": round(self.total_successes / max(1, self.total_requests) * 100, 1),
        }


class NIMConnectionPool:
    """Persistent httpx.AsyncClient pool with circuit breaker and retry logic.

    Manages a shared httpx.AsyncClient with connection pooling, per-provider
    circuit breakers, and exponential backoff with jitter for retries.

    Usage::

        pool = NIMConnectionPool()
        result = await pool.request(
            method="POST",
            url="https://integrate.api.nvidia.com/v1/chat/completions",
            json={"model": "nvidia/llama-3.3-nemotron-super-49b-v1.5", "messages": [...]},
            provider="nvidia",
        )
    """

    def __init__(
        self,
        *,
        pool_size: int = _POOL_SIZE,
        max_keepalive: int = _POOL_MAX_KEEPALIVE,
        request_timeout: float = _REQUEST_TIMEOUT,
        connect_timeout: float = _CONNECT_TIMEOUT,
    ) -> None:
        self._client: httpx.AsyncClient | None = None
        self._pool_size = pool_size
        self._max_keepalive = max_keepalive
        self._request_timeout = request_timeout
        self._connect_timeout = connect_timeout
        self._circuits: dict[str, ProviderCircuit] = {}
        self._lock = asyncio.Lock()
        self._request_count = 0

    # ── Session management ──────────────────────────────────────────────────

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the shared httpx.AsyncClient."""
        if self._client is None:
            limits = httpx.Limits(
                max_connections=self._pool_size,
                max_keepalive_connections=self._max_keepalive,
            )
            timeout = httpx.Timeout(self._request_timeout, connect=self._connect_timeout)
            self._client = httpx.AsyncClient(limits=limits, timeout=timeout)
        return self._client

    @asynccontextmanager
    async def session(self) -> AsyncIterator[httpx.AsyncClient]:
        """Context manager for a pooled client session."""
        client = await self._get_client()
        try:
            yield client
        finally:
            pass  # Keep client alive for reuse

    async def close(self) -> None:
        """Close the connection pool."""
        if self._client:
            await self._client.aclose()
            self._client = None

    # ── Request with circuit breaker and retry ──────────────────────────────

    async def request(
        self,
        *,
        method: str,
        url: str,
        provider: str = "nvidia",
        max_retries: int = _MAX_RETRIES,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an HTTP request through the pool with circuit breaker protection.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            provider: Provider name for circuit breaker tracking
            max_retries: Maximum retry attempts (excluding circuit breaker)
            **kwargs: Passed to httpx.AsyncClient.request()

        Returns:
            httpx.Response object

        Raises:
            CircuitBreakerOpenError: If the provider circuit is open
            httpx.HTTPError: On request failure after all retries
        """
        circuit = self._get_circuit(provider)

        if not circuit.can_request():
            raise CircuitBreakerOpenError(
                f"Circuit breaker is OPEN for provider '{provider}'. "
                f"Recovery in ~{_CB_RECOVERY_TIMEOUT:.0f}s"
            )

        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                async with self.session() as client:
                    self._request_count += 1
                    resp = await client.request(method, url, **kwargs)

                if resp.status_code < 500:
                    circuit.record_success()
                    return resp

                # 5xx: treat as transient failure
                last_exc = httpx.HTTPStatusError(
                    f"Upstream {resp.status_code}",
                    request=resp.request,
                    response=resp,
                )
                circuit.record_failure()

            except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as exc:
                last_exc = exc
                circuit.record_failure()

            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code >= 500:
                    circuit.record_failure()
                else:
                    circuit.record_success()
                    raise

            # Don't retry if circuit just opened
            if not circuit.can_request():
                raise CircuitBreakerOpenError(
                    f"Circuit breaker OPEN for provider '{provider}'"
                ) from last_exc

            if attempt < max_retries:
                delay = self._backoff_delay(attempt)
                log.debug("Retry %d/%d for %s in %.1fs", attempt + 1, max_retries, provider, delay)
                await asyncio.sleep(delay)

        raise last_exc or RuntimeError(f"Request failed for provider '{provider}'")

    async def request_with_retry(
        self,
        *,
        method: str = "POST",
        url: str = "",
        provider: str = "nvidia",
        **kwargs: Any,
    ) -> httpx.Response:
        """Convenience wrapper: request with automatic retry."""
        return await self.request(method=method, url=url, provider=provider, **kwargs)

    # ── Circuit breaker management ──────────────────────────────────────────

    def _get_circuit(self, provider: str) -> ProviderCircuit:
        """Get or create a circuit breaker for a provider."""
        if provider not in self._circuits:
            self._circuits[provider] = ProviderCircuit(provider=provider)
        return self._circuits[provider]

    def circuit_stats(self, provider: str | None = None) -> dict[str, Any] | list[dict[str, Any]]:
        """Return circuit breaker statistics."""
        if provider:
            circuit = self._circuits.get(provider)
            return circuit.stats() if circuit else {}
        return [c.stats() for c in self._circuits.values()]

    def reset_circuit(self, provider: str) -> None:
        """Manually reset a provider's circuit breaker to CLOSED."""
        if provider in self._circuits:
            circuit = self._circuits[provider]
            circuit.state = CircuitState.CLOSED
            circuit.failures = 0
            circuit.successes = 0
            circuit.half_open_attempts = 0
            log.info("Circuit manually reset for provider %s", provider)

    # ── Health ──────────────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return pool statistics."""
        return {
            "pool_size": self._pool_size,
            "request_count": self._request_count,
            "circuits": len(self._circuits),
            "circuit_details": [c.stats() for c in self._circuits.values()],
        }

    @staticmethod
    def _backoff_delay(attempt: int) -> float:
        """Compute exponential backoff delay with jitter."""
        delay = min(_BACKOFF_MAX, _BACKOFF_BASE * (2 ** attempt))
        jitter = random.uniform(0, delay * 0.5)  # nosec B311 — jitter only, not for security
        return delay + jitter


class CircuitBreakerOpenError(RuntimeError):
    """Raised when a request is blocked by an open circuit breaker."""


# ── Module-level singleton ─────────────────────────────────────────────────────

_nim_pool: NIMConnectionPool | None = None


def get_nim_pool() -> NIMConnectionPool:
    """Return the module-level NIMConnectionPool singleton."""
    global _nim_pool
    if _nim_pool is None:
        _nim_pool = NIMConnectionPool()
    return _nim_pool