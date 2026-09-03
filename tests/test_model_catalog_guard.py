"""Unit tests for scripts/check_model_catalog_consistency.py.

The guard is CI's defence against dead / drifted model ids reaching a deploy
(it exists because `z-ai/glm-5.2`, 410 on NVIDIA, sat in the planner's
prefer_models failing every cycle with nothing to catch it). These tests pin its
three checks against fixtures so the guard itself cannot silently regress.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_GUARD_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_model_catalog_consistency.py"
_spec = importlib.util.spec_from_file_location("catalog_guard", _GUARD_PATH)
guard = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(guard)


def _declared():
    # openai/gpt-oss-120b is served by both nvidia and groq (the multi-provider case).
    return guard._llm_declared({
        "models": {
            "nvidia/nemotron-3-super-120b-a12b": {"provider": "nvidia"},
            "openai/gpt-oss-120b": {"providers": ["nvidia", "groq"]},
            "claude-opus-4-8": {"provider": "anthropic", "aliases": ["opus-4-8"]},
        }
    })


def test_declared_folds_both_provider_spellings() -> None:
    declared = _declared()
    assert declared["openai/gpt-oss-120b"] == {"nvidia", "groq"}
    assert declared["nvidia/nemotron-3-super-120b-a12b"] == {"nvidia"}
    # aliases inherit the model's provider set
    assert declared["opus-4-8"] == {"anthropic"}


def test_prefer_models_must_be_declared() -> None:
    declared = _declared()
    routing = {"routing": {"agents": {"planner": {"prefer_models": [
        "openai/gpt-oss-120b", "z-ai/glm-5.2",  # second is undeclared
    ]}}}}
    errors = guard._check_prefer_models(routing, declared)
    assert len(errors) == 1 and "z-ai/glm-5.2" in errors[0]


def test_preset_must_be_in_candidates() -> None:
    brain = {"providers": {"groq": {
        "role_presets": {"planner": "openai/gpt-oss-120b"},
        "candidates": ["openai/gpt-oss-20b"],  # preset missing
    }}}
    errors = guard._check_presets(brain)
    assert len(errors) == 1 and "openai/gpt-oss-120b" in errors[0]


def test_legacy_only_provider_is_not_a_contradiction() -> None:
    # aerolink lives only in config/models.yaml — the gateway never models it, so
    # a claude id it serves is not drift.
    declared = _declared()
    brain = {"providers": {"aerolink": {"candidates": ["claude-opus-4-8"]}}}
    assert guard._check_cross_catalogue(brain, declared) == []


def test_real_contradiction_is_a_hard_failure() -> None:
    # cerebras IS a gateway provider (it serves nemotron here), and it claims an
    # id the gateway declares only under nvidia/groq — genuine drift.
    declared = _declared()
    declared["some-cerebras-model"] = {"cerebras"}  # makes cerebras a gateway provider
    brain = {"providers": {"cerebras": {"candidates": ["openai/gpt-oss-120b"]}}}
    errors = guard._check_cross_catalogue(brain, declared)
    assert len(errors) == 1 and "cerebras" in errors[0]


def test_the_real_repo_catalogues_are_consistent() -> None:
    """The shipped catalogues must pass the guard — this is what CI enforces."""
    assert guard.main() == 0
