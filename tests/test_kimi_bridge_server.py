"""Tests for the Kimi web-bridge HTTP service.

All tests mock browser_driver.ask so no real network/browser is needed.
"""
from __future__ import annotations

import secrets
import pytest
from unittest.mock import AsyncMock, MagicMock


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def auth_token() -> str:
    return secrets.token_hex(16)


@pytest.fixture()
def fake_driver() -> MagicMock:
    """A canned KimiBrowserDriver stand-in that never touches a real browser."""
    driver = MagicMock()
    driver.start = AsyncMock()
    driver.stop = AsyncMock()
    driver.ask = AsyncMock(return_value="Hello from Kimi!")
    return driver


@pytest.fixture()
def kimi_app(fake_driver: MagicMock, auth_token: str, monkeypatch):
    """Return a TestClient for the Kimi bridge app, with a mocked driver.

    The key is patching ``KimiBrowserDriver`` *inside* app.py's namespace —
    that's the name the lifespan closure uses, not the one in browser_driver.py.
    """
    monkeypatch.setenv("KIMI_BRIDGE_TOKEN", auth_token)

    from fastapi.testclient import TestClient
    import services.kimi_bridge_server.app as app_mod

    # Patch the name as it appears in the app module (``from .browser_driver import …``)
    monkeypatch.setattr(app_mod, "KimiBrowserDriver", lambda: fake_driver)
    app_mod._BRIDGE_TOKEN = auth_token

    with TestClient(app_mod.app, raise_server_exceptions=True) as client:
        yield client


# ─── /v1/chat/completions ─────────────────────────────────────────────────────


def test_chat_completions_returns_openai_shape(
    kimi_app, auth_token: str, fake_driver: MagicMock
) -> None:
    resp = kimi_app.post(
        "/v1/chat/completions",
        json={"model": "kimi-k2.6", "messages": [{"role": "user", "content": "hi"}]},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "chat.completion"
    assert len(data["choices"]) == 1
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert data["choices"][0]["message"]["content"] == "Hello from Kimi!"
    assert "usage" in data
    assert data["usage"]["total_tokens"] >= 1
    assert data["usage"]["total_tokens"] == (
        data["usage"]["prompt_tokens"] + data["usage"]["completion_tokens"]
    )
    fake_driver.ask.assert_awaited_once()


def test_chat_completions_messages_forwarded(
    kimi_app, auth_token: str, fake_driver: MagicMock
) -> None:
    msgs = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "What is 2+2?"},
    ]
    resp = kimi_app.post(
        "/v1/chat/completions",
        json={"model": "kimi-k2.6", "messages": msgs},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    # Driver was called with a non-empty messages list
    assert fake_driver.ask.called
    called_messages = fake_driver.ask.call_args.args[0]
    assert any(m["role"] == "system" for m in called_messages)
    assert any(m["role"] == "user" for m in called_messages)


def test_stream_not_supported(kimi_app, auth_token: str) -> None:
    resp = kimi_app.post(
        "/v1/chat/completions",
        json={
            "model": "kimi-k2.6",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 400
    assert "stream" in resp.json()["detail"].lower()


# ─── Auth enforcement ─────────────────────────────────────────────────────────


def test_missing_auth_header_rejected(kimi_app) -> None:
    resp = kimi_app.post(
        "/v1/chat/completions",
        json={"model": "kimi-k2.6", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 401


def test_wrong_token_rejected(kimi_app) -> None:
    resp = kimi_app.post(
        "/v1/chat/completions",
        json={"model": "kimi-k2.6", "messages": [{"role": "user", "content": "hi"}]},
        headers={"Authorization": "Bearer definitely-not-the-right-token"},
    )
    assert resp.status_code == 401


def test_correct_token_accepted(kimi_app, auth_token: str, fake_driver: MagicMock) -> None:
    resp = kimi_app.post(
        "/v1/chat/completions",
        json={"model": "kimi-k2.6", "messages": [{"role": "user", "content": "hi"}]},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200


# ─── /v1/models ───────────────────────────────────────────────────────────────


def test_list_models(kimi_app, auth_token: str) -> None:
    resp = kimi_app.get("/v1/models", headers={"Authorization": f"Bearer {auth_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "list"
    assert len(data["data"]) >= 1
    assert "id" in data["data"][0]


# ─── /health ──────────────────────────────────────────────────────────────────


def test_health_endpoint(kimi_app) -> None:
    resp = kimi_app.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ─── browser_driver helpers ───────────────────────────────────────────────────


def test_messages_to_prompt_basic() -> None:
    from services.kimi_bridge_server.browser_driver import _messages_to_prompt

    msgs = [
        {"role": "system", "content": "Be concise."},
        {"role": "user", "content": "Hello"},
    ]
    prompt = _messages_to_prompt(msgs)
    assert "Be concise." in prompt
    assert "Hello" in prompt


def test_messages_to_prompt_multimodal() -> None:
    from services.kimi_bridge_server.browser_driver import _messages_to_prompt

    msgs = [
        {
            "role": "user",
            "content": [{"type": "text", "text": "Describe this"}, {"type": "image_url"}],
        }
    ]
    prompt = _messages_to_prompt(msgs)
    assert "Describe this" in prompt


def test_messages_to_prompt_assistant_turn() -> None:
    from services.kimi_bridge_server.browser_driver import _messages_to_prompt

    msgs = [
        {"role": "user", "content": "Question"},
        {"role": "assistant", "content": "Answer"},
        {"role": "user", "content": "Follow-up"},
    ]
    prompt = _messages_to_prompt(msgs)
    assert "Question" in prompt
    assert "Answer" in prompt
    assert "Follow-up" in prompt
