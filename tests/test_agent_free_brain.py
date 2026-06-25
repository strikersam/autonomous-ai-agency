"""Free-brain policy regression tests for the agent runtime (issue #656).

Guarantees that with no paid opt-in (``ALLOW_PAID_BRAIN`` unset), the
``internal_agent`` runtime (`agent/loop.py::AgentRunner._chat_text`) NEVER calls
`api.anthropic.com` — even when the requested model is Anthropic-shaped (e.g. a
stale ``AGENT_*_MODEL=us.anthropic.claude-opus-*``) and ``ANTHROPIC_API_KEY`` is
present. Instead it transparently routes to the free NVIDIA brain.
"""
from __future__ import annotations

from typing import ClassVar

import pytest

import brain_policy
from agent.loop import AgentRunner


# ── brain_policy unit tests ──────────────────────────────────────────────────


def test_allow_paid_brain_default_false(monkeypatch):
    monkeypatch.delenv("ALLOW_PAID_BRAIN", raising=False)
    assert brain_policy.allow_paid_brain() is False


def test_allow_paid_brain_opt_in(monkeypatch):
    for v in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("ALLOW_PAID_BRAIN", v)
        assert brain_policy.allow_paid_brain() is True
    monkeypatch.setenv("ALLOW_PAID_BRAIN", "false")
    assert brain_policy.allow_paid_brain() is False


def test_is_anthropic_model():
    assert brain_policy.is_anthropic_model("us.anthropic.claude-opus-4-6-v1")
    assert brain_policy.is_anthropic_model("claude-sonnet-4-6")
    assert brain_policy.is_anthropic_model("claude-3-5-sonnet-latest")
    assert brain_policy.is_anthropic_model("some-opus-model")
    assert not brain_policy.is_anthropic_model("nvidia/nemotron-3-ultra-550b-a55b")
    assert not brain_policy.is_anthropic_model("qwen3-coder:30b")
    assert not brain_policy.is_anthropic_model("")
    assert not brain_policy.is_anthropic_model(None)


def test_resolve_free_nvidia_brain_none_without_key(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVidiaApiKey", raising=False)
    assert brain_policy.resolve_free_nvidia_brain() is None


def test_resolve_free_nvidia_brain_from_env(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-TESTKEY")
    monkeypatch.delenv("NVIDIA_BASE_URL", raising=False)
    monkeypatch.setenv("NVIDIA_DEFAULT_MODEL", "nvidia/nemotron-3-ultra-550b-a55b")
    base, headers, model = brain_policy.resolve_free_nvidia_brain()
    assert base == "https://integrate.api.nvidia.com/v1"
    assert headers == {"Authorization": "Bearer nvapi-TESTKEY"}
    assert model == "nvidia/nemotron-3-ultra-550b-a55b"


# ── _chat_text routing (the #656 leak) ───────────────────────────────────────


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeAsyncClient:
    """Captures the POST url/json/headers so tests can assert the endpoint."""

    captured: ClassVar[dict] = {}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None, headers=None, **kwargs):
        _FakeAsyncClient.captured = {"url": url, "json": json, "headers": headers}
        return _FakeResponse({"choices": [{"message": {"content": "ok-from-nvidia"}}]})


@pytest.fixture
def _free_env(monkeypatch):
    """No paid opt-in; a stale Anthropic key present; NVIDIA configured."""
    monkeypatch.delenv("ALLOW_PAID_BRAIN", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-STALE")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-TESTKEY")
    monkeypatch.setenv("NVIDIA_DEFAULT_MODEL", "nvidia/nemotron-3-ultra-550b-a55b")
    monkeypatch.delenv("NVIDIA_BASE_URL", raising=False)
    _FakeAsyncClient.captured = {}


async def test_chat_text_reroutes_anthropic_model_to_nvidia(_free_env, monkeypatch):
    """The core #656 regression: an Anthropic-shaped model must NOT hit
    api.anthropic.com — it must POST to the free NVIDIA endpoint instead."""
    import agent.loop as loop_mod

    monkeypatch.setattr(loop_mod.httpx, "AsyncClient", _FakeAsyncClient)
    # Guard: if the Anthropic SDK is ever constructed, fail loudly.
    import anthropic as _anthropic  # noqa: F401

    def _boom(*a, **k):
        raise AssertionError("Anthropic SDK must NOT be called under free-brain policy")

    monkeypatch.setattr(_anthropic, "Anthropic", _boom, raising=False)

    runner = AgentRunner(ollama_base="http://localhost:11434")
    out = await runner._chat_text(
        "us.anthropic.claude-opus-4-6-v1",
        [{"role": "user", "content": "hi"}],
    )

    assert out == "ok-from-nvidia"
    cap = _FakeAsyncClient.captured
    assert "integrate.api.nvidia.com" in cap["url"], cap
    assert "anthropic" not in cap["url"].lower()
    # Model rewritten to the free NVIDIA model in the outgoing payload.
    assert cap["json"]["model"] == "nvidia/nemotron-3-ultra-550b-a55b"
    # NVIDIA bearer auth, not the Anthropic key.
    assert cap["headers"]["Authorization"] == "Bearer nvapi-TESTKEY"


async def test_chat_text_refuses_when_no_free_brain(monkeypatch):
    """Free policy + Anthropic-shaped model + NO NVIDIA key → refuse loudly,
    never silently call paid Anthropic."""
    monkeypatch.delenv("ALLOW_PAID_BRAIN", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-STALE")
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVidiaApiKey", raising=False)

    runner = AgentRunner(ollama_base="http://localhost:11434")
    with pytest.raises(RuntimeError, match="free brain"):
        await runner._chat_text(
            "claude-opus-4-6",
            [{"role": "user", "content": "hi"}],
        )


async def test_chat_text_nvidia_model_uses_configured_endpoint(monkeypatch):
    """A non-Anthropic (NVIDIA) model is unaffected — it uses the configured
    provider endpoint normally."""
    monkeypatch.delenv("ALLOW_PAID_BRAIN", raising=False)
    import agent.loop as loop_mod

    monkeypatch.setattr(loop_mod.httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.captured = {}

    runner = AgentRunner(
        ollama_base="https://integrate.api.nvidia.com/v1",
        provider_headers={"Authorization": "Bearer nvapi-X"},
    )
    out = await runner._chat_text(
        "nvidia/nemotron-3-ultra-550b-a55b",
        [{"role": "user", "content": "hi"}],
    )
    assert out == "ok-from-nvidia"
    assert "integrate.api.nvidia.com" in _FakeAsyncClient.captured["url"]
    assert _FakeAsyncClient.captured["json"]["model"] == "nvidia/nemotron-3-ultra-550b-a55b"
