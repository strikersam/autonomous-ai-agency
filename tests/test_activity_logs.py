from __future__ import annotations

import logging
import os

import backend.server as server

_ADMIN_PASSWORD = server.ADMIN_PASSWORD


def _auth_headers(client) -> dict[str, str]:
    login = client.post(
        "/api/auth/login",
        json={"email": "admin@llmrelay.local", "password": _ADMIN_PASSWORD},
    )
    assert login.status_code == 200, (
        f"Login failed ({login.status_code}): {login.text!r}. "
        "Check that ADMIN_PASSWORD env var matches the value set in CI."
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_activity_endpoint_includes_recent_error_logs(client) -> None:
    server.clear_error_log_buffer()
    logging.getLogger("qwen-proxy").error("Synthetic activity log failure for regression test")

    response = client.get("/api/activity", headers=_auth_headers(client))

    assert response.status_code == 200, response.text
    messages = [entry.get("message") for entry in response.json()["activity"]]
    assert "Synthetic activity log failure for regression test" in messages
