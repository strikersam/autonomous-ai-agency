"""packages.ai — provider abstraction, model registry, and failover manager.

SINGLE SOURCE OF TRUTH for all model + provider config. Every caller imports
from here — no hardcoded model ids anywhere else.
"""
from packages.ai.provider import Provider, ChatResponse, HealthStatus, RateLimit
from packages.ai.registry import (
    ModelInfo, register, get, all_models, best_model_for,
    nvidia_default_model, cerebras_default_model, groq_default_model,
    ollama_default_model, ollama_planner_model, ollama_judge_model,
    model_for_role, fallback_chain, default_model_for_provider,
)
from packages.ai.manager import ProviderManager, provider_manager

__all__ = [
    "Provider", "ChatResponse", "HealthStatus", "RateLimit",
    "ModelInfo", "register", "get", "all_models", "best_model_for",
    "nvidia_default_model", "cerebras_default_model", "groq_default_model",
    "ollama_default_model", "ollama_planner_model", "ollama_judge_model",
    "model_for_role", "fallback_chain", "default_model_for_provider",
    "ProviderManager", "provider_manager",
]
