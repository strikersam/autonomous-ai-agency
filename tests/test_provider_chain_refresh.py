"""Provider chain refresh (2026-11-14 production audit).

Pins four behaviours found in Render logs on 2026-11-14:

* a per-model 429 on NVIDIA NIM cooled the whole NVIDIA key, so the NVIDIA model
  that was answering was skipped and calls failed with "All 1 brain provider
  attempt(s) failed: nvidia HTTP 429";
* a provider that needs credits (402, or a refusal naming credit/billing) is
  quarantined for a live, bounded window instead of being switched off for good,
  and a daily free quota that resets is NOT mistaken for it;
* Groq's 400 "Tool choice is none, but model called a tool" moves to the next
  candidate without penalising the provider;
* Browserbase's 402 "browser minutes limit reached" quarantines Browserbase and
  falls back to the local browser.
"""
from __future__ import annotations

import asyncio
import time

import httpx
import pytest

import services.brain_failover as bf
from packages.llm import budget as llm_budget
from packages.llm import cache as llm_cache
from packages.llm import config as llm_config
from packages.llm import health as llm_health
from packages.llm import keys as llm_keys
from packages.llm import metrics as llm_metrics
from packages.llm import quarantine as llm_quarantine
from packages.llm import registry as llm_registry
from packages.llm import router as llm_router
from packages.llm import strategies as llm_strategies
from packages.llm.providers.base import classify_error
from packages.llm.router import LLMRouter
from packages.llm.types import LLMRequest, PermanentError, TransientError

PROVIDERS_YAML = """
providers:
  alpha:
    kind: openai
    base_url: https://alpha.test/v1
    key_env: [ALPHA_KEY]
    tier: free
    priority: 10
    max_concurrency: 4
    rate_limit_scope: model
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
  alpha-big:
    provider: alpha
    context_window: 32768
    supports_tools: true
    priority: 10
  alpha-small:
    provider: alpha
    context_window: 32768
    supports_tools: true
    priority: 11
  beta-model:
    provider: beta
    context_window: 32768
    supports_tools: true
    priority: 20
"""

ROUTING_YAML = """
routing:
  strategy: priority
  allow_paid: false
  queue_enabled: false
  max_providers_per_request: 5
  max_models_per_provider: 3
  retry:
    max_attempts: 6
    base_delay_sec: 0.0
    max_delay_sec: 0.0
    jitter: 0.0
    budget_sec: 30.0
"""

_MODULES = (llm_config, llm_registry, llm_health, llm_keys,
            llm_cache, llm_budget, llm_metrics, llm_router)


def _ok(model: str) -> httpx.Response:
    return httpx.Response(200, json={
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "hi"},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 4, "completion_tokens": 2},
    })


def _model_of(request: httpx.Request) -> str:
    import json
    return json.loads(request.content)["model"]


@pytest.fixture
def router_factory(tmp_path, monkeypatch):
    (tmp_path / "providers.yaml").write_text(PROVIDERS_YAML, encoding="utf-8")
    (tmp_path / "models.yaml").write_text(MODELS_YAML, encoding="utf-8")
    (tmp_path / "routing.yaml").write_text(ROUTING_YAML, encoding="utf-8")
    monkeypatch.setenv("LLM_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("LLM_ROUTER_ENABLED", "true")
    monkeypatch.setenv("ALPHA_KEY", "alpha-key")
    monkeypatch.setenv("BETA_KEY", "beta-key")
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
        if instance._client is not None and not instance._client.is_closed:
            asyncio.run(instance._client.aclose())


def _request() -> LLMRequest:
    return LLMRequest(messages=[{"role": "user", "content": "hello"}])


# ── Chain depth: a per-model 429 must not end the provider ──────────────────


async def test_per_model_429_moves_to_the_same_providers_next_model(router_factory):
    """Regression: production 2026-11-14 16:32 — one nemotron 429 cooled the NVIDIA
    key and gpt-oss-20b (answering all along) was never tried."""
    seen: list[str] = []

    def handler(request):
        model = _model_of(request)
        seen.append(f"{request.url.host}/{model}")
        if model == "alpha-big":
            return httpx.Response(429, json={"error": "Too Many Requests"})
        return _ok(model)

    router = router_factory(handler)
    response = await router.chat(_request())

    assert (response.provider, response.model) == ("alpha", "alpha-small"), seen
    assert "beta.test/beta-model" not in seen


async def test_per_model_429_rests_only_that_model(router_factory):
    def handler(request):
        model = _model_of(request)
        if model == "alpha-big":
            return httpx.Response(429, json={"error": "Too Many Requests"})
        return _ok(model)

    router = router_factory(handler)
    await router.chat(_request())
    assert router._model_is_dead("alpha", "alpha-big")
    assert not router._model_is_dead("alpha", "alpha-small")
    assert not router._keys.all_cooling("alpha", ["alpha-key"])


def test_key_scoped_providers_keep_the_key_wide_429():
    error = classify_error(429, "rate limit", provider_id="groq")
    assert isinstance(error, TransientError) and error.scope == "key"


def test_a_spent_quota_stays_key_scoped_even_on_a_per_model_provider():
    error = classify_error(429, "daily quota exhausted", provider_id="nvidia",
                           rate_limit_scope="model")
    assert error.scope == "key"


async def test_exhaustion_names_the_providers_skipped_without_a_call(router_factory, caplog):
    def handler(request):
        return httpx.Response(429, json={"error": "rate limit"})

    router = router_factory(handler)
    router._keys.record_rate_limit("beta", "beta-key", retry_after=600)
    with caplog.at_level("INFO", logger="llm.router"):
        with pytest.raises(Exception):
            await router.chat(_request())
    assert any("skipped without a call: beta" in r.getMessage() for r in caplog.records)


# ── Funds: quarantine, distinct from a resetting quota ──────────────────────


@pytest.mark.parametrize("status,body", [
    (402, "Payment Required"),
    (400, '{"type":"invalid_request_error","message":"Your credit balance is too low"}'),
    (429, '{"error":{"code":"insufficient_quota"}}'),
    (403, "Account has insufficient balance, please top up"),
])
def test_funds_refusals_are_recognised(status, body):
    assert llm_quarantine.is_funds_refusal(status, body)


@pytest.mark.parametrize("status,body", [
    # Gemini free tier: names billing, resets daily — must stay a rate limit.
    (429, "You exceeded your current quota, please check your plan and billing details."),
    # Groq free tier daily token cap, links to its billing page.
    (429, "Rate limit reached on tokens per day (TPD). Please try again in 7m. "
          "Upgrade to Dev Tier at console.groq.com/settings/billing"),
    (429, "rate limited"),
    (401, "Wrong API Key"),
    (500, "billing service down"),
])
def test_resetting_quotas_and_other_errors_are_not_funds(status, body):
    assert not llm_quarantine.is_funds_refusal(status, body)


async def test_402_quarantines_the_provider_and_fails_over(router_factory):
    def handler(request):
        if request.url.host == "alpha.test":
            return httpx.Response(402, json={"error": "Payment Required"})
        return _ok(_model_of(request))

    router = router_factory(handler)
    response = await router.chat(_request())

    assert response.provider == "beta"
    off = bf.disabled_providers(force=True)
    assert "alpha" in off
    until = bf.quarantine_until(off["alpha"])
    assert until is not None and 23 * 3600 < until - time.time() <= 24 * 3600 + 5


def test_a_quarantine_expires_on_its_own(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "kv.db"))
    monkeypatch.setattr(bf, "_DISABLED_CACHE", ({}, 0.0))
    bf.quarantine_provider("siliconflow", "402 out of credit", 3600)
    assert "siliconflow" in bf.disabled_providers(force=True)
    monkeypatch.setattr(bf.time, "time", lambda: 4e10)
    assert "siliconflow" not in bf.disabled_providers(force=True)


def test_quarantine_is_described_with_its_return_time():
    out = bf.describe_disabled_reason(
        "auto: 402 out of credit [quarantine-until=1900000000]"
    )
    assert out["code"] == "402"
    assert out["auto"] is True
    assert "out of the loop until 2030-03-17" in out["summary"]
    assert out["until"].startswith("2030-03-17")


def test_zero_hours_keeps_the_permanent_switch_off(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "kv.db"))
    monkeypatch.setattr(bf, "_DISABLED_CACHE", ({}, 0.0))
    monkeypatch.setattr(llm_quarantine, "quarantine_seconds", lambda: 0.0)
    llm_quarantine.quarantine_provider("mistral", "402 out of credit")
    reason = bf.disabled_providers(force=True)["mistral"]
    assert bf.quarantine_until(reason) is None


def test_legacy_dispatcher_quarantines_on_402(monkeypatch):
    from packages.ai import failover_client as fc

    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(llm_quarantine, "quarantine_provider",
                        lambda pid, why: calls.append((pid, why)))
    monkeypatch.setattr(fc, "_auto_disable", lambda *a: pytest.fail("permanent disable"))
    fc._quarantine("siliconflow", "402 out of credit")
    assert calls == [("siliconflow", "402 out of credit")]


# ── Groq stray tool call ────────────────────────────────────────────────────


def test_stray_tool_call_400_is_request_scoped():
    error = classify_error(
        400, '{"error":{"message":"Tool choice is none, but model called a tool"}}',
        provider_id="groq",
    )
    assert isinstance(error, TransientError) and error.scope == "request"
    assert not isinstance(error, PermanentError)


async def test_stray_tool_call_tries_the_next_candidate_without_penalty(router_factory):
    def handler(request):
        model = _model_of(request)
        if model == "alpha-big":
            return httpx.Response(400, json={"error": {
                "message": "Tool choice is none, but model called a tool"}})
        return _ok(model)

    router = router_factory(handler)
    response = await router.chat(_request())
    assert response.model == "alpha-small"
    assert not router._model_is_dead("alpha", "alpha-big")
    assert "alpha" not in bf.disabled_providers(force=True)


# ── Browserbase 402 ─────────────────────────────────────────────────────────


async def test_browserbase_402_quarantines_it_and_starts_locally(monkeypatch):
    from agent import browser

    monkeypatch.setattr(browser, "_browserbase_out_until", 0.0)
    monkeypatch.setattr(browser.settings, "browserbase_api_key", "x", raising=False)
    starts: list[bool] = []

    class FakeSession:
        def __init__(self):
            self.remote = not browser.browserbase_quarantined()

        @property
        def backend(self):
            return "browserbase" if self.remote else "local"

        async def start(self):
            starts.append(self.remote)
            if self.remote:
                raise RuntimeError(
                    "BrowserType.connect_over_cdp: WebSocket error: wss://connect."
                    "browserbase.com/ 402 Payment Required - Free plan browser "
                    "minutes limit reached. Please upgrade your account"
                )

        async def stop(self):
            return None

    monkeypatch.setattr(browser, "BrowserSession", FakeSession)
    session, error = await browser._start(FakeSession())
    assert error is None
    assert session.backend == "local"
    assert starts == [True, False]
    assert browser.browserbase_quarantined()


async def test_other_browserbase_failures_do_not_quarantine(monkeypatch):
    from agent import browser

    monkeypatch.setattr(browser, "_browserbase_out_until", 0.0)

    class FailingRemote:
        backend = "browserbase"

        async def start(self):
            raise RuntimeError("WebSocket error: 503 Service Unavailable")

        async def stop(self):
            return None

    _session, error = await browser._start(FailingRemote())
    assert error and "503" in error
    assert not browser.browserbase_quarantined()


def test_availability_summary_reports_when_a_quarantine_ends(tmp_path, monkeypatch):
    """The doctor and Providers screen read this; it must say when the provider returns."""
    from types import SimpleNamespace

    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "kv.db"))
    monkeypatch.setattr(bf, "_DISABLED_CACHE", ({}, 0.0))
    providers = [SimpleNamespace(id="siliconflow", tier="free", is_healthy=True),
                 SimpleNamespace(id="nvidia", tier="free", is_healthy=True)]
    monkeypatch.setattr(bf, "get_failover_manager",
                        lambda: SimpleNamespace(get_providers=lambda: providers))
    bf.quarantine_provider("siliconflow", "402 out of credit", 3600)

    summary = bf.brain_availability_summary()
    assert summary["usable"] == 1
    (entry,) = summary["disabled"]
    assert entry["id"] == "siliconflow" and entry["until"].endswith("UTC")


@pytest.mark.parametrize("status,body,expected", [
    (429, "the claim was discredited by reviewers", False),
    (429, "accreditation pending", False),
    (400, "Invalid input: the 'credit card payment' content was rejected", False),
    (400, "Your credit balance is too low to access the API", True),
    (403, "billing is not enabled for this project", True),
    (429, "You have run out of credits", True),
    (402, "", True),
])
def test_funds_classifier_matches_whole_words_only(status, body, expected):
    from packages.llm.quarantine import is_funds_refusal
    assert is_funds_refusal(status, body) is expected


# ── Review findings on PR #1975 ─────────────────────────────────────────────


def _legacy_refusal(monkeypatch, status: int, text: str):
    """Run the legacy dispatcher against one refusal; return (error, quarantined, disabled)."""
    from types import SimpleNamespace

    from packages.ai import failover_client as fc

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, *a, **k):
            return httpx.Response(status, text=text)

    quarantined: list[str] = []
    disabled: list[str] = []
    monkeypatch.setattr(fc.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(fc, "_quarantine", lambda pid, why: quarantined.append(pid))
    monkeypatch.setattr(fc, "_auto_disable", lambda pid, why: disabled.append(pid))
    monkeypatch.setattr(fc, "_provider_keys", lambda p: [])
    fm = SimpleNamespace(record_failure=lambda *a, **k: None,
                         resolve_model=lambda provider, model: model or "m")
    provider = SimpleNamespace(id="acme", kind="openai", type="openai-compatible",
                               api_key="k", base_url="https://acme.test/v1", models=["m"])
    result, error = asyncio.run(fc._try_provider(
        provider, {"model": "m", "messages": []}, fm, [], 5.0, fc._Budget(3, 60.0)))
    assert result is None
    return error, quarantined, disabled


@pytest.mark.parametrize("status,body", [
    (403, "Payment required: add credits"),
    (429, '{"error":{"code":"insufficient_quota","message":"You exceeded your quota"}}'),
])
def test_legacy_funds_refusal_is_quarantined_before_the_status_returns(
        monkeypatch, status, body):
    _error, quarantined, disabled = _legacy_refusal(monkeypatch, status, body)
    assert quarantined == ["acme"] and disabled == []


def test_legacy_400_the_funds_classifier_rejects_does_not_disable(monkeypatch):
    _error, quarantined, disabled = _legacy_refusal(
        monkeypatch, 400, "Invalid request: prompt contains billing")
    assert quarantined == [] and disabled == []


def test_browserbase_free_plan_402_text_counts_as_funds():
    from agent import browser

    assert browser._is_funds_failure(
        "connect_over_cdp: 402 Free plan browser minutes limit reached")
    assert not browser._is_funds_failure("connect_over_cdp: 503 Service Unavailable")
    assert not browser._is_funds_failure("free plan minutes limit reached")  # no 402


def test_quoted_request_content_is_not_a_funds_refusal():
    echoed = '{"error":{"message":"Invalid message content","input":"payment required"}}'
    assert not llm_quarantine.is_funds_refusal(400, echoed)
    assert not getattr(classify_error(400, echoed, provider_id="acme"), "funds", False)
    real = '{"error":{"message":"Payment required: credit balance is too low"}}'
    assert llm_quarantine.is_funds_refusal(400, real)


def test_env_derived_nvidia_provider_rests_one_model_on_429(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nv-key")
    providers: dict = {}
    llm_config._merge_env_defaults(providers, {})
    assert providers["nvidia"].rate_limit_scope == "model"
    assert all(p.rate_limit_scope == "key" for pid, p in providers.items() if pid != "nvidia")


def test_classify_error_is_within_the_function_length_limit():
    import ast
    import inspect

    from packages.llm.providers import base

    tree = ast.parse(inspect.getsource(base))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            assert node.end_lineno - node.lineno + 1 <= 50, node.name


async def test_funds_refusal_skips_the_providers_remaining_models(router_factory):
    seen: list[str] = []

    def handler(request):
        model = _model_of(request)
        seen.append(model)
        if request.url.host == "alpha.test":
            return httpx.Response(402, json={"error": "Payment Required"})
        return _ok(model)

    router = router_factory(handler)
    response = await router.chat(_request())
    assert response.provider == "beta"
    assert [m for m in seen if m.startswith("alpha")] == ["alpha-big"]


async def test_request_scoped_error_releases_the_half_open_probe_permit(router_factory):
    def handler(request):
        model = _model_of(request)
        if request.url.host == "alpha.test":
            return httpx.Response(400, json={"error": {
                "message": "Tool choice is none, but model called a tool"}})
        return _ok(model)

    router = router_factory(handler)
    health = router._health
    for _ in range(20):
        health.record_failure("alpha", status=500)
    health._get("alpha").state = llm_health.BreakerState.HALF_OPEN
    health._get("alpha").probes_in_flight = 0
    health._get("alpha").probes_allowed = 1
    await router.chat(_request())
    assert health._get("alpha").probes_in_flight == 0


async def test_cancelled_local_startup_closes_the_replacement_session(monkeypatch):
    from agent import browser

    monkeypatch.setattr(browser, "_browserbase_out_until", 0.0)
    stopped: list[str] = []

    class Remote:
        backend = "browserbase"

        async def start(self):
            raise RuntimeError("402 Payment Required - Free plan browser minutes limit reached")

        async def stop(self):
            stopped.append("remote")

    class Local:
        backend = "local"

        async def start(self):
            raise asyncio.CancelledError

        async def stop(self):
            stopped.append("local")

    monkeypatch.setattr(browser, "BrowserSession", Local)
    with pytest.raises(asyncio.CancelledError):
        await browser._start(Remote())
    assert stopped == ["remote", "local"]


def test_long_json_400_echoing_a_billing_phrase_is_not_a_funds_refusal():
    """Regression: truncating before parsing broke the JSON and exposed the echoed input."""
    import json
    from packages.llm.quarantine import is_funds_refusal

    body = json.dumps({"error": {"message": "bad request"},
                       "input": "payment required " + "x" * 5000})
    assert is_funds_refusal(400, body) is False
    assert is_funds_refusal(429, body) is False
    # Truncated or malformed JSON is not scanned as text either...
    assert is_funds_refusal(400, body[:4000]) is False
    assert is_funds_refusal(403, '{"error": "payment required') is False
    # ...but a 402 is a funds refusal whatever the body, and plain text still is.
    assert is_funds_refusal(402, '{"error": "payment') is True
    assert is_funds_refusal(403, "payment required") is True
