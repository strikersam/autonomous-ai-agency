"""Tests for per-key token spend tracking in chat_handlers.

Verifies that:
  - _record_key_spend accumulates prompt/completion tokens per key_id
  - get_key_spend_snapshot returns a correct copy
  - /admin/api/spend endpoint returns spend data for admin users
"""
from __future__ import annotations

import pytest

import chat_handlers


@pytest.fixture(autouse=True)
def _clear_spend():
    """Reset spend counters before and after each test."""
    with chat_handlers._key_spend_lock:
        chat_handlers._key_spend.clear()
    yield
    with chat_handlers._key_spend_lock:
        chat_handlers._key_spend.clear()


# ── Unit tests for _record_key_spend ─────────────────────────────────────────

def test_record_spend_accumulates_tokens():
    chat_handlers._record_key_spend("kid_abc", 100, 50)
    chat_handlers._record_key_spend("kid_abc", 200, 75)

    snap = chat_handlers.get_key_spend_snapshot()
    assert "kid_abc" in snap
    assert snap["kid_abc"]["prompt_tokens"] == 300
    assert snap["kid_abc"]["completion_tokens"] == 125
    assert snap["kid_abc"]["requests"] == 2


def test_record_spend_tracks_multiple_keys_independently():
    chat_handlers._record_key_spend("kid_a", 100, 50)
    chat_handlers._record_key_spend("kid_b", 200, 80)
    chat_handlers._record_key_spend("kid_a", 50, 25)

    snap = chat_handlers.get_key_spend_snapshot()
    assert snap["kid_a"]["prompt_tokens"] == 150
    assert snap["kid_a"]["requests"] == 2
    assert snap["kid_b"]["prompt_tokens"] == 200
    assert snap["kid_b"]["requests"] == 1


def test_record_spend_ignores_none_key_id():
    chat_handlers._record_key_spend(None, 100, 50)
    snap = chat_handlers.get_key_spend_snapshot()
    assert len(snap) == 0


def test_record_spend_ignores_zero_token_entries():
    chat_handlers._record_key_spend("kid_zero", 0, 0)
    snap = chat_handlers.get_key_spend_snapshot()
    assert len(snap) == 0


def test_get_key_spend_snapshot_returns_copy():
    chat_handlers._record_key_spend("kid_copy", 50, 30)
    snap1 = chat_handlers.get_key_spend_snapshot()
    chat_handlers._record_key_spend("kid_copy", 10, 5)
    snap2 = chat_handlers.get_key_spend_snapshot()
    # snap1 must not be affected by the second record call
    assert snap1["kid_copy"]["requests"] == 1
    assert snap2["kid_copy"]["requests"] == 2


# ── HTTP endpoint tests ───────────────────────────────────────────────────────

@pytest.fixture()
def admin_client(monkeypatch):
    from fastapi.testclient import TestClient
    import proxy
    from admin_auth import AdminIdentity

    monkeypatch.setattr(proxy, "ADMIN_SECRET", "test-admin-secret-xyz")
    proxy.ADMIN_AUTH.secret = "test-admin-secret-xyz"

    def fake_admin():
        return AdminIdentity(username="test-admin", auth_source="token")

    proxy.app.dependency_overrides[proxy._get_admin_identity_from_request] = fake_admin
    client = TestClient(proxy.app, raise_server_exceptions=False)
    yield client
    proxy.app.dependency_overrides.clear()


def test_spend_endpoint_returns_empty_when_no_requests(admin_client):
    resp = admin_client.get("/admin/api/spend")
    assert resp.status_code == 200
    data = resp.json()
    assert "spend" in data
    assert data["spend"] == []
    assert data["total_keys"] == 0


def test_spend_endpoint_returns_accumulated_data(admin_client):
    chat_handlers._record_key_spend("kid_x1", 500, 200)
    chat_handlers._record_key_spend("kid_x2", 100, 40)

    resp = admin_client.get("/admin/api/spend")
    assert resp.status_code == 200
    data = resp.json()

    rows = {r["key_id"]: r for r in data["spend"]}
    assert "kid_x1" in rows
    assert rows["kid_x1"]["prompt_tokens"] == 500
    assert rows["kid_x1"]["completion_tokens"] == 200
    assert rows["kid_x1"]["total_tokens"] == 700
    assert rows["kid_x1"]["requests"] == 1
    assert data["total_keys"] == 2


def test_spend_endpoint_sorts_by_total_tokens_descending(admin_client):
    chat_handlers._record_key_spend("kid_small", 10, 5)
    chat_handlers._record_key_spend("kid_large", 1000, 500)
    chat_handlers._record_key_spend("kid_mid", 200, 100)

    resp = admin_client.get("/admin/api/spend")
    rows = resp.json()["spend"]
    totals = [r["total_tokens"] for r in rows]
    assert totals == sorted(totals, reverse=True)


def test_spend_endpoint_requires_admin(monkeypatch):
    from fastapi.testclient import TestClient
    import proxy
    client = TestClient(proxy.app, raise_server_exceptions=False)
    resp = client.get("/admin/api/spend")
    assert resp.status_code in (401, 404)
