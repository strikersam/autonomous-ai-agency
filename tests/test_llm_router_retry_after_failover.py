"""A provider's Retry-After must not stall failover to a different provider.

Regression for ``planning: TimeoutError`` in production. Groq answered the
planner with a 429 and a ~600s Retry-After; the router clamped that to
``max_delay_sec`` (30s) and slept it *before moving on to NVIDIA*, so a quarter
of the planner's 120s budget went idle and a slow NVIDIA reply then overran
what was left. A Retry-After describes the provider that sent it, not the next.
"""
from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from packages.llm.types import RouterExhausted
from tests import test_llm_router_e2e as e2e
from tests.test_llm_router_e2e import _ok, _request, router_factory  # noqa: F401

# Production backoff: a Retry-After is honoured up to 30s.
_PROD_BACKOFF = e2e.ROUTING_YAML.replace(
    "max_delay_sec: 0.0", "max_delay_sec: 30.0"
).replace("budget_sec: 30.0", "budget_sec: 120.0")


@pytest.fixture(autouse=True)
def _production_backoff(monkeypatch):
    """Autouse, so it runs before ``router_factory`` writes routing.yaml."""
    monkeypatch.setattr(e2e, "ROUTING_YAML", _PROD_BACKOFF)


async def test_retry_after_on_one_provider_does_not_delay_the_next(router_factory):
    def handler(request):
        if request.url.host == "alpha.test":
            return httpx.Response(429, json={"error": "rate limit"},
                                  headers={"retry-after": "597"})
        return _ok(model="beta-model")

    router = router_factory(handler)
    started = time.monotonic()
    response = await asyncio.wait_for(router.chat(_request(timeout_sec=120.0)), 5)

    assert response.provider == "beta"
    assert time.monotonic() - started < 2.0, "slept alpha's Retry-After before trying beta"


async def test_a_hung_provider_ends_as_router_exhausted_within_the_budget(
    router_factory, monkeypatch
):
    """The attempt is bounded by the retry budget, not left to the queue's timeout."""
    async def handler(request):
        await asyncio.sleep(30)
        return _ok()

    router = router_factory(handler)
    monkeypatch.setattr(router._config.routing.retry, "budget_sec", 0.5)
    started = time.monotonic()
    with pytest.raises(RouterExhausted):
        await router.chat(_request(timeout_sec=30.0))
    assert time.monotonic() - started < 5.0


async def test_every_attempt_is_logged_with_provider_model_and_latency(router_factory, caplog):
    """Production planner timeouts showed two minutes of silence: no attempt was logged."""
    def handler(request):
        if request.url.host == "alpha.test":
            return httpx.Response(500, json={"error": "boom"})
        return _ok(model="beta-model")

    router = router_factory(handler)
    with caplog.at_level("INFO", logger="llm.router"):
        await router.chat(_request())
    lines = [r.getMessage() for r in caplog.records if "attempt " in r.getMessage()]
    assert any("alpha/alpha-model failed" in line for line in lines), lines
    assert any("beta/beta-model ok in" in line for line in lines), lines


async def test_an_attempt_cancelled_by_the_caller_is_logged(router_factory, caplog):
    async def handler(request):
        await asyncio.sleep(30)
        return _ok()

    router = router_factory(handler)
    with caplog.at_level("INFO", logger="llm.router"):
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(router._dispatch(_request(timeout_sec=30.0)), 0.3)
    assert any(
        "alpha/alpha-model cancelled by the caller's deadline" in r.getMessage()
        for r in caplog.records
    )
