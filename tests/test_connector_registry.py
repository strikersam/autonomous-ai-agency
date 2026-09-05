"""tests/test_connector_registry.py — the connector catalogue + webhook action.

Covers PR4 (Gap B, first step): the connector-registry abstraction and the one
webhook connector, plus the admin gate on the API. The security-critical
assertion is that ``send_webhook`` refuses a non-public target (rule 14) before
any request leaves the process.
"""
from __future__ import annotations

import asyncio

from packages.integrations import connector_registry as cr


# ── registry ──────────────────────────────────────────────────────────────────

def test_catalogue_lists_the_webhook_connector():
    ids = {c["id"] for c in cr.list_connectors()}
    assert "webhook" in ids
    spec = cr.get_connector("webhook")
    assert spec is not None
    d = spec.as_dict()
    assert d["kind"] == "action"
    assert d["auth_type"] == "none"
    assert d["available"] is True


def test_get_connector_unknown_returns_none():
    assert cr.get_connector("does-not-exist") is None


# ── SSRF guard (rule 14) ──────────────────────────────────────────────────────

def test_send_webhook_rejects_loopback_before_any_request():
    # 127.0.0.1 resolves to a loopback address — must be refused with no request.
    result = asyncio.run(cr.send_webhook("http://127.0.0.1/hook", {"x": 1}))
    assert result["ok"] is False
    assert "unsafe target" in result["error"]


def test_send_webhook_rejects_non_http_scheme():
    result = asyncio.run(cr.send_webhook("file:///etc/passwd", {"x": 1}))
    assert result["ok"] is False
    assert "unsafe target" in result["error"]


# ── success path (no real network) ────────────────────────────────────────────

def test_send_webhook_posts_json_on_a_safe_target(monkeypatch):
    calls: dict[str, object] = {}

    # Treat the target as public so the guard passes without a DNS lookup.
    monkeypatch.setattr(cr, "unsafe_target_reason", lambda url: None)

    class _Resp:
        status_code = 200
        text = "ok"

    class _Client:
        def __init__(self, *a, **k):
            calls["follow_redirects"] = k.get("follow_redirects")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None):
            calls["url"] = url
            calls["json"] = json
            return _Resp()

    monkeypatch.setattr(cr.httpx, "AsyncClient", _Client)

    result = asyncio.run(cr.send_webhook("https://example.test/hook", {"n": 7}, event="ping"))
    assert result == {"ok": True, "status": 200, "response_snippet": "ok"}
    assert calls["url"] == "https://example.test/hook"
    assert calls["json"] == {"event": "ping", "data": {"n": 7}}
    # Redirects must never be auto-followed (SSRF bypass guard).
    assert calls["follow_redirects"] is False


def test_send_webhook_does_not_follow_a_redirect(monkeypatch):
    monkeypatch.setattr(cr, "unsafe_target_reason", lambda url: None)

    class _Resp:
        status_code = 302
        text = ""

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None):
            return _Resp()

    monkeypatch.setattr(cr.httpx, "AsyncClient", _Client)

    result = asyncio.run(cr.send_webhook("https://example.test/hook", {}))
    assert result["ok"] is False
    assert result["status"] == 302
    assert "redirect" in result["error"]


# ── API auth matrix ───────────────────────────────────────────────────────────

def test_connectors_list_requires_authentication(unauth_client):
    assert unauth_client.get("/api/connectors/").status_code == 401


def test_connectors_list_forbidden_for_non_admin(non_admin_client):
    assert non_admin_client.get("/api/connectors/").status_code == 403


def test_connectors_list_ok_for_admin(app_client):
    resp = app_client.get("/api/connectors/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == len(body["connectors"]) >= 1
    assert any(c["id"] == "webhook" for c in body["connectors"])
