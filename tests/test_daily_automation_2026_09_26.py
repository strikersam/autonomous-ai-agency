"""Daily automation 2026-09-26 — regression tests.

Changes shipped today:
- ``/api/auth/refresh`` SQLite fix: the endpoint now falls back to a
  string-key DB lookup when ``ObjectId(sub)`` raises (UUID strings from
  SQLite self-hosters), mirroring the identical fallback already in
  ``get_optional_user``. Affected file: ``backend/server.py``.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi.testclient import TestClient

import os

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@llmrelay.local")
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]  # nosec B105 — test credential only


class TestRefreshTokenSQLiteFallback:
    """Regression tests for /api/auth/refresh on the SQLite backend.

    Before today's fix the refresh endpoint called ObjectId(sub) and, when
    that raised (UUID string instead of Mongo hex), only checked for the
    built-in admin_user_001 fallback — any regular self-hosted SQLite user
    got an unconditional 401 on every token refresh.
    """

    def test_sqlite_user_can_refresh_token(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        """A regular SQLite user with a UUID _id must receive a new access
        token when POST /api/auth/refresh is called with a valid refresh token.
        """
        import backend.server

        user_id = str(uuid.uuid4())
        test_user = {
            "_id": user_id,
            "email": "selfhost@example.local",
            "name": "Self-Hosted User",
            "role": "user",
        }

        mock_users = MagicMock()
        # ObjectId(uuid_string) raises *before* find_one is called, so only the
        # string-key fallback makes a DB call.  Return the user on that single call.
        mock_users.find_one = AsyncMock(return_value=test_user)
        mock_store = MagicMock()
        mock_store.users = mock_users

        monkeypatch.setattr(backend.server, "get_db", lambda: mock_store)

        refresh = backend.server.create_refresh_token(user_id)
        r = client.post("/api/auth/refresh", json={"refresh_token": refresh})
        assert r.status_code == 200, (
            f"SQLite user refresh should return 200, got {r.status_code}: {r.text[:300]}"
        )
        data = r.json()
        assert "access_token" in data, f"No access_token in response: {data}"

    def test_sqlite_user_refresh_token_is_valid_access_token(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        """The access_token returned by /api/auth/refresh must itself decode
        with a valid 'sub' (not raise InvalidTokenError).
        """
        import backend.server

        user_id = str(uuid.uuid4())
        test_user = {"_id": user_id, "email": "verify@example.local", "role": "user"}

        mock_users = MagicMock()
        mock_users.find_one = AsyncMock(return_value=test_user)
        mock_store = MagicMock()
        mock_store.users = mock_users

        monkeypatch.setattr(backend.server, "get_db", lambda: mock_store)

        refresh = backend.server.create_refresh_token(user_id)
        r = client.post("/api/auth/refresh", json={"refresh_token": refresh})
        assert r.status_code == 200
        token = r.json()["access_token"]

        from backend.server import JWT_SECRET, JWT_ALGORITHM
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        assert payload["sub"] == user_id
        assert payload.get("type") == "access"

    def test_nonexistent_sqlite_user_returns_401(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        """A valid refresh token whose sub matches no DB record → 401."""
        import backend.server

        user_id = str(uuid.uuid4())

        mock_users = MagicMock()
        # Both ObjectId and string lookups return None — user does not exist.
        mock_users.find_one = AsyncMock(return_value=None)
        mock_store = MagicMock()
        mock_store.users = mock_users

        monkeypatch.setattr(backend.server, "get_db", lambda: mock_store)

        refresh = backend.server.create_refresh_token(user_id)
        r = client.post("/api/auth/refresh", json={"refresh_token": refresh})
        assert r.status_code == 401, (
            f"Non-existent user should 401, got {r.status_code}: {r.text[:200]}"
        )

    def test_admin_user_001_fallback_still_works(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        """The built-in admin_user_001 constant must still bypass DB lookup
        on ObjectId failure — behaviour unchanged from before the fix.
        """
        import backend.server

        mock_users = MagicMock()
        # DB is unreachable — every find_one call raises.
        mock_users.find_one = AsyncMock(side_effect=Exception("DB down"))
        mock_store = MagicMock()
        mock_store.users = mock_users

        monkeypatch.setattr(backend.server, "get_db", lambda: mock_store)

        refresh = backend.server.create_refresh_token("admin_user_001")
        r = client.post("/api/auth/refresh", json={"refresh_token": refresh})
        assert r.status_code == 200, (
            f"admin_user_001 should still work without DB, got {r.status_code}: {r.text[:200]}"
        )
        assert "access_token" in r.json()

    def test_no_refresh_token_returns_401(self, client: TestClient):
        """POST /api/auth/refresh with missing body → 401."""
        r = client.post("/api/auth/refresh", json={})
        assert r.status_code == 401

    def test_invalid_refresh_token_returns_401(self, client: TestClient):
        """POST /api/auth/refresh with garbage token → 401."""
        r = client.post("/api/auth/refresh", json={"refresh_token": "garbage.token.here"})
        assert r.status_code == 401

    def test_access_token_as_refresh_returns_401(self, client: TestClient):
        """Passing an access token in the refresh slot → 401 (wrong type)."""
        import backend.server
        access = backend.server.create_access_token("admin_user_001", ADMIN_EMAIL)
        r = client.post("/api/auth/refresh", json={"refresh_token": access})
        assert r.status_code == 401, (
            f"Access token must be rejected at refresh endpoint, got {r.status_code}"
        )


class TestRefreshEndpointCodeStructure:
    """Static checks to confirm the fix is in place in server.py."""

    def test_string_fallback_present_in_refresh_endpoint(self):
        """The refresh_token function must contain the SQLite string-ID fallback
        that mirrors get_optional_user — i.e. a second find_one call with the
        raw string after the ObjectId lookup fails.
        """
        from pathlib import Path
        src = Path(__file__).resolve().parents[1] / "backend" / "server.py"
        text = src.read_text()

        # Locate the refresh_token function body.
        start = text.find("async def refresh_token(")
        assert start != -1, "refresh_token function not found in server.py"
        # Extract up to the next async def to stay in scope.
        snippet = text[start: text.find("\nasync def ", start + 1)]

        assert 'get_db().users.find_one({"_id": payload["sub"]})' in snippet, (
            "SQLite string-ID fallback missing from refresh_token: "
            'expected: get_db().users.find_one({"_id": payload["sub"]})'
        )
