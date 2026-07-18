"""tests/test_north_mini_code.py — North Mini Code 1.0 integration.

Covers the wiring that makes Cohere's ``north-mini-code-1.0`` the default
agentic coding brain for the agency + Hermes:

  1. Registered in the router registry (both the Ollama id and the OpenRouter
     free-tier alias) so the proxy can route / serve / health-check it.
  2. It does NOT displace the existing heaviest-tier default coder in
     ``best_model_for`` (no proxy-routing regression).
  3. It is the Ollama executor (code-writing) preset + an Ollama failover
     candidate, and the OpenRouter executor preset + candidate.
  4. ``resolve_coding_model_preference`` returns North only when the flag is on
     AND the active provider can serve it (else ``None`` → normal brain runs),
     which is what keeps NVIDIA-only production untouched.
  5. The InternalAgentAdapter (the path Hermes runs through) consults the
     resolver, and the Hermes adapter still declares the full Hermes-OS
     capability set.
"""
from __future__ import annotations

import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

OLLAMA_ID = "north-mini-code-1.0"
OPENROUTER_ID = "cohere/north-mini-code:free"


# ── 1. Router registry ─────────────────────────────────────────────────────


def test_north_registered_in_router_registry():
    from router.registry import get_registry

    reg = get_registry()
    for model_id in (OLLAMA_ID, OPENROUTER_ID):
        assert model_id in reg, f"{model_id!r} missing from router registry"
        cap = reg[model_id]
        assert cap.type == "coder"
        assert cap.context_window == 262144
        for strength in ("code_generation", "code_debugging", "tool_use", "long_context"):
            assert strength in cap.strengths


def test_north_does_not_displace_default_coder():
    """North is cost_tier=2, so it must not become the ``best_model_for``
    pick for the code categories (which return the heaviest-tier coder).
    Guards against a silent proxy-routing regression for external harnesses."""
    from router.registry import best_model_for, get_registry

    reg = get_registry()
    for category in ("code_generation", "code_debugging", "code_review", "tool_use"):
        chosen = best_model_for(category, reg)
        assert chosen not in (OLLAMA_ID, OPENROUTER_ID), (
            f"North unexpectedly won best_model_for({category!r}) = {chosen!r}"
        )
        assert reg[chosen].cost_tier == 3


# ── 2. Catalog presets + candidates ────────────────────────────────────────


def test_ollama_executor_preset_is_north():
    from packages.ai.brain_config import PROVIDER_PRESETS

    assert PROVIDER_PRESETS["ollama"]["executor"] == OLLAMA_ID
    # Planner / verifier / judge stay on the dedicated reasoning model.
    assert PROVIDER_PRESETS["ollama"]["planner"] == "deepseek-r1:32b"


def test_north_in_ollama_and_openrouter_candidates():
    from packages.ai.brain_config import PROVIDER_CANDIDATES

    assert OLLAMA_ID in PROVIDER_CANDIDATES["ollama"]
    assert OPENROUTER_ID in PROVIDER_CANDIDATES["openrouter"]


def test_openrouter_executor_preset_is_north():
    from packages.ai.brain_config import PROVIDER_PRESETS

    assert PROVIDER_PRESETS["openrouter"]["executor"] == OPENROUTER_ID


# ── 3. Provider mapping + resolver ──────────────────────────────────────────


def test_north_mini_code_model_for_maps_only_serving_providers():
    from packages.ai.brain_config import north_mini_code_model_for

    assert north_mini_code_model_for("ollama") == OLLAMA_ID
    assert north_mini_code_model_for("openrouter") == OPENROUTER_ID
    assert north_mini_code_model_for("OpenRouter") == OPENROUTER_ID  # case-insensitive
    for other in ("nvidia", "cerebras", "groq", "anthropic", "", None):
        assert north_mini_code_model_for(other) is None


def test_resolve_coding_pref_prefers_north_when_enabled(monkeypatch):
    import packages.ai.brain_config as bc

    monkeypatch.setattr(bc, "is_north_mini_code_default", lambda: True)
    assert bc.resolve_coding_model_preference("ollama") == OLLAMA_ID
    assert bc.resolve_coding_model_preference("openrouter") == OPENROUTER_ID
    # NVIDIA-only production: no North available → None → normal brain runs.
    assert bc.resolve_coding_model_preference("nvidia") is None


def test_resolve_coding_pref_none_when_flag_disabled(monkeypatch):
    import packages.ai.brain_config as bc

    monkeypatch.setattr(bc, "is_north_mini_code_default", lambda: False)
    assert bc.resolve_coding_model_preference("ollama") is None
    assert bc.resolve_coding_model_preference("openrouter") is None


def test_flag_default_is_on():
    """The switch defaults ON so North is the default post-install."""
    from packages.config import settings

    assert settings.is_north_mini_code_default is True


# ── 4. Wiring — InternalAgentAdapter + Hermes ───────────────────────────────


def test_internal_agent_consults_coding_resolver():
    """The agency/Hermes execution path defaults to North via the resolver."""
    src = (REPO_ROOT / "runtimes" / "adapters" / "internal_agent.py").read_text(encoding="utf-8")
    assert "resolve_coding_model_preference" in src


def test_hermes_declares_full_capability_set():
    """Hermes must be able to run the agency with the full Hermes-OS capacity
    set — the mechanism that guarantees 'Hermes runs the agency'."""
    pytest.importorskip("httpx")
    from runtimes.adapters.hermes import HermesAdapter
    from runtimes.base import RuntimeCapability as C

    caps = HermesAdapter.CAPABILITIES
    required = (
        C.CODE_GENERATION,
        C.TOOL_USE,
        C.SHELL_EXEC,
        C.AGENT_DELEGATION,
        C.SCHEDULED_TASKS,
        C.MEMORY_SESSIONS,
        C.MCP_CONNECTIVITY,
        C.AUTONOMOUS_LOOP,
        C.FILE_READ_WRITE,
    )
    for cap in required:
        assert cap in caps, f"Hermes missing capability {cap!r}"
