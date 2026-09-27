"""Regression tests: 410 Gone is a per-model condition, not per-provider.

Historically a single model returning 410 (permanently removed upstream, e.g.
a deprecated NVIDIA NIM model) cooled the *entire* provider for 5 minutes,
taking every other model on it offline. These tests lock in the fix:

- a 410 on the requested model falls over to the next candidate model on the
  same provider (rather than abandoning the provider);
- the dead model is remembered and skipped on subsequent requests;
- only when *every* candidate model is dead does the provider get cooled.
"""

from __future__ import annotations

import httpx
import pytest

from packages.ai.router import (
    ProviderConfig,
    ProviderRouter,
    clear_cooldowns,
    get_dead_models,
    is_provider_on_cooldown,
    _is_model_dead,
)


@pytest.fixture(autouse=True)
async def reset_state():
    await clear_cooldowns()
    yield
    await clear_cooldowns()


def _nvidia(default_model: str = "meta/llama-3.3-70b-instruct") -> ProviderConfig:
    return ProviderConfig(
        "nvidia",
        "openai",
        "https://integrate.api.nvidia.com/v1",
        default_model=default_model,
        priority=0,
    )


@pytest.mark.anyio
async def test_410_on_requested_model_falls_over_to_default_same_provider(monkeypatch):
    """Dead requested model → the provider's live default model still serves it."""
    tried: list[str] = []

    async def fake_post_chat(self, provider, payload, timeout_sec):
        model = payload["model"]
        tried.append(model)
        if model == "dead/model":
            return httpx.Response(410, json={"error": "Gone"})
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}]}
        )

    monkeypatch.setattr(ProviderRouter, "_post_chat", fake_post_chat)
    router = ProviderRouter([_nvidia()])

    result = await router.chat_completion(
        {"model": "dead/model", "messages": [{"role": "user", "content": "hi"}]},
        max_retries=0,
    )

    # Served by the same provider on its live default model — no failover away.
    assert result.provider.provider_id == "nvidia"
    assert result.model == "meta/llama-3.3-70b-instruct"
    assert tried == ["dead/model", "meta/llama-3.3-70b-instruct"]
    # The provider must NOT be on cooldown — only one of its models was dead.
    assert await is_provider_on_cooldown("nvidia") is False
    # The dead model is remembered.
    assert _is_model_dead("nvidia", "dead/model") is True
    assert "nvidia/dead/model" in get_dead_models()


@pytest.mark.anyio
async def test_dead_model_is_skipped_on_next_request(monkeypatch):
    """Once a model 410s, later requests don't waste a call re-probing it."""
    tried: list[str] = []

    async def fake_post_chat(self, provider, payload, timeout_sec):
        model = payload["model"]
        tried.append(model)
        if model == "dead/model":
            return httpx.Response(410, json={"error": "Gone"})
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}]}
        )

    monkeypatch.setattr(ProviderRouter, "_post_chat", fake_post_chat)
    router = ProviderRouter([_nvidia()])

    payload = {"model": "dead/model", "messages": [{"role": "user", "content": "hi"}]}
    await router.chat_completion(dict(payload), max_retries=0)
    tried.clear()
    result = await router.chat_completion(dict(payload), max_retries=0)

    # Second request skips the known-dead model entirely.
    assert "dead/model" not in tried
    assert result.model == "meta/llama-3.3-70b-instruct"


@pytest.mark.anyio
async def test_dead_model_becomes_eligible_again_after_ttl_expiry(monkeypatch):
    """Once _DEAD_MODEL_COOLDOWN_SECONDS elapses, the model is re-probed."""
    import packages.ai.router as router_mod

    tried: list[str] = []

    async def fake_post_chat(self, provider, payload, timeout_sec):
        model = payload["model"]
        tried.append(model)
        if model == "dead/model":
            return httpx.Response(410, json={"error": "Gone"})
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}]}
        )

    monkeypatch.setattr(ProviderRouter, "_post_chat", fake_post_chat)
    # Negative window → the entry is already expired the instant it is marked.
    monkeypatch.setattr(router_mod, "_DEAD_MODEL_COOLDOWN_SECONDS", -1)
    router = ProviderRouter([_nvidia()])

    payload = {"model": "dead/model", "messages": [{"role": "user", "content": "hi"}]}
    await router.chat_completion(dict(payload), max_retries=0)

    # Expired immediately → not considered dead, and pruned from the snapshot.
    assert _is_model_dead("nvidia", "dead/model") is False
    assert get_dead_models() == {}

    tried.clear()
    await router.chat_completion(dict(payload), max_retries=0)
    # Eligible again → the model is re-probed rather than silently skipped.
    assert "dead/model" in tried


@pytest.mark.anyio
async def test_all_models_dead_cools_the_provider(monkeypatch):
    """When every candidate 410s, the provider is cooled and failover proceeds."""
    async def fake_post_chat(self, provider, payload, timeout_sec):
        if provider.provider_id == "nvidia":
            return httpx.Response(410, json={"error": "Gone"})
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "from-ollama"}}]}
        )

    monkeypatch.setattr(ProviderRouter, "_post_chat", fake_post_chat)
    router = ProviderRouter(
        [
            _nvidia(),
            ProviderConfig(
                "ollama", "ollama", "http://localhost:11434",
                default_model="m", priority=5,
            ),
        ]
    )

    result = await router.chat_completion(
        {"model": "meta/llama-3.3-70b-instruct",
         "messages": [{"role": "user", "content": "hi"}]},
        max_retries=0,
    )

    # Failed over to the next provider, and the dead one is on cooldown.
    assert result.provider.provider_id == "ollama"
    assert await is_provider_on_cooldown("nvidia") is True


# ── A stale default_model must not bench a provider that has live models ─────
# Production 2026-09-26: the CEO's call failed on anthropic-claude (400) and fell
# over to nvidia-nim, whose saved default_model was z-ai/glm-5.2 (410 since
# 2026-08-28). On a fallback provider only default_model is a candidate, so
# every fallback call hit the dead model and cooled NVIDIA, the main free brain,
# for 300s, starving the planner into "planning: TimeoutError".

_LIVE = "nvidia/nemotron-3-super-120b-a12b"  # first live catalogue model


def _stale_nim() -> ProviderConfig:
    return ProviderConfig(
        "nvidia-nim", "openai-compatible", "https://integrate.api.nvidia.com/v1",
        default_model="z-ai/glm-5.2", priority=0,
    )


def _failing_primary() -> ProviderConfig:
    return ProviderConfig(
        "anthropic-claude", "openai-compatible", "https://example.invalid/v1",
        default_model="claude-x", priority=-50,
    )


@pytest.mark.anyio
async def test_stale_default_on_fallback_provider_serves_a_catalogue_model(monkeypatch):
    tried: list[tuple[str, str]] = []

    async def fake_post_chat(self, provider, payload, timeout_sec):
        tried.append((provider.provider_id, payload["model"]))
        if provider.provider_id == "anthropic-claude":
            return httpx.Response(400, json={"error": "bad request"})
        if payload["model"] == "z-ai/glm-5.2":
            return httpx.Response(410, json={"error": "Gone"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(ProviderRouter, "_post_chat", fake_post_chat)
    router = ProviderRouter([_failing_primary(), _stale_nim()])
    payload = {"model": "claude-x", "messages": [{"role": "user", "content": "plan"}]}

    result = await router.chat_completion(payload, max_retries=0)
    assert (result.provider.provider_id, result.model) == ("nvidia-nim", _LIVE)
    assert await is_provider_on_cooldown("nvidia-nim") is False
    assert _is_model_dead("nvidia-nim", "z-ai/glm-5.2")

    # Next call never touches the dead model again: no second 410.
    tried.clear()
    await router.chat_completion(dict(payload), max_retries=0)
    assert ("nvidia-nim", "z-ai/glm-5.2") not in tried
    assert await is_provider_on_cooldown("nvidia-nim") is False


@pytest.mark.anyio
async def test_provider_without_a_catalogue_entry_is_still_benched_when_all_dead(monkeypatch):
    async def fake_post_chat(self, provider, payload, timeout_sec):
        return httpx.Response(410, json={"error": "Gone"})

    monkeypatch.setattr(ProviderRouter, "_post_chat", fake_post_chat)
    custom = ProviderConfig("my-gateway", "openai-compatible", "https://gw.example/v1",
                            default_model="gone-model", priority=0)
    with pytest.raises(Exception):
        await ProviderRouter([custom]).chat_completion(
            {"model": "gone-model", "messages": [{"role": "user", "content": "x"}]},
            max_retries=0,
        )
    assert await is_provider_on_cooldown("my-gateway") is True

