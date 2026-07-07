"""services/brain_failover.py — Universal multi-provider brain failover system.

Solves the recurring NVIDIA 429/410 rate-limit problem by treating EVERY
configured provider as a potential brain. When the active provider returns
429 (rate-limited), 410 (gone), or 5xx (server error), this module marks
it as unhealthy with a cooldown period and returns the next healthy
provider in priority order.

Design:
  * **Provider registry**: every provider with an API key in env is a
    candidate brain. The registry is built at call time (not import time)
    so env vars set after boot are honoured.
  * **Circuit breaker**: each provider has a health state — CLOSED
    (healthy), OPEN (rate-limited, in cooldown), HALF_OPEN (cooldown
    expired, next call is a probe). Cooldown is provider-specific
    (NVIDIA gets 60s, others 30s) and doubles on consecutive failures.
  * **Intelligent ordering**: free providers are tried first (nvidia,
    groq, cerebras, zhipu, deepseek, together, dashscope, moonshot),
    then paid (anthropic, openrouter, minimax, google), then local
    (ollama). Within each tier, the provider with the best recent
    latency wins.
  * **Model mapping**: each provider has a default model + a set of
    aliases so the agent's requested model is mapped to the provider's
    equivalent (e.g. "meta/llama-3.3-70b-instruct" on nvidia →
    "llama-3.3-70b-versatile" on groq).
  * **Observability**: /api/brain/failover/status returns the full health
    snapshot for debugging.

Usage in agent/loop.py::

    from services.brain_failover import get_failover_manager

    fm = get_failover_manager()
    for attempt in range(fm.max_attempts()):
        provider = fm.next_provider(exclude=tried)
        if provider is None:
            raise RuntimeError("No healthy brain provider")
        resp = await call_provider(provider, ...)
        if resp.status_code == 429:
            fm.record_failure(provider.id, "rate_limited")
            continue
        if resp.status_code == 410:
            fm.record_failure(provider.id, "gone")
            continue
        if resp.status_code >= 500:
            fm.record_failure(provider.id, "server_error")
            continue
        fm.record_success(provider.id)
        return resp.json()
"""
from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("qwen-proxy")


# ── Provider definitions ─────────────────────────────────────────────────


class ProviderHealth(Enum):
    """Circuit-breaker state for a provider."""
    CLOSED = "closed"      # healthy — accepting traffic
    OPEN = "open"          # rate-limited/erroring — in cooldown
    HALF_OPEN = "half_open"  # cooldown expired — next call is a probe


@dataclass
class ProviderInfo:
    """A configured LLM provider with its connection details + health state."""
    id: str
    name: str
    tier: str  # "free" | "paid" | "local"
    base_url: str
    api_key: str
    default_model: str
    # Models this provider serves. The failover layer maps the requested
    # model to the closest match on this provider.
    models: list[str] = field(default_factory=list)
    # Health state
    health: ProviderHealth = ProviderHealth.CLOSED
    failure_count: int = 0
    last_failure: float = 0.0
    last_success: float = 0.0
    cooldown_until: float = 0.0
    cooldown_seconds: float = 60.0
    # Latency tracking (exponential moving average)
    avg_latency_ms: float = 0.0
    total_calls: int = 0
    total_failures: int = 0
    last_error: str = ""

    @property
    def is_healthy(self) -> bool:
        """True when the provider can accept traffic right now."""
        if self.health == ProviderHealth.CLOSED:
            return True
        if self.health == ProviderHealth.OPEN:
            if time.time() >= self.cooldown_until:
                # Cooldown expired — transition to HALF_OPEN on next call
                self.health = ProviderHealth.HALF_OPEN
                return True
            return False
        if self.health == ProviderHealth.HALF_OPEN:
            return True  # allow one probe call
        return True


# ── Provider registry ────────────────────────────────────────────────────

# All providers we know how to route to. Each entry maps the provider id to
# its env-var name, base URL, default model, and tier.
_PROVIDER_REGISTRY: list[dict[str, Any]] = [
    # ── Free tier (tried first) ──
    {
        "id": "nvidia",
        "name": "NVIDIA NIM",
        "tier": "free",
        "key_env": "NVIDIA_API_KEY",
        "base_url_env": "NVIDIA_BASE_URL",
        "default_base_url": "https://integrate.api.nvidia.com",
        "default_model": "meta/llama-3.3-70b-instruct",
        "models": [
            "meta/llama-3.3-70b-instruct",
            "z-ai/glm-5.2",
            "z-ai/glm-5.1",
            "nvidia/llama-3.1-nemotron-70b-instruct",
            "meta/llama-3.1-8b-instruct",
            "deepseek-ai/deepseek-r1",
        ],
        "cooldown": 90.0,  # NVIDIA rate limits are ~40 req/min — 90s cooldown
    },
    {
        "id": "groq",
        "name": "Groq",
        "tier": "free",
        "key_env": "GROQ_API_KEY",
        "base_url_env": "GROQ_BASE_URL",
        "default_base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "models": [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "deepseek-r1-distill-llama-70b",
            "mixtral-8x7b-32768",
        ],
        "cooldown": 30.0,
    },
    {
        "id": "cerebras",
        "name": "Cerebras",
        "tier": "free",
        "key_env": "CEREBRAS_API_KEY",
        "base_url_env": "CEREBRAS_BASE_URL",
        "default_base_url": "https://api.cerebras.ai",
        "default_model": "llama-3.3-70b",
        "models": ["llama-3.3-70b", "llama-3.1-8b", "qwen-3-coder-480b"],
        "cooldown": 30.0,
    },
    {
        "id": "zhipu",
        "name": "ZhipuAI (GLM)",
        "tier": "free",
        "key_env": "ZHIPU_API_KEY",
        "base_url_env": "ZHIPU_BASE_URL",
        "default_base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
        "models": ["glm-4-flash", "glm-4", "glm-4-air", "glm-5.2", "glm-5.1"],
        "cooldown": 30.0,
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "tier": "free",
        "key_env": "DEEPSEEK_API_KEY",
        "base_url_env": "DEEPSEEK_BASE_URL",
        "default_base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "models": ["deepseek-chat", "deepseek-reasoner", "deepseek-coder"],
        "cooldown": 30.0,
    },
    {
        "id": "together",
        "name": "Together AI",
        "tier": "free",
        "key_env": "TOGETHER_API_KEY",
        "base_url_env": "TOGETHER_BASE_URL",
        "default_base_url": "https://api.together.xyz/v1",
        "default_model": "Llama-3.3-70B-Instruct-Turbo-Free",
        "models": ["Llama-3.3-70B-Instruct-Turbo-Free", "Mixtral-8x7B-Instruct-v0.1-Free"],
        "cooldown": 30.0,
    },
    {
        "id": "dashscope",
        "name": "Qwen DashScope",
        "tier": "free",
        "key_env": "DASHSCOPE_API_KEY",
        "base_url_env": "DASHSCOPE_BASE_URL",
        "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "models": ["qwen-plus", "qwen-max", "qwen-turbo", "qwen-coder-plus"],
        "cooldown": 30.0,
    },
    {
        "id": "moonshot",
        "name": "Moonshot (Kimi)",
        "tier": "free",
        "key_env": "MOONSHOT_API_KEY",
        "base_url_env": "MOONSHOT_BASE_URL",
        "default_base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        "cooldown": 30.0,
    },
    {
        "id": "zai",
        "name": "Z.ai (GLM international)",
        "tier": "free",
        "key_env": "ZAI_API_KEY",
        "base_url_env": "ZAI_BASE_URL",
        "default_base_url": "https://api.z.ai/api/paas/v4",
        "default_model": "glm-5.2",
        "models": ["glm-5.2", "glm-5.1", "glm-4-flash", "glm-4", "glm-4-air"],
        "cooldown": 30.0,
    },
    # ── Paid tier (tried last, only if ALLOW_PAID_BRAIN=true) ──
    {
        "id": "aerolink",
        "name": "Aerolink (Claude gateway)",
        "tier": "paid",
        "key_env": "AEROLINK_API_KEY",
        "base_url_env": "AEROLINK_BASE_URL",
        "default_base_url": "https://capi.aerolink.lat/v1",
        "default_model": "claude-sonnet-4-6",
        "models": [
            "claude-opus-4-8",
            "claude-opus-4-7",
            "claude-opus-4-6",
            "claude-fable-5",
            "claude-sonnet-5",
            "claude-sonnet-4-6",
            "claude-haiku-4-5-20251001",
        ],
        "cooldown": 30.0,
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "tier": "paid",
        "key_env": "OPENROUTER_API_KEY",
        "base_url_env": "OPENROUTER_BASE_URL",
        "default_base_url": "https://openrouter.ai/api/v1",
        "default_model": "meta-llama/llama-3.3-70b-instruct",
        "models": ["meta-llama/llama-3.3-70b-instruct", "anthropic/claude-3.5-sonnet"],
        "cooldown": 30.0,
    },
    {
        "id": "minimax",
        "name": "MiniMax",
        "tier": "paid",
        "key_env": "MINIMAX_API_KEY",
        "base_url_env": "MINIMAX_BASE_URL",
        "default_base_url": "https://api.minimax.chat/v1",
        "default_model": "MiniMax-Text-01",
        "models": ["MiniMax-Text-01", "abab6.5s-chat"],
        "cooldown": 30.0,
    },
    {
        "id": "google",
        "name": "Google Gemini",
        "tier": "paid",
        "key_env": "GOOGLE_API_KEY",
        "base_url_env": "GOOGLE_BASE_URL",
        "default_base_url": "https://generativelanguage.googleapis.com",
        "default_model": "gemini-2.0-flash",
        "models": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
        "cooldown": 30.0,
    },
    {
        "id": "anthropic",
        "name": "Anthropic (Claude)",
        "tier": "paid",
        "key_env": "ANTHROPIC_API_KEY",
        "base_url_env": "ANTHROPIC_BASE_URL",
        "default_base_url": "https://api.anthropic.com",
        "default_model": "claude-3-5-sonnet-20241022",
        "models": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-opus-4-5"],
        "cooldown": 30.0,
    },
    # ── Local (always available if configured) ──
    {
        "id": "ollama",
        "name": "Local Ollama",
        "tier": "local",
        "key_env": None,
        "base_url_env": "OLLAMA_BASE",
        "default_base_url": "http://localhost:11434",
        "default_model": "llama3.3:70b",
        "models": ["llama3.3:70b", "qwen2.5-coder:32b", "deepseek-r1:32b"],
        "cooldown": 10.0,
    },
]

# Model alias mapping — when the requested model isn't on the provider, map
# it to the closest equivalent. This is what makes "I want llama-3.3-70b" work
# across nvidia, groq, cerebras, together, etc.
_MODEL_ALIASES: dict[str, dict[str, str]] = {
    "meta/llama-3.3-70b-instruct": {
        "groq": "llama-3.3-70b-versatile",
        "cerebras": "llama-3.3-70b",
        "together": "Llama-3.3-70B-Instruct-Turbo-Free",
        "openrouter": "meta-llama/llama-3.3-70b-instruct",
        "ollama": "llama3.3:70b",
        "dashscope": "qwen-plus",  # fallback
        "zhipu": "glm-4-flash",  # fallback
    },
    "z-ai/glm-5.2": {
        "zhipu": "glm-5.2",
        "zai": "glm-5.2",
        "nvidia": "z-ai/glm-5.2",
    },
    "z-ai/glm-5.1": {
        "zhipu": "glm-5.1",
        "zai": "glm-5.1",
        "nvidia": "z-ai/glm-5.1",
    },
}


# ── Failover manager ─────────────────────────────────────────────────────


class BrainFailoverManager:
    """Manages multi-provider brain failover with circuit breakers.

    Thread-safe. Singleton via :func:`get_failover_manager`.
    """

    def __init__(self) -> None:
        self._providers: dict[str, ProviderInfo] = {}
        self._lock = threading.RLock()
        self._last_registry_build = 0.0
        # Rebuild the provider registry every 60s so newly-set env vars are picked up.
        self._registry_ttl = 60.0

    def _build_registry(self) -> None:
        """Build the provider registry from env vars.

        Called lazily and every 60s so newly-set keys are picked up without a restart.
        """
        with self._lock:
            now = time.time()
            if now - self._last_registry_build < self._registry_ttl and self._providers:
                return

            old_providers = self._providers
            self._providers = {}

            for spec in _PROVIDER_REGISTRY:
                pid = spec["id"]
                # Get the API key
                key_env = spec["key_env"]
                if key_env:
                    api_key = (os.environ.get(key_env) or "").strip()
                    if not api_key:
                        continue  # provider not configured
                else:
                    api_key = ""  # ollama — no key

                # Get the base URL
                base_url_env = spec["base_url_env"]
                base_url = spec["default_base_url"]
                if base_url_env:
                    env_url = (os.environ.get(base_url_env) or "").strip()
                    if env_url:
                        base_url = env_url.rstrip("/")

                # For ollama, skip if no base URL configured (not reachable on Render free)
                if pid == "ollama" and base_url == "http://localhost:11434":
                    # Still include it as a last-resort — it might work in dev
                    pass

                # Check if paid providers are allowed
                if spec["tier"] == "paid":
                    allow_paid = os.environ.get("ALLOW_PAID_BRAIN", "false").strip().lower() in ("true", "1", "yes", "on")
                    if not allow_paid:
                        continue

                # Preserve health state from the old registry
                # Honor NVIDIA_DEFAULT_MODEL env var (set by the free-brain guard
                # and operator config) so the failover uses the same model the
                # rest of the system expects.
                default_model = spec["default_model"]
                if pid == "nvidia":
                    env_model = (os.environ.get("NVIDIA_DEFAULT_MODEL") or "").strip()
                    if env_model:
                        default_model = env_model

                old = old_providers.get(pid)
                if old:
                    info = ProviderInfo(
                        id=pid,
                        name=spec["name"],
                        tier=spec["tier"],
                        base_url=base_url,
                        api_key=api_key,
                        default_model=default_model,
                        models=spec["models"] + ([default_model] if default_model not in spec["models"] else []),
                        cooldown_seconds=spec["cooldown"],
                        health=old.health,
                        failure_count=old.failure_count,
                        last_failure=old.last_failure,
                        last_success=old.last_success,
                        cooldown_until=old.cooldown_until,
                        avg_latency_ms=old.avg_latency_ms,
                        total_calls=old.total_calls,
                        total_failures=old.total_failures,
                        last_error=old.last_error,
                    )
                else:
                    info = ProviderInfo(
                        id=pid,
                        name=spec["name"],
                        tier=spec["tier"],
                        base_url=base_url,
                        api_key=api_key,
                        default_model=default_model,
                        models=spec["models"] + ([default_model] if default_model not in spec["models"] else []),
                        cooldown_seconds=spec["cooldown"],
                    )
                self._providers[pid] = info

            self._last_registry_build = now
            log.debug("brain_failover: registry built — %d providers: %s",
                      len(self._providers), list(self._providers.keys()))

    def get_providers(self) -> list[ProviderInfo]:
        """Return all configured providers (health snapshot)."""
        self._build_registry()
        with self._lock:
            return list(self._providers.values())

    def get_provider(self, provider_id: str) -> ProviderInfo | None:
        """Return a specific provider by id."""
        self._build_registry()
        with self._lock:
            return self._providers.get(provider_id)

    def next_provider(
        self,
        *,
        exclude: set[str] | None = None,
        requested_model: str | None = None,
    ) -> ProviderInfo | None:
        """Return the next healthy provider, excluding any in the exclude set.

        Ordering:
          1. Free providers (by avg latency, best first)
          2. Local providers (ollama)
          3. Paid providers (by avg latency)

        When ``requested_model`` is given, providers that have a model alias
        for it are preferred.
        """
        self._build_registry()
        exclude = exclude or set()

        with self._lock:
            healthy = [
                p for p in self._providers.values()
                if p.id not in exclude and p.is_healthy
            ]

        if not healthy:
            return None

        # Prefer providers that can serve the requested model
        if requested_model:
            model_lower = requested_model.lower()
            has_model = [
                p for p in healthy
                if any(model_lower in m.lower() for m in p.models)
                or requested_model in _MODEL_ALIASES and p.id in _MODEL_ALIASES[requested_model]
            ]
            if has_model:
                healthy = has_model

        # Sort by tier (free first, then local, then paid) then by avg latency
        tier_order = {"free": 0, "local": 1, "paid": 2}
        healthy.sort(key=lambda p: (tier_order.get(p.tier, 3), p.avg_latency_ms))

        return healthy[0] if healthy else None

    def record_success(self, provider_id: str, latency_ms: float = 0.0) -> None:
        """Record a successful call — resets the circuit breaker."""
        self._build_registry()
        with self._lock:
            p = self._providers.get(provider_id)
            if not p:
                return
            p.health = ProviderHealth.CLOSED
            p.failure_count = 0
            p.last_success = time.time()
            p.total_calls += 1
            if latency_ms > 0:
                # Exponential moving average
                if p.avg_latency_ms == 0:
                    p.avg_latency_ms = latency_ms
                else:
                    p.avg_latency_ms = 0.7 * p.avg_latency_ms + 0.3 * latency_ms

    def record_failure(
        self,
        provider_id: str,
        reason: str = "unknown",
        status_code: int | None = None,
    ) -> None:
        """Record a provider failure — opens the circuit breaker on threshold."""
        self._build_registry()
        with self._lock:
            p = self._providers.get(provider_id)
            if not p:
                return
            p.failure_count += 1
            p.total_failures += 1
            p.total_calls += 1
            p.last_failure = time.time()
            p.last_error = f"{reason} (status={status_code})" if status_code else reason

            # 410 Gone = permanent — long cooldown (10 min)
            if status_code == 410:
                p.cooldown_until = time.time() + 600.0
                p.health = ProviderHealth.OPEN
                log.warning(
                    "brain_failover: %s marked OPEN (410 Gone — 10min cooldown)",
                    provider_id,
                )
                return

            # 429 / 419 = rate-limited — exponential backoff
            if status_code in (429, 419):
                backoff = p.cooldown_seconds * (2 ** min(p.failure_count - 1, 4))
                p.cooldown_until = time.time() + backoff
                p.health = ProviderHealth.OPEN
                log.warning(
                    "brain_failover: %s marked OPEN (429 rate-limited — %.0fs cooldown, "
                    "failure #%d)",
                    provider_id, backoff, p.failure_count,
                )
                return

            # 5xx = server error — short cooldown
            if status_code and status_code >= 500:
                p.cooldown_until = time.time() + 15.0
                p.health = ProviderHealth.OPEN
                log.warning(
                    "brain_failover: %s marked OPEN (5xx — 15s cooldown)",
                    provider_id,
                )
                return

            # Other failures — 30s cooldown
            p.cooldown_until = time.time() + p.cooldown_seconds
            p.health = ProviderHealth.OPEN
            log.warning(
                "brain_failover: %s marked OPEN (%s — %.0fs cooldown)",
                provider_id, reason, p.cooldown_seconds,
            )

    def resolve_model(self, provider: ProviderInfo, requested_model: str | None) -> str:
        """Map a requested model to the provider's equivalent.

        If the requested model is in the alias table for this provider, use
        the alias. Otherwise, if the requested model is in the provider's
        model list, use it as-is. Otherwise, fall back to the provider's
        default model.
        """
        if not requested_model:
            return provider.default_model

        # Check aliases first
        aliases = _MODEL_ALIASES.get(requested_model, {})
        if provider.id in aliases:
            return aliases[provider.id]

        # Check if the provider serves this model directly
        if requested_model in provider.models:
            return requested_model

        # Fuzzy match — if the model name contains part of a provider model
        for m in provider.models:
            if requested_model.lower() in m.lower() or m.lower() in requested_model.lower():
                return m

        # Fall back to the provider's default
        return provider.default_model

    def max_attempts(self) -> int:
        """Maximum number of provider attempts before giving up."""
        self._build_registry()
        with self._lock:
            return max(len(self._providers), 1)

    def status_snapshot(self) -> dict[str, Any]:
        """Return a full health snapshot for observability."""
        self._build_registry()
        with self._lock:
            return {
                "providers": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "tier": p.tier,
                        "health": p.health.value,
                        "is_healthy": p.is_healthy,
                        "failure_count": p.failure_count,
                        "total_calls": p.total_calls,
                        "total_failures": p.total_failures,
                        "avg_latency_ms": round(p.avg_latency_ms, 1),
                        "last_success": p.last_success,
                        "last_failure": p.last_failure,
                        "cooldown_until": p.cooldown_until,
                        "last_error": p.last_error,
                        "base_url": p.base_url,
                        "default_model": p.default_model,
                    }
                    for p in self._providers.values()
                ],
                "total_providers": len(self._providers),
                "healthy_providers": sum(1 for p in self._providers.values() if p.is_healthy),
            }


# ── Singleton ────────────────────────────────────────────────────────────

_manager: BrainFailoverManager | None = None
_manager_lock = threading.Lock()


def get_failover_manager() -> BrainFailoverManager:
    """Return the singleton BrainFailoverManager."""
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = BrainFailoverManager()
    return _manager


def reset_failover_manager() -> None:
    """Reset the singleton (for tests)."""
    global _manager
    with _manager_lock:
        _manager = None
