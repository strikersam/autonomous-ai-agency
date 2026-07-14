"""Tests for ``providers/colibri.py``.

Mirrors the style of the deleted ``tests/test_kimi_local_llama_provider.py``:
- Disabled by default (env-gated via COLIBRI_ENABLED).
- Build the right ``ProviderConfig`` when enabled.
- Status snapshot has the expected shape.
- The router registers it (and classifies it as ``free_cloud``).

The post-V2 import path ``packages.ai.router.ProviderConfig`` is the canonical
location after ``provider_router.py`` was migrated to ``packages/ai/router.py``
(PR #895).
"""
from __future__ import annotations

import pytest

from packages.ai.router import ProviderRouter, provider_access_tier

from providers.colibri import (
    COLIBRI_PROVIDER_ID,
    colibri_enabled,
    colibri_provider_config,
    colibri_status,
)


def test_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COLIBRI_ENABLED", raising=False)
    assert colibri_provider_config() is None
    assert colibri_enabled() is False


def test_enabled_returns_openai_compatible_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLIBRI_ENABLED", "true")
    monkeypatch.setenv("COLIBRI_URL",     "http://127.0.0.1:9000/v1")
    monkeypatch.setenv("COLIBRI_MODEL",   "glm-5.2-test")
    cfg = colibri_provider_config()
    assert cfg is not None
    assert cfg.provider_id == COLIBRI_PROVIDER_ID
    assert cfg.type == "openai-compatible"
    assert cfg.base_url == "http://127.0.0.1:9000/v1"
    assert cfg.default_model == "glm-5.2-test"
    assert cfg.api_key == ""        # local server has no auth


def test_priority_default_is_negative10(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLIBRI_ENABLED", "true")
    monkeypatch.delenv("COLIBRI_PRIORITY", raising=False)
    cfg = colibri_provider_config()
    assert cfg is not None
    assert cfg.priority == -10


def test_priority_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLIBRI_ENABLED",  "true")
    monkeypatch.setenv("COLIBRI_PRIORITY", "5")
    cfg = colibri_provider_config()
    assert cfg is not None
    assert cfg.priority == 5


def test_priority_garbage_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLIBRI_ENABLED",  "true")
    monkeypatch.setenv("COLIBRI_PRIORITY", "not-a-number")
    cfg = colibri_provider_config()
    assert cfg is not None
    assert cfg.priority == -10


def test_status_dict_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COLIBRI_ENABLED", raising=False)
    status = colibri_status()
    assert set(status.keys()) == {"provider_id", "enabled", "url", "model", "priority"}
    assert status["provider_id"] == COLIBRI_PROVIDER_ID
    assert status["enabled"] is False
    assert status["url"] == "http://localhost:8081/v1"
    assert status["model"] == "glm-5.2"


def test_status_reflects_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLIBRI_ENABLED", "true")
    monkeypatch.setenv("COLIBRI_MODEL",   "alt-model")
    status = colibri_status()
    assert status["enabled"] is True
    assert status["model"] == "alt-model"


def test_provider_id_constant_is_stable() -> None:
    """The provider_id is part of the public contract — pin it."""
    assert COLIBRI_PROVIDER_ID == "colibri"


def test_provider_router_picks_up_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Integration smoke: ProviderRouter.from_env() must include the new provider.

    Also asserts the tier classification is `free_cloud` (per _FREE_CLOUD_PROVIDER_IDS
    in packages/ai/router.py). Mis-classifying this provider as `windows_server`
    would group it with ngrok'd cloud servers, not with the free local cluster.
    """
    monkeypatch.setenv("COLIBRI_ENABLED", "true")
    monkeypatch.setenv("COLIBRI_URL",     "http://127.0.0.1:8765/v1")
    monkeypatch.setenv("COLIBRI_MODEL",   "glm-5.2")
    router = ProviderRouter.from_env()
    cfg = next((p for p in router.providers if p.provider_id == COLIBRI_PROVIDER_ID), None)
    assert cfg is not None, "colibri should appear in ProviderRouter.from_env() when enabled"
    assert cfg.base_url      == "http://127.0.0.1:8765/v1"
    assert cfg.default_model == "glm-5.2"
    assert cfg.priority      == -10  # COLIBRI_PRIORITY default
    assert cfg.api_key       == ""    # local — no auth
    assert provider_access_tier(cfg) == "free_cloud", (
        "colibri must be classified `free_cloud` (paired with other free local/cloud "
        "providers), not `windows_server` or `commercial`."
    )


def test_provider_router_absent_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default-off assertion: no env var → the provider is NOT in the router."""
    monkeypatch.delenv("COLIBRI_ENABLED", raising=False)
    router = ProviderRouter.from_env()
    ids = [p.provider_id for p in router.providers]
    assert COLIBRI_PROVIDER_ID not in ids, (
        "colibri must NOT appear when COLIBRI_ENABLED is unset"
    )
