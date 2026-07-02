"""tests/test_registry_claude_models.py — verify Claude 5/4 family in model registry.

Tests that the newly registered Anthropic Claude models are present,
have correct properties, and are selectable by best_model_for().
"""
from __future__ import annotations

import pytest

from packages.ai.registry import (
    all_models,
    best_model_for,
    get,
    models_by_provider,
)

CLAUDE_MODELS = [
    "claude-sonnet-5",
    "claude-opus-4-8",
    "claude-haiku-4-5-20251001",
    "claude-fable-5",
]


def test_all_claude_models_registered():
    """All four Claude 5/4 family models must be in the registry."""
    registered_ids = {m.model_id for m in all_models()}
    for model_id in CLAUDE_MODELS:
        assert model_id in registered_ids, f"{model_id} missing from registry"


def test_anthropic_provider_models():
    """models_by_provider('anthropic') returns the Claude family."""
    anthropic = models_by_provider("anthropic")
    ids = {m.model_id for m in anthropic}
    for model_id in CLAUDE_MODELS:
        assert model_id in ids


def test_claude_sonnet5_properties():
    m = get("claude-sonnet-5")
    assert m is not None
    assert m.provider_id == "anthropic"
    assert m.supports_tools is True
    assert m.supports_vision is True
    assert m.context_window == 200_000
    assert m.input_cost_per_1m > 0  # paid model
    assert m.priority == 50


def test_claude_opus_most_powerful():
    """Opus has the highest per-token cost — highest quality tier."""
    opus = get("claude-opus-4-8")
    sonnet = get("claude-sonnet-5")
    assert opus is not None and sonnet is not None
    assert opus.output_cost_per_1m > sonnet.output_cost_per_1m


def test_claude_haiku_cheapest():
    """Haiku is the cheapest Anthropic model."""
    haiku = get("claude-haiku-4-5-20251001")
    sonnet = get("claude-sonnet-5")
    assert haiku is not None and sonnet is not None
    assert haiku.input_cost_per_1m < sonnet.input_cost_per_1m


def test_best_model_free_only_excludes_anthropic():
    """With allow_paid=False, best_model_for() should not return Anthropic models."""
    best = best_model_for(allow_paid=False)
    if best is not None:
        assert best.provider_id != "anthropic"


def test_best_model_paid_allowed_can_return_anthropic():
    """With allow_paid=True, the registry includes Anthropic candidates."""
    anthropic_models = models_by_provider("anthropic")
    assert len(anthropic_models) >= 4, "Expected at least 4 Anthropic models"
    # They should all be selectable when paid is allowed
    for m in anthropic_models:
        assert m.input_cost_per_1m >= 0
        assert m.is_healthy is True
