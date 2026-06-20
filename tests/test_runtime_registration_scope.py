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
