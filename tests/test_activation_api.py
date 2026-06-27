"""Tests for activation_api — instance status, OpenAPI schema, and role route.

Regression coverage for two onboarding bugs:
  1. ``/api/activation/status`` must return a non-empty instanceId so the
     activation wizard can display it (frontend showed "unknown" when this
     surface was unreachable).
  2. ``change_user_role`` referenced undefined names (``_RoleUpdateResponse``,
     ``get_db``), which crashed OpenAPI schema generation and the route itself.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from activation_api import activation_router


def _client(*, admin: bool) -> TestClient:
    app = FastAPI()

    @app.middleware("http")
    async def inject_user(request: Request, call_next):
        if admin:
            request.state.user = {"email": "admin@example.com", "role": "admin"}
        return await call_next(request)

    app.include_router(activation_router)
    return TestClient(app, raise_server_exceptions=False)


def test_status_returns_non_empty_instance_id() -> None:
    client = _client(admin=False)
    r = client.get("/api/activation/status")
    assert r.status_code == 200
    body = r.json()
    assert body["instance_id"]  # must be truthy — frontend shows "unknown" otherwise
    assert body["activated"] is False


def test_openapi_schema_generates() -> None:
    # Previously failed with 500 because change_user_role's return annotation
    # (_RoleUpdateResponse) was undefined.
    client = _client(admin=False)
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert "/api/activation/users/{user_id}/role" in r.json()["paths"]


def test_change_role_requires_authentication() -> None:
    client = _client(admin=False)
    r = client.post("/api/activation/users/someone@example.com/role", json={"role": "admin"})
    assert r.status_code == 401


def test_change_role_rejects_invalid_role() -> None:
    client = _client(admin=True)
    r = client.post("/api/activation/users/someone@example.com/role", json={"role": "wizard"})
    assert r.status_code == 422


def test_change_role_updates_existing_user() -> None:
    class _FakeUsers:
        async def update_one(self, query, update):
            return SimpleNamespace(matched_count=1)

    fake_store = SimpleNamespace(users=_FakeUsers())
    client = _client(admin=True)
    with patch("activation_api.get_store", return_value=fake_store):
        r = client.post(
            "/api/activation/users/someone@example.com/role",
            json={"role": "power_user"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body == {"user_id": "someone@example.com", "role": "power_user", "updated": True}


def test_change_role_returns_404_for_missing_user() -> None:
    class _FakeUsers:
        async def update_one(self, query, update):
            return SimpleNamespace(matched_count=0)

    fake_store = SimpleNamespace(users=_FakeUsers())
    client = _client(admin=True)
    with patch("activation_api.get_store", return_value=fake_store):
        r = client.post(
            "/api/activation/users/ghost@example.com/role",
            json={"role": "user"},
        )
    assert r.status_code == 404


# ── Global onboarding-gate settings ──────────────────────────────────────────

def test_get_settings_requires_admin() -> None:
    client = _client(admin=False)
    r = client.get("/api/activation/settings")
    assert r.status_code == 401


def test_get_settings_returns_defaults() -> None:
    import app_settings

    client = _client(admin=True)
    with patch.object(app_settings, "all_settings") as m:
        async def _all():
            return {
                app_settings.ONBOARDING_GATE_ENABLED_KEY: True,
                app_settings.EPHEMERAL_TTL_HOURS_KEY: 24,
            }
        m.side_effect = _all
        r = client.get("/api/activation/settings")
    assert r.status_code == 200
    body = r.json()
    assert body == {"onboarding_gate_enabled": True, "ephemeral_company_ttl_hours": 24}


def test_update_settings_disables_gate() -> None:
    import app_settings

    captured: dict = {}

    async def _set(key, value, updated_by="admin"):
        captured[key] = value

    async def _all():
        return {
            app_settings.ONBOARDING_GATE_ENABLED_KEY: captured.get(
                app_settings.ONBOARDING_GATE_ENABLED_KEY, True
            ),
            app_settings.EPHEMERAL_TTL_HOURS_KEY: captured.get(
                app_settings.EPHEMERAL_TTL_HOURS_KEY, 24
            ),
        }

    client = _client(admin=True)
    with patch.object(app_settings, "set_setting", side_effect=_set), \
            patch.object(app_settings, "all_settings", side_effect=_all):
        r = client.put(
            "/api/activation/settings",
            json={"onboarding_gate_enabled": False},
        )
    assert r.status_code == 200
    assert r.json()["onboarding_gate_enabled"] is False
    assert captured[app_settings.ONBOARDING_GATE_ENABLED_KEY] is False


def test_update_settings_rejects_bad_ttl() -> None:
    client = _client(admin=True)
    r = client.put(
        "/api/activation/settings",
        json={"ephemeral_company_ttl_hours": 0},
    )
    assert r.status_code == 422


def test_update_settings_requires_admin() -> None:
    client = _client(admin=False)
    r = client.put("/api/activation/settings", json={"onboarding_gate_enabled": False})
    assert r.status_code == 401
