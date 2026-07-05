"""tests/test_telegram_diag_endpoint.py — /api/telegram/diag HTTP endpoint.

Verifies the diagnostic endpoint returns the expected config snapshot without
requiring authentication and without leaking the full bot token.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def client(monkeypatch):
    """Build a TestClient against the FastAPI app with controlled env."""
    # Set controlled env vars
    monkeypatch.setenv("RUN_TELEGRAM_BOT", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjklMNO")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "8120976")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "8120976")
    monkeypatch.setenv("TELEGRAM_ADMIN_USER_IDS", "8120976")
    monkeypatch.setenv("TELEGRAM_POLLER_DISABLED", "false")
    monkeypatch.setenv("FREEBUFF_REPO_URL", "https://github.com/strikersam/autonomous-ai-agency")
    monkeypatch.setenv("FREEBUFF_BASE_BRANCH", "master")
    monkeypatch.setenv("BOT_KEEPALIVE", "true")
    monkeypatch.setenv("FREEBUFF_EMBEDDED", "true")
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://local-llm-server.onrender.com")

    # Import after env is set
    from backend.server import app
    return TestClient(app)


def test_telegram_diag_returns_200(client):
    """The /api/telegram/diag endpoint returns 200."""
    resp = client.get("/api/telegram/diag")
    assert resp.status_code == 200


def test_telegram_diag_returns_config_snapshot(client):
    """The endpoint returns the expected config fields."""
    resp = client.get("/api/telegram/diag")
    data = resp.json()
    assert data["run_telegram_bot"] is True
    assert data["poller_disabled"] is False
    assert data["bot_token_set"] is True
    assert data["chat_id"] == "8120976"
    assert data["allowed_user_ids"] == "8120976"
    assert data["admin_user_ids"] == "8120976"
    assert "autonomous-ai-agency" in data["freebuff_repo_url"]
    assert data["bot_keepalive"] is True
    assert data["freebuff_embedded"] is True
    assert data["render_external_url"] == "https://local-llm-server.onrender.com"


def test_telegram_diag_masks_token(client):
    """The endpoint must NOT return the full bot token — only a masked prefix."""
    resp = client.get("/api/telegram/diag")
    data = resp.json()
    prefix = data["bot_token_prefix"]
    # The full token is "123456789:ABCdefGHIjklMNO" — the masked prefix should
    # be "12345678..." (first 8 chars + "..."), NOT the full token.
    assert "12345678" in prefix  # first 8 chars
    assert "ABCdefGHIjklMNO" not in prefix  # secret part must not appear
    assert prefix.endswith("...")


def test_telegram_diag_has_diagnostic_hints(client):
    """The endpoint includes diagnostic hints for common failure modes."""
    resp = client.get("/api/telegram/diag")
    data = resp.json()
    hints = data["diagnostic_hints"]
    assert "bot_silent" in hints
    assert "stale_repo" in hints
    assert "webhook_conflict" in hints
    # The stale_repo hint should mention local-llm-server → autonomous-ai-agency
    assert "local-llm-server" in hints["stale_repo"]
    assert "autonomous-ai-agency" in hints["stale_repo"]


def test_telegram_diag_no_auth_required(client):
    """The endpoint does not require authentication (it's a diagnostic tool)."""
    # TestClient doesn't send auth headers by default — if the endpoint
    # required auth, it would return 401.
    resp = client.get("/api/telegram/diag")
    assert resp.status_code != 401
    assert resp.status_code != 403


def test_telegram_diag_unset_token(client, monkeypatch):
    """When TELEGRAM_BOT_TOKEN is unset, bot_token_set is False and prefix is (unset)."""
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    resp = client.get("/api/telegram/diag")
    data = resp.json()
    assert data["bot_token_set"] is False
    assert data["bot_token_prefix"] == "(unset)"
