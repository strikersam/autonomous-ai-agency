"""The default RuntimeManager registers only internal_agent + Hermes when
RUNTIME_EXTERNAL_DISABLED=true and RUNTIME_HERMES_ENABLED=true (render.yaml).
"""
from __future__ import annotations

import pytest

import runtimes.manager as rm_mod

_OTHER_FLAGS = (
    "RUNTIME_GOOSE_ENABLED",
    "RUNTIME_AIDER_ENABLED",
    "RUNTIME_OPENCODE_ENABLED",
    "RUNTIME_CLAUDE_CODE_ENABLED",
    "RUNTIME_JCODE_ENABLED",
    "RUNTIME_DOCKER_ENABLED",
    "AGENT_MODE_DOCKER",
    "RUNTIME_OPENHANDS_ENABLED",
    "TASK_HARNESS_ENABLED",
)


def test_only_internal_and_hermes_registered(monkeypatch):
    monkeypatch.setenv("RUNTIME_EXTERNAL_DISABLED", "true")
    monkeypatch.setenv("RUNTIME_HERMES_ENABLED", "true")
    for flag in _OTHER_FLAGS:
        monkeypatch.delenv(flag, raising=False)

    mgr = rm_mod._build_default_manager()
    ids = set(mgr._registry.ids())

    assert ids == {"internal_agent", "hermes"}, f"expected internal+hermes only, got {sorted(ids)}"


def test_external_disabled_without_hermes_flag_leaves_only_internal(monkeypatch):
    monkeypatch.setenv("RUNTIME_EXTERNAL_DISABLED", "true")
    for flag in _OTHER_FLAGS + ("RUNTIME_HERMES_ENABLED",):
        monkeypatch.delenv(flag, raising=False)

    mgr = rm_mod._build_default_manager()
    ids = set(mgr._registry.ids())

    assert ids == {"internal_agent"}, f"expected internal only, got {sorted(ids)}"


def test_code_generation_task_type_routes_to_hermes(monkeypatch):
    """RUNTIME_CODE_GENERATION=hermes wires a code_generation→Hermes override so a
    decomposed task's code slice runs on Hermes (falling back to internal_agent
    when the Hermes sidecar is down)."""
    monkeypatch.setenv("RUNTIME_EXTERNAL_DISABLED", "true")
    monkeypatch.setenv("RUNTIME_HERMES_ENABLED", "true")
    monkeypatch.setenv("RUNTIME_CODE_GENERATION", "hermes")
    for flag in _OTHER_FLAGS:
        monkeypatch.delenv(flag, raising=False)

    mgr = rm_mod._build_default_manager()

    assert "hermes" in set(mgr._registry.ids())
    overrides = mgr._router._policy.task_type_runtime_overrides
    assert overrides.get("code_generation") == "hermes"
    # fallback safety net stays internal_agent for when Hermes is unavailable
    assert "internal_agent" in mgr._router._policy.fallback_runtime_ids
