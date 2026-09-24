"""GET /api/activation/users must list registered users, not just toggled ones.

It returned only the ids in ``.onboarding_state.json`` — which is written only
when an admin toggles someone — and no role. With the onboarding gate ON (the
default), a new sign-up was blocked from onboarding *and* absent from Settings →
People & access, so an admin had no way to find and approve them; every row's
role badge was also blank.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

import activation_api


class _Cursor:
    def __init__(self, docs):
        self._docs = docs

    async def to_list(self, length=None):
        return list(self._docs)


@pytest.fixture()
def client(tmp_path, monkeypatch) -> TestClient:
    state_file = tmp_path / "onboarding.json"
    state_file.write_text(json.dumps({
        "ann@example.com": {"onboarding_allowed": True, "updated_at": 1.0, "updated_by": "admin"},
        "legacy-id": {"onboarding_allowed": False},
    }))
    monkeypatch.setattr(activation_api, "_ONBOARDING_STATE_FILE", state_file)

    store = MagicMock()
    store.users.find = MagicMock(return_value=_Cursor([
        {"_id": "u1", "email": "ann@example.com", "name": "Ann", "role": "admin", "password_hash": "x"},
        {"_id": "u2", "email": "bob@example.com", "name": "Bob", "role": "user"},
    ]))
    monkeypatch.setattr(activation_api, "get_store", lambda: store)
    monkeypatch.setattr(activation_api, "is_user_onboarding_allowed", lambda uid: False)

    app = FastAPI()

    @app.middleware("http")
    async def as_admin(request: Request, call_next):
        request.state.user = SimpleNamespace(email="root@example.com", role="admin")
        return await call_next(request)

    app.include_router(activation_api.activation_router)
    return TestClient(app)


def test_lists_registered_users_with_roles_and_keeps_state_only_entries(client) -> None:
    resp = client.get("/api/activation/users")
    assert resp.status_code == 200, resp.text
    rows = {r["user_id"]: r for r in resp.json()}

    assert set(rows) == {"ann@example.com", "bob@example.com", "legacy-id"}
    assert rows["bob@example.com"]["role"] == "user"
    assert rows["bob@example.com"]["name"] == "Bob"
    assert rows["bob@example.com"]["onboarding_allowed"] is False
    assert rows["ann@example.com"]["onboarding_allowed"] is True
    assert rows["ann@example.com"]["updated_by"] == "admin"
    assert "password_hash" not in resp.text
