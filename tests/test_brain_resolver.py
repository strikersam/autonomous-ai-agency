"""tests/test_brain_resolver.py — Tests for the single brain resolver.

The agency now picks the active brain LLM through ONE function
``brain_policy.resolve_active_brain()``. Every selector in the codebase
delegates to it: ``services/workflow_orchestrator._resolve_brain_provider``
(wrapped as a thin alias for backward compat),
``services/workflow_orchestrator.get_provider_role_tags`` (new delegate),
``router/model_router._opus_model`` (early-returns None when ALLOW_PAID_BRAIN
is unset), ``services/ceo_dispatcher.ROLE_RUNTIME_PREFERENCE`` (reordered so
``internal_agent`` is picked first), and eventually the harness adapter and
scripts/agency_fix.py.

These tests pin the binding contract for the single source of truth so the
operators' ONE-place intent (Providers screen priority reorder propagates
everywhere) cannot silently regress.
"""
from __future__ import annotations

import asyncio
import os

import pytest


# ── Helpers ────────────────────────────────────────────────────────────────────


def _run(coro):
    return asyncio.run(coro)


def _records(*items: dict):
    """Return a coroutine that resolves to ``list(items)`` on await.

    ``brain_policy._read_provider_records`` does ``await _list_configured_provider_records()``,
    so the patched attribute must be a coroutine (not an async function object,
    which would TypeError on await).  Each test patches with
    ``monkeypatch.setattr("backend.server.X", _records({...}, {...}))`` and
    brain_policy can then ``await`` the patched attribute directly.
    """
    async def _list_records():
        return list(items)
    return _list_records()


# ── env override — always wins, even over a paid provider record ─────────────


def test_env_override_wins_over_paid_records(monkeypatch):
    """AGENT_LLM_BASE_URL beat the highest-priority paid provider.

    Pins the docstring contract of ``resolve_active_brain``: env override is
    step 1, even when ANTHROPIC_API_KEY is set and an Anthropic record exists.
    Critical because operators rely on AGENT_LLM_BASE_URL as a kill switch.
    """
    monkeypatch.delenv("ALLOW_PAID_BRAIN", raising=False)
    monkeypatch.setattr(
        "backend.server._list_configured_provider_records",
        lambda: _records(
            {"provider_id": "anthropic-claude", "type": "anthropic",
             "base_url": "https://api.anthropic.com/v1", "api_key": "sk-x",
             "default_model": "claude-sonnet-4-6", "priority": 999},
        ),
    )

    monkeypatch.setenv("AGENT_LLM_BASE_URL", "https://my-free.example/v1")
    monkeypatch.setenv("AGENT_LLM_API_KEY", "sk-free")
    monkeypatch.setenv("AGENT_LLM_MODEL", "my-free-model")

    from brain_policy import resolve_active_brain
    brain = _run(resolve_active_brain())
    assert brain.provider_id == "env_override"
    assert "my-free.example" in brain.base_url
    assert brain.model == "my-free-model"
    assert brain.role == "env_override"


def test_env_override_no_key_returns_no_headers(monkeypatch):
    monkeypatch.setenv("AGENT_LLM_BASE_URL", "http://env-no-key.local/v1")
    from brain_policy import resolve_active_brain
    brain = _run(resolve_active_brain())
    assert brain.provider_id == "env_override"
    assert brain.auth_headers is None


# ── free-first: paid records skipped when a free record exists ───────────────


def test_brain_skips_paid_when_free_configured(monkeypatch):
    """When a free provider (NVIDIA NIM) is configured, the brain must NOT
    auto-pick Anthropic even when ANTHROPIC_API_KEY is set in the env."""
    monkeypatch.delenv("AGENT_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("ALLOW_PAID_BRAIN", raising=False)
    monkeypatch.setattr(
        "backend.server._list_configured_provider_records",
        lambda: _records(
            {"provider_id": "anthropic", "type": "anthropic",
             "base_url": "https://api.anthropic.com", "api_key": "sk-x",
             "default_model": "claude-sonnet-4-6", "priority": 999},
            {"provider_id": "nvidia-nim", "type": "openai-compatible",
             "base_url": "https://integrate.api.nvidia.com", "api_key": "nvapi-x",
             "default_model": "nvidia/llama-3.3-nemotron-super-49b-v1", "priority": 5},
        ),
    )

    from brain_policy import resolve_active_brain
    brain = _run(resolve_active_brain())
    assert "nvidia" in brain.base_url or "nemotron" in (brain.model or "").lower()
    assert brain.provider_id == "nvidia-nim"
    assert brain.free_tier is True


def test_brain_escalates_to_paid_only_when_explicitly_opted_in(monkeypatch):
    """When only a paid record exists AND ALLOW_PAID_BRAIN is set, the brain
    picks the paid one — single-tenant setups that legitimately rely on
    Anthropic can still opt in."""
    monkeypatch.setenv("ALLOW_PAID_BRAIN", "true")
    monkeypatch.delenv("AGENT_LLM_BASE_URL", raising=False)
    monkeypatch.setattr(
        "backend.server._list_configured_provider_records",
        lambda: _records(
            {"provider_id": "anthropic", "type": "anthropic",
             "base_url": "https://api.anthropic.com/v1", "api_key": "sk-x",
             "default_model": "claude-sonnet-4-6", "priority": 10},
        ),
    )

    from brain_policy import resolve_active_brain
    brain = _run(resolve_active_brain())
    assert "anthropic" in brain.base_url
    assert brain.free_tier is False


# ── exclusion: failover retry path ───────────────────────────────────────────


def test_excluded_url_is_skipped(monkeypatch):
    """When a base_url is excluded (transient retry failure), the next-best
    free provider is picked. Local Ollama fallback when ALL free configs are
    excluded."""
    monkeypatch.delenv("AGENT_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("ALLOW_PAID_BRAIN", raising=False)
    monkeypatch.setenv("OLLAMA_BASE", "http://my-ollama:11434")
    monkeypatch.setattr(
        "backend.server._list_configured_provider_records",
        lambda: _records(
            {"provider_id": "primary", "type": "openai-compatible",
             "base_url": "https://primary.example", "api_key": "k1",
             "default_model": "primary-model", "priority": 100},
        ),
    )

    from brain_policy import resolve_active_brain
    brain = _run(resolve_active_brain(exclude_base_urls={"https://primary.example/v1"}))
    assert brain.provider_id == "ollama-local-fallback"
    assert brain.role == "ollama_local"


# ── free fallback when no records ────────────────────────────────────────────


def test_no_records_falls_back_to_nvidia_then_ollama(monkeypatch):
    """When provider records are missing AND ``NVIDIA_API_KEY`` is set,
    resolve to the free NVIDIA NIM default — exactly the brain_policy
    resolve_free_nvidia_brain path."""
    monkeypatch.delenv("AGENT_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("ALLOW_PAID_BRAIN", raising=False)
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    monkeypatch.delenv("AGENT_LLM_BASE_URL", raising=False)
    monkeypatch.setattr(
        "backend.server._list_configured_provider_records",
        lambda: _records(),
    )

    from brain_policy import resolve_active_brain, DEFAULT_FREE_NVIDIA_MODEL
    brain = _run(resolve_active_brain())
    assert brain.provider_id == "nvidia-nim-free-default"
    assert brain.model == DEFAULT_FREE_NVIDIA_MODEL
    assert brain.free_tier is True


def test_no_records_no_nvidia_key_falls_back_to_ollama(monkeypatch):
    """When nothing is configured AND NVIDIA_API_KEY unset, fall through to
    local Ollama so the brain never silently escalates to a paid endpoint."""
    monkeypatch.delenv("AGENT_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("ALLOW_PAID_BRAIN", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVidiaApiKey", raising=False)
    monkeypatch.setenv("OLLAMA_BASE", "http://fallback-ollama:11434")
    monkeypatch.setattr(
        "backend.server._list_configured_provider_records",
        lambda: _records(),
    )

    from brain_policy import resolve_active_brain
    brain = _run(resolve_active_brain())
    assert brain.provider_id == "ollama-local-fallback"
    assert brain.role == "ollama_local"


# ── cache: invalidate_brain_cache + get_active_brain_sync ────────────────────


def test_cache_invalidates_on_next_resolution(monkeypatch):
    """Operators must see provider-reorder edits immediately. invalidate_cache
    (called by webui/providers.py after edit) must force refresh."""
    monkeypatch.delenv("AGENT_LLM_BASE_URL", raising=False)
    monkeypatch.setattr(
        "backend.server._list_configured_provider_records",
        lambda: _records(
            {"provider_id": "nvidia-nim", "type": "openai-compatible",
             "base_url": "https://integrate.api.nvidia.com", "api_key": "nv-x",
             "default_model": "nvidia/llama-3.3-nemotron-super-49b-v1", "priority": 5},
        ),
    )

    from brain_policy import resolve_active_brain, get_active_brain_sync, invalidate_brain_cache
    invalidate_brain_cache()
    assert get_active_brain_sync() is None

    _run(resolve_active_brain())
    first = get_active_brain_sync()
    assert first is not None
    assert first.provider_id == "nvidia-nim"

    invalidate_brain_cache()
    assert get_active_brain_sync() is None


# ── workflow_orchestrator delegate regression-free ──────────────────────────


def test_workflow_orchestrator_still_returns_same_tuple_shape(monkeypatch):
    """The thin wrapper module keeps the existing (base, headers, model)
    tuple contract so tests/test_orchestrator_failover.py still pass. The
    underlying selection is now brain_policy.resolve_active_brain."""
    monkeypatch.delenv("AGENT_LLM_BASE_URL", raising=False)
    monkeypatch.setattr(
        "backend.server._list_configured_provider_records",
        lambda: _records(
            {"provider_id": "nvidia-nim", "type": "openai-compatible",
             "base_url": "https://integrate.api.nvidia.com", "api_key": "nv-x",
             "default_model": "nvidia/llama-3.3-nemotron-super-49b-v1", "priority": 5},
        ),
    )

    from services.workflow_orchestrator import _resolve_brain_provider
    base, headers, model = _run(_resolve_brain_provider())
    assert "nvidia" in base.lower()
    # Headers passed through unchanged.
    assert headers and "nv-x" in str(headers)
    assert model == "nvidia/llama-3.3-nemotron-super-49b-v1"


def test_workflow_orchestrator_supports_exclude_base_urls(monkeypatch):
    """Existing failover tests in tests/test_orchestrator_failover.py call
    ``_resolve_brain_provider(exclude_base_urls=...)`` — that signature MUST
    keep working post-consolidation."""
    monkeypatch.delenv("AGENT_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("ALLOW_PAID_BRAIN", raising=False)
    monkeypatch.setenv("OLLAMA_BASE", "http://fb-ollama:11434")
    monkeypatch.setattr(
        "backend.server._list_configured_provider_records",
        lambda: _records(
            {"provider_id": "only", "type": "openai-compatible",
             "base_url": "https://only.example", "api_key": "k1",
             "default_model": "only-model", "priority": 1},
        ),
    )

    from services.workflow_orchestrator import _resolve_brain_provider
    base, headers, model = _run(
        _resolve_brain_provider(exclude_base_urls={"https://only.example/v1"})
    )
    assert "fb-ollama" in base.lower() or "localhost" in base.lower()


# ── get_provider_role_tags ──────────────────────────────────────────────────


def test_role_tags_classify_correctly(monkeypatch):
    monkeypatch.delenv("AGENT_LLM_BASE_URL", raising=False)
    monkeypatch.setattr(
        "backend.server._list_configured_provider_records",
        lambda: _records(
            {"provider_id": "nvidia-nim", "type": "openai-compatible",
             "base_url": "https://integrate.api.nvidia.com", "api_key": "nv-x",
             "default_model": "nvidia/llama-3.3-nemotron-super-49b-v1", "priority": 0},
            {"provider_id": "anthropic", "type": "anthropic",
             "base_url": "https://api.anthropic.com/v1", "api_key": "sk-x",
             "default_model": "claude-sonnet-4-6", "priority": -90},
            {"provider_id": "no-key", "type": "openai-compatible",
             "base_url": "https://unconfigured.example", "api_key": "",
             "default_model": "x", "priority": 5},
        ),
    )

    from brain_policy import get_provider_role_tags
    tags = _run(get_provider_role_tags())
    assert tags["nvidia-nim"]["role"] == "brain"
    assert tags["nvidia-nim"]["is_brain"] is True
    assert tags["anthropic"]["role"] == "fallback"
    assert tags["anthropic"]["is_brain"] is False
    assert tags["no-key"]["role"] == "unconfigured"
