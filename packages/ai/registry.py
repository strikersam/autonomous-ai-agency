"""packages/ai/registry.py — Model Registry (SINGLE SOURCE OF TRUTH).

Every agent, route, runtime, and UI component reads model names from this
registry. No hardcoded model ids anywhere else in the codebase.

The registry defines:
  1. Which models exist (model_id + provider_id)
  2. Which model to use for each role (planner / executor / verifier / judge)
  3. Fallback chains — if a model fails, which model to try next
  4. Per-provider default models

Changing a model here propagates everywhere: direct chat, SAM voice agent,
runtimes (internal_agent, Hermes), workflow orchestrator, setup wizard, etc.

Env var overrides (all optional):
  NVIDIA_DEFAULT_MODEL   — override the NVIDIA default
  CEREBRAS_DEFAULT_MODEL — override the Cerebras default
  GROQ_DEFAULT_MODEL     — override the Groq default
  OLLAMA_MODEL           — override the Ollama default
  AGENT_PLANNER_MODEL    — override the planner role
  AGENT_EXECUTOR_MODEL   — override the executor role
  AGENT_VERIFIER_MODEL   — override the verifier role
  AGENT_JUDGE_MODEL      — override the judge role
"""
from __future__ import annotations

import os
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


# ── Per-provider + per-role defaults (SINGLE SOURCE OF TRUTH) ────────────────
#
# These are the ONLY places model ids are hardcoded. Every other module
# imports from here. Env var overrides take precedence.

def nvidia_default_model() -> str:
    """The default NVIDIA NIM model (live, free tier)."""
    return os.environ.get("NVIDIA_DEFAULT_MODEL", "").strip() or "meta/llama-3.3-70b-instruct"


def cerebras_default_model() -> str:
    """The default Cerebras model (live, free tier)."""
    return os.environ.get("CEREBRAS_DEFAULT_MODEL", "").strip() or "qwen-3-coder-480b"


def groq_default_model() -> str:
    """The default Groq model (live, free tier)."""
    return os.environ.get("GROQ_DEFAULT_MODEL", "").strip() or "deepseek-r1-distill-llama-70b"


def ollama_default_model() -> str:
    """The default Ollama model (local)."""
    return os.environ.get("OLLAMA_MODEL", "").strip() or "qwen3-coder:30b"


def ollama_planner_model() -> str:
    """The Ollama model for planning (deeper reasoning)."""
    return os.environ.get("AGENT_PLANNER_MODEL", "").strip() or "deepseek-r1:32b"


def ollama_judge_model() -> str:
    """The Ollama model for judging (deeper reasoning)."""
    return os.environ.get("AGENT_JUDGE_MODEL", "").strip() or ollama_planner_model()


# ── Role-based model resolution ──────────────────────────────────────────────
#
# Roles: planner, executor, verifier, judge
# Each role resolves to a model based on the active provider.
# If the model fails, the fallback chain kicks in.

def model_for_role(role: str, provider: str | None = None) -> str:
    """Resolve the model for a given role + provider.

    Args:
        role: "planner", "executor", "verifier", or "judge"
        provider: "nvidia", "cerebras", "groq", "ollama", or None (auto)

    Returns:
        The model id to use. Never returns None — always falls back to a
        known-good model.
    """
    role = role.lower().strip()
    # Env var override (highest precedence)
    env_var = f"AGENT_{role.upper()}_MODEL"
    env_val = os.environ.get(env_var, "").strip()
    if env_val:
        return env_val

    # Provider-specific resolution
    if provider is None:
        provider = os.environ.get("BRAIN_PREFERENCE", "nvidia").lower().strip()
        if provider not in ("nvidia", "cerebras", "groq", "ollama"):
            provider = "nvidia"

    if provider == "ollama":
        # Ollama uses different models per role
        if role == "planner":
            return ollama_planner_model()
        if role == "executor":
            return ollama_default_model()
        if role == "verifier":
            return ollama_planner_model()
        if role == "judge":
            return ollama_judge_model()
        return ollama_default_model()

    if provider == "cerebras":
        return cerebras_default_model()
    if provider == "groq":
        return groq_default_model()
    # NVIDIA default
    return nvidia_default_model()


def fallback_chain(model_id: str) -> list[str]:
    """Return the fallback chain for a model.

    If the model fails, try each subsequent model in order. The last resort
    is always the Ollama local model (which never has a cloud outage).
    """
    chain = [model_id]
    info = get(model_id)
    if info and info.fallback_model:
        chain.append(info.fallback_model)
    # Always end with Ollama as the last resort
    ollama = ollama_default_model()
    if ollama not in chain:
        chain.append(ollama)
    return chain


def default_model_for_provider(provider: str) -> str:
    """Return the default model for a provider. Never returns None."""
    provider = provider.lower().strip()
    if provider == "nvidia":
        return nvidia_default_model()
    if provider == "cerebras":
        return cerebras_default_model()
    if provider == "groq":
        return groq_default_model()
    if provider == "ollama":
        return ollama_default_model()
    # Unknown provider — fall back to NVIDIA (free, always-on)
    return nvidia_default_model()


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
        fallback_model="qwen3-coder:30b",  # fall back to Ollama local
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

    # Ollama (local, no cost, never has a cloud outage)
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

    # Ollama planner model (deeper reasoning)
    register(ModelInfo(
        model_id="deepseek-r1:32b",
        provider_id="ollama",
        display_name="DeepSeek R1 32B (local planner)",
        supports_streaming=True,
        context_window=32768,
        max_output_tokens=8192,
        speed_tier="medium",
        input_cost_per_1m=0.0,
        output_cost_per_1m=0.0,
        priority=50,
    ))


# Register defaults on import
_register_defaults()
