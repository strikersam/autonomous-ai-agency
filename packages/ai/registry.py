"""packages/ai/registry.py — Model Registry.

Centralized registry of all models across all providers. Every agent,
route, and UI component reads from this registry — no hardcoded models
anywhere else.

Models declare their provider, capabilities, pricing, speed, context
window, and fallback priority. The ProviderManager uses this to select
the best model for a given task.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModelInfo:
    """Information about a specific model."""
    model_id: str                    # e.g. "meta/llama-3.3-70b-instruct"
    provider_id: str                 # e.g. "nvidia"
    display_name: str                # e.g. "Llama 3.3 70B Instruct"
    
    # Capabilities
    supports_tools: bool = False
    supports_vision: bool = False
    supports_streaming: bool = True
    supports_embeddings: bool = False
    
    # Performance
    context_window: int = 4096
    max_output_tokens: int = 4096
    speed_tier: str = "medium"       # "fast", "medium", "slow"
    
    # Cost (USD per 1M tokens)
    input_cost_per_1m: float = 0.0   # Free = 0.0
    output_cost_per_1m: float = 0.0
    
    # Fallback
    priority: int = 100              # Lower = higher priority
    fallback_model: str | None = None  # Model to try if this one fails
    
    # Health
    is_healthy: bool = True
    last_health_check: float = 0.0


# ── The Registry ─────────────────────────────────────────────────────────────

_REGISTRY: dict[str, ModelInfo] = {}


def register(model: ModelInfo) -> None:
    """Register a model in the registry."""
    _REGISTRY[model.model_id] = model


def get(model_id: str) -> ModelInfo | None:
    """Get model info by ID."""
    return _REGISTRY.get(model_id)


def all_models() -> list[ModelInfo]:
    """Return all registered models."""
    return list(_REGISTRY.values())


def models_by_provider(provider_id: str) -> list[ModelInfo]:
    """Return all models for a given provider."""
    return [m for m in _REGISTRY.values() if m.provider_id == provider_id]


def best_model_for(task: str = "chat", *, allow_paid: bool = False,
                   require_tools: bool = False, require_vision: bool = False) -> ModelInfo | None:
    """Find the best model for a given task.
    
    Selection criteria:
    1. Filter by capabilities (tools, vision, etc.)
    2. Filter by cost (free only if allow_paid=False)
    3. Sort by priority (lower = better)
    4. Return the first healthy model
    """
    candidates = list(_REGISTRY.values())
    
    # Filter by capabilities
    if require_tools:
        candidates = [m for m in candidates if m.supports_tools]
    if require_vision:
        candidates = [m for m in candidates if m.supports_vision]
    
    # Filter by cost
    if not allow_paid:
        candidates = [m for m in candidates if m.input_cost_per_1m == 0.0]
    
    # Filter by health
    candidates = [m for m in candidates if m.is_healthy]
    
    if not candidates:
        return None
    
    # Sort by priority
    candidates.sort(key=lambda m: m.priority)
    return candidates[0]


# ── Default Model Registrations ──────────────────────────────────────────────

def _register_defaults() -> None:
    """Register the default free-tier models."""
    
    # NVIDIA NIM (free, always-on floor)
    register(ModelInfo(
        model_id="meta/llama-3.3-70b-instruct",
        provider_id="nvidia",
        display_name="Llama 3.3 70B Instruct",
        supports_streaming=True,
        context_window=128000,
        max_output_tokens=4096,
        speed_tier="medium",
        input_cost_per_1m=0.0,
        output_cost_per_1m=0.0,
        priority=30,
        fallback_model="nvidia/llama-3.3-nemotron-super-49b-v1.5",
    ))

    # GLM-5.2 (Z.AI) on NVIDIA NIM — the operator's preferred brain model.
    # https://build.nvidia.com/z-ai/glm-5.2 — free, high-quality, fast.
    # Registered with priority 20 (higher than llama-3.3-70b at 30) so
    # best_model_for() prefers it when both are available.
    register(ModelInfo(
        model_id="z-ai/glm-5.2",
        provider_id="nvidia",
        display_name="GLM-5.2 (Z.AI)",
        supports_streaming=True,
        context_window=128000,
        max_output_tokens=8192,
        speed_tier="fast",
        input_cost_per_1m=0.0,
        output_cost_per_1m=0.0,
        priority=20,
        fallback_model="meta/llama-3.3-70b-instruct",
    ))
    
    # Cerebras (free, fastest)
    register(ModelInfo(
        model_id="qwen-3-coder-480b",
        provider_id="cerebras",
        display_name="Qwen 3 Coder 480B",
        supports_streaming=True,
        context_window=32768,
        max_output_tokens=8192,
        speed_tier="fast",
        input_cost_per_1m=0.0,
        output_cost_per_1m=0.0,
        priority=10,
        fallback_model="meta/llama-3.3-70b-instruct",
    ))
    
    # Groq (free, fast)
    register(ModelInfo(
        model_id="deepseek-r1-distill-llama-70b",
        provider_id="groq",
        display_name="DeepSeek R1 Distill 70B",
        supports_streaming=True,
        context_window=32768,
        max_output_tokens=8192,
        speed_tier="fast",
        input_cost_per_1m=0.0,
        output_cost_per_1m=0.0,
        priority=20,
        fallback_model="meta/llama-3.3-70b-instruct",
    ))
    
    # Llama 4 Maverick on Groq — MoE 17B active/128E total, fast and capable (Meta, 2025)
    register(ModelInfo(
        model_id="llama-4-maverick-17b-128e-instruct",
        provider_id="groq",
        display_name="Llama 4 Maverick 17B (Groq)",
        supports_tools=True,
        supports_streaming=True,
        context_window=131072,
        max_output_tokens=8192,
        speed_tier="fast",
        input_cost_per_1m=0.0,
        output_cost_per_1m=0.0,
        priority=8,
        fallback_model="llama-3.3-70b-versatile",
    ))

    # Llama 4 Maverick on NVIDIA NIM — same model, NIM endpoint
    register(ModelInfo(
        model_id="meta/llama-4-maverick-17b-128e-instruct",
        provider_id="nvidia",
        display_name="Llama 4 Maverick 17B (NVIDIA NIM)",
        supports_tools=True,
        supports_streaming=True,
        context_window=131072,
        max_output_tokens=8192,
        speed_tier="fast",
        input_cost_per_1m=0.0,
        output_cost_per_1m=0.0,
        priority=15,
        fallback_model="meta/llama-3.3-70b-instruct",
    ))

    # Gemini 2.5 Flash — fast, 1M context, tool-use, free via Google AI Studio key
    register(ModelInfo(
        model_id="gemini-2.5-flash",
        provider_id="google",
        display_name="Gemini 2.5 Flash",
        supports_tools=True,
        supports_vision=True,
        supports_streaming=True,
        context_window=1048576,
        max_output_tokens=8192,
        speed_tier="fast",
        input_cost_per_1m=0.0,
        output_cost_per_1m=0.0,
        priority=12,
        fallback_model="gemini-2.0-flash",
    ))

    # Ollama (local, no cost)
    register(ModelInfo(
        model_id="qwen3-coder:30b",
        provider_id="ollama",
        display_name="Qwen3 Coder 30B (local)",
        supports_streaming=True,
        context_window=32768,
        max_output_tokens=8192,
        speed_tier="medium",
        input_cost_per_1m=0.0,
        output_cost_per_1m=0.0,
        priority=40,
    ))


# Register defaults on import
_register_defaults()
