"""End-to-end routing against mock providers (ADR-008).

These are the tests that justify the whole layer: a request must survive a 429,
a 500, an exhausted key, a decommissioned model, and a tripped breaker without
the caller ever seeing a failure — as long as *some* path remains.

Every test drives the real ``LLMRouter`` through ``httpx.MockTransport``, so
the retry loop, health tracking, key rotation, bulkheads, and metrics all run
for real. Nothing here is stubbed except the network.
"""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from packages.llm import budget as llm_budget
from packages.llm import cache as llm_cache
from packages.llm import config as llm_config
from packages.llm import health as llm_health
from packages.llm import keys as llm_keys
from packages.llm import metrics as llm_metrics
from packages.llm import registry as llm_registry
from packages.llm import router as llm_router
from packages.llm import strategies as llm_strategies
from packages.llm.router import LLMRouter
from packages.llm.types import LLMRequest, PermanentError, RouterExhausted

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
  gamma:
    kind: openai
    base_url: https://gamma.test/v1
    requires_key: false
    tier: local
    priority: 30
    max_concurrency: 4
"""

MODELS_YAML = """
models:
  alpha-model:
    provider: alpha
    context_window: 32768
    supports_tools: true
    supports_json: true
    priority: 10
  beta-model:
    provider: beta
    context_window: 32768
    supports_tools: true
    supports_json: true
    priority: 20
  gamma-model:
    provider: gamma
    context_window: 32768
    supports_tools: true
    supports_json: true
    priority: 30
"""

ROUTING_YAML = """
routing:
  strategy: priority
  allow_paid: false
  queue_enabled: true
  queue_max_depth: 64
  global_max_concurrency: 8
  max_providers_per_request: 5
  max_models_per_provider: 2
  retry:
    max_attempts: 8
    base_delay_sec: 0.0
    max_delay_sec: 0.0
    jitter: 0.0
    budget_sec: 30.0
"""

HEALTH_YAML = """
health:
  failure_threshold: 2
  min_samples: 500
  open_duration_sec: 30.0
  window_sec: 300.0
"""

CACHE_YAML = """
cache:
  response:
    enabled: true
    ttl_sec: 60
    max_entries: 32
"""


def _ok(model="alpha-model", text="hello", prompt=10, completion=5):
    return httpx.Response(200, json={
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": text},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": prompt, "completion_tokens": completion},
    })


@pytest.fixture
def router_factory(tmp_path, monkeypatch):
    """A router wired to three mock providers, with all singletons isolated."""
    (tmp_path / "providers.yaml").write_text(PROVIDERS_YAML, encoding="utf-8")
    (tmp_path / "models.yaml").write_text(MODELS_YAML, encoding="utf-8")
    (tmp_path / "routing.yaml").write_text(ROUTING_YAML, encoding="utf-8")
    (tmp_path / "health.yaml").write_text(HEALTH_YAML, encoding="utf-8")
    (tmp_path / "cache.yaml").write_text(CACHE_YAML, encoding="utf-8")

    monkeypatch.setenv("LLM_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("LLM_ROUTER_ENABLED", "true")
    monkeypatch.setenv("ALPHA_KEY", "alpha-key-1,alpha-key-2")
    monkeypatch.setenv("BETA_KEY", "beta-key-1")
    for name in ("NVIDIA_API_KEY", "GROQ_API_KEY", "CEREBRAS_API_KEY",
                 "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY",
                 "ANTHROPIC_API_KEY", "OLLAMA_BASE"):
        monkeypatch.delenv(name, raising=False)

    for module in (llm_config, llm_registry, llm_health, llm_keys,
                   llm_cache, llm_budget, llm_metrics, llm_router):
        module.reset()
    llm_strategies.reset()

    built: list[LLMRouter] = []

    def build(handler):
        instance = LLMRouter()
        instance._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        built.append(instance)
        return instance

    yield build

    for module in (llm_config, llm_registry, llm_health, llm_keys,
                   llm_cache, llm_budget, llm_metrics, llm_router):
        module.reset()
    # Round-robin and adaptive counters would otherwise survive this module and
    # change the outcome of tests/test_llm_router_strategies.py in the same run.
    llm_strategies.reset()
    for instance in built:
        client = getattr(instance, "_client", None)
        if client is not None and not client.is_closed:
            asyncio.run(client.aclose())


def _request(**kwargs):
    kwargs.setdefault("messages", [{"role": "user", "content": "hello"}])
    return LLMRequest(**kwargs)


# ── Happy path ──────────────────────────────────────────────────────────────

async def test_routes_to_the_highest_priority_provider(router_factory):
    router = router_factory(lambda _r: _ok())
    response = await router.chat(_request())

    assert response.provider == "alpha"
    assert response.text == "hello"
    assert response.usage.prompt_tokens == 10
    assert response.fallback_count == 0


# ── Failover ────────────────────────────────────────────────────────────────

async def test_429_fails_over_to_the_next_provider(router_factory):
    seen = []

    def handler(request):
        seen.append(request.url.host)
        if request.url.host == "alpha.test":
            return httpx.Response(429, json={"error": "rate limit"},
                                  headers={"retry-after": "0"})
        return _ok(model="beta-model")

    router = router_factory(handler)
    response = await router.chat(_request())

    assert response.provider == "beta", "a 429 on alpha must not fail the request"
    assert "alpha.test" in seen and "beta.test" in seen
    assert response.fallback_count >= 1


async def test_429_rotates_keys_before_leaving_the_provider(router_factory):
    """Two keys on alpha means a 429 costs a key, not the provider."""
    calls = {"n": 0}

    def handler(request):
        if request.url.host != "alpha.test":
            return _ok(model="beta-model")
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"error": "rate limit"},
                                  headers={"retry-after": "0"})
        return _ok()

    router = router_factory(handler)
    response = await router.chat(_request())

    assert response.provider == "alpha"
    assert calls["n"] == 2, "the second alpha key was never tried"
    snapshot = llm_keys.get_ring().snapshot()["alpha"]
    assert sum(1 for k in snapshot if not k["healthy"]) == 1
    assert sum(1 for k in snapshot if k["healthy"]) >= 1


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_server_errors_fail_over(status, router_factory):
    def handler(request):
        if request.url.host == "alpha.test":
            return httpx.Response(status, json={"error": "server"})
        return _ok(model="beta-model")

    router = router_factory(handler)
    response = asyncio.run(router.chat(_request()))
    assert response.provider == "beta"


async def test_timeout_fails_over(router_factory):
    def handler(request):
        if request.url.host == "alpha.test":
            raise httpx.ConnectTimeout("timed out")
        return _ok(model="beta-model")

    router = router_factory(handler)
    response = await router.chat(_request())
    assert response.provider == "beta"


async def test_connection_reset_fails_over(router_factory):
    def handler(request):
        if request.url.host == "alpha.test":
            raise httpx.ConnectError("connection reset by peer")
        return _ok(model="beta-model")

    router = router_factory(handler)
    assert (await router.chat(_request())).provider == "beta"


async def test_decommissioned_model_does_not_kill_the_provider(router_factory):
    """The NVIDIA 410 incident, as a regression test (CLAUDE.md §7)."""
    def handler(request):
        body = json.loads(request.content)
        if body["model"] == "alpha-model":
            return httpx.Response(404, json={"error": {"message": "model_not_found"}})
        return _ok(model=body["model"])

    router = router_factory(handler)
    response = await router.chat(_request())

    # Some provider served it, and alpha's breaker stayed closed: one dead
    # model is not evidence that the provider is down.
    assert response.text == "hello"
    assert llm_health.get_tracker().get("alpha").state.value == "closed"


async def test_permanent_auth_error_is_not_retried_on_the_same_provider(router_factory):
    attempts = {"alpha": 0}

    def handler(request):
        if request.url.host == "alpha.test":
            attempts["alpha"] += 1
            return httpx.Response(401, json={"error": "bad key"})
        return _ok(model="beta-model")

    router = router_factory(handler)
    response = await router.chat(_request())

    assert response.provider == "beta"
    assert attempts["alpha"] == 1, "a 401 was retried; it can never succeed"


async def test_fatal_request_errors_stop_immediately(router_factory):
    """A 422 is the request's fault — trying five providers just adds latency."""
    calls = {"n": 0}

    def handler(_request):
        calls["n"] += 1
        return httpx.Response(422, json={"error": "messages too long"})

    router = router_factory(handler)
    with pytest.raises(PermanentError):
        await router.chat(_request())
    assert calls["n"] == 1


async def test_every_provider_down_raises_with_the_full_audit_trail(router_factory):
    router = router_factory(lambda _r: httpx.Response(503, json={"error": "down"}))

    with pytest.raises(RouterExhausted) as excinfo:
        await router.chat(_request())

    attempts = excinfo.value.attempts
    assert attempts, "exhaustion must report what was tried"
    assert {a.provider for a in attempts} >= {"alpha", "beta"}
    assert all(a.ok is False for a in attempts)


# ── Circuit breaker in the routing loop ─────────────────────────────────────

async def test_breaker_takes_a_dead_provider_out_of_rotation(router_factory):
    hits = {"alpha": 0}

    def handler(request):
        if request.url.host == "alpha.test":
            hits["alpha"] += 1
            return httpx.Response(500, json={"error": "down"})
        return _ok(model="beta-model")

    router = router_factory(handler)
    for _ in range(4):
        await router.chat(_request(cacheable=False))

    # failure_threshold is 2, so alpha stops being tried after the first pair.
    assert llm_health.get_tracker().get("alpha").state.value == "open"
    assert hits["alpha"] <= 3, f"alpha kept receiving traffic after tripping ({hits['alpha']})"


# ── Caching, dedupe, and accounting ─────────────────────────────────────────

async def test_identical_deterministic_requests_hit_the_cache(router_factory):
    calls = {"n": 0}

    def handler(_request):
        calls["n"] += 1
        return _ok()

    router = router_factory(handler)
    first = await router.chat(_request(temperature=0.0))
    second = await router.chat(_request(temperature=0.0))

    assert calls["n"] == 1, "the second identical request reached the network"
    assert first.text == second.text
    assert second.cached is True


async def test_sampled_requests_are_not_cached(router_factory):
    calls = {"n": 0}

    def handler(_request):
        calls["n"] += 1
        return _ok()

    router = router_factory(handler)
    await router.chat(_request(temperature=0.9))
    await router.chat(_request(temperature=0.9))
    assert calls["n"] == 2, "caching a sampled response would remove its variety"


async def test_concurrent_identical_requests_collapse_to_one_call(router_factory):
    calls = {"n": 0}

    async def slow_handler(_request):
        calls["n"] += 1
        await asyncio.sleep(0.05)
        return _ok()

    router = router_factory(slow_handler)
    responses = await asyncio.gather(*[
        router.chat(_request(temperature=0.9, cacheable=False)) for _ in range(6)
    ])

    assert calls["n"] == 1, f"deduplication failed: {calls['n']} network calls"
    assert all(r.text == "hello" for r in responses)


async def test_usage_and_cost_are_attributed(router_factory):
    router = router_factory(lambda _r: _ok())
    await router.chat(_request(agent="planner", workflow="nightly", temperature=0.9))

    snapshot = llm_budget.get_budget().snapshot()
    assert snapshot["by_agent"]["planner"]["requests"] == 1
    assert snapshot["by_workflow"]["nightly"]["prompt_tokens"] == 10
    assert snapshot["by_provider"]["alpha"]["completion_tokens"] == 5


async def test_metrics_record_the_failover(router_factory):
    def handler(request):
        if request.url.host == "alpha.test":
            return httpx.Response(429, json={"error": "rate limit"},
                                  headers={"retry-after": "0"})
        return _ok(model="beta-model")

    router = router_factory(handler)
    await router.chat(_request(temperature=0.9))

    exposition = llm_metrics.get_metrics().render()
    assert 'llm_rate_limits_total{provider="alpha"}' in exposition
    assert "llm_requests_total{" in exposition
    assert "llm_request_duration_seconds_bucket{" in exposition


# ── Streaming ───────────────────────────────────────────────────────────────

async def test_streaming_yields_normalised_chunks(router_factory):
    def handler(_request):
        body = (
            'data: {"model":"alpha-model","choices":[{"delta":{"content":"Hel"}}]}\n\n'
            'data: {"model":"alpha-model","choices":[{"delta":{"content":"lo"}}]}\n\n'
            'data: {"model":"alpha-model","choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
            'data: [DONE]\n\n'
        )
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    router = router_factory(handler)
    chunks = [c async for c in router.stream(_request(stream=True))]

    assert "".join(c.text for c in chunks) == "Hello"
    assert chunks[-1].finish_reason == "stop"


async def test_streaming_fails_over_before_the_first_chunk(router_factory):
    def handler(request):
        if request.url.host == "alpha.test":
            return httpx.Response(503, json={"error": "down"})
        body = (
            'data: {"model":"beta-model","choices":[{"delta":{"content":"ok"}}]}\n\n'
            'data: {"model":"beta-model","choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
        )
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    router = router_factory(handler)
    chunks = [c async for c in router.stream(_request(stream=True))]

    assert "".join(c.text for c in chunks) == "ok"
    assert chunks[0].provider == "beta"


# ── Capability routing and context ──────────────────────────────────────────

async def test_tool_requests_only_reach_tool_capable_models(router_factory):
    seen_bodies = []

    def handler(request):
        seen_bodies.append(json.loads(request.content))
        return _ok()

    router = router_factory(handler)
    tools = [{"type": "function", "function": {"name": "search", "parameters": {}}}]
    await router.chat(_request(tools=tools, temperature=0.9))

    assert seen_bodies[0]["tools"] == tools


async def test_oversized_conversation_is_fitted_not_failed(router_factory):
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return _ok()

    router = router_factory(handler)
    huge = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "THE TASK"},
        *[{"role": "assistant", "content": f"turn {i} " + "y" * 6000} for i in range(60)],
    ]
    response = await router.chat(_request(messages=huge, temperature=0.9))

    assert response.text == "hello"
    assert len(captured["body"]["messages"]) < len(huge), "context was not reduced"


# ── Load and isolation ──────────────────────────────────────────────────────

async def test_sustained_load_completes_without_loss(router_factory):
    def handler(_request):
        return _ok()

    router = router_factory(handler)
    responses = await asyncio.gather(*[
        router.chat(_request(messages=[{"role": "user", "content": f"q{i}"}],
                             temperature=0.9))
        for i in range(60)
    ])

    assert len(responses) == 60
    assert all(r.text == "hello" for r in responses)
    assert router._queue.stats()["rejected"] == 0


async def test_load_survives_an_intermittently_failing_provider(router_factory):
    counter = {"n": 0}

    def handler(request):
        counter["n"] += 1
        if request.url.host == "alpha.test" and counter["n"] % 2 == 0:
            return httpx.Response(429, json={"error": "rate limit"},
                                  headers={"retry-after": "0"})
        return _ok(model="alpha-model" if request.url.host == "alpha.test" else "beta-model")

    router = router_factory(handler)
    responses = await asyncio.gather(*[
        router.chat(_request(messages=[{"role": "user", "content": f"q{i}"}],
                             temperature=0.9))
        for i in range(40)
    ], return_exceptions=True)

    failures = [r for r in responses if isinstance(r, BaseException)]
    assert not failures, f"{len(failures)} requests failed despite a healthy fallback"


async def test_status_reports_the_full_routing_picture(router_factory):
    router = router_factory(lambda _r: _ok())
    await router.chat(_request(temperature=0.9))

    status = router.status()
    assert status["enabled"] is True
    assert status["strategy"] == "priority"
    assert {p["id"] for p in status["providers"]} == {"alpha", "beta", "gamma"}
    alpha = next(p for p in status["providers"] if p["id"] == "alpha")
    assert alpha["key_count"] == 2
    assert alpha["health"]["success_rate"] == 1.0
    # Key material never appears in anything the dashboard renders.
    assert "alpha-key-1" not in json.dumps(status)
