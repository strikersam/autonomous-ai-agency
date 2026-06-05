"""Tests for the free Kimi web-bridge provider.

The bridge must be: (1) absent unless KIMI_BRIDGE_ENABLED is set, (2) classified
FREE so the routing policy never treats it as paid escalation, and (3) present in
ProviderRouter.from_env() when enabled — which is what lets internal_agent / Hermes
reach a capable Kimi model without a paid API key.
"""

from __future__ import annotations

import pytest

from provider_router import ProviderRouter, provider_access_tier
from providers.kimi_bridge import (
    KIMI_BRIDGE_PROVIDER_ID,
    kimi_bridge_provider_config,
    kimi_bridge_status,
)


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("KIMI_BRIDGE_ENABLED", raising=False)
    assert kimi_bridge_provider_config() is None
    assert kimi_bridge_status()["enabled"] is False


def test_enabled_returns_free_classified_config(monkeypatch):
    monkeypatch.setenv("KIMI_BRIDGE_ENABLED", "true")
    monkeypatch.setenv("KIMI_BRIDGE_URL", "http://bridge.local:9000/v1")
    cfg = kimi_bridge_provider_config()
    assert cfg is not None
    assert cfg.provider_id == KIMI_BRIDGE_PROVIDER_ID
    assert cfg.type == "openai-compatible"
    assert cfg.base_url == "http://bridge.local:9000/v1"
    # Crucially: the routing policy must see this as a free (non-paid) provider.
    assert provider_access_tier(cfg) == "free_cloud"


def test_browser_mode_requires_ack(monkeypatch):
    monkeypatch.setenv("KIMI_BRIDGE_ENABLED", "true")
    monkeypatch.setenv("KIMI_BRIDGE_MODE", "browser")
    monkeypatch.delenv("KIMI_BRIDGE_BROWSER", raising=False)
    # Browser mode is refused until explicitly acknowledged (no implicit browser).
    assert kimi_bridge_provider_config() is None

    monkeypatch.setenv("KIMI_BRIDGE_BROWSER", "true")
    assert kimi_bridge_provider_config() is not None


def test_present_in_from_env_when_enabled(monkeypatch):
    monkeypatch.setenv("KIMI_BRIDGE_ENABLED", "true")
    monkeypatch.delenv("KIMI_BRIDGE_MODE", raising=False)
    router = ProviderRouter.from_env()
    ids = [p.provider_id for p in router.providers]
    assert KIMI_BRIDGE_PROVIDER_ID in ids


def test_absent_in_from_env_when_disabled(monkeypatch):
    monkeypatch.delenv("KIMI_BRIDGE_ENABLED", raising=False)
    router = ProviderRouter.from_env()
    ids = [p.provider_id for p in router.providers]
    assert KIMI_BRIDGE_PROVIDER_ID not in ids
