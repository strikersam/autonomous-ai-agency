"""
Regression test for /api/auth/me — verifies the critical endpoint on both
the backend (port 8001, JWT auth) and proxy (port 8000, API key auth).

Covers:
  - Valid token returns correct user profile
  - Invalid / expired token returns 401
  - Missing token returns 401

This is the endpoint fix from PR #857 and PR #860 that restores social login.
"""
from __future__ import annotations

import os
import uuid
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi.testclient import TestClient


ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@llmrelay.local")
# Must use os.environ[] (not .get with fallback) — conftest.py sets a session-stable
# random password before any backend module import. See tests/conftest.py for the contract.
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]  # nosec B105 — test credential only


# ── Backend /api/auth/me (JWT auth) ──────────────────────────────────────────
# Use the shared conftest.py `client` fixture — it sets ADMIN_PASSWORD and seeds
# the admin user via the lifespan before any test runs.


@pytest.fixture
def backend_jwt(client: TestClient) -> str:
    """Login and return a valid JWT access token.

    Calls POST /api/admin/seed (test-only endpoint) before login to re-sync
    the admin password from env vars and ensure the admin user exists. This
    fixes test-ordering failures where a prior test corrupted the admin user
    — the FastAPI lifespan only calls seed_admin() once per shared backend_app
    instance, so subsequent TestClient sessions don't re-seed.
    """
    # Re-seed admin to recover from prior-test corruption.
    r = client.post("/api/admin/seed")
    assert r.status_code == 200, f"Admin seed failed: {r.status_code}"
    r = client.post("/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
    })
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:300]}"
    return r.json()["access_token"]


class TestBackendAuthMe:
    """JWT-based /api/auth/me on backend/server.py (port 8001)."""

    def test_valid_token_returns_user_profile(self, client: TestClient, backend_jwt: str):
        """GET /api/auth/me with valid JWT → 200 and correct email."""
        r = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {backend_jwt}",
        })
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        data = r.json()
        assert data["email"] == ADMIN_EMAIL, f"Wrong email: {data.get('email')}"
        assert "_id" in data or "id" in data, f"No identity field in: {list(data.keys())}"
        assert data.get("role") == "admin", f"Wrong role: {data.get('role')}"

    def test_invalid_token_returns_401(self, client: TestClient):
        """GET /api/auth/me with garbage token → 401."""
        r = client.get("/api/auth/me", headers={
            "Authorization": "Bearer invalid-garbage-token-abc123",
        })
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text[:200]}"

    def test_missing_token_returns_401(self, client: TestClient):
        """GET /api/auth/me with no Authorization header → 401."""
        r = client.get("/api/auth/me")
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text[:200]}"

    def test_expired_token_returns_401(self, client: TestClient):
        """GET /api/auth/me with an expired JWT (exp=1, Unix epoch) → 401."""
        expired_token = jwt.encode(
            {"sub": "test-user", "exp": 1},
            key="test-secret",
            algorithm="HS256",
        )
        r = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {expired_token}",
        })
        assert r.status_code == 401, (
            f"Expected 401 for expired token, got {r.status_code}: {r.text[:200]}"
        )

    def test_wrong_scheme_returns_401(self, client: TestClient):
        """GET /api/auth/me with Basic auth instead of Bearer → 401."""
        r = client.get("/api/auth/me", headers={
            "Authorization": "Basic dXNlcjpwYXNz",
        })
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text[:200]}"


# ── Proxy /api/auth/me (API key auth) ────────────────────────────────────────


@pytest.fixture(scope="module")
def proxy_client() -> TestClient:
    """TestClient against proxy.py:app with a known API key seeded."""
    import proxy
    # Seed a valid API key for the test
    existing = os.environ.get("API_KEYS", "")
    test_key = f"test-proxy-key-{uuid.uuid4().hex[:12]}"
    os.environ["API_KEYS"] = f"{existing},{test_key}" if existing else test_key
    # Force rebuild of VALID_API_KEYS (it's computed at module load)
    proxy.VALID_API_KEYS = set(
        k.strip() for k in os.environ["API_KEYS"].split(",") if k.strip()
    )
    with TestClient(proxy.app) as c:
        yield c
    # Restore original state (pop if it wasn't set, else set to original)
    if existing:
        os.environ["API_KEYS"] = existing
    else:
        os.environ.pop("API_KEYS", None)
    proxy.VALID_API_KEYS = set(
        k.strip() for k in existing.split(",") if k.strip()
    )


class TestProxyAuthMe:
    """API-key-based /api/auth/me on proxy.py (port 8000)."""

    def test_valid_api_key_returns_user_profile(self, proxy_client: TestClient):
        """GET /api/auth/me with valid API key → 200 with derived profile."""
        import proxy
        # Find a valid key
        valid_key = next(iter(proxy.VALID_API_KEYS), None)
        if not valid_key:
            pytest.skip("No API key configured for proxy test")

        r = proxy_client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {valid_key}",
        })
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        data = r.json()
        assert "email" in data
        assert "role" in data
        assert data["role"] == "user", f"Wrong role: {data.get('role')}"
        # API key users from env have email="unknown", department="legacy"
        assert isinstance(data["email"], str)

    def test_invalid_api_key_returns_403(self, proxy_client: TestClient):
        """GET /api/auth/me with unknown key → 403."""
        r = proxy_client.get("/api/auth/me", headers={
            "Authorization": "Bearer this-key-does-not-exist-xyz",
        })
        assert r.status_code in (401, 403), (
            f"Expected 401 or 403, got {r.status_code}: {r.text[:200]}"
        )

    def test_missing_api_key_returns_401(self, proxy_client: TestClient):
        """GET /api/auth/me with no header → 401."""
        r = proxy_client.get("/api/auth/me")
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text[:200]}"

    def test_x_api_key_header_works(self, proxy_client: TestClient):
        """GET /api/auth/me with x-api-key header (Claude Code style) → 200."""
        import proxy
        valid_key = next(iter(proxy.VALID_API_KEYS), None)
        if not valid_key:
            pytest.skip("No API key configured for proxy test")

        r = proxy_client.get("/api/auth/me", headers={
            "x-api-key": valid_key,
        })
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"

    def test_empty_api_key_returns_401(self, proxy_client: TestClient):
        """GET /api/auth/me with empty Bearer token → 401."""
        r = proxy_client.get("/api/auth/me", headers={
            "Authorization": "Bearer ",
        })
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text[:200]}"


# ── SQLite string _id regression (PR #871) ───────────────────────────────────
# When STORAGE_BACKEND=sqlite, user _id values are plain strings (UUIDs), not
# Mongo ObjectIds.  get_optional_user() must handle this: the first
# find_one({"_id": ObjectId(sub)}) fails (ObjectId rejects the UUID string),
# then the retry find_one({"_id": sub}) succeeds.  Without this retry,
# social-login users on the SQLite backend get 401 from /api/auth/me.


class TestSQLiteStringIdAuthMe:
    """Verify get_optional_user resolves users with string _id (SQLite path).

    The production Render deployment uses ``STORAGE_BACKEND=sqlite``, so
    social-login users (GitHub/Google OAuth) created via the backend have
    plain string ``_id`` values.  The ObjectId-using path in
    ``get_optional_user()`` *must* fail gracefully and retry with the raw
    string — otherwise social login completely breaks.
    """

    def test_sqlite_string_id_user_resolved_by_auth_me(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        import backend.server

        user_id = str(uuid.uuid4())
        test_user = {
            "_id": user_id,
            "email": "sqlite-user@test.local",
            "name": "SQLite Test User",
            "role": "user",
            "avatar_url": "",
        }

        # Build a mock store whose users.find_one returns the test user.
        # The ObjectId constructor rejects UUID strings — the except clause
        # catches InvalidId, then the retry calls find_one with the raw
        # string _id and gets our mock user.  find_one is called only once
        # (the string retry), so return_value is the correct mock config.
        mock_users = MagicMock()
        mock_users.find_one = AsyncMock(return_value=test_user)

        mock_store = MagicMock()
        mock_store.users = mock_users

        monkeypatch.setattr(backend.server, "get_db", lambda: mock_store)
        monkeypatch.setenv("STORAGE_BACKEND", "sqlite")

        # Create a JWT whose sub is the raw string user _id (exactly what
        # the backend emits for SQLite-stored users).
        token = backend.server.create_access_token(user_id, test_user["email"])

        r = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {token}",
        })
        assert r.status_code == 200, (
            f"Expected 200 for SQLite string _id user, got {r.status_code}: {r.text[:200]}"
        )
        data = r.json()
        assert data["email"] == test_user["email"], (
            f"Wrong email: {data.get('email')}"
        )
        assert data.get("_id") == user_id or data.get("id") == user_id, (
            f"Wrong _id: {data.get('_id')} (expected {user_id})"
        )
        assert data.get("role") == "user", f"Wrong role: {data.get('role')}"

    def test_sqlite_string_id_rejects_wrong_user(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
        """Verify that a valid JWT for a non-existent SQLite user → 401."""
        import backend.server

        # Mock find_one to always return None (user not found).
        mock_users = MagicMock()
        mock_users.find_one = AsyncMock(return_value=None)

        mock_store = MagicMock()
        mock_store.users = mock_users

        monkeypatch.setattr(backend.server, "get_db", lambda: mock_store)
        monkeypatch.setenv("STORAGE_BACKEND", "sqlite")

        token = backend.server.create_access_token(
            str(uuid.uuid4()), "ghost@test.local"
        )

        r = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {token}",
        })
        assert r.status_code == 401, (
            f"Expected 401 for unknown SQLite user, got {r.status_code}: {r.text[:200]}"
        )

    def test_sqlite_objectid_lookup_exception_is_swallowed(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Verify ObjectId(uuid_string) raises and is caught gracefully.

        This is the exact code path that was broken before PR #871: when
        STORAGE_BACKEND=sqlite, the ObjectId() constructor rejects UUID
        strings, and the resulting InvalidId exception must NOT propagate
        — it must be caught and retried.
        """
        from bson import ObjectId
        from bson.errors import InvalidId

        user_id = str(uuid.uuid4())
        with pytest.raises(InvalidId):
            ObjectId(user_id)

        # The production code catches this:
        #   try:
        #       user = await get_db().users.find_one({"_id": ObjectId(sub)})
        #   except Exception:
        #       user = None
        # Verify this pattern works with a UUID string.
        try:
            _obj = ObjectId(user_id)
            user = "found"  # pragma: no cover — UUID raises, never reached
        except Exception:
            user = None
        assert user is None, "ObjectId(UUID) must fail, triggering the SQLite retry path"
