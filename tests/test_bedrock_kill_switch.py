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
    reached: list[str] = []

    async def _spy(self, url, *_a, **_k):
        reached.append(str(url))
        raise AssertionError("model discovery reached Bedrock")

    monkeypatch.setattr("httpx.AsyncClient.get", _spy)
    assert asyncio.run(model_discovery.discover_models(provider)) is None
    assert reached == []


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


# ── Round-2 review: user-created Providers-UI records, OpenClaw, liveness probe ──

BEDROCK_URL = "https://bedrock-mantle.us-east-1.api.aws/v1"


def _webui_client(tmp_path, monkeypatch):
    """A TestClient whose /ui/api uses a store that already holds a Bedrock record."""
    from fastapi.testclient import TestClient

    import proxy
    from webui.config_store import JsonConfigStore, JsonStorePaths
    from webui.providers import ProviderManager
    from webui.workspaces import WorkspaceManager

    store = JsonConfigStore(JsonStorePaths(
        providers=tmp_path / "providers.json", workspaces=tmp_path / "workspaces.json"))
    # Written straight to the store, as a record created before the switch existed.
    store.save("providers", [{
        "provider_id": "prov_bedrock", "name": "aws", "base_url": BEDROCK_URL,
        "api_key": "k", "kind": "openai_compat", "default_model": "m",
        "default_temperature": 0.2, "priority": 0,
        "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
    }])
    proxy.app.state.webui_providers = ProviderManager(store)
    proxy.app.state.webui_workspaces = WorkspaceManager(store, default_local_root=tmp_path)
    proxy.app.dependency_overrides[proxy.verify_api_key] = lambda: proxy.AuthContext(
        key="k", email="t@example.com", department="e", key_id="kid", source="legacy")
    return TestClient(proxy.app), proxy


def test_webui_chat_and_model_list_refuse_a_stored_bedrock_record(tmp_path, monkeypatch):
    monkeypatch.delenv("BEDROCK_DISABLED", raising=False)
    reached: list[str] = []

    async def _spy(self, url, *_a, **_k):
        reached.append(str(url))
        raise AssertionError("the Providers UI reached Bedrock")

    monkeypatch.setattr("httpx.AsyncClient.get", _spy)
    monkeypatch.setattr("httpx.AsyncClient.post", _spy)
    client, proxy = _webui_client(tmp_path, monkeypatch)
    try:
        chat = client.post("/ui/api/chat", json={
            "provider_id": "prov_bedrock", "model": "m",
            "messages": [{"role": "user", "content": "hi"}]})
        models = client.get("/ui/api/providers/prov_bedrock/models")
    finally:
        proxy.app.dependency_overrides.clear()
    assert chat.status_code == 403 and models.status_code == 403
    assert reached == []


def test_webui_cannot_create_a_bedrock_provider_while_the_switch_is_on(monkeypatch):
    from webui.providers import _validate_provider_base_url

    monkeypatch.delenv("BEDROCK_DISABLED", raising=False)
    with pytest.raises(ValueError, match="BEDROCK_DISABLED"):
        _validate_provider_base_url(BEDROCK_URL)
    with pytest.raises(ValueError, match="BEDROCK_DISABLED"):
        _validate_provider_base_url("https://bedrock-runtime.us-east-1.amazonaws.com/openai")
    monkeypatch.setenv("BEDROCK_DISABLED", "false")
    assert _validate_provider_base_url(BEDROCK_URL)


def test_liveness_probe_never_posts_to_a_bedrock_override(monkeypatch):
    from services import brain_liveness

    monkeypatch.delenv("BEDROCK_DISABLED", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "x")
    reached: list[str] = []

    async def _spy(self, url, *_a, **_k):
        reached.append(str(url))
        raise AssertionError("liveness probe reached Bedrock")

    monkeypatch.setattr("httpx.AsyncClient.post", _spy)
    result = asyncio.run(brain_liveness.probe_model_liveness(
        "groq", "m", base_url="https://bedrock-mantle.us-east-1.api.aws"))
    assert result.live is False and "BEDROCK_DISABLED" in result.reason
    assert reached == []


def test_openclaw_chat_skips_a_provider_whose_url_is_bedrock(monkeypatch):
    from services import openclaw_gateway

    monkeypatch.delenv("BEDROCK_DISABLED", raising=False)
    reached: list[str] = []

    async def _spy(self, url, *_a, **_k):
        reached.append(str(url))
        raise AssertionError("OpenClaw reached Bedrock")

    monkeypatch.setattr("httpx.AsyncClient.post", _spy)
    provider = SimpleNamespace(
        id="openrouter", kind="openai", type="openai-compatible", api_key="k",
        base_url="https://bedrock-mantle.us-east-1.api.aws/v1")
    sent = {"done": False}

    class _FM:
        def max_attempts(self):
            return 2

        def next_provider(self, exclude=()):
            if sent["done"]:
                return None
            sent["done"] = True
            return provider

        def resolve_model(self, *_a, **_k):
            return "m"

    import services.brain_failover as bf

    monkeypatch.setattr(bf, "get_failover_manager", lambda: _FM())
    asyncio.run(openclaw_gateway._cmd_chat({"message": "hi"}))
    assert reached == []


# ── Process-wide httpx guard (round 3: one check instead of one per call site) ──

def _mock_client(calls: list[str], *, sync: bool = False):
    import httpx

    def _handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(_handler)
    return httpx.Client(transport=transport) if sync else httpx.AsyncClient(transport=transport)


@pytest.mark.parametrize("url", [
    "https://bedrock-mantle.us-east-1.api.aws/v1/chat/completions",
    "https://bedrock-runtime.us-east-1.amazonaws.com/model/x/converse",
    "https://BEDROCK-RUNTIME.eu-west-1.amazonaws.com/openai/v1/chat/completions",
    "https://vpce-0abc.bedrock-runtime.us-east-1.vpce.amazonaws.com/x",
])
def test_http_guard_refuses_every_bedrock_host_for_async_and_sync_clients(monkeypatch, url):
    monkeypatch.delenv("BEDROCK_DISABLED", raising=False)
    calls: list[str] = []

    async def _go():
        async with _mock_client(calls) as client:
            await client.post(url, json={})

    with pytest.raises(RuntimeError, match="BEDROCK_DISABLED"):
        asyncio.run(_go())
    with pytest.raises(RuntimeError, match="BEDROCK_DISABLED"):
        _mock_client(calls, sync=True).post(url, json={})
    assert calls == [], "the request reached the transport"


def test_http_guard_lets_other_hosts_through_even_if_the_path_says_bedrock(monkeypatch):
    monkeypatch.delenv("BEDROCK_DISABLED", raising=False)
    calls: list[str] = []

    async def _go():
        async with _mock_client(calls) as client:
            await client.get("https://github.com/aws/bedrock-samples")
            await client.get("https://api.groq.com/openai/v1/models?q=bedrock")

    asyncio.run(_go())
    assert len(calls) == 2


def test_http_guard_follows_the_live_switch(monkeypatch):
    calls: list[str] = []
    url = "https://bedrock-mantle.us-east-1.api.aws/v1/models"

    async def _go():
        async with _mock_client(calls) as client:
            return await client.get(url)

    monkeypatch.setenv("BEDROCK_DISABLED", "false")
    assert asyncio.run(_go()).status_code == 200
    monkeypatch.setenv("BEDROCK_DISABLED", "true")
    with pytest.raises(RuntimeError):
        asyncio.run(_go())
    monkeypatch.delenv("BEDROCK_DISABLED")
    with pytest.raises(RuntimeError):
        asyncio.run(_go())
    assert len(calls) == 1


def test_http_guard_is_installed_once_by_importing_the_brain_module():
    import httpx

    from packages.security import bedrock_guard

    attr = "_send_single_request" if hasattr(httpx.Client, "_send_single_request") else "send"
    assert getattr(httpx.AsyncClient, attr).__name__ == "guarded_async_send"
    assert getattr(httpx.Client, attr).__name__ == "guarded_send"
    assert bedrock_guard.install_bedrock_http_guard() is False  # idempotent


def test_a_bedrock_model_preference_is_rejected_for_cli_runtimes(monkeypatch):
    """model_preference reaches `--model` (aider runs on litellm): a bedrock/ name must 400."""
    from fastapi import HTTPException

    from runtimes import api

    monkeypatch.delenv("BEDROCK_DISABLED", raising=False)
    adapter_used: list[str] = []

    class _Registry:
        def get(self, _id):
            adapter_used.append("adapter")
            return SimpleNamespace()

    monkeypatch.setattr(api, "get_runtime_manager", lambda: SimpleNamespace(_registry=_Registry()))
    for name in ("bedrock/anthropic.claude-3", "bedrock_converse/x", "Bedrock/Y"):
        body = api.RunTaskBody(instruction="hi", model_preference=name)
        with pytest.raises(HTTPException) as err:
            asyncio.run(api.run_task_on_runtime("aider", body, user={}))
        assert err.value.status_code == 400
        assert "Bedrock" in str(err.value.detail)


def test_the_docker_sidecar_refuses_a_bedrock_base_url(monkeypatch):
    import importlib.util
    import pathlib

    from fastapi import HTTPException

    path = pathlib.Path(__file__).resolve().parent.parent / "docker" / "agent_runtime.py"
    spec = importlib.util.spec_from_file_location("agent_runtime_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.delenv("BEDROCK_DISABLED", raising=False)
    with pytest.raises(HTTPException) as err:
        asyncio.run(module._chat_with_openai_compat(
            base_url="https://bedrock-mantle.us-east-1.api.aws/v1", api_key="k",
            messages=[], model="m"))
    assert err.value.status_code == 503


def test_http_guard_refuses_a_redirect_from_an_allowed_host_to_bedrock(monkeypatch):
    import httpx

    monkeypatch.delenv("BEDROCK_DISABLED", raising=False)
    reached: list[str] = []

    def _handler(request):
        reached.append(request.url.host)
        if request.url.host == "ok.example.com":
            return httpx.Response(302, headers={
                "location": "https://bedrock-runtime.us-east-1.amazonaws.com/x"})
        return httpx.Response(200, json={})

    async def _go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(_handler),
                                     follow_redirects=True) as client:
            await client.get("https://ok.example.com/start")

    with pytest.raises(RuntimeError, match="BEDROCK_DISABLED"):
        asyncio.run(_go())
    with pytest.raises(RuntimeError, match="BEDROCK_DISABLED"):
        httpx.Client(transport=httpx.MockTransport(_handler),
                     follow_redirects=True).get("https://ok.example.com/start")
    assert "bedrock-runtime.us-east-1.amazonaws.com" not in reached


def test_cli_runtime_children_do_not_inherit_bedrock_credentials(monkeypatch):
    from packages.ai.brain import bedrock_safe_env

    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_BEARER_TOKEN_BEDROCK",
                 "AWS_SESSION_TOKEN", "AWS_PROFILE", "ANTHROPIC_BEDROCK_BASE_URL"):
        monkeypatch.setenv(name, "secret")
    monkeypatch.setenv("CLAUDE_CODE_USE_BEDROCK", "1")
    monkeypatch.setenv("GROQ_API_KEY", "keep-me")
    monkeypatch.delenv("BEDROCK_DISABLED", raising=False)

    env = bedrock_safe_env()
    assert env["CLAUDE_CODE_USE_BEDROCK"] == "0"
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_BEARER_TOKEN_BEDROCK",
                 "AWS_SESSION_TOKEN", "AWS_PROFILE", "ANTHROPIC_BEDROCK_BASE_URL"):
        assert name not in env, name
    assert env["GROQ_API_KEY"] == "keep-me"  # nothing else is touched
    # And a caller-supplied env is scrubbed too, without mutating the input.
    given = {"AWS_ACCESS_KEY_ID": "x", "PATH": "/bin"}
    assert "AWS_ACCESS_KEY_ID" not in bedrock_safe_env(given) and "AWS_ACCESS_KEY_ID" in given

    monkeypatch.setenv("BEDROCK_DISABLED", "false")  # switched off: untouched
    assert bedrock_safe_env()["AWS_ACCESS_KEY_ID"] == "secret"


def test_cli_adapters_launch_their_task_with_the_scrubbed_env():
    import inspect

    from runtimes.adapters import aider, claude_code, goose, jcode, opencode, task_harness

    for module in (aider, claude_code, goose, jcode, opencode, task_harness):
        assert "bedrock_safe_env" in inspect.getsource(module), module.__name__
