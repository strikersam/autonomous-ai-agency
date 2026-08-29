"""One brain default, consistent across every surface that names one.

This file began life as ``test_glm52_brain.py`` (PR #984), asserting that
``z-ai/glm-5.2`` was the brain in the registry, the resolver, the provider
presets and ``render.yaml``. On 2026-08-28 a live probe against the production
key found that id answering ``410 Gone`` — along with every other candidate the
NVIDIA rotation carried — so every assertion here was pinning a dead model into
place, and the file's name asserted it too.

The durable property was never *which* id: it was that all five surfaces name
the **same** one, so a change in the catalogue cannot leave one of them behind.
That is what is tested now. The id itself comes from the catalogue, which is
the thing the platform actually reads.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _catalogue_default() -> str:
    from packages.ai.brain_config import SAFE_DEFAULT_MODEL

    return SAFE_DEFAULT_MODEL


def test_the_catalogue_names_a_default_at_all() -> None:
    """Guards every assertion below from passing vacuously on an empty string."""
    assert _catalogue_default()


def test_brain_default_matches_the_catalogue() -> None:
    """``packages/ai/brain.py`` is a separate copy of "the free NVIDIA model"."""
    from packages.ai.brain import DEFAULT_FREE_NVIDIA_MODEL

    assert DEFAULT_FREE_NVIDIA_MODEL == _catalogue_default()


def test_every_nvidia_role_preset_matches_the_catalogue() -> None:
    from packages.ai.brain_config import PROVIDER_PRESETS

    nvidia = PROVIDER_PRESETS["nvidia"]
    for role in ("planner", "executor", "verifier", "judge"):
        assert nvidia[role] == _catalogue_default(), (
            f"nvidia/{role} preset drifted from the catalogue default"
        )


def test_the_default_leads_the_rotation() -> None:
    """A default that is not the first candidate wastes the first attempt."""
    from packages.ai.brain_config import PROVIDER_CANDIDATES

    candidates = PROVIDER_CANDIDATES.get("nvidia") or []
    assert candidates, "the nvidia rotation must not be empty"
    assert candidates[0] == _catalogue_default()


def test_render_yaml_ships_the_same_default() -> None:
    """Production env values override every default in the code.

    ``render.yaml`` pinned the retired id in five places; because these are
    literal ``value:`` entries rather than ``sync: false``, they are deployed —
    so production kept using the dead model no matter what the code said.
    """
    content = (REPO_ROOT / "render.yaml").read_text(encoding="utf-8")
    default = _catalogue_default()
    assert f'value: "{default}"' in content, (
        "render.yaml must ship the catalogue default"
    )
    for retired in (
        "z-ai/glm-5.2",
        "z-ai/glm-5.1",
        "meta/llama-3.3-70b-instruct",
    ):
        assert f'value: "{retired}"' not in content, (
            f"render.yaml still ships a retired model id: {retired}"
        )
