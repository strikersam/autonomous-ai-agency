"""The Google provider must only advertise models its endpoint actually serves.

``GOOGLE_BASE_URL`` points at Google's generative-language endpoint, which
serves the **Gemini** family. Gemma is a separate open-weight family Google does
not serve there, so a request for ``gemma-4`` 404s unconditionally.

``backend/server.py`` already documents this at the ``GEMINI_MODEL`` definition
and the seeded provider's ``default_model`` was corrected accordingly — but the
user-facing model picker (``PREDEFINED_MODELS``) and the per-role assignment
(``AGENT_ROLE_MODELS``) still shipped ``gemma-4``, so anyone selecting Google in
the UI got a provider that could never answer.
"""
from __future__ import annotations

from backend.server import (
    AGENT_ROLE_MODELS,
    GEMINI_MODEL,
    PREDEFINED_MODELS,
)


def test_google_catalog_offers_no_gemma_models() -> None:
    offered = [m["id"] for m in PREDEFINED_MODELS["google"]]

    assert offered, "the google provider must offer at least one model"
    assert not any("gemma" in model_id.lower() for model_id in offered), (
        f"the google provider offers a Gemma model {offered!r}; Google does not "
        f"serve Gemma through the generative-language endpoint GOOGLE_BASE_URL "
        f"targets, so it 404s unconditionally."
    )


def test_google_catalog_offers_gemini_models() -> None:
    offered = [m["id"] for m in PREDEFINED_MODELS["google"]]

    assert all(model_id.startswith("gemini-") for model_id in offered), (
        f"expected only Gemini model ids for the google provider, got {offered!r}"
    )
    assert GEMINI_MODEL in offered, (
        f"the default {GEMINI_MODEL!r} must be selectable in the picker"
    )


def test_google_role_models_match_the_configured_default() -> None:
    roles = AGENT_ROLE_MODELS["google"]

    assert set(roles) == {"planner", "executor", "verifier"}
    for role, model_id in roles.items():
        assert "gemma" not in model_id.lower(), (
            f"google/{role} is assigned {model_id!r}, which 404s"
        )
        assert model_id == GEMINI_MODEL, (
            f"google/{role} is {model_id!r} but the provider's configured "
            f"default is {GEMINI_MODEL!r} — one provider, one default."
        )


def test_google_role_models_are_offered_by_the_catalog() -> None:
    """A role must never be assigned a model the picker does not list."""
    offered = {m["id"] for m in PREDEFINED_MODELS["google"]}

    for role, model_id in AGENT_ROLE_MODELS["google"].items():
        assert model_id in offered, (
            f"google/{role} is assigned {model_id!r}, which is not in the "
            f"provider's catalog {sorted(offered)!r}"
        )
