"""tests/test_doctor_coding_brain.py

Surfaces the North Mini Code coding-brain state on the `/api/doctor` report so
the dashboard's Doctor screen (which renders `checks` generically) shows which
model powers the executor / Hermes, the NORTH_MINI_CODE_DEFAULT flag, and the
interleaved-thinking setting — alongside the already-present Hermes runtime
health check.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from packages.auth.rbac import require_authenticated
    from backend.server import app, get_current_user

    app.dependency_overrides[require_authenticated] = lambda: {
        "email": "test@example.com", "role": "admin", "user_id": "test-user",
    }

    async def _mock_user(request=None):
        return {"email": "test@example.com", "role": "admin", "user_id": "test-user"}

    app.dependency_overrides[get_current_user] = _mock_user
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _coding_brain_check(report: dict) -> dict | None:
    for c in report.get("checks", []):
        if c.get("id") in ("coding_brain", "coding_brain_error"):
            return c
    return None


def test_doctor_includes_coding_brain_check(client):
    resp = client.get("/api/doctor")
    assert resp.status_code == 200, resp.text
    report = resp.json()
    check = _coding_brain_check(report)
    assert check is not None, "coding_brain check missing from /api/doctor report"
    assert check["category"] == "Models"
    assert check["status"] in ("pass", "warn", "fail")
    assert check.get("detail")


def test_coding_brain_check_reflects_flag_off(client, monkeypatch):
    """With NORTH_MINI_CODE_DEFAULT off, the check warns and says so."""
    import packages.ai.brain_config as bc

    monkeypatch.setattr(bc, "is_north_mini_code_default", lambda: False)
    resp = client.get("/api/doctor")
    assert resp.status_code == 200, resp.text
    check = _coding_brain_check(resp.json())
    assert check is not None
    # When the resolver is reachable, an OFF flag yields a warn + explanatory detail.
    if check["id"] == "coding_brain":
        assert check["status"] == "warn"
        assert "OFF" in check["detail"].upper()
