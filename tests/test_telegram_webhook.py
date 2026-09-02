"""tests/test_telegram_webhook.py — inbound Telegram webhook receiver.

The webhook is the delivery path that does not depend on the getUpdates
long-poll consumer: Telegram POSTs each update to /api/telegram/webhook, which
dispatches to the SAME handlers the poller uses. These tests pin the parts that
would be dangerous to get wrong:

  * the secret-token header is the endpoint's authentication — a missing or
    mismatched secret is a flat 403, so the endpoint can never be an
    unauthenticated trigger for the admin actions the callback handlers perform;
  * webhook mode requires BOTH the flag and a valid secret (fail closed);
  * register_webhook asks Telegram for exactly the updates the bot acts on;
  * process_webhook_update routes callback_query vs message like the poller.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SECRET = "s3cret_ABC-123"


# ── pure helpers ─────────────────────────────────────────────────────────────


def test_webhook_mode_requires_flag_and_secret(monkeypatch):
    import telegram_bot as tb

    monkeypatch.setenv("TELEGRAM_WEBHOOK_ENABLED", "true")
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    assert tb.webhook_mode_enabled() is False  # flag on, no secret → off

    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SECRET)
    assert tb.webhook_mode_enabled() is True

    monkeypatch.setenv("TELEGRAM_WEBHOOK_ENABLED", "false")
    assert tb.webhook_mode_enabled() is False  # secret set, flag off → off


def test_webhook_secret_rejects_invalid(monkeypatch):
    import telegram_bot as tb

    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "has spaces!")
    assert tb.webhook_secret() is None  # Telegram allows only [A-Za-z0-9_-]
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "x" * 257)
    assert tb.webhook_secret() is None  # >256 chars
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SECRET)
    assert tb.webhook_secret() == SECRET


@pytest.mark.asyncio
async def test_register_webhook_posts_secret_in_body_not_url(monkeypatch):
    """The secret must go in the POST body, never the URL (URLs get logged)."""
    import telegram_bot as tb

    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(tb, "TELEGRAM_BOT_TOKEN", "123:ABC")
    captured: dict = {}

    class _FakeResp:
        def json(self):
            return {"ok": True, "result": True}

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None):
            captured["url"] = url
            captured["json"] = json
            return _FakeResp()

    monkeypatch.setattr(tb.httpx, "AsyncClient", _FakeClient)
    result = await tb.register_webhook("https://x.onrender.com/")
    assert result["ok"] is True
    # URL is the plain setWebhook endpoint — no secret in the query string.
    assert captured["url"].endswith("/setWebhook")
    assert SECRET not in captured["url"]
    # Params (incl. the secret) travel in the JSON body.
    assert captured["json"]["url"] == "https://x.onrender.com/api/telegram/webhook"
    assert captured["json"]["secret_token"] == SECRET
    assert captured["json"]["allowed_updates"] == ["message", "callback_query"]


@pytest.mark.asyncio
async def test_process_webhook_update_routes_callback_and_message(monkeypatch):
    import telegram_bot as tb

    monkeypatch.setattr(tb, "ensure_config_loaded", lambda: None)
    calls: list[str] = []

    async def fake_cb(token, cb):
        calls.append(f"cb:{cb['id']}")

    async def fake_update(token, upd):
        calls.append(f"msg:{upd['message']['text']}")

    monkeypatch.setattr(tb, "_process_callback", fake_cb)
    monkeypatch.setattr(tb, "_process_update", fake_update)

    await tb.process_webhook_update({"callback_query": {"id": "c1"}})
    await tb.process_webhook_update({"message": {"text": "hi"}})
    assert calls == ["cb:c1", "msg:hi"]


@pytest.mark.asyncio
async def test_process_webhook_update_never_raises(monkeypatch):
    import telegram_bot as tb

    monkeypatch.setattr(tb, "ensure_config_loaded", lambda: None)

    async def boom(token, cb):
        raise RuntimeError("handler blew up")

    monkeypatch.setattr(tb, "_process_callback", boom)
    # Must swallow — a raised error would make Telegram retry in a storm.
    await tb.process_webhook_update({"callback_query": {"id": "c1"}})


# ── endpoint ─────────────────────────────────────────────────────────────────


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjklMNO")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SECRET)
    from fastapi.testclient import TestClient

    from backend.server import app
    return TestClient(app)


def test_webhook_rejects_missing_secret_header(client):
    resp = client.post("/api/telegram/webhook", json={"update_id": 1})
    assert resp.status_code == 403


def test_webhook_rejects_wrong_secret(client):
    resp = client.post(
        "/api/telegram/webhook",
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
    )
    assert resp.status_code == 403


def test_webhook_accepts_correct_secret(client, monkeypatch):
    import telegram_bot as tb

    async def _noop(update):
        return None

    monkeypatch.setattr(tb, "process_webhook_update", _noop)
    resp = client.post(
        "/api/telegram/webhook",
        json={"update_id": 1, "callback_query": {"id": "c1"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_webhook_403_when_secret_unconfigured(client, monkeypatch):
    # Even with a header, an unconfigured/invalid server secret fails closed.
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    resp = client.post(
        "/api/telegram/webhook",
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
    )
    assert resp.status_code == 403
