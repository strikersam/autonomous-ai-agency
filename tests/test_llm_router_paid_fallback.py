"""Regression: a named free model must not open the door to paid siblings.

A request that names a model without ``pin_model`` gets the named model first
and the rest of its provider's catalogue as fallbacks. That fallback list was
built without the ``allow_paid`` filter the unpinned path applies, so a request
for the free ``gemini-2.5-flash`` with ``allow_paid=False`` could fail over to
a paid Gemini model on the same (free-tier) provider and be billed for it.
"""
from __future__ import annotations

import pytest

import packages.llm.router as router_mod
from packages.llm.router import LLMRouter
from packages.llm.types import LLMRequest

_MESSAGES = [{"role": "user", "content": "hi"}]


@pytest.fixture
def router(monkeypatch: pytest.MonkeyPatch) -> LLMRouter:
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setattr(router_mod, "disabled_provider_ids", lambda: frozenset())
    return LLMRouter()


def _google(router: LLMRouter, request: LLMRequest) -> list:
    return [c.model for c in router._candidates(request) if c.provider.id == "google"]


def test_named_free_model_does_not_fall_back_to_paid_siblings(router: LLMRouter) -> None:
    request = LLMRequest(messages=_MESSAGES, model="gemini-2.5-flash", allow_paid=False)
    models = _google(router, request)
    assert models and models[0].id == "gemini-2.5-flash"
    paid = [m.id for m in models if not (m.is_free or m.paid_opt_in)]
    assert paid == [], f"paid fallbacks with allow_paid=False: {paid}"


def test_paid_fallbacks_remain_when_paid_is_allowed(router: LLMRouter) -> None:
    request = LLMRequest(messages=_MESSAGES, model="gemini-2.5-flash", allow_paid=True)
    assert any(not m.is_free for m in _google(router, request))
