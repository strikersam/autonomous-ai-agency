"""tests/test_brain_resolution.py — call-time resolver precedence tests.

Pins the contract from docs/plans/db-brain-switcher.md §3b:

  ``_resolve_role_model(role, requested)`` resolves in this order:
    1. explicit ``requested_model``
    2. BrainConfig (DB) — when the admin UI has applied a config
    3. env var (``AGENT_<ROLE>_MODEL`` / ``NVIDIA_DEFAULT_MODEL``)
    4. safe default (``nvidia/llama-3.3-nemotron-super-49b-v1``)

  The DB change takes effect without a re-import (call-time resolution),
  so an admin Apply is picked up by the next agent run.

Also pins:
  * ``brain_policy.resolve_active_brain`` honours a DB-stored BrainConfig
    when it has been applied (``updated_at`` is set).
  * The env override ``AGENT_LLM_BASE_URL`` still wins over everything
    (existing contract from test_brain_resolver.py is preserved).
"""
from __future__ import annotations

import asyncio
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch as mock_patch

import pytest

from services.brain_config_store import (
    BrainConfig,
    BrainConfigStore,
    SAFE_DEFAULT_MODEL,
    invalidate_brain_config_cache,
    resolve_role_model_sync,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    """Strip env vars that would change role resolution + reset the singleton."""
    import services.brain_config_store as mod
    monkeypatch.setattr(mod, "_store", None)
    # Isolate the sqlite mirror to a per-test tmp dir so a previous test's
    # persisted config doesn't leak into the next.
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "test.db"))
    for v in (
        "AGENT_PLANNER_MODEL", "AGENT_EXECUTOR_MODEL",
        "AGENT_VERIFIER_MODEL", "AGENT_JUDGE_MODEL",
        "NVIDIA_DEFAULT_MODEL", "AGENT_LLM_BASE_URL",
        "AGENT_LLM_API_KEY", "AGENT_LLM_MODEL",
    ):
        monkeypatch.delenv(v, raising=False)


# ── Precedence ──────────────────────────────────────────────────────────────


def test_requested_wins_over_everything(monkeypatch):
    """An explicit requested_model wins over DB, env, and the safe default."""
    monkeypatch.setenv("AGENT_PLANNER_MODEL", "env-planner")
    # Prime the cache with a DB value.
    store = BrainConfigStore()
    store._cache = BrainConfig(
        primary_provider="cerebras",
        planner_model="db-planner",
        executor_model="db-executor",
        verifier_model="db-verifier",
        judge_model="db-judge",
        updated_at="2026-06-26T00:00:00Z",
        updated_by="test",
    )
    store._cache_at = time.monotonic()
    import services.brain_config_store as mod
    mod._store = store

    assert resolve_role_model_sync("planner", "explicit-request") == "explicit-request"


def test_db_overrides_env(monkeypatch):
    """When the cache holds a DB config, it wins over env vars."""
    monkeypatch.setenv("AGENT_PLANNER_MODEL", "env-planner")
    store = BrainConfigStore()
    store._cache = BrainConfig(
        primary_provider="cerebras",
        planner_model="db-planner",
        executor_model="db-executor",
        verifier_model="db-verifier",
        judge_model="db-judge",
        updated_at="2026-06-26T00:00:00Z",
        updated_by="test",
    )
    store._cache_at = time.monotonic()
    import services.brain_config_store as mod
    mod._store = store

    assert resolve_role_model_sync("planner") == "db-planner"
    assert resolve_role_model_sync("executor") == "db-executor"
    assert resolve_role_model_sync("verifier") == "db-verifier"
    assert resolve_role_model_sync("judge") == "db-judge"


def test_env_wins_when_no_db(monkeypatch):
    """With no DB cache, the env var is the next source."""
    monkeypatch.setenv("AGENT_PLANNER_MODEL", "env-planner")
    monkeypatch.setenv("AGENT_EXECUTOR_MODEL", "env-executor")
    monkeypatch.setenv("AGENT_VERIFIER_MODEL", "env-verifier")
    monkeypatch.setenv("AGENT_JUDGE_MODEL", "env-judge")

    assert resolve_role_model_sync("planner") == "env-planner"
    assert resolve_role_model_sync("executor") == "env-executor"
    assert resolve_role_model_sync("verifier") == "env-verifier"
    assert resolve_role_model_sync("judge") == "env-judge"


def test_safe_default_when_nothing_set(monkeypatch):
    """With no DB, no env, no requested → the safe default wins."""
    assert resolve_role_model_sync("planner") == SAFE_DEFAULT_MODEL
    assert resolve_role_model_sync("executor") == SAFE_DEFAULT_MODEL
    assert resolve_role_model_sync("verifier") == SAFE_DEFAULT_MODEL
    assert resolve_role_model_sync("judge") == SAFE_DEFAULT_MODEL


def test_nvidia_default_model_env_var_still_works(monkeypatch):
    """``NVIDIA_DEFAULT_MODEL`` is honoured as a fallback env var for planner/verifier.

    This preserves the existing import-time constant's behaviour so an
    operator who has NVIDIA_DEFAULT_MODEL set but no AGENT_PLANNER_MODEL
    keeps getting that model.
    """
    monkeypatch.setenv("NVIDIA_DEFAULT_MODEL", "nvidia/some-custom-model")
    assert resolve_role_model_sync("planner") == "nvidia/some-custom-model"
    assert resolve_role_model_sync("verifier") == "nvidia/some-custom-model"
    # executor + judge don't consult NVIDIA_DEFAULT_MODEL in the existing
    # import-time constants — they fall through to the safe default.
    assert resolve_role_model_sync("executor") == SAFE_DEFAULT_MODEL


# ── Call-time resolution: DB change takes effect without re-import ─────────


def test_db_change_takes_effect_at_call_time(monkeypatch):
    """The plan's core requirement: a DB Apply is visible on the next call.

    Simulates: agent loop is running (module already imported). Admin UI
    issues a PATCH that updates the DB-stored config. The next
    ``resolve_role_model_sync`` call returns the new value — no re-import.
    """
    import services.brain_config_store as mod

    # Step 1: no DB cache → env / safe default.
    assert resolve_role_model_sync("executor") == SAFE_DEFAULT_MODEL

    # Step 2: simulate an admin Apply — the store's set_brain_config refreshes
    # the in-process cache.
    store = BrainConfigStore()
    store._cache = BrainConfig(
        primary_provider="cerebras",
        planner_model="new-planner",
        executor_model="new-executor",
        verifier_model="new-verifier",
        judge_model="new-judge",
        updated_at="2026-06-26T05:14:00Z",
        updated_by="admin@example.com",
    )
    store._cache_at = time.monotonic()
    mod._store = store

    # Step 3: the next call picks it up — no re-import required.
    assert resolve_role_model_sync("executor") == "new-executor"
    assert resolve_role_model_sync("planner") == "new-planner"
    assert resolve_role_model_sync("verifier") == "new-verifier"
    assert resolve_role_model_sync("judge") == "new-judge"


def test_invalidate_then_refresh_picks_up_db_change(monkeypatch):
    """invalidate() forces the next call to re-read the DB."""
    # Set up a fake Mongo doc that "appears" after the first read.
    docs = {"current": None}

    class _FakeCollection:
        async def find_one(self, q):
            return docs["current"]
        async def update_one(self, q, update, upsert=False):
            docs["current"] = dict(update["$set"])
            docs["current"]["_id"] = q["_id"]
            return MagicMock(matched_count=1)

    db = MagicMock()
    db.app_settings = _FakeCollection()

    # Apply a config via the store — refreshes cache.
    with mock_patch("backend.server.get_db", return_value=db):
        from services.brain_config_store import set_brain_config, get_brain_config
        asyncio.run(set_brain_config(
            __import__("services.brain_config_store", fromlist=["BrainConfigPatch"]).BrainConfigPatch(
                executor_model="first-value"
            ),
            actor="test",
        ))
        # Cache is fresh — get returns the cached value.
        cfg = asyncio.run(get_brain_config())
        assert cfg.executor_model == "first-value"

        # Simulate an external edit to the Mongo doc (e.g. another process).
        docs["current"]["executor_model"] = "external-edit"

        # Cache is still fresh → returns stale value.
        cfg = asyncio.run(get_brain_config())
        assert cfg.executor_model == "first-value"  # stale

        # Invalidate → next get re-reads.
        invalidate_brain_config_cache()
        cfg = asyncio.run(get_brain_config())
        assert cfg.executor_model == "external-edit"  # picked up


# ── agent/loop.py integration ──────────────────────────────────────────────


def test_agent_loop_resolve_role_model_delegates_to_store():
    """``agent.loop._resolve_role_model`` delegates to the store and falls back gracefully."""
    from agent.loop import _resolve_role_model, DEFAULT_VERIFIER_MODEL

    # Explicit requested wins.
    assert _resolve_role_model("planner", "explicit") == "explicit"

    # With no store primed, falls back to the env-var constants the module
    # already consults at import time (DEFAULT_PLANNER_MODEL etc).
    val = _resolve_role_model("verifier")
    assert val  # some non-empty string
    assert isinstance(val, str)


def test_agent_loop_default_judge_model_constant_exists():
    """The new DEFAULT_JUDGE_MODEL constant is exported for the judge phase."""
    from agent.loop import DEFAULT_JUDGE_MODEL, DEFAULT_VERIFIER_MODEL
    # When AGENT_JUDGE_MODEL is unset, it falls back to the verifier model.
    assert DEFAULT_JUDGE_MODEL == DEFAULT_VERIFIER_MODEL


# ── brain_policy integration ────────────────────────────────────────────────


def test_resolve_active_brain_honours_db_brain_config(monkeypatch):
    """A DB-stored BrainConfig wins over provider records + env (except AGENT_LLM_BASE_URL)."""
    monkeypatch.delenv("AGENT_LLM_BASE_URL", raising=False)
    monkeypatch.setenv("CEREBRAS_API_KEY", "fake-cb")

    # Prime the BrainConfigStore cache with a DB-stored config.
    import services.brain_config_store as mod
    store = BrainConfigStore()
    store._cache = BrainConfig(
        primary_provider="cerebras",
        planner_model="qwen-3-coder-480b",
        executor_model="qwen-3-coder-480b",
        verifier_model="llama-3.3-70b",
        judge_model="llama-3.3-70b",
        updated_at="2026-06-26T05:14:00Z",
        updated_by="admin@example.com",
    )
    store._cache_at = time.monotonic()
    mod._store = store

    from brain_policy import resolve_active_brain, invalidate_brain_cache
    invalidate_brain_cache()
    brain = asyncio.run(resolve_active_brain())

    assert brain.role == "brain_config"
    assert "cerebras.ai" in brain.base_url
    assert brain.model == "qwen-3-coder-480b"  # executor_model is the hot-path call


def test_resolve_active_brain_falls_through_when_db_unset(monkeypatch):
    """When BrainConfig.updated_at is empty (never applied), the resolver
    falls through to provider records / env — preserving the existing
    test_brain_resolver.py contract."""
    monkeypatch.delenv("AGENT_LLM_BASE_URL", raising=False)
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")

    # BrainConfigStore returns the safe default (updated_at="").
    import services.brain_config_store as mod
    monkeypatch.setattr(mod, "_store", None)

    # No provider records.
    async def _empty_records():
        return []
    monkeypatch.setattr(
        "backend.server._list_configured_provider_records",
        lambda: _empty_records(),
    )

    from brain_policy import resolve_active_brain, invalidate_brain_cache
    invalidate_brain_cache()
    brain = asyncio.run(resolve_active_brain())

    # Falls through to the free NVIDIA NIM default.
    assert brain.role == "free_fallback"
    assert brain.provider_id == "nvidia-nim-free-default"


def test_env_override_still_wins_over_db_brain_config(monkeypatch):
    """AGENT_LLM_BASE_URL (the operator kill-switch) wins over a DB-stored config."""
    monkeypatch.setenv("AGENT_LLM_BASE_URL", "https://kill-switch.example/v1")
    monkeypatch.setenv("AGENT_LLM_API_KEY", "sk-kill")
    monkeypatch.setenv("AGENT_LLM_MODEL", "kill-model")

    # Prime the BrainConfigStore cache — even with a DB config set, the env
    # override must win.
    import services.brain_config_store as mod
    store = BrainConfigStore()
    store._cache = BrainConfig(
        primary_provider="cerebras",
        planner_model="db-planner",
        executor_model="db-executor",
        verifier_model="db-verifier",
        judge_model="db-judge",
        updated_at="2026-06-26T05:14:00Z",
        updated_by="admin@example.com",
    )
    store._cache_at = time.monotonic()
    mod._store = store

    from brain_policy import resolve_active_brain, invalidate_brain_cache
    invalidate_brain_cache()
    brain = asyncio.run(resolve_active_brain())

    assert brain.role == "env_override"
    assert "kill-switch.example" in brain.base_url
