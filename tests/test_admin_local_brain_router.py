"""tests/test_admin_local_brain_router.py — auth + toggle flow for /admin/api/local-brain/*.

Seven cases pinned by the user-facing bug:

  1. Unauthenticated (dep raises 401) → 401.
  2. Authenticated non-admin user → 403 (RBAC inside _require_admin).
  3. Admin GET → 200 with the documented body shape
     (state.desired / state.last_heartbeat / state.lease).
  4. Admin POST desired_state='on' → set_desired fires, GET reflects the
     flip within the same SQLite row.
  5. Admin POST desired_state='foo' → 422 (validation gate, not 200).
  6. Admin POST desired_state='off' (no explicit provider) → persisted as
     provider='auto' (default-fallback contract).
  7. Admin POST as non-admin → 403 (RBAC fires on POST too, not just GET).

Pure unit tests use ``tmp_path`` for the sqlite DB so the operator's
production ``.data/agency_brain.db`` is never touched. Auth is faked
by constructing a minimal ``FastAPI()`` app, mounting the admin router
via ``include_router(builder(get_current_user_dep))``, and using the
admin dep's own callable as the dependency-override key.

NOTE: We construct the ``TestClient`` *without* a ``with`` block on
Python 3.14 (the FastAPI TestClient lifespan manager raises an
``AssertionError: fastapi_middleware_astack not found in request scope``
under that combination). Single-process TestClient still works.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


_ADMIN_USER = {"_id": "admin-user", "email": "admin@llmrelay.local", "role": "admin", "name": "Admin"}
_REGULAR_USER = {"_id": "regular-user", "email": "user@llmrelay.local", "role": "user", "name": "User"}


def _make_app(auth_user, *, auth_should_raise: bool = False) -> FastAPI:
    """Build a minimal FastAPI app wrapping the admin router with a fake auth dep.

    ``auth_user`` is what the dep returns on success. ``auth_should_raise=True``
    makes the dep raise HTTPException(401) to mimic get_current_user's
    no-JWT short-circuit in production.

    Important: ``build_admin_local_brain_router`` returns an APIRouter, NOT
    a FastAPI app. We must wrap with a FastAPI instance and ``include_router``
    so that TestClient has a proper ASGI scope on which to install middleware.
    """
    from backend.admin_local_brain_router import build_admin_local_brain_router

    async def _fake_get_current_user():
        if auth_should_raise:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return auth_user

    admin_router = build_admin_local_brain_router(_fake_get_current_user)
    app = FastAPI()
    app.include_router(admin_router)
    return app


# 1. Unauthenticated (dep raises 401) → 401
def test_get_state_unauthenticated_returns_401(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "brain.db"))
    app = _make_app(_ADMIN_USER, auth_should_raise=True)
    client = TestClient(app)
    r = client.get("/admin/api/local-brain/state")
    assert r.status_code == 401, r.text


# 2. Authenticated non-admin user GET → 403
def test_get_state_non_admin_returns_403(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "brain.db"))
    app = _make_app(_REGULAR_USER)
    client = TestClient(app)
    r = client.get("/admin/api/local-brain/state")
    assert r.status_code == 403, r.text
    assert "admin" in r.text.lower() or "Admin" in r.text


# 3. Admin GET → 200 with the documented body shape
def test_get_state_admin_returns_documented_shape(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "brain.db"))
    app = _make_app(_ADMIN_USER)
    client = TestClient(app)
    r = client.get("/admin/api/local-brain/state")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "desired" in body and "last_heartbeat" in body and "lease" in body
    assert body["desired"]["state"] == "off"
    assert body["desired"]["provider"] == "auto"
    assert body["last_heartbeat"]["status"] == "unknown"
    assert body["lease"]["valid"] is False


# 4. Admin POST desired_state='on' → flips + GET reflects
def test_post_toggle_on_flips_persisted_state(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "brain.db"))
    app = _make_app(_ADMIN_USER)
    client = TestClient(app)
    r = client.post(
        "/admin/api/local-brain/toggle",
        json={
            "desired_state": "on",
            "desired_provider": "colibri",
            "machine_id": "test-box-1",
            "actor": "test:test_toggle_on",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["desired"]["state"] == "on"
    assert body["desired"]["provider"] == "colibri"
    assert body["desired"]["machine_id"] == "test-box-1"
    assert body["desired"]["updated_by"] == "test:test_toggle_on"
    r2 = client.get("/admin/api/local-brain/state")
    assert r2.status_code == 200
    assert r2.json()["desired"]["state"] == "on"


# 5. Admin POST invalid desired_state → 422
def test_post_toggle_invalid_state_returns_422(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "brain.db"))
    app = _make_app(_ADMIN_USER)
    client = TestClient(app)
    r = client.post(
        "/admin/api/local-brain/toggle",
        json={"desired_state": "maybe", "desired_provider": "auto"},
    )
    assert r.status_code == 422, r.text


# 6. Admin POST 'off' (no provider) → persisted provider='auto'
def test_post_toggle_off_persists_with_auto_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "brain.db"))
    app = _make_app(_ADMIN_USER)
    client = TestClient(app)
    r = client.post(
        "/admin/api/local-brain/toggle",
        json={"desired_state": "off"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["desired"]["state"] == "off"
    assert body["desired"]["provider"] == "auto"


# 7. Admin POST as non-admin → 403 (RBAC fires on POST too)
def test_post_toggle_non_admin_returns_403(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "brain.db"))
    app = _make_app(_REGULAR_USER)
    client = TestClient(app)
    r = client.post(
        "/admin/api/local-brain/toggle",
        json={"desired_state": "on", "desired_provider": "colibri"},
    )
    assert r.status_code == 403, r.text
