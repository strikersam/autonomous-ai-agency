"""Tests for the FreeBuff free-NVIDIA coding agent and its control surfaces.

Covers:
  * ``FreeBuffAgent`` free-model routing (agent/loop.py)
  * proxy rate-limit exemption helper + wiring (proxy.py)
  * proxy /freebuff/* endpoints (proxy.py)
  * Telegram inline-button model selection + accept/reject flow (telegram_bot.py)
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

import proxy
from agent.loop import FreeBuffAgent, free_nvidia_models


# ── FreeBuffAgent: free-model routing ────────────────────────────────────────


def test_available_models_default_are_nvidia_nim():
    models = FreeBuffAgent.available_models()
    assert models, "expected a non-empty free-model list"
    # Every default model is a free NVIDIA NIM-style provider/model id.
    assert all("/" in m for m in models)
    assert "meta/llama-3.3-70b-instruct" in models


def test_available_models_env_override(monkeypatch):
    monkeypatch.setenv("FREEBUFF_MODELS", "meta/llama-3.1-8b-instruct, qwen/qwen2.5-coder-32b-instruct")
    assert free_nvidia_models() == [
        "meta/llama-3.1-8b-instruct",
        "qwen/qwen2.5-coder-32b-instruct",
    ]


def test_is_free_model():
    assert FreeBuffAgent.is_free_model("meta/llama-3.3-70b-instruct") is True
    assert FreeBuffAgent.is_free_model("claude-opus-4-8") is False
    assert FreeBuffAgent.is_free_model(None) is False


def test_resolve_model_coerces_non_free_to_default(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVidiaApiKey", raising=False)
    agent = FreeBuffAgent(model="claude-opus-4-8")  # paid model requested
    # Must never resolve to a paid model.
    assert FreeBuffAgent.is_free_model(agent.model)
    # An explicit free model is honoured.
    assert agent.resolve_model("meta/llama-3.3-70b-instruct") == "meta/llama-3.3-70b-instruct"
    # A non-free request falls back to the selected free model.
    assert FreeBuffAgent.is_free_model(agent.resolve_model("gpt-4o"))


def test_pins_nvidia_base_and_header_when_key_present(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-123")
    agent = FreeBuffAgent(model="meta/llama-3.3-70b-instruct")
    assert agent.ollama_base.startswith("https://integrate.api.nvidia.com")
    assert agent.provider_headers.get("Authorization") == "Bearer nvapi-test-123"


def test_falls_back_to_local_base_without_key(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVidiaApiKey", raising=False)
    agent = FreeBuffAgent()
    assert "nvidia" not in agent.ollama_base.lower()


@pytest.mark.skipif(
    not os.environ.get("NVIDIA_API_KEY") and not os.environ.get("OLLAMA_BASE"),
    reason="Requires a live LLM endpoint for planning (NVIDIA NIM or Ollama) — "
           "skipped in CI where no LLM is configured.",
)
async def test_run_coerces_requested_model_to_free(monkeypatch):
    captured: dict = {}

    async def fake_run(self, *, instruction, history, requested_model, auto_commit, max_steps, **kwargs):
        captured["requested_model"] = requested_model
        return {"summary": "ok", "plan": None, "steps": [], "commits": []}

    monkeypatch.setattr("agent.loop.AgentRunner.run", fake_run)
    agent = FreeBuffAgent(model="meta/llama-3.3-70b-instruct")
    await agent.run(instruction="do a thing", requested_model="claude-opus-4-8")
    # The paid model the caller asked for was replaced by a free model.
    assert FreeBuffAgent.is_free_model(captured["requested_model"])


# ── Rate-limit exemption ─────────────────────────────────────────────────────


def test_is_rate_limit_exempt(monkeypatch):
    monkeypatch.setenv("FREEBUFF_RATELIMIT_EXEMPT_KEY_IDS", "kid_bot, kid_other")
    assert proxy.is_rate_limit_exempt("kid_bot") is True
    assert proxy.is_rate_limit_exempt("kid_other") is True
    assert proxy.is_rate_limit_exempt("kid_random") is False
    # Legacy keys (no key_id) are never exempt.
    assert proxy.is_rate_limit_exempt(None) is False


def test_is_rate_limit_exempt_default_none(monkeypatch):
    monkeypatch.delenv("FREEBUFF_RATELIMIT_EXEMPT_KEY_IDS", raising=False)
    assert proxy.is_rate_limit_exempt("kid_anything") is False


async def test_verify_api_key_skips_limiter_for_exempt_key(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setenv("FREEBUFF_RATELIMIT_EXEMPT_KEY_IDS", "kid_bot")
    rec = SimpleNamespace(email="bot@x.com", department="ops", key_id="kid_bot")
    monkeypatch.setattr(proxy.KEY_STORE, "lookup_plain_key", lambda k, **_: rec)

    called: dict = {"limited": False}

    async def fake_check(api_key):
        called["limited"] = True

    monkeypatch.setattr(proxy, "check_rate_limit", fake_check)

    ctx = await proxy.verify_api_key(request=None, authorization="Bearer secret", x_api_key=None)
    assert ctx.key_id == "kid_bot"
    assert called["limited"] is False  # exempt key bypassed the limiter


def test_is_freebuff_unlimited_path(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.delenv("FREEBUFF_UNLIMITED", raising=False)  # default = unlimited
    fb_req = SimpleNamespace(url=SimpleNamespace(path="/freebuff/run"))
    chat_req = SimpleNamespace(url=SimpleNamespace(path="/v1/chat/completions"))
    assert proxy._is_freebuff_unlimited(fb_req) is True
    assert proxy._is_freebuff_unlimited(chat_req) is False
    assert proxy._is_freebuff_unlimited(None) is False


def test_freebuff_unlimited_can_be_disabled(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setenv("FREEBUFF_UNLIMITED", "false")
    fb_req = SimpleNamespace(url=SimpleNamespace(path="/freebuff/run"))
    assert proxy._is_freebuff_unlimited(fb_req) is False


async def test_verify_api_key_skips_limiter_on_freebuff_path(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.delenv("FREEBUFF_UNLIMITED", raising=False)
    monkeypatch.delenv("FREEBUFF_RATELIMIT_EXEMPT_KEY_IDS", raising=False)
    rec = SimpleNamespace(email="u@x.com", department="eng", key_id="kid_normal")
    monkeypatch.setattr(proxy.KEY_STORE, "lookup_plain_key", lambda k, **_: rec)

    called: dict = {"limited": False}

    async def fake_check(api_key):
        called["limited"] = True

    monkeypatch.setattr(proxy, "check_rate_limit", fake_check)

    req = SimpleNamespace(url=SimpleNamespace(path="/freebuff/run"))
    await proxy.verify_api_key(request=req, authorization="Bearer secret", x_api_key=None)
    assert called["limited"] is False  # FreeBuff path is unlimited even for a normal key


async def test_verify_api_key_enforces_limiter_for_non_exempt_key(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.delenv("FREEBUFF_RATELIMIT_EXEMPT_KEY_IDS", raising=False)
    rec = SimpleNamespace(email="u@x.com", department="eng", key_id="kid_normal")
    monkeypatch.setattr(proxy.KEY_STORE, "lookup_plain_key", lambda k, **_: rec)

    called: dict = {"limited": False}

    async def fake_check(api_key):
        called["limited"] = True

    monkeypatch.setattr(proxy, "check_rate_limit", fake_check)

    await proxy.verify_api_key(request=None, authorization="Bearer secret", x_api_key=None)
    assert called["limited"] is True  # normal key was rate-limited as usual


# ── proxy /freebuff/* endpoints ──────────────────────────────────────────────


def _override_auth():
    proxy.app.dependency_overrides[proxy.verify_api_key] = lambda: proxy.AuthContext(
        key="test-key", email="t@x.com", department="eng", key_id="kid_t", source="legacy"
    )


def test_freebuff_models_endpoint():
    _override_auth()
    try:
        client = TestClient(proxy.app)
        resp = client.get("/freebuff/models")
        assert resp.status_code == 200
        assert resp.json()["models"] == FreeBuffAgent.available_models()
    finally:
        proxy.app.dependency_overrides.clear()


def test_freebuff_plan_endpoint(monkeypatch):
    from agent.models import AgentPlan

    async def fake_plan(self, **kwargs):
        return AgentPlan(goal="fix bug", steps=[])

    monkeypatch.setattr("agent.loop.FreeBuffAgent.plan", fake_plan)
    _override_auth()
    try:
        client = TestClient(proxy.app)
        resp = client.post(
            "/freebuff/plan",
            json={"instruction": "fix the bug", "model": "claude-opus-4-8"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["plan"]["goal"] == "fix bug"
        # Paid model coerced to a free one in the response.
        assert FreeBuffAgent.is_free_model(body["model"])
    finally:
        proxy.app.dependency_overrides.clear()
