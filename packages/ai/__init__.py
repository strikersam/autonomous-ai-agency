"""packages.ai — provider abstraction, model registry, and failover manager."""
from packages.ai.provider import Provider, ChatResponse, HealthStatus, RateLimit
from packages.ai.registry import ModelInfo, register, get, all_models, best_model_for
from packages.ai.manager import ProviderManager, provider_manager

__all__ = [
    "Provider", "ChatResponse", "HealthStatus", "RateLimit",
    "ModelInfo", "register", "get", "all_models", "best_model_for",
    "ProviderManager", "provider_manager",
]
