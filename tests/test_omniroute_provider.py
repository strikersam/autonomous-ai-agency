"""tests/test_omniroute_provider.py — OmniRoute self-hosted gateway wiring.

Regression coverage for adding OmniRoute (github.com/diegosouzapw/OmniRoute) as
a free-tier brain provider (2026-09-11). OmniRoute is a self-hosted, MIT-licensed
OpenAI-compatible gateway that fronts many free-tier providers behind one
endpoint and does its own internal fan-out. Two properties are load-bearing and
each has a test here:

  1. **It is inert until deployed.** The provider is gated on ``OMNIROUTE_API_KEY``
     so a deploy that has not configured OmniRoute pays nothing — the registry
     build skips it and it never costs a failover attempt. This is also a
     security property: a networked OmniRoute with no token is an open LLM
     gateway, so requiring the token is deliberate.
  2. **It is one provider, one model.** OmniRoute fans out internally; nesting
     that inside this repo's failover would re-amplify 429s. So it is wired as a
     single ``auto`` model and kept out of ``RECOMMENDED_PROVIDER_PRIORITY`` — a
     bonus at the back of the free tier, never a default.
"""
from __future__ import annotations

import pytest

from packages.ai import brain_config
from packages.ai.brain_config import (
    PROVIDER_BASE_URL_ENV,
    PROVIDER_CANDIDATES,
    PROVIDER_DEFAULT_BASE_URL,
    PROVIDER_KEY_ENV,
    PROVIDER_PRESETS,
    RECOMMENDED_PROVIDER_PRIORITY,
    all_provider_ids,
    get_provider_tier,
)


def test_omniroute_in_literal_and_catalog():
    assert "omniroute" in all_provider_ids()
    assert PROVIDER_KEY_ENV["omniroute"] == "OMNIROUTE_API_KEY"
    assert PROVIDER_BASE_URL_ENV["omniroute"] == "OMNIROUTE_BASE_URL"
    assert PROVIDER_DEFAULT_BASE_URL["omniroute"] == "http://localhost:20128/v1"
    assert get_provider_tier("omniroute") == "free"


def test_omniroute_is_a_single_auto_model():
    """One provider, one model — OmniRoute does its own internal fan-out."""
    assert PROVIDER_CANDIDATES["omniroute"] == ["auto"]
    presets = PROVIDER_PRESETS["omniroute"]
    for role in ("planner", "executor", "verifier", "judge"):
        assert presets[role] == "auto"


def test_omniroute_is_top_of_the_free_tier_behind_the_nvidia_floor():
    """Promoted to the preferred free provider, but NVIDIA stays the floor.

    OmniRoute is the top of the free breadth tier (index 1), so once deployed it
    is tried first for capacity; NVIDIA stays at index 0 as the always-on
    reliable baseline that catches an OmniRoute outage instantly.
    """
    assert "omniroute" in RECOMMENDED_PROVIDER_PRIORITY
    assert RECOMMENDED_PROVIDER_PRIORITY.index("omniroute") == 1
    assert RECOMMENDED_PROVIDER_PRIORITY.index("nvidia") == 0
    # Ahead of the rest of the free cloud tier.
    for later in ("tokenin", "cerebras", "groq"):
        assert RECOMMENDED_PROVIDER_PRIORITY.index("omniroute") < \
            RECOMMENDED_PROVIDER_PRIORITY.index(later)


def test_brain_failover_registry_entry():
    import services.brain_failover as bf

    reg = {p["id"]: p for p in bf._PROVIDER_REGISTRY}
    assert "omniroute" in reg
    entry = reg["omniroute"]
    assert entry["tier"] == "free"
    assert entry["key_env"] == "OMNIROUTE_API_KEY"
    assert entry["base_url_env"] == "OMNIROUTE_BASE_URL"
    assert entry["default_model"] == "auto"
    assert entry["models"] == ["auto"]


def test_omniroute_is_inert_without_a_token(monkeypatch):
    """No OMNIROUTE_API_KEY → not in the chain at all, costing zero attempts.

    This is the whole point of gating on the key: an un-deployed OmniRoute must
    not sit in the failover chain failing every cycle.
    """
    monkeypatch.delenv("OMNIROUTE_API_KEY", raising=False)
    import services.brain_failover as bf

    mgr = bf.get_failover_manager()
    mgr._last_registry_build = 0.0
    mgr._build_registry()
    assert "omniroute" not in [p.id for p in mgr.get_providers()]


def test_omniroute_joins_the_free_tier_once_configured(monkeypatch):
    monkeypatch.setenv("OMNIROUTE_API_KEY", "test-scoped-token")
    monkeypatch.setenv("OMNIROUTE_BASE_URL", "https://omniroute.example.com/v1")
    import services.brain_failover as bf

    mgr = bf.get_failover_manager()
    mgr._last_registry_build = 0.0
    mgr._build_registry()
    by_id = {p.id: p for p in mgr.get_providers()}
    assert "omniroute" in by_id
    entry = by_id["omniroute"]
    assert entry.tier == "free"
    assert entry.default_model == "auto"
    assert entry.base_url == "https://omniroute.example.com/v1"


def test_omniroute_base_url_falls_back_to_localhost(monkeypatch):
    """Without an explicit base URL it points at the local default, never blank."""
    monkeypatch.setenv("OMNIROUTE_API_KEY", "test-scoped-token")
    monkeypatch.delenv("OMNIROUTE_BASE_URL", raising=False)
    import services.brain_failover as bf

    mgr = bf.get_failover_manager()
    mgr._last_registry_build = 0.0
    mgr._build_registry()
    entry = {p.id: p for p in mgr.get_providers()}.get("omniroute")
    assert entry is not None
    assert entry.base_url == "http://localhost:20128/v1"
