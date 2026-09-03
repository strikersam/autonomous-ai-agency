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
    
    # NVIDIA NIM (free, always-on floor).
    #
    # This module is a *second* model source: packages/llm/registry.py imports
    # it (`_seed_from_legacy`) and adds anything absent from config/llm YAML.
    # That is how meta/llama-3.3-70b-instruct, z-ai/glm-5.2 and Llama 4
    # Maverick — all removed from the YAML catalogues on 2026-08-28 after a
    # live probe found them answering 410 — kept reappearing as tool-calling
    # candidates on the gateway path. Removing an id from the catalogues is not
    # enough while it is still registered here.
    #
    # Probed live 2026-08-28 (catalogue-probe run 33201732226): serves, and
    # emits tool_calls.
    register(ModelInfo(
        model_id="nvidia/nemotron-3-super-120b-a12b",
        provider_id="nvidia",
        display_name="Nemotron 3 Super 120B-a12b",
        supports_tools=True,
        supports_streaming=True,
        # NVIDIA's /v1/models returns no capability fields, so these are the
        # conservative defaults rather than measured limits — they prune
        # prompts rather than overflow them. Raise once someone measures.
        context_window=32768,
        max_output_tokens=4096,
        speed_tier="fast",
        input_cost_per_1m=0.0,
        output_cost_per_1m=0.0,
        priority=10,
    ))
    
    # Cerebras (free, fastest)
    register(ModelInfo(
        model_id="gpt-oss-120b",
        provider_id="cerebras",
        display_name="GPT-OSS 120B (Cerebras)",
        supports_streaming=True,
        context_window=32768,
        max_output_tokens=8192,
        speed_tier="fast",
        input_cost_per_1m=0.0,
        output_cost_per_1m=0.0,
        priority=10,
        fallback_model="nvidia/nemotron-3-super-120b-a12b",
    ))
    
    # Groq (free, fast). Groq's live free models are the GPT-OSS pair registered
    # below (also served by NVIDIA NIM). The two ids that used to sit here —
    # deepseek-r1-distill-llama-70b and llama-4-maverick-17b-128e-instruct — are
    # not in this account's catalogue and answered 404/400, so registering them
    # only advertised a dead endpoint. Removed; do not re-add without a probe.

    # GPT-OSS on NVIDIA NIM. Replaces the Llama 4 Maverick NIM registration,
    # which answered 410 when probed on 2026-08-28. Both probed live in run
    # 33201732226: serve, and emit tool_calls.
    register(ModelInfo(
        model_id="openai/gpt-oss-120b",
        provider_id="nvidia",
        display_name="GPT-OSS 120B (NVIDIA NIM)",
        supports_tools=True,
        supports_streaming=True,
        context_window=32768,
        max_output_tokens=4096,
        speed_tier="medium",
        input_cost_per_1m=0.0,
        output_cost_per_1m=0.0,
        priority=25,
    ))

    register(ModelInfo(
        model_id="openai/gpt-oss-20b",
        provider_id="nvidia",
        display_name="GPT-OSS 20B (NVIDIA NIM)",
        supports_tools=True,
        supports_streaming=True,
        context_window=32768,
        max_output_tokens=4096,
        speed_tier="fast",
        input_cost_per_1m=0.0,
        output_cost_per_1m=0.0,
        priority=30,
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
        # Was gemini-2.0-flash, never registered here. Falls back across
        # providers, which is the pattern the free-tier entries already use.
        fallback_model="nvidia/nemotron-3-super-120b-a12b",
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
