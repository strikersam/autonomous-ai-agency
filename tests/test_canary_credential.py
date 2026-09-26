"""Canary credential (packages/config/autonomy_limits.py, packages/security/canary.py).

A decoy token is planted in the environment every agent subprocess inherits.
Its value reaching an agent's LLM request or an outbound URL means something
dumped the environment: the action is blocked and the operator is alerted.
"""
from __future__ import annotations

import os

import httpx
import pytest

from packages.ai.agent_budget import agent_scope
from packages.ai.router import ProviderConfig, ProviderRouter
from packages.config import autonomy_limits
from packages.config.autonomy_limits import CANARY_ENV, canary_value, plant_canary
from packages.security import canary
from packages.security.canary import CanaryTripped, contains_canary


@pytest.fixture()
def alerts(monkeypatch):
    monkeypatch.setattr(autonomy_limits, "_canary_value", None)
    monkeypatch.delenv(CANARY_ENV, raising=False)
    monkeypatch.delenv("AGENCY_CANARY_ENABLED", raising=False)
    sent: list[str] = []
    monkeypatch.setattr(canary, "_notify", sent.append)
    yield sent
    os.environ.pop(CANARY_ENV, None)


def _router(monkeypatch, calls: list[str]) -> ProviderRouter:
    async def fake_post_chat(self, provider, payload, timeout_sec):
        calls.append(provider.provider_id)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(ProviderRouter, "_post_chat", fake_post_chat)
    return ProviderRouter([
        ProviderConfig("only", "openai-compatible", "https://a/v1", api_key="k",
                       default_model="a", priority=0),
    ])


def test_plant_sets_a_token_shaped_decoy_once(alerts):
    value = plant_canary()
    assert value and value.startswith("ghp_") and len(value) == 40
    assert os.environ[CANARY_ENV] == value
    assert plant_canary() == value


def test_plant_respects_the_toggle_and_an_existing_value(alerts, monkeypatch):
    monkeypatch.setenv("AGENCY_CANARY_ENABLED", "false")
    assert plant_canary() is None
    monkeypatch.setenv("AGENCY_CANARY_ENABLED", "true")
    monkeypatch.setenv(CANARY_ENV, "operator-owned-value")
    assert plant_canary() is None
    assert canary_value() is None
    assert os.environ[CANARY_ENV] == "operator-owned-value"


def test_nothing_matches_before_planting(alerts):
    assert contains_canary("anything at all") is False


@pytest.mark.anyio
async def test_agent_llm_request_carrying_the_decoy_is_blocked(alerts, monkeypatch):
    value = plant_canary()
    calls: list[str] = []
    router = _router(monkeypatch, calls)
    leaked = {"model": "a", "messages": [{"role": "tool", "content": f"{CANARY_ENV}={value}"}]}
    with agent_scope("dev"):
        with pytest.raises(CanaryTripped):
            await router.chat_completion(leaked, max_retries=0)
    assert calls == []
    assert len(alerts) == 1 and "dev" in alerts[0]
    assert value not in alerts[0]  # the alert never repeats the value


@pytest.mark.anyio
async def test_clean_agent_requests_and_human_traffic_pass(alerts, monkeypatch):
    value = plant_canary()
    calls: list[str] = []
    router = _router(monkeypatch, calls)
    with agent_scope("dev"):
        await router.chat_completion(
            {"model": "a", "messages": [{"role": "user", "content": "hi"}]}, max_retries=0
        )
    # No bound agent: a human proxy request is never inspected.
    await router.chat_completion(
        {"model": "a", "messages": [{"role": "user", "content": value}]}, max_retries=0
    )
    assert calls == ["only", "only"]
    assert alerts == []


def test_outbound_url_with_the_decoy_is_refused_before_dns(alerts, monkeypatch):
    from agent import web_reach

    value = plant_canary()

    def no_dns(*args, **kwargs):
        raise AssertionError("DNS lookup would already leak the value")

    monkeypatch.setattr(web_reach.socket, "getaddrinfo", no_dns)
    reason = web_reach.unsafe_target_reason(f"https://collector.example/?k={value}")
    assert reason == "URL carries the canary credential"
    assert len(alerts) == 1
