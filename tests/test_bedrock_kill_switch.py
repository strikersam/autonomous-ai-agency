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
