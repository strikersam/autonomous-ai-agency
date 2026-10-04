"""Amazon Bedrock as an opt-in paid brain (Qwen3 Coder Next on the OpenAI-compatible Mantle endpoint).

Bedrock is billed to the AWS account, so it must stay out of the pool until the
operator turns it on, and turning it on must not open the other paid providers
(the Anthropic API) the way ALLOW_PAID_BRAIN does.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from packages.llm import config as llm_config
from packages.llm import keys as llm_keys
from packages.llm.router import LLMRouter
from packages.llm.types import LLMRequest

_CONFIG_DIR = Path(__file__).resolve().parents[1] / "config" / "llm"
_BEDROCK_MODELS = {"qwen.qwen3-coder-next"}


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for name in ("BEDROCK_BRAIN_ENABLED", "ALLOW_PAID_BRAIN", "AWS_BEARER_TOKEN_BEDROCK"):
        monkeypatch.delenv(name, raising=False)
    llm_config.reset()
    llm_keys.reset()
    yield
    llm_config.reset()
    llm_keys.reset()


def test_bedrock_is_off_by_default():
    cfg = llm_config.load_config(_CONFIG_DIR)
    assert cfg.providers["bedrock"].enabled is False
    assert "bedrock" not in {p.id for p in cfg.enabled_providers()}


def test_bedrock_models_are_paid_but_opted_in():
    cfg = llm_config.load_config(_CONFIG_DIR)
    for mid in _BEDROCK_MODELS:
        model = cfg.models[mid]
        assert model.provider == "bedrock"
        assert not model.is_free and model.paid_opt_in
        assert model.supports_tools


def test_enabled_bedrock_serves_without_opening_other_paid_models(monkeypatch):
    monkeypatch.setenv("BEDROCK_BRAIN_ENABLED", "true")
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "test-token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    cfg = llm_config.load_config(_CONFIG_DIR)
    assert cfg.routing.allow_paid is False
    bedrock = cfg.providers["bedrock"]
    assert bedrock.base_url == "https://bedrock-mantle.us-east-1.api.aws/v1"

    router = LLMRouter(cfg)
    request = LLMRequest(messages=[{"role": "user", "content": "hi"}])
    served = {m.id for m in router._models_for(bedrock, None, request, False)}
    assert _BEDROCK_MODELS <= served
    anthropic = router._models_for(cfg.providers["anthropic"], None, request, False)
    assert all(m.is_free for m in anthropic)  # the Anthropic API stays closed


def test_registry_keeps_opted_in_paid_models_only():
    cfg = llm_config.load_config(_CONFIG_DIR)
    from packages.llm.registry import ModelRegistry

    registry = ModelRegistry(cfg)
    kept = {m.id for m in registry.candidates(allow_paid=False)}
    assert _BEDROCK_MODELS <= kept
    assert all(cfg.models[m].is_free or cfg.models[m].paid_opt_in for m in kept)


def test_bedrock_routes_only_the_coding_model():
    """gpt-oss-20b invented tool results in production (2026-10-04), and any
    cheaper Bedrock twin would outrank the coding model on cost."""
    cfg = llm_config.load_config(_CONFIG_DIR)
    on_bedrock = {mid for mid, m in cfg.models.items() if m.provider == "bedrock"}
    assert on_bedrock == _BEDROCK_MODELS
    assert cfg.providers["bedrock"].default_model == "qwen.qwen3-coder-next"


def test_bedrock_model_is_priced():
    from packages.ai.cost_tracker import _DEFAULT_COST_TABLE

    for mid in _BEDROCK_MODELS:
        assert mid in _DEFAULT_COST_TABLE
