"""tests/test_openclaw_endpoints.py — /api/openclaw/* HTTP endpoint tests."""
from __future__ import annotations

import os
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
    assert "local-llm-server.onrender.com" in data["gateway_url"]
    assert data["qr_payload"] is not None
    assert "openclaw://pair" in data["qr_payload"]


def test_openclaw_qr_returns_payload(client):
    resp = client.get("/api/openclaw/qr")
    assert resp.status_code == 200
    data = resp.json()
    assert "payload" in data
    assert "openclaw://pair" in data["payload"]
    assert "manual_entry" in data


def test_openclaw_qr_unset_token(client, monkeypatch):
    monkeypatch.delenv("OPENCLAW_PAIRING_TOKEN", raising=False)
    resp = client.get("/api/openclaw/qr")
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data


def test_openclaw_reverse_proxy_returns_503_when_gateway_down(client):
    """When the OpenClaw CLI is not installed, the reverse-proxy returns 503."""
    resp = client.get("/openclaw/health")
    assert resp.status_code in (503, 502)  # 503 = ConnectError, 502 = other
