"""
Regression test for PUT/DELETE /api/github/token returning 500 for
SQLite-backed (or env-admin-fallback) users.

Root cause: set_github_token()/delete_github_token() built the Mongo update
filter with a bare ObjectId(uid). On the production Render deployment
(STORAGE_BACKEND=sqlite) — and for the env-admin fallback user created in
get_optional_user() when the DB is briefly unreachable — the user's `_id` is
a plain string (UUID or "admin_user_001"), not a valid Mongo ObjectId hex
string. ObjectId() raises bson.errors.InvalidId, which was uncaught and
propagated as an unhandled 500 — exactly the "Request failed with status
code 500" surfaced in the onboarding wizard's "Connect your resources" step
when a GitHub access token is entered.

Fix: _user_id_filter() tries ObjectId(uid) and falls back to the raw string,
mirroring the existing ObjectId-then-string retry in get_optional_user().
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


class TestGithubTokenSQLiteRegression:
    def test_set_github_token_sqlite_string_id_does_not_500(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        import backend.server

        user_id = str(uuid.uuid4())

        mock_github_settings = MagicMock()
        mock_github_settings.update_one = AsyncMock(return_value=None)

        mock_users = MagicMock()
        mock_users.update_one = AsyncMock(return_value=None)

        mock_store = MagicMock()
        mock_store.github_settings = mock_github_settings
        mock_store.users = mock_users

        monkeypatch.setattr(backend.server, "get_db", lambda: mock_store)
        monkeypatch.setenv("STORAGE_BACKEND", "sqlite")

        # Bypass auth entirely and hand the endpoint a SQLite-shaped user
        # (string _id, not a Mongo ObjectId) — this is exactly the shape
        # get_optional_user() returns for SQLite users and the env-admin
        # fallback.
        async def fake_current_user():
            return {"_id": user_id, "email": "sqlite-user@test.local", "role": "user"}

        backend.server.app.dependency_overrides[backend.server.get_current_user] = (
            fake_current_user
        )

        class _FakeGHResponse:
            status_code = 200

            def json(self):
                return {"login": "sqlite-gh-user"}

        class _FakeAsyncClient:
            def __init__(self, *a, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, *a, **kw):
                return _FakeGHResponse()

        monkeypatch.setattr(backend.server.httpx, "AsyncClient", _FakeAsyncClient)

        try:
            r = client.put(
                "/api/github/token",
                json={"token": "ghp_faketoken1234567890"},
            )
        finally:
            backend.server.app.dependency_overrides.pop(
                backend.server.get_current_user, None
            )

        assert r.status_code == 200, (
            f"Expected 200 for SQLite string _id user, got {r.status_code}: {r.text[:300]}"
        )
        assert r.json().get("ok") is True

        # The update_one filter must have used the raw string id, not a
        # bson ObjectId (which would have raised before reaching here).
        assert mock_users.update_one.await_count == 1
        called_filter = mock_users.update_one.await_args.args[0]
        assert called_filter == {"_id": user_id}

    def test_delete_github_token_sqlite_string_id_does_not_500(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        import backend.server

        user_id = str(uuid.uuid4())

        mock_github_settings = MagicMock()
        mock_github_settings.delete_one = AsyncMock(return_value=None)

        mock_users = MagicMock()
        mock_users.update_one = AsyncMock(return_value=None)

        mock_store = MagicMock()
        mock_store.github_settings = mock_github_settings
        mock_store.users = mock_users

        monkeypatch.setattr(backend.server, "get_db", lambda: mock_store)
        monkeypatch.setenv("STORAGE_BACKEND", "sqlite")

        async def fake_current_user():
            return {"_id": user_id, "email": "sqlite-user@test.local", "role": "user"}

        backend.server.app.dependency_overrides[backend.server.get_current_user] = (
            fake_current_user
        )

        try:
            r = client.delete("/api/github/token")
        finally:
            backend.server.app.dependency_overrides.pop(
                backend.server.get_current_user, None
            )

        assert r.status_code == 200, (
            f"Expected 200 for SQLite string _id user, got {r.status_code}: {r.text[:300]}"
        )
        assert r.json().get("ok") is True

        called_filter = mock_users.update_one.await_args.args[0]
        assert called_filter == {"_id": user_id}
