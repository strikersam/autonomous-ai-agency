"""Social-login start URLs are browser navigations: an unconfigured provider
must send the user back to /login with a reason, not a raw JSON 503 page."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import backend.server as server


@pytest.mark.parametrize(
    ("path", "var", "provider"),
    [
        ("/api/auth/github/start/abc123", "GITHUB_CLIENT_ID", "github"),
        ("/api/auth/github/login", "GITHUB_CLIENT_ID", "github"),
        ("/api/auth/google/start/abc123", "GOOGLE_CLIENT_ID", "google"),
    ],
)
def test_unconfigured_provider_redirects_to_login(monkeypatch, path, var, provider) -> None:
    monkeypatch.setattr(server, var, "")
    resp = TestClient(server.app).get(path, follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert resp.headers["location"].endswith(f"/login?oauth_error={provider}_not_configured")
