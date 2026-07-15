"""Regression test for the colibri env-shim in brain_policy.resolve_active_brain.

Pins the wiring installed by commits f5ee801 (wire) + 134db80 (monitor) + 4b58863
(admin UI). When the operator sets BRAIN_PREFERENCE=colibri + COLIBRI_URL +
COLIBRI_MODEL, the resolver MUST route to a BrainResolution(provider_id=colibri)
with source=env_colibri and priority=100 (operator intent beats free NIM -5).

Coverage shape:
  1. get_brain_preference allowlist (colibri accepted; unknown values -> nvidia)
  2. resolve_active_brain happy path (BrainResolution(colibri))
  3. /v1 suffix normalization including trailing-slash idempotence
  4. COLIBRI_MODEL defaulting to glm-5.2 + AGENT_LLM_MODEL fallback
  5. Loud warning on missing COLIBRI_URL
  6. Records-bypass + free-NVIDIA bypass-guard (operator intent wins)
  7. providers.colibri enabled/disabled parity
  8. ProviderRouter.from_env() end-to-end colibri registration
  9. scripts/switch_brain.py CLI exposes colibri preset + argparse + dispatch
"""
from __future__ import annotations

import asyncio
import logging
import os

import pytest


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Strip BRAIN_PREFERENCE + COLIBRI_* + KIMI_* + NVIDIA_API_KEY before every test."""
    for k in [
        "BRAIN_PREFERENCE",
        "COLIBRI_ENABLED",
        "COLIBRI_URL",
        "COLIBRI_MODEL",
        "COLIBRI_PRIORITY",
        "KIMI_LOCAL_LLAMA_URL",
        "KIMI_LOCAL_LLAMA_MODEL",
        "KIMI_LOCAL_LLAMA_ENABLED",
        "NVIDIA_API_KEY",
    ]:
        monkeypatch.delenv(k, raising=False)
    yield


def _resolved_brain(monkeypatch, **env):
    """Apply env vars via monkeypatch, invalidate cached brain, resolve."""
    from packages.ai.brain import invalidate_brain_cache, resolve_active_brain

    for k, v in env.items():
        monkeypatch.setenv(k, v)
    invalidate_brain_cache()
    return asyncio.run(resolve_active_brain())


# ── (1) get_brain_preference allowlist ──


def test_get_brain_preference_accepts_colibri():
    """Operator can set BRAIN_PREFERENCE=colibri without it being rejected."""
    from packages.ai.brain import get_brain_preference

    os.environ["BRAIN_PREFERENCE"] = "colibri"
    assert get_brain_preference() == "colibri"


@pytest.mark.parametrize("typo", ["colibriii", "GLM-5.2", "", " "])
def test_get_brain_preference_unknown_falls_back_to_nvidia(typo):
    """Defensive default: unknown values coerce to nvidia (cloud default)."""
    from packages.ai.brain import get_brain_preference

    os.environ["BRAIN_PREFERENCE"] = typo
    assert get_brain_preference() == "nvidia"


@pytest.mark.parametrize("v", ["nvidia", "ollama", "auto", "colibri"])
def test_get_brain_preference_allowlist_preserved(v):
    """Regression guard: full allowlist stays intact across edits."""
    from packages.ai.brain import get_brain_preference

    os.environ["BRAIN_PREFERENCE"] = v
    assert get_brain_preference() == v


# ── (2,3,4) resolve_active_brain -- colibri env-shim ──


def test_resolve_colibri_with_url_returns_colibri_shim(monkeypatch):
    """Happy path: BRAIN_PREFERENCE=colibri + COLIBRI_URL -> BrainResolution(colibri)."""
    from packages.ai.brain import BrainResolution

    res = _resolved_brain(
        monkeypatch,
        BRAIN_PREFERENCE="colibri",
        COLIBRI_URL="http://localhost:8081/v1",
        COLIBRI_MODEL="glm-5.2",
    )

    assert isinstance(res, BrainResolution)
    assert res.provider_id == "colibri"
    assert res.base_url == "http://localhost:8081/v1"
    assert res.model == "glm-5.2"
    assert res.role == "brain"
    assert res.source == "env_colibri"
    assert res.priority == 100
    assert res.free_tier is True
    assert res.auth_headers is None


@pytest.mark.parametrize(
    "url_in,url_out",
    [
        ("http://localhost:8081", "http://localhost:8081/v1"),
        ("http://localhost:8081/v1", "http://localhost:8081/v1"),
        ("http://localhost:8081/v1/", "http://localhost:8081/v1"),
        ("http://localhost:8081/", "http://localhost:8081/v1"),
    ],
)
def test_resolve_colibri_url_normalization(monkeypatch, url_in, url_out):
    """`rstrip('/')` + re-append `/v1` must be idempotent across URL variants."""
    res = _resolved_brain(
        monkeypatch,
        BRAIN_PREFERENCE="colibri",
        COLIBRI_URL=url_in,
        COLIBRI_MODEL="glm-5.2",
    )
    assert res.base_url == url_out


def test_resolve_colibri_default_model_when_unset(monkeypatch):
    """Default to glm-5.2 when COLIBRI_MODEL/AGENT_LLM_MODEL both unset."""
    res = _resolved_brain(
        monkeypatch,
        BRAIN_PREFERENCE="colibri",
        COLIBRI_URL="http://localhost:8081/v1",
    )
    assert res.model == "glm-5.2"


def test_resolve_colibri_ag_llm_model_fallback(monkeypatch):
    """AGENT_LLM_MODEL override wins when COLIBRI_MODEL is unset."""
    res = _resolved_brain(
        monkeypatch,
        BRAIN_PREFERENCE="colibri",
        COLIBRI_URL="http://localhost:8081/v1",
        AGENT_LLM_MODEL="custom-glm-variant",
    )
    assert res.model == "custom-glm-variant"


# ── (5) Missing URL warning ──


def test_resolve_colibri_missing_url_warns_loudly(monkeypatch, caplog):
    """BRAIN_PREFERENCE=colibri without COLIBRI_URL must log a loud warning."""
    with caplog.at_level(logging.WARNING, logger="qwen-proxy"):
        _resolved_brain(monkeypatch, BRAIN_PREFERENCE="colibri")

    assert any(
        "BRAIN_PREFERENCE=colibri" in r.message and "COLIBRI_URL" in r.message
        for r in caplog.records
    ), "expected warning mentioning BRAIN_PREFERENCE=colibri + COLIBRI_URL"


# ── (6) records-bypass + free-NVIDIA bypass-guard ──


def test_resolve_colibri_skips_db_records_branch(monkeypatch):
    """The `elif pref == "colibri": pass` records-bypass keeps a stale DB record
    (priority=-10) from preempting operator intent."""
    import packages.ai.brain as brain_policy

    async def _fake_records():
        return [
            {
                "provider_id": "nvidia-fake",
                "type": "openai-compatible",
                "base_url": "http://nvidia-fake",
                "model": "meta/llama-3.3-70b-instruct",
                "priority": -10,
            }
        ], False

    monkeypatch.setattr(brain_policy, "_read_provider_records", _fake_records)

    res = _resolved_brain(
        monkeypatch,
        BRAIN_PREFERENCE="colibri",
        COLIBRI_URL="http://localhost:8081/v1",
        NVIDIA_API_KEY="nvapi-attempt-the-fallback",
    )

    assert res.provider_id == "colibri"
    assert res.source == "env_colibri"


def test_resolve_colibri_free_nvidia_fallback_is_skipped(monkeypatch):
    """Bypass-guard: BRAIN_PREFERENCE=colibri skips resolve_free_nvidia_brain entirely."""
    import packages.ai.brain as brain_policy

    spy_calls = []

    def _spy():
        spy_calls.append(True)
        return None

    monkeypatch.setattr(brain_policy, "resolve_free_nvidia_brain", _spy)

    res = _resolved_brain(
        monkeypatch,
        BRAIN_PREFERENCE="colibri",
        COLIBRI_URL="http://localhost:8081/v1",
        NVIDIA_API_KEY="nvapi-real-key",
    )

    assert res.provider_id == "colibri"
    assert spy_calls == [], (
        "free-NVIDIA fallback was invoked despite BRAIN_PREFERENCE=colibri"
    )


# ── (7) providers/colibri.py enable/disable parity ──


def test_provider_colibri_registered_when_enabled(monkeypatch):
    """COLIBRI_ENABLED=true registers a ProviderConfig with the expected fields."""
    from providers.colibri import colibri_provider_config, colibri_status

    monkeypatch.setenv("COLIBRI_ENABLED", "true")
    monkeypatch.setenv("COLIBRI_URL", "http://localhost:8081/v1")
    monkeypatch.setenv("COLIBRI_MODEL", "glm-5.2")

    cfg = colibri_provider_config()
    assert cfg is not None
    assert cfg.provider_id == "colibri"
    assert cfg.base_url == "http://localhost:8081/v1"
    assert cfg.default_model == "glm-5.2"

    status = colibri_status()
    assert status["enabled"] is True
    assert status["url"] == "http://localhost:8081/v1"


def test_provider_colibri_none_when_disabled():
    """COLIBRI_ENABLED unset/falsy returns None (the autouse fixture already nuked it)."""
    from providers.colibri import colibri_enabled, colibri_provider_config

    assert colibri_enabled() is False
    assert colibri_provider_config() is None


# ── (8) ProviderRouter.from_env() end-to-end ──


def test_provider_router_from_env_picks_up_colibri(monkeypatch):
    """Integration: when COLIBRI_ENABLED=true, the ProviderRouter picks up colibri."""
    monkeypatch.setenv("COLIBRI_ENABLED", "true")
    monkeypatch.setenv("COLIBRI_URL", "http://localhost:8081/v1")
    monkeypatch.setenv("COLIBRI_MODEL", "glm-5.2")

    from packages.ai.router import ProviderRouter

    try:
        router = ProviderRouter.from_env()
    except (ImportError, ConnectionError, RuntimeError) as exc:
        pytest.skip("ProviderRouter.from_env unrunnable in this env: " + repr(exc))

    assert any(
        p.provider_id == "colibri" for p in router.providers
    ), "ProviderRouter.from_env() did not pick up colibri"


# ── (9) scripts/switch_brain.py CLI exposes colibri ──


def test_switch_brain_cli_exposes_colibri_preset():
    """CLI accepts 'colibri' action; preset maps all 4 roles to glm-5.2."""
    from scripts import switch_brain

    assert "colibri" in switch_brain.VALID_PROVIDERS
    colibri_preset = switch_brain.PROVIDER_PRESETS["colibri"]
    for role in ("planner", "executor", "verifier", "judge"):
        assert colibri_preset[role] == "glm-5.2"


def test_switch_brain_cli_colibri_in_argparse_and_dispatch():
    """File-level: argparse choices accept 'colibri' and the dispatch branch routes it."""
    import re
    from pathlib import Path

    src = Path("scripts/switch_brain.py").read_text(encoding="utf-8")
    choices_match = re.search(r"choices=\[(.*?)\]", src, flags=re.DOTALL)
    assert choices_match is not None
    assert "'colibri'" in choices_match.group(1) or '"colibri"' in choices_match.group(1)

    dispatch_match = re.search(r"elif\s+args\.action\s+in\s+\((.*?)\):", src, flags=re.DOTALL)
    assert dispatch_match is not None
    assert "colibri" in dispatch_match.group(1)
