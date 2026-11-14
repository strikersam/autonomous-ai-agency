from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from packages.ai import brain
from packages.ai.router import ProviderConfig, ProviderRouter


def _aws(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-access")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("ALLOW_PAID_BRAIN", "true")


def _bedrock_ids(router: ProviderRouter) -> list[str]:
    return [p.provider_id for p in router.providers if p.type == "bedrock"]


@pytest.mark.parametrize("value", [None, "", "true", "1", "on", "garbage"])
def test_kill_switch_is_on_unless_explicitly_turned_off(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("BEDROCK_DISABLED", raising=False)
    else:
        monkeypatch.setenv("BEDROCK_DISABLED", value)
    assert brain.bedrock_disabled() is True


@pytest.mark.parametrize("value", ["false", "0", "off", "no", " FALSE "])
def test_kill_switch_turns_off_only_on_an_explicit_false(monkeypatch, value):
    monkeypatch.setenv("BEDROCK_DISABLED", value)
    assert brain.bedrock_disabled() is False


def test_router_never_registers_bedrock_while_the_switch_is_on(monkeypatch):
    """AWS keys plus ALLOW_PAID_BRAIN used to be enough to register Bedrock."""
    _aws(monkeypatch)
    monkeypatch.delenv("BEDROCK_DISABLED", raising=False)
    assert _bedrock_ids(ProviderRouter.from_env()) == []


def test_router_registers_bedrock_only_when_the_switch_is_off(monkeypatch):
    _aws(monkeypatch)
    monkeypatch.setenv("BEDROCK_DISABLED", "false")
    assert _bedrock_ids(ProviderRouter.from_env()) == ["bedrock"]


def test_an_explicit_bedrock_provider_is_refused_at_call_time(monkeypatch):
    monkeypatch.delenv("BEDROCK_DISABLED", raising=False)
    provider = ProviderConfig(
        provider_id="bedrock",
        type="bedrock",
        base_url="https://bedrock-runtime.us-east-1.amazonaws.com",
        api_key="test-access",
        default_model="us.anthropic.claude-opus-4-6-v1",
        priority=15,
        headers={"X-Bedrock-Secret": "test-secret", "X-Bedrock-Region": "us-east-1"},
    )
    router = ProviderRouter([provider])
    with pytest.raises(RuntimeError, match="BEDROCK_DISABLED"):
        asyncio.run(router._post_bedrock_converse(provider, {"messages": []}))


def test_gateway_drops_a_bedrock_provider_even_when_it_is_enabled(monkeypatch):
    from packages.llm.config import bedrock_blocked

    mantle = SimpleNamespace(
        id="bedrock", kind="openai", base_url="https://bedrock-mantle.us-east-1.api.aws/v1"
    )
    nvidia = SimpleNamespace(
        id="nvidia", kind="openai", base_url="https://integrate.api.nvidia.com/v1"
    )
    monkeypatch.delenv("BEDROCK_DISABLED", raising=False)
    assert bedrock_blocked(mantle) is True
    assert bedrock_blocked(nvidia) is False
    monkeypatch.setenv("BEDROCK_DISABLED", "false")
    assert bedrock_blocked(mantle) is False


def test_gateway_config_hides_bedrock_while_the_switch_is_on(monkeypatch):
    from packages.llm.config import get_config

    monkeypatch.setenv("BEDROCK_BRAIN_ENABLED", "true")
    monkeypatch.delenv("BEDROCK_DISABLED", raising=False)
    config = get_config()
    assert all("bedrock" not in p.base_url.lower() for p in config.enabled_providers())


def test_agent_loop_bedrock_fallback_checks_the_switch():
    import inspect

    from agent.loop import AgentRunner

    src = inspect.getsource(AgentRunner._chat_text)
    assert "not _bedrock_disabled()" in src


def test_the_switch_is_a_live_platform_control_defaulting_on():
    from packages.config.control_catalogue import CONTROLS

    control = next(c for c in CONTROLS if c.key == "BEDROCK_DISABLED")
    assert control.default == "true"
    assert control.live is True


def test_a_router_built_before_the_switch_went_on_stops_probing_bedrock(monkeypatch):
    """Health and discovery calls are free, but a kill switch should mean no calls."""
    from packages.llm.router import LLMRouter

    calls: list[str] = []

    class _Provider:
        id = "bedrock"
        config = SimpleNamespace(
            id="bedrock", kind="openai", tier="cheap", key_env=[],
            base_url="https://bedrock-mantle.us-east-1.api.aws/v1",
        )

        async def health(self, **_):
            calls.append("health")
            return {"healthy": True}

        async def list_models(self, **_):
            calls.append("list_models")
            return ["qwen.qwen3-coder-next"]

    async def _client():
        return None

    router = LLMRouter.__new__(LLMRouter)
    router._providers = {"bedrock": _Provider()}
    router._http = _client
    monkeypatch.delenv("BEDROCK_DISABLED", raising=False)

    assert asyncio.run(router.health_check()) == []
    assert asyncio.run(router.health_check("bedrock")) == []
    assert asyncio.run(router.discover_models()) == {}
    assert calls == []


# ── Gaps found by review of the first version ───────────────────────────────────

def _mantle_provider() -> ProviderConfig:
    """Labelled openai-compatible, but it spends on the Bedrock account."""
    return ProviderConfig(
        provider_id="my-gateway",
        type="openai-compatible",
        base_url="https://bedrock-mantle.us-east-1.api.aws/v1",
        api_key="test-key",
        default_model="qwen.qwen3-coder-next",
        priority=15,
    )


def test_a_generic_provider_pointing_at_bedrock_is_refused_at_call_time(monkeypatch):
    monkeypatch.delenv("BEDROCK_DISABLED", raising=False)
    provider = _mantle_provider()
    with pytest.raises(RuntimeError, match="BEDROCK_DISABLED"):
        asyncio.run(ProviderRouter([provider])._post_chat(provider, {"messages": []}))


def test_a_generic_bedrock_endpoint_is_not_health_probed_or_reported_healthy(monkeypatch):
    monkeypatch.delenv("BEDROCK_DISABLED", raising=False)
    provider = _mantle_provider()

    attempts: list[str] = []

    async def _record(self, url, *_a, **_k):  # any HTTP use here would be a call to AWS
        attempts.append(str(url))
        return SimpleNamespace(status_code=200, json=lambda: {"data": []})

    monkeypatch.setattr("httpx.AsyncClient.get", _record)
    monkeypatch.setattr("httpx.AsyncClient.post", _record)
    assert asyncio.run(ProviderRouter([provider]).health_check(provider)) is False
    assert attempts == [], f"health_check probed {attempts}"


def test_an_unrelated_provider_is_not_affected_by_the_switch(monkeypatch):
    monkeypatch.delenv("BEDROCK_DISABLED", raising=False)
    other = ProviderConfig(
        provider_id="nvidia", type="openai-compatible",
        base_url="https://integrate.api.nvidia.com/v1", api_key="k",
        default_model="m", priority=10,
    )
    from packages.ai.brain import is_bedrock_endpoint

    assert is_bedrock_endpoint(other.provider_id, other.base_url, other.type) is False


def test_embeddings_skip_a_bedrock_provider_while_the_switch_is_on(monkeypatch):
    from packages.llm.router import LLMRouter

    posted: list[str] = []

    class _Client:
        async def post(self, url, **_):
            posted.append(url)
            raise AssertionError("an embeddings call reached Bedrock")

    class _Registry:
        def candidates(self, **_):
            return [SimpleNamespace(id="amazon.titan-embed", provider="bedrock")]

        def get(self, _model):
            return None

    class _Cache:
        embedding = SimpleNamespace(get=lambda _k: None, put=lambda *_a, **_k: None)

    async def _http():
        return _Client()

    router = LLMRouter.__new__(LLMRouter)
    router._providers = {"bedrock": SimpleNamespace(
        config=SimpleNamespace(
            id="bedrock", kind="openai", key_env=["X"],
            base_url="https://bedrock-mantle.us-east-1.api.aws/v1"),
        auth_headers=lambda _k: {},
    )}
    router._registry = _Registry()
    router._cache = _Cache()
    router._http = _http
    router._health = SimpleNamespace(
        is_available=lambda _p: True, record_failure=lambda *_a, **_k: None)
    router._keys = SimpleNamespace(acquire=lambda *_a, **_k: ("key", 0))
    router._metrics = SimpleNamespace(record_cache=lambda **_k: None)
    monkeypatch.delenv("BEDROCK_DISABLED", raising=False)
    monkeypatch.setenv("X", "key")

    try:
        asyncio.run(router.embed(["hello"]))
    except Exception:  # noqa: BLE001 - exhaustion is fine; reaching AWS is not
        pass
    assert posted == []


def test_a_providers_ui_record_pointing_at_bedrock_is_refused(monkeypatch):
    """backend/llm_providers.py builds configs by hand and never met ProviderRouter."""
    from backend import llm_providers as lp

    monkeypatch.delenv("BEDROCK_DISABLED", raising=False)
    calls: list[str] = []

    class _Client:
        async def post(self, url, **_):
            calls.append(url)
            raise AssertionError("chat reached Bedrock")

        async def get(self, url, **_):
            calls.append(url)
            raise AssertionError("model listing reached Bedrock")

    record = lp.LlmProviderConfig(
        type="openai_compat", base_url="https://bedrock-mantle.us-east-1.api.aws/v1",
        api_key="k", default_model="m",
    )
    with pytest.raises(RuntimeError, match="BEDROCK_DISABLED"):
        asyncio.run(lp.chat_completion_text(
            record, messages=[{"role": "user", "content": "x"}], model="m",
            temperature=0.1, client=_Client()))
    with pytest.raises(RuntimeError, match="BEDROCK_DISABLED"):
        asyncio.run(lp.list_openai_models(record, client=_Client()))
    assert calls == []


def test_failover_and_discovery_never_call_a_bedrock_base_url(monkeypatch):
    from packages.ai import failover_client, model_discovery

    monkeypatch.delenv("BEDROCK_DISABLED", raising=False)
    provider = SimpleNamespace(
        id="custom", kind="openai", type="openai-compatible", api_key="k",
        base_url="https://bedrock-runtime.us-east-1.amazonaws.com",
    )
    result, err = asyncio.run(failover_client._try_provider(
        provider, {"model": "m", "messages": []}, None, [], 5.0, None))
    assert result is None and "BEDROCK_DISABLED" in err
    assert asyncio.run(model_discovery.discover_models(provider)) is None


def test_stream_refuses_a_candidate_whose_switch_flipped_while_waiting(monkeypatch):
    """Behavioural: the recheck after the bulkhead slot must stop the provider call."""
    import contextlib

    from packages.llm.router import LLMRouter
    from packages.llm.types import LLMRequest

    provider_calls: list[str] = []
    config = SimpleNamespace(
        id="bedrock", kind="openai", key_env=[],
        base_url="https://bedrock-mantle.us-east-1.api.aws/v1")

    class _Provider:
        async def stream(self, *_a, **_k):
            provider_calls.append("stream")
            yield SimpleNamespace(delta="x")

    @contextlib.asynccontextmanager
    async def _slot(_pid, timeout=0):
        monkeypatch.delenv("BEDROCK_DISABLED", raising=False)  # the switch goes ON while queued
        yield True

    async def _http():
        return None

    router = LLMRouter.__new__(LLMRouter)
    router._providers = {"bedrock": _Provider()}
    router._bulkhead = SimpleNamespace(slot=_slot)
    router._health = SimpleNamespace(is_available=lambda _p: True,
                                     record_success=lambda *_a, **_k: None)
    router._keys = SimpleNamespace(acquire=lambda *_a, **_k: ("k", 0),
                                   record_success=lambda *_a, **_k: None)
    router._metrics = SimpleNamespace(record_request=lambda **_k: None)
    router._http = _http
    router._apply_policy = lambda r: r
    router._candidates = lambda _r: [SimpleNamespace(
        provider=config, model=SimpleNamespace(id="m"))]
    router._retry_budget = lambda _r: SimpleNamespace(
        charge=lambda: None, exhausted=lambda: False)
    router._penalise = lambda *_a, **_k: None
    monkeypatch.setenv("BEDROCK_DISABLED", "false")  # off when the candidates were built

    async def _drain():
        async for _ in router.stream(LLMRequest(messages=[{"role": "user", "content": "x"}])):
            pass

    with pytest.raises(Exception):  # noqa: B017 - every candidate was skipped: exhausted
        asyncio.run(_drain())
    assert provider_calls == []
