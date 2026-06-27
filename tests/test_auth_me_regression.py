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

    Retries the login up to 3 times with a short delay to handle transient
    test-ordering failures (e.g. a prior test leaving the DB admin user in
    a stale state before the lifespan's seed_admin re-syncs it).
    """
    import time
    last_status = None
    last_text = ""
    for attempt in range(3):
        r = client.post("/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
        })
        if r.status_code == 200:
            return r.json()["access_token"]
        last_status = r.status_code
        last_text = r.text[:300]
        if attempt < 2:
            time.sleep(0.3)
    pytest.fail(f"Login failed after 3 attempts: {last_status} {last_text}")


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
