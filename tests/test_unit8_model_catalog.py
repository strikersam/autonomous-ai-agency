"""tests/test_unit8_model_catalog.py — UNIT 8 regression tests.

Verifies that:
  1. The ``FREELLM_API_MODEL_CATALOG_ENABLED`` flag defaults to ON.
  2. ``is_catalog_enabled()`` returns True by default, False when the
     env var is set to a non-``true`` value.
  3. ``ModelCatalogStore._build_in_memory()`` builds a complete catalog
     with all 15 providers, the safe default, and the recommended
     priority list.
  4. Each catalog provider entry has the expected fields
     (display_name, tier, key_env, candidates, etc.).
  5. The ``active_brain`` block is populated when the brain config cache
     is fresh; empty otherwise.
  6. ``GET /api/catalog/models`` returns 503 when the flag is OFF.
  7. ``GET /api/catalog/models`` returns the catalog when the flag is ON
     (which is the default).
  8. ``POST /api/admin/maintenance/sync-catalog`` requires admin auth.
  9. ``POST /api/admin/maintenance/sync-catalog`` returns 503 when the
     flag is OFF.
 10. ``POST /api/admin/maintenance/sync-catalog`` rebuilds + persists
     when the flag is ON.
 11. The catalog mirror never raises on storage errors (graceful
     degradation to in-memory build).
 12. The catalog is advisory-only — ``resolve_component_model()`` is
     unaffected by the catalog mirror's state.
"""
from __future__ import annotations

import os
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.ai.brain_config import (
    BrainConfig,
    PROVIDER_CANDIDATES,
    PROVIDER_DISPLAY_NAMES,
    PROVIDER_KEY_ENV,
    PROVIDER_PRESETS,
    PROVIDER_TIERS,
    RECOMMENDED_PROVIDER_PRIORITY,
    SAFE_DEFAULT_MODEL,
    SAFE_DEFAULT_PROVIDER,
    all_provider_ids,
)
from packages.ai.model_catalog import (
    CatalogActiveBrain,
    CatalogMirror,
    CatalogProviderEntry,
    ModelCatalogStore,
    invalidate_catalog_cache,
    is_catalog_enabled,
)


# ── 1-2. Flag default + setter ─────────────────────────────────────────────


def test_catalog_flag_defaults_on(monkeypatch):
    """The flag must default to ON (UNIT 8 — rollout complete, flag is the
    rollback lever)."""
    monkeypatch.delenv("FREELLM_API_MODEL_CATALOG_ENABLED", raising=False)
    # Need to bypass lru_cache by constructing a fresh Settings.
    from packages.config.settings import Settings
    s = Settings()
    assert s.freellm_api_model_catalog_enabled == "true"
    assert s.is_freellm_api_model_catalog_enabled is True


def test_is_catalog_enabled_returns_true_by_default(monkeypatch):
    monkeypatch.delenv("FREELLM_API_MODEL_CATALOG_ENABLED", raising=False)
    # Force a fresh settings instance.
    from packages.config.settings import Settings
    # Bypass lru_cache by constructing fresh.
    s = Settings()
    assert s.is_freellm_api_model_catalog_enabled is True


def test_is_catalog_enabled_returns_true_when_set(monkeypatch):
    """Setting FREELLM_API_MODEL_CATALOG_ENABLED=true enables the flag."""
    monkeypatch.setenv("FREELLM_API_MODEL_CATALOG_ENABLED", "true")
    from packages.config.settings import Settings
    s = Settings()
    assert s.is_freellm_api_model_catalog_enabled is True


def test_is_catalog_enabled_case_insensitive(monkeypatch):
    """The flag value is lowercased so 'TRUE' / 'True' also enable."""
    for val in ("TRUE", "True", "true"):
        monkeypatch.setenv("FREELLM_API_MODEL_CATALOG_ENABLED", val)
        from packages.config.settings import Settings
        s = Settings()
        assert s.is_freellm_api_model_catalog_enabled is True, f"value={val!r}"


def test_is_catalog_enabled_other_values_are_false(monkeypatch):
    """Any value other than 'true' (case-insensitive) is treated as False."""
    for val in ("false", "0", "off", "no", "", "yes"):
        monkeypatch.setenv("FREELLM_API_MODEL_CATALOG_ENABLED", val)
        from packages.config.settings import Settings
        s = Settings()
        assert s.is_freellm_api_model_catalog_enabled is False, f"value={val!r}"


# ── 3. _build_in_memory builds a complete catalog ──────────────────────────


def test_build_in_memory_returns_catalog_with_all_15_providers():
    """The catalog mirror includes every provider from the BrainProvider Literal."""
    store = ModelCatalogStore()
    mirror = store._build_in_memory()
    assert isinstance(mirror, CatalogMirror)
    assert len(mirror.providers) == 15
    actual_ids = {p.provider_id for p in mirror.providers}
    assert actual_ids == set(all_provider_ids())


def test_build_in_memory_has_safe_default():
    store = ModelCatalogStore()
    mirror = store._build_in_memory()
    assert mirror.safe_default == {
        "provider": SAFE_DEFAULT_PROVIDER,
        "model": SAFE_DEFAULT_MODEL,
    }


def test_build_in_memory_has_recommended_priority():
    store = ModelCatalogStore()
    mirror = store._build_in_memory()
    assert mirror.recommended_priority == list(RECOMMENDED_PROVIDER_PRIORITY)


def test_build_in_memory_has_mirrored_at_timestamp():
    store = ModelCatalogStore()
    mirror = store._build_in_memory()
    assert mirror.mirrored_at
    # ISO 8601 UTC format: 2026-07-11T14:22:48Z
    assert mirror.mirrored_at.endswith("Z")
    assert "T" in mirror.mirrored_at


# ── 4. Per-provider entry fields ───────────────────────────────────────────


def test_build_in_memory_provider_entry_has_all_fields():
    store = ModelCatalogStore()
    mirror = store._build_in_memory()
    nvidia = next(p for p in mirror.providers if p.provider_id == "nvidia")
    assert nvidia.display_name == PROVIDER_DISPLAY_NAMES["nvidia"]
    assert nvidia.tier == PROVIDER_TIERS["nvidia"]
    assert nvidia.key_env == PROVIDER_KEY_ENV["nvidia"]
    assert nvidia.role_presets == PROVIDER_PRESETS["nvidia"]
    assert nvidia.candidates == PROVIDER_CANDIDATES["nvidia"]
    assert nvidia.default_base_url  # non-empty


def test_build_in_memory_provider_entry_key_present_reflects_env(monkeypatch):
    """``key_present`` is True when the env var is set."""
    monkeypatch.setenv("NVIDIA_API_KEY", "fake-nv")
    store = ModelCatalogStore()
    mirror = store._build_in_memory()
    nvidia = next(p for p in mirror.providers if p.provider_id == "nvidia")
    assert nvidia.key_present is True


def test_build_in_memory_provider_entry_key_present_false_when_unset(monkeypatch):
    """``key_present`` is False when the env var is not set."""
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVidiaApiKey", raising=False)
    store = ModelCatalogStore()
    mirror = store._build_in_memory()
    nvidia = next(p for p in mirror.providers if p.provider_id == "nvidia")
    assert nvidia.key_present is False


def test_build_in_memory_ollama_key_present_always_true():
    """Ollama is local — ``key_present`` is always True."""
    store = ModelCatalogStore()
    mirror = store._build_in_memory()
    ollama = next(p for p in mirror.providers if p.provider_id == "ollama")
    assert ollama.key_present is True
    assert ollama.tier == "local"


# ── 5. active_brain block ──────────────────────────────────────────────────


def test_build_in_memory_active_brain_empty_when_cache_cold(monkeypatch):
    """When the brain config cache is cold, active_brain is empty."""
    import packages.ai.brain_config as mod
    monkeypatch.setattr(mod, "_store", None)
    store = ModelCatalogStore()
    mirror = store._build_in_memory()
    assert mirror.active_brain.primary_provider == ""


def test_build_in_memory_active_brain_populated_when_cache_fresh(monkeypatch):
    """When the brain config cache is fresh, active_brain reflects it."""
    import packages.ai.brain_config as mod
    fake_cfg = BrainConfig(
        primary_provider="cerebras",
        planner_model="cb-planner",
        executor_model="cb-executor",
        verifier_model="cb-verifier",
        judge_model="cb-judge",
        updated_at="2026-07-11T00:00:00Z",
        updated_by="test",
    )
    fake_store = mod.BrainConfigStore()
    fake_store._cache = fake_cfg
    fake_store._cache_at = time.monotonic()
    monkeypatch.setattr(mod, "_store", fake_store)

    store = ModelCatalogStore()
    mirror = store._build_in_memory()
    assert mirror.active_brain.primary_provider == "cerebras"
    assert mirror.active_brain.planner_model == "cb-planner"
    assert mirror.active_brain.updated_by == "test"

    # The cerebras entry is marked active=True.
    cerebras = next(p for p in mirror.providers if p.provider_id == "cerebras")
    assert cerebras.active is True
    # All other providers are active=False.
    for p in mirror.providers:
        if p.provider_id != "cerebras":
            assert p.active is False


# ── 6. GET /api/catalog/models returns 503 when flag OFF ──────────────────


def test_get_catalog_models_returns_503_when_flag_off(app_client, monkeypatch):
    """The endpoint returns 503 when the flag is explicitly set to OFF.

    The flag defaults to ON (UNIT 8 rollout complete), so this test must
    explicitly set it to ``false`` to verify the 503 path.
    """
    monkeypatch.setattr(
        "packages.ai.model_catalog.is_catalog_enabled", lambda: False
    )
    r = app_client.get("/api/catalog/models")
    assert r.status_code == 503
    body = r.json()
    assert body["ok"] is False
    assert body["enabled"] is False
    assert "FREELLM_API_MODEL_CATALOG_ENABLED" in body["detail"]


# ── 7. GET /api/catalog/models returns catalog when flag ON ────────────────


def test_get_catalog_models_returns_catalog_when_flag_on(app_client, monkeypatch):
    """The endpoint returns the catalog when the flag is ON."""
    # Force the flag ON by monkeypatching is_catalog_enabled.
    import packages.ai.model_catalog as mc
    monkeypatch.setattr(mc, "is_catalog_enabled", lambda: True)
    # Also patch the import inside the route handler.
    import backend.server as srv
    monkeypatch.setattr(
        "packages.ai.model_catalog.is_catalog_enabled", lambda: True
    )

    r = app_client.get("/api/catalog/models")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["enabled"] is True
    catalog = body["catalog"]
    assert catalog["catalog_version"] == 1
    assert len(catalog["providers"]) == 15
    assert catalog["safe_default"]["provider"] == "nvidia"
    assert catalog["safe_default"]["model"] == "z-ai/glm-5.2"


# ── 8. POST sync-catalog requires admin auth ──────────────────────────────


def test_sync_catalog_requires_auth(unauth_client):
    r = unauth_client.post("/api/admin/maintenance/sync-catalog")
    assert r.status_code == 401


def test_sync_catalog_requires_admin_role(non_admin_client):
    r = non_admin_client.post("/api/admin/maintenance/sync-catalog")
    assert r.status_code == 403


# ── 9. POST sync-catalog returns 503 when flag OFF ────────────────────────


def test_sync_catalog_returns_503_when_flag_off(app_client, monkeypatch):
    """When the flag is explicitly OFF, the sync endpoint returns 503."""
    monkeypatch.setattr(
        "packages.ai.model_catalog.is_catalog_enabled", lambda: False
    )
    r = app_client.post("/api/admin/maintenance/sync-catalog")
    assert r.status_code == 503
    body = r.json()
    assert body["ok"] is False
    assert body["enabled"] is False


# ── 10. POST sync-catalog rebuilds + persists when flag ON ─────────────────


def test_sync_catalog_rebuilds_when_flag_on(app_client, monkeypatch):
    """When the flag is ON, the sync endpoint rebuilds the catalog and
    returns it with ``ok=True``."""
    monkeypatch.setattr(
        "packages.ai.model_catalog.is_catalog_enabled", lambda: True
    )
    r = app_client.post("/api/admin/maintenance/sync-catalog")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["enabled"] is True
    catalog = body["catalog"]
    assert len(catalog["providers"]) == 15
    assert catalog["mirrored_at"]


# ── 11. Graceful degradation ───────────────────────────────────────────────


def test_get_catalog_never_raises_on_storage_error(monkeypatch):
    """When both Mongo and sqlite fail, the catalog is built in-memory."""
    store = ModelCatalogStore()
    # Force Mongo to raise — patch the get_db symbol inside the
    # model_catalog module's import scope (which is `from backend.server
    # import get_db` done lazily inside the method).
    def boom_get_db():
        raise RuntimeError("mongo is down")
    # Patch the late import path. The _load_unlocked method does
    # `from backend.server import get_db` — patch backend.server.get_db.
    import backend.server as srv
    monkeypatch.setattr(srv, "get_db", boom_get_db)
    # Force sqlite to return None (no mirror file).
    monkeypatch.setattr(store, "_load_sqlite_mirror", lambda: None)
    # The async get_catalog must not raise — it falls back to in-memory.
    import asyncio
    catalog = asyncio.run(store.get_catalog())
    assert isinstance(catalog, CatalogMirror)
    assert len(catalog.providers) == 15


def test_sync_catalog_never_raises_on_storage_error(monkeypatch):
    """When persist fails, sync_catalog still returns the in-memory catalog."""
    store = ModelCatalogStore()
    def boom_get_db():
        raise RuntimeError("mongo is down")
    import backend.server as srv
    monkeypatch.setattr(srv, "get_db", boom_get_db)
    monkeypatch.setattr(store, "_save_sqlite_mirror", lambda cfg: None)
    import asyncio
    catalog = asyncio.run(store.sync_catalog(actor="test"))
    assert isinstance(catalog, CatalogMirror)
    assert len(catalog.providers) == 15


# ── 12. Advisory-only — doesn't affect routing ────────────────────────────


def test_catalog_mirror_does_not_affect_resolve_component_model(monkeypatch):
    """The catalog mirror is advisory — ``resolve_component_model()`` is
    unaffected by the mirror's state. The catalog preset is returned
    regardless of what's in the mirror."""
    from packages.ai.brain_config import resolve_component_model
    import packages.ai.brain_config as mod
    monkeypatch.setattr(mod, "_store", None)

    # Build a mirror and persist it (best-effort).
    store = ModelCatalogStore()
    mirror = store._build_in_memory()
    # The mirror has all 15 providers. resolve_component_model should
    # still return the catalog preset, NOT consult the mirror.
    m = resolve_component_model("test", "planner", provider="nvidia")
    assert m == PROVIDER_PRESETS["nvidia"]["planner"]
    # The mirror's presence didn't change the resolution.
    assert mirror.providers[0].role_presets["planner"] == m


def test_catalog_mirror_has_no_public_write_methods():
    """The CatalogMirror API has no public write methods — it's a snapshot.

    The read-only contract is enforced by the API surface (no public
    setters or mutators), not by the Pydantic model itself.
    """
    # Get the CatalogMirror's own methods (not inherited from BaseModel).
    own_methods = [
        name for name in vars(CatalogMirror)
        if not name.startswith("_") and callable(vars(CatalogMirror)[name])
    ]
    # CatalogMirror doesn't define any public methods of its own — it's
    # a pure data container. Pydantic's BaseModel methods (model_dump,
    # model_validate, etc.) are inherited, not "write" methods in the
    # mutable-state sense.
    assert own_methods == [], (
        f"CatalogMirror should not define public methods; found: {own_methods}"
    )
