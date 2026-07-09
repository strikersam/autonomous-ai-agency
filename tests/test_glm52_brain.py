"""tests/test_glm52_brain.py — PR #984

Verifies GLM-5.2 (z-ai/glm-5.2) is configured as the default agency brain
model across the registry, brain resolver, provider presets, and render.yaml.
"""
from __future__ import annotations

import inspect
import os


def test_glm52_registered_in_model_registry():
    """packages/ai/registry.py must register z-ai/glm-5.2."""
    from packages.ai.registry import _REGISTRY
    assert "z-ai/glm-5.2" in _REGISTRY, "z-ai/glm-5.2 must be registered in the model registry"


def test_glm52_has_higher_priority_than_llama():
    """GLM-5.2 must have a lower priority number (higher precedence) than llama-3.3-70b."""
    from packages.ai.registry import _REGISTRY
    glm = _REGISTRY["z-ai/glm-5.2"]
    llama = _REGISTRY["meta/llama-3.3-70b-instruct"]
    assert glm.priority < llama.priority, (
        f"GLM-5.2 priority ({glm.priority}) must be < llama priority ({llama.priority})"
    )


def test_brain_default_is_glm52():
    """packages/ai/brain.py DEFAULT_FREE_NVIDIA_MODEL must be z-ai/glm-5.2."""
    from packages.ai.brain import DEFAULT_FREE_NVIDIA_MODEL
    assert DEFAULT_FREE_NVIDIA_MODEL == "z-ai/glm-5.2", (
        f"DEFAULT_FREE_NVIDIA_MODEL should be z-ai/glm-5.2, got {DEFAULT_FREE_NVIDIA_MODEL}"
    )


def test_safe_default_model_is_glm52():
    """packages/ai/brain_config.py SAFE_DEFAULT_MODEL must be z-ai/glm-5.2."""
    from packages.ai.brain_config import SAFE_DEFAULT_MODEL
    assert SAFE_DEFAULT_MODEL == "z-ai/glm-5.2", (
        f"SAFE_DEFAULT_MODEL should be z-ai/glm-5.2, got {SAFE_DEFAULT_MODEL}"
    )


def test_nvidia_provider_preset_uses_glm52():
    """PROVIDER_PRESETS['nvidia'] must use z-ai/glm-5.2 for all roles."""
    from packages.ai.brain_config import PROVIDER_PRESETS
    nvidia = PROVIDER_PRESETS["nvidia"]
    for role in ("planner", "executor", "verifier", "judge"):
        assert nvidia[role] == "z-ai/glm-5.2", (
            f"PROVIDER_PRESETS['nvidia']['{role}'] should be z-ai/glm-5.2, got {nvidia[role]}"
        )


def test_render_yaml_uses_glm52():
    """render.yaml must set NVIDIA_DEFAULT_MODEL + AGENT_*_MODEL to z-ai/glm-5.2."""
    with open("render.yaml") as f:
        content = f.read()
    assert 'value: "z-ai/glm-5.2"' in content, "render.yaml must set z-ai/glm-5.2 as the model"
    # Must NOT have the old default
    assert 'value: "meta/llama-3.3-70b-instruct"' not in content, (
        "render.yaml must not have the old meta/llama-3.3-70b-instruct default"
    )


def test_startup_migrates_old_brain_to_glm52():
    """backend/server.py must have the _migrate_brain_to_glm52 startup task."""
    import backend.server as srv
    src = inspect.getsource(srv)
    assert "_migrate_brain_to_glm52" in src
    assert "z-ai/glm-5.2" in src
    assert "meta/llama-3.3-70b-instruct" in src  # the old model it migrates FROM
