"""tests/test_brain_patch_service_token.py — N5 acceptance: PATCH /admin/api/policy/brain
accepts a service token (the Telegram bot's /setbrain command path).

Tests the dual-auth flow:
  - service token valid → 200/422 (passes auth, runs the liveness probe)
  - service token invalid → 401
  - service token absent + no user session → 401
  - service token absent + non-admin user → 403
  - service token absent + admin user → 200/422 (existing dashboard flow, unchanged)
  - SERVICE_TOKEN env var unset + X-Service-Token header sent → 503
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def clean_store(monkeypatch, tmp_path):
    """Reset the brain config store + point SQLITE_DB_PATH at a tmp path."""
    import packages.ai.brain_config as mod
    monkeypatch.setattr(mod, "_store", None)
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "test.db"))
    # Always reset SERVICE_TOKEN so each test starts from a known state.
    monkeypatch.delenv("SERVICE_TOKEN", raising=False)


def _make_client_with_user(user_dict: dict | None):
    """Build a TestClient with the given user identity (or None for unauth)."""
    from backend.server import app, get_current_user, get_optional_user
    app.dependency_overrides[get_current_user] = (
        (lambda: user_dict) if user_dict else (lambda: None)
    )
    app.dependency_overrides[get_optional_user] = lambda: user_dict
    from fastapi.testclient import TestClient
    return TestClient(app, raise_server_exceptions=False), app


def _clear_overrides(app):
    app.dependency_overrides.clear()


def test_patch_brain_accepts_valid_service_token(clean_store, monkeypatch):
    """N5 acceptance: a valid X-Service-Token header authenticates the request
    even when no user session is present (the Telegram bot's path)."""
    monkeypatch.setenv("SERVICE_TOKEN", "tok_correct_value_xyz")
    client, app = _make_client_with_user(None)
    try:
        # Stub probe_model_liveness so we don't hit a real provider. The
        # service token passes auth; the probe fails (no real provider) so
        # we expect 422 — but that proves auth succeeded (401/403 would
        # mean auth failed).
        with patch("backend.server.probe_model_liveness", new=AsyncMock(return_value=MagicMock(
            live=False, status_code=503, reason="stub", elapsed_ms=10, provider="nvidia",
        ))):
            r = client.patch(
                "/admin/api/policy/brain",
                json={"primary_provider": "nvidia"},
                headers={"X-Service-Token": "tok_correct_value_xyz"},
            )
        assert r.status_code in (422, 200), (
            f"Service-token auth should pass (then probe may succeed or fail). "
            f"Got {r.status_code}: {r.text}"
        )
        # 422 means auth passed + probe failed (expected with our stub)
        # 200 means auth passed + probe succeeded (would need a real provider)
        # 401/403 would mean auth FAILED — that's a regression.
        assert r.status_code != 401, "service token was rejected — verify_service_token broken"
        assert r.status_code != 403, "service token path hit admin-role check — dual-auth broken"
    finally:
        _clear_overrides(app)


def test_patch_brain_rejects_invalid_service_token(clean_store, monkeypatch):
    """N5 acceptance: invalid service token → 401 (not 403, not 200)."""
    monkeypatch.setenv("SERVICE_TOKEN", "tok_correct_value_xyz")
    client, app = _make_client_with_user(None)
    try:
        r = client.patch(
            "/admin/api/policy/brain",
            json={"primary_provider": "nvidia"},
            headers={"X-Service-Token": "tok_wrong_value"},
        )
        assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text}"
    finally:
        _clear_overrides(app)


def test_patch_brain_service_token_503_when_unset(clean_store, monkeypatch):
    """N5 acceptance: SERVICE_TOKEN unset + X-Service-Token header sent → 503
    (misconfiguration signal, distinct from 401 'wrong token')."""
    monkeypatch.delenv("SERVICE_TOKEN", raising=False)
    client, app = _make_client_with_user(None)
    try:
        r = client.patch(
            "/admin/api/policy/brain",
            json={"primary_provider": "nvidia"},
            headers={"X-Service-Token": "any-value-at-all"},
        )
        assert r.status_code == 503, f"expected 503, got {r.status_code}: {r.text}"
    finally:
        _clear_overrides(app)


def test_patch_brain_rejects_no_auth_no_service_token(clean_store, monkeypatch):
    """N5 acceptance: no service token + no user session → 401 (not 200)."""
    client, app = _make_client_with_user(None)
    try:
        r = client.patch(
            "/admin/api/policy/brain",
            json={"primary_provider": "nvidia"},
        )
        assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text}"
    finally:
        _clear_overrides(app)


def test_patch_brain_non_admin_user_still_gets_403(clean_store, monkeypatch):
    """N5 regression: the existing dashboard path (no service token, non-admin
    user) must still return 403, NOT 401. The dual-auth change must not
    break the existing admin-role check."""
    client, app = _make_client_with_user({"_id": "u1", "email": "u@x", "role": "user"})
    try:
        r = client.patch(
            "/admin/api/policy/brain",
            json={"primary_provider": "nvidia"},
        )
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"
    finally:
        _clear_overrides(app)


def test_patch_brain_admin_user_path_unchanged(clean_store, monkeypatch):
    """N5 regression: the existing admin dashboard path (no service token,
    admin user) still works — passes auth + runs the liveness probe."""
    client, app = _make_client_with_user({"_id": "a1", "email": "a@x", "role": "admin"})
    try:
        # Stub the probe so the test doesn't hit a real provider. Return
        # failure → expect 422, which proves auth + admin-role passed.
        with patch("backend.server.probe_model_liveness", new=AsyncMock(return_value=MagicMock(
            live=False, status_code=503, reason="stub", elapsed_ms=10, provider="nvidia",
        ))):
            r = client.patch(
                "/admin/api/policy/brain",
                json={"primary_provider": "nvidia"},
            )
        assert r.status_code in (200, 422), (
            f"admin path should pass auth + admin-role (then probe may succeed or fail). "
            f"Got {r.status_code}: {r.text}"
        )
        assert r.status_code != 401 and r.status_code != 403, (
            "admin path regressed: auth or admin-role check broke"
        )
    finally:
        _clear_overrides(app)
