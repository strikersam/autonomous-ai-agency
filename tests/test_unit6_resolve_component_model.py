"""tests/test_unit6_resolve_component_model.py — UNIT 6 regression tests.

Verifies that:
  1. ``resolve_component_model()`` returns the catalog preset when no DB
     config is cached.
  2. ``resolve_component_model()`` honours a per-call ``requested`` override.
  3. ``resolve_component_model()`` honours a saved DB brain config when
     the requested provider matches the active primary.
  4. ``resolve_component_model()`` falls back to the catalog preset when
     the requested provider differs from the active primary.
  5. ``resolve_component_model()`` falls back to the env var when no DB
     and no catalog preset.
  6. ``resolve_component_model()`` returns the safe default on unknown
     role / unknown provider.
  7. ``resolve_component_role_models()`` returns all four roles.
  8. ``telegram_bot.cmd_setbrain`` uses the catalog (no inline preset table).
  9. ``backend/server._default_agent_role_models`` uses the catalog (no
     hardcoded model ids).
 10. ``services/brain_failover._PROVIDER_REGISTRY`` derives ``default_model``
     and ``models`` from the catalog.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from packages.ai.brain_config import (
    BrainConfig,
    PROVIDER_CANDIDATES,
    PROVIDER_PRESETS,
    SAFE_DEFAULT_MODEL,
    _CACHE_TTL_SECONDS,
    _store,
    invalidate_brain_config_cache,
    resolve_component_model,
    resolve_component_role_models,
)


# ── 1. Catalog preset when no DB ───────────────────────────────────────────


def test_resolve_returns_catalog_preset_when_no_db():
    """With no DB cache, the resolver returns the catalog preset."""
    invalidate_brain_config_cache()
    try:
        # Force a clean state.
        import packages.ai.brain_config as mod
        mod._store = None
        m = resolve_component_model(
            component="test",
            role="planner",
            provider="nvidia",
        )
        assert m == PROVIDER_PRESETS["nvidia"]["planner"]
    finally:
        pass


def test_resolve_returns_catalog_preset_for_each_provider():
    """Every catalog provider's planner preset is returned verbatim."""
    invalidate_brain_config_cache()
    import packages.ai.brain_config as mod
    mod._store = None
    for provider, presets in PROVIDER_PRESETS.items():
        m = resolve_component_model("test", "planner", provider=provider)
        assert m == presets["planner"]


# ── 2. Per-call override ───────────────────────────────────────────────────


def test_resolve_requested_override_wins():
    """A non-empty `requested` is returned verbatim."""
    m = resolve_component_model(
        component="test",
        role="planner",
        provider="nvidia",
        requested="custom/model-id",
    )
    assert m == "custom/model-id"


def test_resolve_requested_empty_string_falls_through():
    """An empty `requested` is treated as None (falls through to catalog)."""
    invalidate_brain_config_cache()
    import packages.ai.brain_config as mod
    mod._store = None
    m = resolve_component_model(
        component="test",
        role="planner",
        provider="nvidia",
        requested="   ",
    )
    assert m == PROVIDER_PRESETS["nvidia"]["planner"]


# ── 3. DB cache honours matching provider ──────────────────────────────────


def test_resolve_db_cache_used_when_provider_matches(monkeypatch):
    """When the DB cache is fresh AND provider matches the active primary,
    the DB-saved model wins over the catalog preset."""
    import packages.ai.brain_config as mod

    fake_cfg = BrainConfig(
        primary_provider="nvidia",
        planner_model="db-saved-planner",
        executor_model="db-saved-executor",
        verifier_model="db-saved-verifier",
        judge_model="db-saved-judge",
    )
    fake_store = mod.BrainConfigStore()
    fake_store._cache = fake_cfg
    fake_store._cache_at = time.monotonic()
    monkeypatch.setattr(mod, "_store", fake_store)

    m = resolve_component_model(
        component="test",
        role="planner",
        provider="nvidia",  # matches the DB primary
    )
    assert m == "db-saved-planner"


def test_resolve_db_cache_skipped_when_provider_differs(monkeypatch):
    """When the DB primary differs from the requested provider, the catalog
    preset for the requested provider wins (not the DB-saved model)."""
    import packages.ai.brain_config as mod

    fake_cfg = BrainConfig(
        primary_provider="nvidia",
        planner_model="db-saved-planner",
    )
    fake_store = mod.BrainConfigStore()
    fake_store._cache = fake_cfg
    fake_store._cache_at = time.monotonic()
    monkeypatch.setattr(mod, "_store", fake_store)

    m = resolve_component_model(
        component="test",
        role="planner",
        provider="cerebras",  # differs from DB primary
    )
    assert m == PROVIDER_PRESETS["cerebras"]["planner"]


def test_resolve_db_cache_used_when_provider_none(monkeypatch):
    """When `provider` is None, the DB primary's saved model wins."""
    import packages.ai.brain_config as mod

    fake_cfg = BrainConfig(
        primary_provider="cerebras",
        planner_model="db-saved-planner",
    )
    fake_store = mod.BrainConfigStore()
    fake_store._cache = fake_cfg
    fake_store._cache_at = time.monotonic()
    monkeypatch.setattr(mod, "_store", fake_store)

    m = resolve_component_model(
        component="test",
        role="planner",
        provider=None,
    )
    assert m == "db-saved-planner"


# ── 5. Env var fallback ────────────────────────────────────────────────────


def test_resolve_env_var_when_no_db_no_provider(monkeypatch):
    """With no DB cache and no provider, the env var is consulted."""
    import packages.ai.brain_config as mod
    monkeypatch.setattr(mod, "_store", None)
    monkeypatch.setenv("AGENT_PLANNER_MODEL", "env-override-model")
    try:
        m = resolve_component_model(
            component="test",
            role="planner",
            provider=None,
        )
        assert m == "env-override-model"
    finally:
        monkeypatch.delenv("AGENT_PLANNER_MODEL", raising=False)


# ── 6. Safe default fallback ───────────────────────────────────────────────


def test_resolve_unknown_role_returns_safe_default():
    """An unknown role returns the safe default rather than raising."""
    invalidate_brain_config_cache()
    import packages.ai.brain_config as mod
    mod._store = None
    m = resolve_component_model(
        component="test",
        role="not-a-real-role",
        provider="nvidia",
    )
    assert m == SAFE_DEFAULT_MODEL


def test_resolve_unknown_provider_returns_safe_default(monkeypatch):
    """An unknown provider (no catalog preset) falls through to env / safe default."""
    import packages.ai.brain_config as mod
    monkeypatch.setattr(mod, "_store", None)
    monkeypatch.delenv("AGENT_PLANNER_MODEL", raising=False)
    monkeypatch.delenv("NVIDIA_DEFAULT_MODEL", raising=False)
    m = resolve_component_model(
        component="test",
        role="planner",
        provider="not-a-real-provider",
    )
    assert m == SAFE_DEFAULT_MODEL


def test_resolve_default_role_is_synonym_for_executor():
    """The 'default' role is treated as 'executor'."""
    invalidate_brain_config_cache()
    import packages.ai.brain_config as mod
    mod._store = None
    m = resolve_component_model(
        component="test",
        role="default",
        provider="nvidia",
    )
    assert m == PROVIDER_PRESETS["nvidia"]["executor"]


# ── 7. resolve_component_role_models ───────────────────────────────────────


def test_resolve_all_roles_returns_four_roles():
    """``resolve_component_role_models`` returns all four role models."""
    invalidate_brain_config_cache()
    import packages.ai.brain_config as mod
    mod._store = None
    out = resolve_component_role_models(
        component="test",
        provider="nvidia",
    )
    assert set(out.keys()) == {"planner", "executor", "verifier", "judge"}
    for role, model in out.items():
        assert model == PROVIDER_PRESETS["nvidia"][role]


def test_resolve_all_roles_with_requested_override():
    """Per-role ``requested`` overrides win for each role independently."""
    out = resolve_component_role_models(
        component="test",
        provider="nvidia",
        requested={"planner": "override-planner"},
    )
    assert out["planner"] == "override-planner"
    # Other roles fall through to the catalog.
    assert out["executor"] == PROVIDER_PRESETS["nvidia"]["executor"]


# ── 8. telegram_bot.cmd_setbrain uses the catalog ──────────────────────────


def test_telegram_bot_cmd_setbrain_uses_catalog_no_inline_presets():
    """``cmd_setbrain`` must NOT have a hardcoded inline preset table.

    Before UNIT 6, the function had a 4-provider ``presets = {...}`` dict
    that mirrored ``PROVIDER_PRESETS``. UNIT 6 replaced it with a call to
    ``resolve_component_role_models`` so the catalog is the single source
    of truth.
    """
    src = Path(__file__).resolve().parent.parent / "telegram_bot.py"
    src = src.read_text(encoding="utf-8")
    # Find the cmd_setbrain function body — use a regex to grab the whole
    # function (the docstring contains \n\n so a naive \n\n search stops
    # too early).
    import re
    m = re.search(r"async def cmd_setbrain\(.*?(?=\nasync def |\ndef |\nclass )", src, re.DOTALL)
    assert m, "cmd_setbrain function not found"
    body = m.group(0)
    # The old hardcoded preset table is gone.
    assert '"cerebras": {' not in body, (
        "cmd_setbrain still has a hardcoded cerebras preset block"
    )
    # The new catalog resolver is used.
    assert "resolve_component_role_models" in body
    # The valid set is derived from all_provider_ids() (catalog-driven).
    assert "all_provider_ids()" in body


def test_telegram_bot_cmd_setbrain_accepts_all_14_providers():
    """``cmd_setbrain`` must accept any of the 14 catalog providers, not
    just the original 4 (cerebras/groq/nvidia/ollama)."""
    src = Path(__file__).resolve().parent.parent / "telegram_bot.py"
    src = src.read_text(encoding="utf-8")
    import re
    m = re.search(r"async def cmd_setbrain\(.*?(?=\nasync def |\ndef |\nclass )", src, re.DOTALL)
    assert m
    body = m.group(0)
    # The old hardcoded 4-element set is gone.
    assert 'valid = {"cerebras", "groq", "nvidia", "ollama"}' not in body
    # The new valid set is derived from all_provider_ids().
    assert "set(all_provider_ids())" in body


# ── 9. backend/server._default_agent_role_models uses the catalog ──────────


def test_server_default_agent_role_models_uses_catalog():
    """``_default_agent_role_models`` must NOT have hardcoded model ids
    in its executable body (the docstring may reference them for context).

    Before UNIT 6, the function had ``"qwen/qwen3-coder-480b-a35b-instruct"``
    and ``"deepseek-ai/deepseek-v4-pro"`` hardcoded as return values. UNIT 6
    replaced the body with a call to ``resolve_component_model``.
    """
    src = Path(__file__).resolve().parent.parent / "backend" / "server.py"
    src = src.read_text(encoding="utf-8")
    import re
    m = re.search(
        r"def _default_agent_role_models\(\).*?(?=\nasync def _resolve_user_agent_role_models)",
        src,
        re.DOTALL,
    )
    assert m
    body = m.group(0)
    # Strip the docstring (between the first """ and the next """) so we
    # only check the executable body for stale model ids.
    body_no_doc = re.sub(r'"""[^"]*"""', '', body, count=1, flags=re.DOTALL)
    # The old hardcoded stale model ids are gone from the executable body.
    assert "qwen/qwen3-coder-480b-a35b-instruct" not in body_no_doc, (
        "_default_agent_role_models still has the stale qwen/qwen3-coder model id in its body"
    )
    assert "deepseek-ai/deepseek-v4-pro" not in body_no_doc, (
        "_default_agent_role_models still has the stale deepseek-v4-pro model id in its body"
    )
    # The new catalog resolver is used.
    assert "resolve_component_model" in body


# ── 10. brain_failover._PROVIDER_REGISTRY derives from catalog ────────────


def test_brain_failover_registry_default_model_matches_catalog():
    """Every provider in the registry has ``default_model`` == the first
    entry in ``PROVIDER_CANDIDATES`` (the catalog preset)."""
    from services.brain_failover import _PROVIDER_REGISTRY
    for entry in _PROVIDER_REGISTRY:
        pid = entry["id"]
        cands = PROVIDER_CANDIDATES.get(pid)
        if cands:
            assert entry["default_model"] == cands[0], (
                f"provider {pid!r}: registry default_model={entry['default_model']!r} "
                f"!= catalog first candidate {cands[0]!r}"
            )


def test_brain_failover_registry_models_matches_catalog():
    """Every provider in the registry has ``models`` == the catalog's
    candidate list."""
    from services.brain_failover import _PROVIDER_REGISTRY
    for entry in _PROVIDER_REGISTRY:
        pid = entry["id"]
        cands = PROVIDER_CANDIDATES.get(pid)
        if cands:
            assert entry["models"] == cands, (
                f"provider {pid!r}: registry models={entry['models']!r} "
                f"!= catalog candidates {cands!r}"
            )
