"""tests/test_openclaw_endpoints.py — OpenClaw HTTP + WebSocket endpoint tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://local-llm-server.onrender.com")
    monkeypatch.setenv("OPENCLAW_PAIRING_TOKEN", "test_pairing_token_12345")
    monkeypatch.setenv("OPENCLAW_AGENT_BASE_URL", "https://local-llm-server.onrender.com/v1")
    monkeypatch.setenv("OPENCLAW_MCP_BASE_URL", "https://local-llm-server.onrender.com/mcp-internal")
    from backend.server import app
    return TestClient(app)


def test_openclaw_status_returns_200(client):
    resp = client.get("/api/openclaw/status")
    assert resp.status_code == 200


def test_openclaw_status_returns_config(client):
    resp = client.get("/api/openclaw/status")
    data = resp.json()
    assert data["enabled"] is True
    assert data["pairing_token_set"] is True
    assert "websocket_url" in data
    assert "/openclaw/ws" in data["websocket_url"]
    assert data["qr_payload"] is not None
    assert "mobile_ui" in data


def test_openclaw_qr_returns_payload(client):
    resp = client.get("/api/openclaw/qr")
    assert resp.status_code == 200
    data = resp.json()
    assert "payload" in data
    assert "websocket_url" in data
    assert "/openclaw/ws" in data["websocket_url"]
    assert "manual_entry" in data
    assert data["manual_entry"]["path"] == "/openclaw/ws"


def test_openclaw_qr_unset_token(client, monkeypatch):
    monkeypatch.delenv("OPENCLAW_PAIRING_TOKEN", raising=False)
    resp = client.get("/api/openclaw/qr")
    data = resp.json()
    assert "error" in data


def test_mobile_ui_returns_html(client):
    resp = client.get("/mobile")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    html = resp.text
    assert "Agency Control" in html
    assert "WebSocket" in html or "websocket" in html.lower()
    assert "connect" in html.lower()


def test_openclaw_catch_all_returns_info(client):
    resp = client.get("/openclaw/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["gateway"] == "openclaw"
    assert "websocket_url" in data
    assert "mobile_ui" in data


def test_websocket_pairing_rejects_wrong_token(client):
    """WebSocket with wrong token is rejected (connection closed)."""
    try:
        with client.websocket_connect("/openclaw/ws") as ws:
            ws.send_text(json.dumps({"type": "pair", "token": "wrong_token"}))
            # The server should close the connection — trying to receive will raise
            with pytest.raises(Exception):
                ws.receive_text()
    except Exception:
        # Connection refused/closed is also acceptable
        pass


def test_websocket_pairing_accepts_correct_token(client):
    """WebSocket with correct token pairs successfully."""
    with client.websocket_connect("/openclaw/ws") as ws:
        ws.send_text(json.dumps({"type": "pair", "token": "test_pairing_token_12345"}))
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "paired"
        assert msg["ok"] is True


def test_websocket_ping_command(client):
    """After pairing, ping command returns pong."""
    with client.websocket_connect("/openclaw/ws") as ws:
        ws.send_text(json.dumps({"type": "pair", "token": "test_pairing_token_12345"}))
        ws.receive_text()  # paired response
        ws.send_text(json.dumps({"type": "ping"}))
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "pong"


def test_websocket_unknown_command(client):
    """Unknown command returns error."""
    with client.websocket_connect("/openclaw/ws") as ws:
        ws.send_text(json.dumps({"type": "pair", "token": "test_pairing_token_12345"}))
        ws.receive_text()
        ws.send_text(json.dumps({"type": "unknown_cmd"}))
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "error"
