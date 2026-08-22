"""tests/test_tokenin_provider.py — TokenIn free frontier gateway wiring.

Regression coverage for adding tokenin.my.id as a rotatable free brain
provider (2026-08-22). Verifies the provider is wired end-to-end across the
four sync points that a new provider touches:

  1. ``config/models.yaml`` catalog + the ``BrainProvider`` Literal.
  2. The hardcoded fallback dicts in ``packages/ai/brain_config.py``.
  3. ``services/brain_failover.py`` registry + the opus cross-provider alias.
  4. ``packages/ai/router.py`` ``from_env`` + free-tier classification, and
     that the request URL resolves to the gateway's real endpoint.
"""
from __future__ import annotations

import os

import pytest

from packages.ai import brain_config
from packages.ai.brain_config import (
    PROVIDER_CANDIDATES,
    PROVIDER_DEFAULT_BASE_URL,
    PROVIDER_KEY_ENV,
    PROVIDER_PRESETS,
    RECOMMENDED_PROVIDER_PRIORITY,
    all_provider_ids,
    get_provider_tier,
)

# The ten free models tokenin exposes (myt/ prefix, exact casing from the
# dashboard copy field). This list is the failover rotation.
EXPECTED_MODELS = [
    "myt/glm-5.3-free",
    "myt/deepseek-v4-pro-free",
    "myt/MiniMax-M3-free",
    "myt/mimo-v2.5-free",
    "myt/qwen3.8-max-free",
    "myt/kimi-k3-free",
    "myt/gemini-3.5-flash-free",
    "myt/grok-4.6-free",
    "myt/gpt-5.6-sol-free",
    "myt/claude-opus-4-8-free",
]


def test_tokenin_in_literal_and_catalog():
    assert "tokenin" in all_provider_ids()
    assert PROVIDER_KEY_ENV["tokenin"] == "TOKENIN_API_KEY"
    assert PROVIDER_DEFAULT_BASE_URL["tokenin"] == "https://tokenin.my.id/v1"
    assert get_provider_tier("tokenin") == "free"


def test_tokenin_candidates_are_the_rotation():
    assert PROVIDER_CANDIDATES["tokenin"] == EXPECTED_MODELS
    # Role presets must be real candidates on the provider.
    presets = PROVIDER_PRESETS["tokenin"]
    for role in ("planner", "executor", "verifier", "judge"):
        assert presets[role] in EXPECTED_MODELS


def test_tokenin_high_in_recommended_priority():
    assert "tokenin" in RECOMMENDED_PROVIDER_PRIORITY
    # Preferred among the rich free set, just behind the always-on nvidia floor.
    assert RECOMMENDED_PROVIDER_PRIORITY.index("tokenin") == 1


def test_brain_failover_registry_and_opus_alias():
    import services.brain_failover as bf

    reg = {p["id"]: p for p in bf._PROVIDER_REGISTRY}
    assert "tokenin" in reg
    entry = reg["tokenin"]
    assert entry["tier"] == "free"
    assert entry["key_env"] == "TOKENIN_API_KEY"
    # UNIT 6 override makes the catalog the source of truth for models.
    assert entry["default_model"] == EXPECTED_MODELS[0]
    assert entry["models"] == EXPECTED_MODELS
    # A bare opus request can rotate onto tokenin's free opus.
    assert bf._MODEL_ALIASES["claude-opus-4-8"]["tokenin"] == "myt/claude-opus-4-8-free"


def test_router_from_env_registers_tokenin(monkeypatch):
    from packages.ai.router import (
        ProviderRouter,
        _FREE_CLOUD_PROVIDER_IDS,
        _KNOWN_FREE_HOSTS,
        _openai_url,
        provider_access_tier,
    )

    monkeypatch.setenv("TOKENIN_API_KEY", "sk-test-dummy")
    monkeypatch.delenv("TOKENIN_BASE_URL", raising=False)
    monkeypatch.delenv("TOKENIN_MODEL", raising=False)

    router = ProviderRouter.from_env()
    tk = [p for p in router.providers if p.provider_id == "tokenin"]
    assert tk, "tokenin should be registered when TOKENIN_API_KEY is set"
    provider = tk[0]

    # The request URL must resolve to the gateway's real endpoint, not a
    # doubled or bare-host variant.
    assert (
        _openai_url(provider.base_url, "/chat/completions")
        == "https://tokenin.my.id/v1/chat/completions"
    )
    assert provider.default_model == "myt/glm-5.3-free"

    # Classified free so the routing policy uses it before any paid escalation.
    assert "tokenin" in _FREE_CLOUD_PROVIDER_IDS
    assert "tokenin.my.id" in _KNOWN_FREE_HOSTS
    assert provider_access_tier(provider) == "free_cloud"


def test_router_omits_tokenin_without_key(monkeypatch):
    from packages.ai.router import ProviderRouter

    monkeypatch.delenv("TOKENIN_API_KEY", raising=False)
    router = ProviderRouter.from_env()
    assert not [p for p in router.providers if p.provider_id == "tokenin"]
