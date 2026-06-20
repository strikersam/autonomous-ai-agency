"""The free-brain default model must be an endpoint-live model.

Regression for the latent bug where ``brain_policy.DEFAULT_FREE_NVIDIA_MODEL``
pointed at ``nvidia/nemotron-3-super-120b-a12b`` — a model the curated live
endpoint testing found returns 404. A deploy that leaves ``NVIDIA_DEFAULT_MODEL``
unset would then resolve a dead brain and every dispatched task would fail at
EXECUTE. The default must match the live model the rest of the codebase uses.
"""
from __future__ import annotations

import os

import brain_policy


_DEAD_MODEL = "nvidia/nemotron-3-super-120b-a12b"
_LIVE_MODEL = "nvidia/llama-3.3-nemotron-super-49b-v1"


def test_default_model_is_not_the_dead_one():
    assert brain_policy.DEFAULT_FREE_NVIDIA_MODEL != _DEAD_MODEL
    assert brain_policy.DEFAULT_FREE_NVIDIA_MODEL == _LIVE_MODEL


def test_resolve_uses_default_when_env_unset(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    monkeypatch.delenv("NVIDIA_DEFAULT_MODEL", raising=False)
    resolved = brain_policy.resolve_free_nvidia_brain()
    assert resolved is not None, "a key is set, so a brain must resolve"
    _base, _headers, model = resolved
    assert model == _LIVE_MODEL


def test_resolve_respects_env_override(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    monkeypatch.setenv("NVIDIA_DEFAULT_MODEL", "nvidia/some-other-model")
    resolved = brain_policy.resolve_free_nvidia_brain()
    assert resolved is not None
    assert resolved[2] == "nvidia/some-other-model"
