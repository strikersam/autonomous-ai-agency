"""tests/test_sam_livekit.py — SAM realtime voice (LiveKit) integration.

Covers:
- voice/livekit_token.py  — access-token minting (claims, TTL clamp, validation)
- voice/livekit_config.py — env resolution + configured/missing reporting
- backend endpoints       — /agent/sam/livekit/status + /agent/sam/livekit/token
- voice/sam_livekit_worker.py — importable without livekit-agents installed
"""
from __future__ import annotations

import os

import jwt
import pytest

from voice.livekit_config import get_livekit_config
from voice.livekit_token import MAX_TTL_S, mint_access_token


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def auth_headers(client):
    """Auth headers for the seeded admin user (same pattern as test_agile_api)."""
    from backend.server import ADMIN_EMAIL

    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    resp = client.post(
        "/api/auth/login", json={"email": ADMIN_EMAIL, "password": admin_password}
    )
    if resp.status_code == 200:
        token = resp.json().get("access_token") or resp.json().get("token")
        if token:
            return {"Authorization": f"Bearer {token}"}
    return {}


@pytest.fixture()
def livekit_env(monkeypatch):
    """Configure a fake LiveKit deployment via env vars."""
    monkeypatch.setenv("LIVEKIT_URL", "wss://test-agency.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "APItestkey")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "secret-" + "x" * 32)


@pytest.fixture()
def no_livekit_env(monkeypatch):
    """Ensure LiveKit env vars are absent."""
    for var in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"):
        monkeypatch.delenv(var, raising=False)


# ── Token minting ─────────────────────────────────────────────────────────────

def test_mint_token_claims():
    """Token must carry the LiveKit iss/sub/video-grant claim shape."""
    token = mint_access_token(
        api_key="APIkey",
        api_secret="s3cret",
        identity="commander@agency.dev",
        room="sam-voice-commander",
        name="Commander",
    )
    claims = jwt.decode(token, "s3cret", algorithms=["HS256"], issuer="APIkey")
    assert claims["sub"] == "commander@agency.dev"
    assert claims["name"] == "Commander"
    grant = claims["video"]
    assert grant["room"] == "sam-voice-commander"
    assert grant["roomJoin"] is True
    assert grant["canPublish"] is True
    assert grant["canSubscribe"] is True
    assert claims["exp"] > claims["nbf"]


def test_mint_token_ttl_clamped():
    """TTL must be clamped to at most 24 hours and at least 60 seconds."""
    import time

    token = mint_access_token(
        api_key="k", api_secret="s", identity="i", room="r", ttl_s=10_000_000
    )
    claims = jwt.decode(token, "s", algorithms=["HS256"], issuer="k")
    assert claims["exp"] - int(time.time()) <= MAX_TTL_S + 60

    token = mint_access_token(
        api_key="k", api_secret="s", identity="i", room="r", ttl_s=1
    )
    claims = jwt.decode(token, "s", algorithms=["HS256"], issuer="k")
    assert claims["exp"] - claims["nbf"] >= 60


@pytest.mark.parametrize(
    "kwargs",
    [
        {"api_key": "", "api_secret": "s", "identity": "i", "room": "r"},
        {"api_key": "k", "api_secret": "", "identity": "i", "room": "r"},
        {"api_key": "k", "api_secret": "s", "identity": "", "room": "r"},
        {"api_key": "k", "api_secret": "s", "identity": "i", "room": ""},
    ],
)
def test_mint_token_rejects_missing_args(kwargs):
    """Empty key/secret/identity/room must raise ValueError."""
    with pytest.raises(ValueError):
        mint_access_token(**kwargs)


# ── Config resolution ─────────────────────────────────────────────────────────

def test_config_unconfigured_reports_missing(no_livekit_env):
    cfg = get_livekit_config()
    assert cfg.configured is False
    assert "LIVEKIT_URL" in cfg.missing
    assert "LIVEKIT_API_KEY" in cfg.missing
    assert "LIVEKIT_API_SECRET" in cfg.missing


def test_config_configured(livekit_env):
    cfg = get_livekit_config()
    assert cfg.configured is True
    assert cfg.missing == ()
    assert cfg.url == "wss://test-agency.livekit.cloud"
    assert cfg.room_prefix == "sam-voice"
    assert cfg.llm_base_url.startswith("https://")
    assert cfg.llm_model  # always resolves to a default


def test_config_llm_override(livekit_env, monkeypatch):
    """SAM_LLM_* env vars must override the NVIDIA defaults (Hermes/proxy routing)."""
    monkeypatch.setenv("SAM_LLM_BASE_URL", "http://localhost:8100/v1")
    monkeypatch.setenv("SAM_LLM_MODEL", "hermes-local")
    cfg = get_livekit_config()
    assert cfg.llm_base_url == "http://localhost:8100/v1"
    assert cfg.llm_model == "hermes-local"


# ── Backend endpoints ─────────────────────────────────────────────────────────

def test_livekit_status_requires_auth(client):
    resp = client.get("/agent/sam/livekit/status")
    assert resp.status_code == 401


def test_livekit_token_requires_auth(client):
    resp = client.post("/agent/sam/livekit/token", json={})
    assert resp.status_code == 401


def test_livekit_status_unconfigured(client, auth_headers, no_livekit_env):
    if not auth_headers:
        pytest.skip("admin login unavailable")
    resp = client.get("/agent/sam/livekit/status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is False
    assert "LIVEKIT_URL" in data["missing"]


def test_livekit_token_unconfigured_returns_503(client, auth_headers, no_livekit_env):
    if not auth_headers:
        pytest.skip("admin login unavailable")
    resp = client.post("/agent/sam/livekit/token", json={}, headers=auth_headers)
    assert resp.status_code == 503


def test_livekit_status_configured(client, auth_headers, livekit_env):
    if not auth_headers:
        pytest.skip("admin login unavailable")
    resp = client.get("/agent/sam/livekit/status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is True
    assert data["url"] == "wss://test-agency.livekit.cloud"
    assert data["missing"] == []


def test_livekit_token_minted_for_user(client, auth_headers, livekit_env):
    if not auth_headers:
        pytest.skip("admin login unavailable")
    resp = client.post("/agent/sam/livekit/token", json={}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["url"] == "wss://test-agency.livekit.cloud"
    assert data["room"].startswith("sam-voice-")
    claims = jwt.decode(
        data["token"], "secret-" + "x" * 32, algorithms=["HS256"], issuer="APItestkey"
    )
    assert claims["sub"] == data["identity"]
    assert claims["video"]["room"] == data["room"]


def test_livekit_token_room_override(client, auth_headers, livekit_env):
    if not auth_headers:
        pytest.skip("admin login unavailable")
    resp = client.post(
        "/agent/sam/livekit/token", json={"room": "war-room"}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["room"] == "war-room"


# ── Worker module ─────────────────────────────────────────────────────────────

def test_worker_importable_without_livekit():
    """The worker module must import cleanly even when livekit-agents is absent."""
    import voice.sam_livekit_worker as worker

    assert callable(worker.entrypoint)
    assert callable(worker.main)
    assert "1-3 short sentences" in worker.VOICE_EXTRA_INSTRUCTIONS


def test_sam_public_context_snapshot():
    """SamAgent.build_context (used by worker tools) must return a dict."""
    import asyncio

    from agent.sam import SamAgent

    ctx = asyncio.run(SamAgent().build_context())
    assert isinstance(ctx, dict)
    assert "timestamp" in ctx
