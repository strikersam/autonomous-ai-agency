"""tests/test_doctor_service_token_check.py — N5 follow-up: doctor check for
SERVICE_TOKEN configuration status.

Verifies the new doctor diagnostics endpoint surfaces the service-token
configuration gap so the operator can see it in the Doctor screen before
trying /setbrain or /merge from the phone.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture
def clean_store(monkeypatch, tmp_path):
    """Reset brain config store + SQLITE_DB_PATH + SERVICE_TOKEN."""
    import services.brain_config_store as mod
    monkeypatch.setattr(mod, "_store", None)
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.delenv("SERVICE_TOKEN", raising=False)


def _authed_client():
    """Build a TestClient authenticated as admin (for /api/doctor/diagnostics)."""
    from backend.server import app, get_current_user, get_optional_user
    admin_dict = {"_id": "admin-1", "email": "admin@example.com", "role": "admin"}
    app.dependency_overrides[get_current_user] = lambda: admin_dict
    app.dependency_overrides[get_optional_user] = lambda: admin_dict
    from fastapi.testclient import TestClient
    return TestClient(app, raise_server_exceptions=False), app


def _clear(app):
    app.dependency_overrides.clear()


def test_doctor_surfaces_service_token_warn_when_unset(clean_store, monkeypatch):
    """When SERVICE_TOKEN is not set, the doctor endpoint must surface a 'warn'
    check with a clear explanation pointing at the deployment runbook."""
    monkeypatch.delenv("SERVICE_TOKEN", raising=False)
    client, app = _authed_client()
    try:
        r = client.get("/api/doctor/diagnostics")
        assert r.status_code == 200
        checks = r.json().get("checks", [])
        token_check = next((c for c in checks if c["id"] == "service_token"), None)
        assert token_check is not None, "service_token check missing from doctor diagnostics"
        assert token_check["status"] == "warn"
        assert "SERVICE_TOKEN not set" in token_check["detail"]
        # Explanation must tell the operator how to fix it
        assert token_check["explanation"] is not None
        assert "SERVICE_TOKEN" in token_check["explanation"]
        assert "secrets.token_urlsafe" in token_check["explanation"]
    finally:
        _clear(app)


def test_doctor_surfaces_service_token_pass_when_configured(clean_store, monkeypatch):
    """When SERVICE_TOKEN is set, the doctor endpoint must surface a 'pass' check."""
    monkeypatch.setenv("SERVICE_TOKEN", "st_fake_token_for_test_only")
    client, app = _authed_client()
    try:
        r = client.get("/api/doctor/diagnostics")
        assert r.status_code == 200
        checks = r.json().get("checks", [])
        token_check = next((c for c in checks if c["id"] == "service_token"), None)
        assert token_check is not None
        assert token_check["status"] == "pass"
        assert "configured" in token_check["detail"].lower()
        # No 'explanation' needed when passing
        assert token_check.get("explanation") is None or token_check["explanation"] == ""
    finally:
        _clear(app)


def test_doctor_service_token_check_does_not_break_overall_ready(clean_store, monkeypatch):
    """The service_token check is 'warn' (not 'fail') when unset — it must NOT
    drag the overall `ready` flag down, because the rest of the agency works
    fine without it. Only 'fail' checks block readiness."""
    monkeypatch.delenv("SERVICE_TOKEN", raising=False)
    client, app = _authed_client()
    try:
        r = client.get("/api/doctor/diagnostics")
        assert r.status_code == 200
        body = r.json()
        # ready is True iff zero 'fail' checks. A 'warn' on service_token
        # must not flip ready to False.
        if body.get("ready") is False:
            # If not ready, it must be because of an actual 'fail' check, NOT service_token
            fail_checks = [c for c in body["checks"] if c["status"] == "fail"]
            assert all(c["id"] != "service_token" for c in fail_checks), (
                "service_token is 'warn' (not 'fail') — must not block overall readiness"
            )
    finally:
        _clear(app)
