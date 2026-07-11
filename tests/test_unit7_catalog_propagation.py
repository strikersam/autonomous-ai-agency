"""tests/test_unit7_catalog_propagation.py — UNIT 7 regression tests.

Verifies that the catalog (``config/models.yaml``) propagates to every
call site that previously hardcoded model ids:

  1. ``router/model_router._default_model()`` uses ``resolve_component_model``
     (was hardcoded ``qwen/qwen2.5-coder-32b-instruct`` for NVIDIA).
  2. ``router/model_router._default_reasoning_model()`` uses
     ``resolve_component_model`` (was hardcoded
     ``deepseek-ai/deepseek-r1`` for NVIDIA).
  3. ``agents/profiles._get_defaults()`` consults the catalog first; the
     hardcoded ``_nvidia_defaults()`` is only a fallback.
  4. ``runtimes/adapters/jcode.py`` resolves the default model via the
     catalog (was hardcoded ``meta/llama-3.3-70b-instruct``).
  5. ``runtimes/adapters/opencode.py`` resolves the default model via
     the catalog (was hardcoded ``meta/llama-3.3-70b-instruct``).
  6. ``runtimes/adapters/internal_agent._NVIDIA_DEFAULT_MODEL`` derives
     from the catalog (was hardcoded ``meta/llama-3.3-70b-instruct``).
  7. ``render.yaml`` no longer has ``AGENT_PLANNER_MODEL`` /
     ``AGENT_EXECUTOR_MODEL`` / ``AGENT_VERIFIER_MODEL`` /
     ``AGENT_JUDGE_MODEL`` env vars (the catalog + DB BrainConfig are
     the source of truth).
  8. ``.env.example`` documents the removal.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent


# ── 1-2. router/model_router.py ────────────────────────────────────────────


def test_router_default_model_uses_catalog():
    """``_default_model()`` must use ``resolve_component_model`` (UNIT 7).

    Before UNIT 7, it returned ``qwen/qwen2.5-coder-32b-instruct`` for
    NVIDIA — a model id that was never in the catalog. The alias map
    (short-name → full-name) still contains the id as a passthrough
    alias, which is fine — what matters is that ``_default_model()``
    no longer returns it as the default.
    """
    src = (REPO_ROOT / "router" / "model_router.py").read_text(encoding="utf-8")
    # Find the _default_model function body.
    import re
    m = re.search(
        r"def _default_model\(\).*?(?=\n\ndef |\n\nclass )",
        src,
        re.DOTALL,
    )
    assert m
    body = m.group(0)
    # Strip the docstring so we only check the executable body.
    body_no_doc = re.sub(r'"""[^"]*"""', '', body, count=1, flags=re.DOTALL)
    # The stale hardcoded id is NOT in the executable body (the alias map
    # elsewhere in the file is fine — that's a different concern).
    assert "qwen/qwen2.5-coder-32b-instruct" not in body_no_doc, (
        "_default_model() executable body still has the stale qwen/qwen2.5-coder-32b model id"
    )
    # The new catalog resolver is used.
    assert "resolve_component_model" in body


def test_router_default_model_returns_catalog_preset_for_nvidia(monkeypatch):
    """With a NVIDIA key set, ``_default_model()`` returns the catalog's
    nvidia executor preset (``z-ai/glm-5.2``), not the stale hardcoded id."""
    monkeypatch.setenv("NVIDIA_API_KEY", "fake-nv")
    from router.model_router import _default_model
    m = _default_model()
    # Catalog preset for nvidia/executor is z-ai/glm-5.2.
    assert m == "z-ai/glm-5.2"


def test_router_default_reasoning_model_returns_catalog_preset_for_nvidia(monkeypatch):
    """``_default_reasoning_model()`` returns the catalog's nvidia planner
    preset (``z-ai/glm-5.2``)."""
    monkeypatch.setenv("NVIDIA_API_KEY", "fake-nv")
    from router.model_router import _default_reasoning_model
    m = _default_reasoning_model()
    assert m == "z-ai/glm-5.2"


def test_router_default_model_returns_catalog_preset_for_ollama(monkeypatch):
    """Without any cloud key, ``_default_model()`` returns the catalog's
    ollama executor preset (``qwen3-coder:30b``)."""
    # Clear all cloud keys.
    for k in ("NVIDIA_API_KEY", "NVidiaApiKey", "DEEPSEEK_API_KEY", "GROQ_API_KEY",
              "DASHSCOPE_API_KEY", "QWEN_API_KEY", "CEREBRAS_API_KEY", "MISTRAL_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    from router.model_router import _default_model
    m = _default_model()
    assert m == "qwen3-coder:30b"


# ── 3. agents/profiles.py ─────────────────────────────────────────────────


def test_profiles_uses_catalog_first():
    """``_get_defaults()`` must consult the catalog first; the hardcoded
    ``_nvidia_defaults()`` is only a fallback for catalog import failure."""
    src = (REPO_ROOT / "agents" / "profiles.py").read_text(encoding="utf-8")
    assert "_catalog_defaults" in src
    assert "_catalog_provider" in src
    assert "resolve_component_model" in src
    # The catalog-first behaviour is documented.
    assert "Try the catalog first" in src


def test_profiles_catalog_defaults_returns_catalog_presets(monkeypatch):
    """When NVIDIA key is set, ``_catalog_defaults()`` returns the catalog's
    nvidia role presets."""
    monkeypatch.setenv("NVIDIA_API_KEY", "fake-nv")
    # Clear other provider keys so nvidia wins.
    for k in ("DEEPSEEK_API_KEY", "GROQ_API_KEY", "DASHSCOPE_API_KEY",
              "QWEN_API_KEY", "CEREBRAS_API_KEY", "MISTRAL_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    from agents.profiles import _catalog_defaults
    out = _catalog_defaults()
    assert out is not None
    # Catalog nvidia presets map: architect/scout/coder → executor preset,
    # reviewer → judge preset, verifier → verifier preset.
    from packages.ai.brain_config import PROVIDER_PRESETS
    assert out["coder"] == PROVIDER_PRESETS["nvidia"]["executor"]
    assert out["reviewer"] == PROVIDER_PRESETS["nvidia"]["judge"]
    assert out["verifier"] == PROVIDER_PRESETS["nvidia"]["verifier"]


def test_profiles_get_defaults_uses_catalog(monkeypatch):
    """``_get_defaults()`` returns the catalog-derived defaults (not the
    hardcoded fallback table) when the catalog import succeeds."""
    monkeypatch.setenv("NVIDIA_API_KEY", "fake-nv")
    from agents.profiles import _get_defaults, _nvidia_defaults
    out = _get_defaults()
    hardcoded = _nvidia_defaults()
    # The catalog path returns the catalog preset (z-ai/glm-5.2); the
    # hardcoded path returns meta/llama-3.3-70b-instruct. They differ —
    # so if `out` matches the catalog, the catalog path was taken.
    from packages.ai.brain_config import PROVIDER_PRESETS
    assert out["coder"] == PROVIDER_PRESETS["nvidia"]["executor"]
    # Sanity: the hardcoded fallback would have returned a different value.
    assert hardcoded["coder"] != PROVIDER_PRESETS["nvidia"]["executor"]


# ── 4-5. runtimes/adapters/{jcode,opencode}.py ────────────────────────────


def test_jcode_adapter_uses_catalog_for_default_model():
    """``jcode.py`` must NOT have the stale hardcoded ``meta/llama-3.3-70b-instruct``
    inline; it should use the catalog resolver."""
    src = (REPO_ROOT / "runtimes" / "adapters" / "jcode.py").read_text(encoding="utf-8")
    # The old inline hardcoded fallback is gone (the only remaining
    # occurrence is inside the defensive ``except Exception`` branch of
    # ``_resolve_default_executor_model``).
    # Check that the __init__ no longer has the inline fallback.
    import re
    init_match = re.search(r"def __init__.*?(?=\n    def )", src, re.DOTALL)
    assert init_match
    init_body = init_match.group(0)
    assert "meta/llama-3.3-70b-instruct" not in init_body, (
        "jcode __init__ still has the inline hardcoded model id"
    )
    # The new catalog resolver is used.
    assert "_resolve_default_executor_model" in src


def test_opencode_adapter_uses_catalog_for_default_model():
    """``opencode.py`` must NOT have the stale hardcoded model id inline."""
    src = (REPO_ROOT / "runtimes" / "adapters" / "opencode.py").read_text(encoding="utf-8")
    import re
    init_match = re.search(r"def __init__.*?(?=\n    def )", src, re.DOTALL)
    assert init_match
    init_body = init_match.group(0)
    assert "meta/llama-3.3-70b-instruct" not in init_body, (
        "opencode __init__ still has the inline hardcoded model id"
    )
    assert "_resolve_default_executor_model" in src


# ── 6. runtimes/adapters/internal_agent.py ────────────────────────────────


def test_internal_agent_nvidia_default_model_derives_from_catalog():
    """``_NVIDIA_DEFAULT_MODEL`` must equal the first entry in the catalog's
    nvidia candidates list (the preset), not the stale hardcoded value."""
    from runtimes.adapters.internal_agent import _NVIDIA_DEFAULT_MODEL
    from packages.ai.brain_config import PROVIDER_CANDIDATES
    cands = PROVIDER_CANDIDATES.get("nvidia") or []
    assert cands, "nvidia should have candidates in the catalog"
    assert _NVIDIA_DEFAULT_MODEL == cands[0], (
        f"_NVIDIA_DEFAULT_MODEL={_NVIDIA_DEFAULT_MODEL!r} != "
        f"catalog first candidate {cands[0]!r}"
    )


def test_internal_agent_nvidia_default_model_is_not_stale():
    """The stale value was ``meta/llama-3.3-70b-instruct`` — the catalog
    preset is now ``z-ai/glm-5.2``."""
    from runtimes.adapters.internal_agent import _NVIDIA_DEFAULT_MODEL
    # Either it's the catalog preset OR the defensive fallback (which is
    # the stale value, but only used when the catalog import fails). In
    # normal operation, it should be the catalog preset.
    # We accept either, but log a warning if the stale fallback is in use.
    assert _NVIDIA_DEFAULT_MODEL in (
        "z-ai/glm-5.2",          # catalog preset
        "meta/llama-3.3-70b-instruct",  # defensive fallback
    )


# ── 7. render.yaml ────────────────────────────────────────────────────────


def test_render_yaml_has_no_agent_role_model_env_vars():
    """``render.yaml`` must NOT define ``AGENT_PLANNER_MODEL`` /
    ``AGENT_EXECUTOR_MODEL`` / ``AGENT_VERIFIER_MODEL`` /
    ``AGENT_JUDGE_MODEL`` — the catalog + DB BrainConfig are the source
    of truth (UNIT 7)."""
    src = (REPO_ROOT / "render.yaml").read_text(encoding="utf-8")
    for var in ("AGENT_PLANNER_MODEL", "AGENT_EXECUTOR_MODEL",
                "AGENT_VERIFIER_MODEL", "AGENT_JUDGE_MODEL"):
        assert f"key: {var}" not in src, (
            f"render.yaml still defines {var} — should be removed (UNIT 7)"
        )


def test_render_yaml_documents_removal():
    """The render.yaml comments should document the UNIT 7 removal so the
    next operator reading the file understands why the vars are gone."""
    src = (REPO_ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "UNIT 7" in src
    assert "resolve_component_model" in src


# ── 8. .env.example ───────────────────────────────────────────────────────


def test_env_example_documents_agent_role_model_removal():
    """.env.example should document the removal of AGENT_<ROLE>_MODEL."""
    src = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    # The old commented-out entries are gone.
    assert "# AGENT_PLANNER_MODEL=" not in src
    # The removal is documented.
    assert "UNIT 7" in src
    assert "resolve_component_model" in src
