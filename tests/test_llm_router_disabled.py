"""The router must honour the durable provider on/off switch (ADR-008).

``services/brain_failover.py`` owns one persisted set of disabled providers: an
operator flips a provider off in the Providers screen, or the platform switches
one off because its key was revoked. That set survives a Render deploy and is
what the UI renders.

``LLMRouter``'s circuit breaker is a different instrument — in-memory, self-
healing, reset on restart — which is right for "this provider is having a bad
minute" and wrong for "this key was revoked". Before this was wired up, turning
on ``LLM_ROUTER_ENABLED`` meant a disabled provider was still routed to and a
dead key was retried on every request, forever.
"""
from __future__ import annotations

import asyncio

import httpx
import pytest

import services.brain_failover as bf
from packages.llm import budget as llm_budget
from packages.llm import cache as llm_cache
from packages.llm import config as llm_config
from packages.llm import disabled as llm_disabled
from packages.llm import health as llm_health
from packages.llm import keys as llm_keys
from packages.llm import metrics as llm_metrics
from packages.llm import registry as llm_registry
from packages.llm import router as llm_router
from packages.llm import strategies as llm_strategies
from packages.llm.router import LLMRouter
from packages.llm.types import LLMRequest, RouterExhausted

PROVIDERS_YAML = """
providers:
  alpha:
    kind: openai
    base_url: https://alpha.test/v1
    key_env: [ALPHA_KEY]
    tier: free
    priority: 10
    max_concurrency: 4
  beta:
    kind: openai
    base_url: https://beta.test/v1
    key_env: [BETA_KEY]
    tier: free
    priority: 20
    max_concurrency: 4
"""

MODELS_YAML = """
models:
  alpha-model:
    provider: alpha
    context_window: 32768
    priority: 10
  beta-model:
    provider: beta
    context_window: 32768
    priority: 20
"""

ROUTING_YAML = """
routing:
  strategy: priority
  retry:
    max_attempts: 2
    base_delay_sec: 0.0
    max_delay_sec: 0.0
    total_budget_sec: 5.0
"""

_MODULES = (llm_config, llm_registry, llm_health, llm_keys,
            llm_cache, llm_budget, llm_metrics, llm_router)


def _ok(model="beta-model"):
    return httpx.Response(200, json={
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "hi"},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 4, "completion_tokens": 2},
    })


@pytest.fixture
def router_factory(tmp_path, monkeypatch):
    (tmp_path / "providers.yaml").write_text(PROVIDERS_YAML, encoding="utf-8")
    (tmp_path / "models.yaml").write_text(MODELS_YAML, encoding="utf-8")
    (tmp_path / "routing.yaml").write_text(ROUTING_YAML, encoding="utf-8")

    monkeypatch.setenv("LLM_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("LLM_ROUTER_ENABLED", "true")
    monkeypatch.setenv("ALPHA_KEY", "alpha-key")
    monkeypatch.setenv("BETA_KEY", "beta-key")
    # The disabled set is persisted — point it at a temp DB and clear its cache
    # so one test's auto-disable cannot decide the next test's routing.
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "kv.db"))
    monkeypatch.setattr(bf, "_DISABLED_CACHE", ({}, 0.0))
    for name in ("NVIDIA_API_KEY", "GROQ_API_KEY", "CEREBRAS_API_KEY",
                 "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY",
                 "ANTHROPIC_API_KEY", "OLLAMA_BASE"):
        monkeypatch.delenv(name, raising=False)

    for module in _MODULES:
        module.reset()
    llm_strategies.reset()

    built: list[LLMRouter] = []

    def build(handler):
        instance = LLMRouter()
        instance._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        built.append(instance)
        return instance

    yield build

    for module in _MODULES:
        module.reset()
    llm_strategies.reset()
    monkeypatch.setattr(bf, "_DISABLED_CACHE", ({}, 0.0))
    for instance in built:
        client = getattr(instance, "_client", None)
        if client is not None and not client.is_closed:
            asyncio.run(client.aclose())


def _request(**kwargs):
    kwargs.setdefault("messages", [{"role": "user", "content": "hello"}])
    return LLMRequest(**kwargs)


# ── Reading the switch ───────────────────────────────────────────────────────


async def test_a_disabled_provider_is_not_routed_to(router_factory):
    """The operator's off-switch has to mean something to the router."""
    bf.set_provider_enabled("alpha", False, "manual test")
    bf.disabled_providers(force=True)

    seen: list[str] = []

    def handler(request):
        seen.append(request.url.host)
        return _ok()

    router = router_factory(handler)
    response = await router.chat(_request())

    assert response.provider == "beta"
    assert "alpha.test" not in seen, "a disabled provider was still called"


async def test_disabling_every_provider_exhausts_rather_than_ignoring_the_switch(
    router_factory,
):
    """Turning everything off must fail loudly, not quietly route anyway."""
    for provider_id in ("alpha", "beta"):
        bf.set_provider_enabled(provider_id, False, "manual test")
    bf.disabled_providers(force=True)

    router = router_factory(lambda _r: _ok())
    with pytest.raises(RouterExhausted):
        await router.chat(_request())


async def test_re_enabling_a_provider_puts_it_back_in_rotation(router_factory):
    bf.set_provider_enabled("alpha", False, "manual test")
    bf.disabled_providers(force=True)
    bf.set_provider_enabled("alpha", True)
    bf.disabled_providers(force=True)

    seen: list[str] = []

    def handler(request):
        seen.append(request.url.host)
        return _ok(model="alpha-model")

    router = router_factory(handler)
    await router.chat(_request())
    assert seen[0] == "alpha.test"


# ── Writing the switch ───────────────────────────────────────────────────────


@pytest.mark.parametrize(("status", "body", "why"), [
    (401, {"error": "unauthorized"}, "invalid key"),
    (403, {"error": "forbidden"}, "forbidden account"),
    (402, {"error": {"message": "Insufficient Balance"}}, "no credit"),
    (400, {"error": {"message":
        "Your credit balance is too low to access the Anthropic API."}},
     "billing-shaped 400"),
])
async def test_unfixable_failures_auto_disable_the_provider(
    router_factory, status, body, why,
):
    """Only a human can fix these — a self-healing breaker would retry forever."""
    def handler(request):
        if request.url.host == "alpha.test":
            return httpx.Response(status, json=body)
        return _ok()

    router = router_factory(handler)
    await router.chat(_request())

    off = bf.disabled_providers(force=True)
    assert "alpha" in off, f"{why} should auto-disable the provider"
    assert off["alpha"].startswith("auto:")


@pytest.mark.parametrize(("status", "body", "why"), [
    (429, {"error": "rate limited"}, "quota refills on its own"),
    (500, {"error": "server error"}, "transient"),
    (503, {"error": "unavailable"}, "transient"),
])
async def test_transient_failures_never_auto_disable(
    router_factory, status, body, why,
):
    """The critical guard: disabling on a 429 switches off every free provider."""
    def handler(request):
        if request.url.host == "alpha.test":
            return httpx.Response(status, json=body)
        return _ok()

    router = router_factory(handler)
    await router.chat(_request())

    assert "alpha" not in bf.disabled_providers(force=True), (
        f"{why} — this must be left to the circuit breaker"
    )


# ── The classifier itself ────────────────────────────────────────────────────


@pytest.mark.parametrize(("status", "body"), [
    (401, ""), (402, ""), (403, ""),
    (400, "your credit balance is too low"),
    (429, "insufficient_quota"),
])
def test_is_unfixable_recognises_the_human_only_failures(status, body):
    assert llm_disabled.is_unfixable(status, body) is True


@pytest.mark.parametrize(("status", "body"), [
    (429, "rate limited"), (500, "server error"), (503, "unavailable"),
    (404, "model not found"), (None, "connection reset"),
])
def test_is_unfixable_leaves_recoverable_failures_alone(status, body):
    assert llm_disabled.is_unfixable(status, body) is False


def test_disabled_bridge_degrades_instead_of_raising(monkeypatch):
    """A storage problem must never take the brain offline."""
    def _boom(*_a, **_k):
        raise OSError("disk gone")

    monkeypatch.setattr(bf, "disabled_providers", _boom)
    monkeypatch.setattr(bf, "auto_disable_provider", _boom)

    assert llm_disabled.disabled_provider_ids() == frozenset()
    llm_disabled.auto_disable("alpha", "401 invalid key")  # must not raise
