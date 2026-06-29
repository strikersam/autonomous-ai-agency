"""Tests for app_settings — DB-persisted settings + onboarding-gate default.

These run against the SQLite storage backend (no MongoDB required) so they are
hermetic on any machine.
"""
from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def sqlite_store(tmp_path, monkeypatch):
    """Point db.get_store() at an isolated temp SQLite DB."""
    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "settings.db"))

    import db
    import packages.storage.sqlite as sqlite_store_mod

    importlib.reload(sqlite_store_mod)  # re-read SQLITE_DB_PATH
    db.reset_store()

    import packages.config.app_settings as app_settings
    importlib.reload(app_settings)
    app_settings.reset_cache_for_tests()
    yield app_settings
    db.reset_store()


@pytest.mark.asyncio
async def test_defaults_when_unset(sqlite_store):
    app_settings = sqlite_store
    assert await app_settings.onboarding_gate_enabled() is True
    assert await app_settings.ephemeral_ttl_hours() == 24


@pytest.mark.asyncio
async def test_set_and_get_persists(sqlite_store):
    app_settings = sqlite_store
    await app_settings.set_setting(
        app_settings.ONBOARDING_GATE_ENABLED_KEY, False, "admin@example.com"
    )
    assert await app_settings.onboarding_gate_enabled() is False
    # Cache mirrors the write — sync read agrees.
    assert app_settings.onboarding_gate_enabled_cached() is False


@pytest.mark.asyncio
async def test_ttl_roundtrip(sqlite_store):
    app_settings = sqlite_store
    await app_settings.set_setting(app_settings.EPHEMERAL_TTL_HOURS_KEY, 48, "admin")
    assert await app_settings.ephemeral_ttl_hours() == 48
    assert app_settings.ephemeral_ttl_hours_cached() == 48


@pytest.mark.asyncio
async def test_refresh_cache_warms_sync_readers(sqlite_store):
    app_settings = sqlite_store
    await app_settings.set_setting(app_settings.ONBOARDING_GATE_ENABLED_KEY, False, "admin")
    app_settings.reset_cache_for_tests()
    # After reset, the cached default is back to True until refreshed.
    assert app_settings.onboarding_gate_enabled_cached() is True
    await app_settings.refresh_cache()
    assert app_settings.onboarding_gate_enabled_cached() is False


def test_gate_default_controls_unlisted_user(sqlite_store, monkeypatch):
    """is_user_onboarding_allowed falls back to the global default for users
    with no explicit allow-list record."""
    app_settings = sqlite_store
    import packages.config.activation_api as activation_api

    # No per-user state file entries.
    monkeypatch.setattr(activation_api, "_load_onboarding_state", lambda: {})

    # Gate ON (default): an unlisted user is blocked.
    app_settings.reset_cache_for_tests()
    assert activation_api.is_user_onboarding_allowed("nobody@example.com") is False

    # Gate OFF: an unlisted user is allowed by default.
    app_settings._cache[app_settings.ONBOARDING_GATE_ENABLED_KEY] = False
    assert activation_api.is_user_onboarding_allowed("nobody@example.com") is True


def test_explicit_record_overrides_default(sqlite_store, monkeypatch):
    app_settings = sqlite_store
    import packages.config.activation_api as activation_api

    # Gate OFF would allow by default, but an explicit block wins.
    app_settings._cache[app_settings.ONBOARDING_GATE_ENABLED_KEY] = False
    monkeypatch.setattr(
        activation_api,
        "_load_onboarding_state",
        lambda: {"blocked@example.com": {"onboarding_allowed": False}},
    )
    assert activation_api.is_user_onboarding_allowed("blocked@example.com") is False
