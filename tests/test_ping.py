"""Tests for the /api/ping health endpoint (no auth required)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from proxy import app
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def test_ping_returns_ok(client: TestClient) -> None:
    resp = client.get("/api/ping")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_ping_timestamp_is_iso(client: TestClient) -> None:
    resp = client.get("/api/ping")
    ts = resp.json()["timestamp"]
    parsed = datetime.fromisoformat(ts)
    assert parsed.tzinfo is not None


def test_ping_no_auth_required(client: TestClient) -> None:
    resp = client.get("/api/ping")
    assert resp.status_code == 200


def test_ping_response_shape(client: TestClient) -> None:
    resp = client.get("/api/ping")
    data = resp.json()
    assert set(data.keys()) == {"status", "timestamp"}
