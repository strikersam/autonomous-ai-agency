"""tests/test_openclaw_gateway.py — OpenClaw Gateway + Telegram fix tests.

Covers:
  * render.yaml topology: openclaw-gateway service exists with the right env
    vars + persistent disk.
  * Dockerfile.openclaw exists and is valid.
  * /api/telegram/diag endpoint returns the expected config snapshot.
  * Stale FREEBUFF_REPO_URL references are repointed to autonomous-ai-agency.
  * .env.example documents the OpenClaw env vars.
"""
from __future__ import annotations

import os
import re
import subprocess
import yaml
import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


# ── render.yaml topology ──────────────────────────────────────────────────


@pytest.fixture
def render_yaml():
    """Load render.yaml as a dict."""
    path = REPO_ROOT / "render.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def test_openclaw_gateway_service_exists(render_yaml):
    """render.yaml defines an openclaw-gateway service."""
    services = render_yaml.get("services", [])
    names = [s.get("name") for s in services]
    assert "openclaw-gateway" in names, (
        f"openclaw-gateway service not found; got: {names}"
    )


def test_openclaw_gateway_is_web_type(render_yaml):
    """openclaw-gateway is a web service (needs HTTP for pairing + WebSocket)."""
    svc = next(s for s in render_yaml["services"] if s.get("name") == "openclaw-gateway")
    assert svc["type"] == "web"


def test_openclaw_gateway_uses_dockerfile(render_yaml):
    """openclaw-gateway uses Dockerfile.openclaw."""
    svc = next(s for s in render_yaml["services"] if s.get("name") == "openclaw-gateway")
    assert svc.get("dockerfilePath") == "./Dockerfile.openclaw"


def test_openclaw_gateway_has_health_check(render_yaml):
    """openclaw-gateway has a healthCheckPath."""
    svc = next(s for s in render_yaml["services"] if s.get("name") == "openclaw-gateway")
    assert svc.get("healthCheckPath") == "/health"


def test_openclaw_gateway_env_vars(render_yaml):
    """openclaw-gateway has the required env vars for agency backend + MCP."""
    svc = next(s for s in render_yaml["services"] if s.get("name") == "openclaw-gateway")
    env = {e["key"]: e.get("value", "") for e in svc.get("envVars", [])}
    assert "OPENCLAW_AGENT_BASE_URL" in env
    assert "local-llm-server.onrender.com" in env["OPENCLAW_AGENT_BASE_URL"]
    assert "OPENCLAW_MCP_BASE_URL" in env
    assert "/mcp-internal" in env["OPENCLAW_MCP_BASE_URL"]
    assert "OPENCLAW_AGENT_API_KEY" in env
    assert "OPENCLAW_MCP_SECRET_TOKEN" in env
    assert "OPENCLAW_PAIRING_TOKEN" in env


def test_openclaw_gateway_has_persistent_disk(render_yaml):
    """openclaw-gateway mounts a persistent disk for ~/.openclaw state."""
    svc = next(s for s in render_yaml["services"] if s.get("name") == "openclaw-gateway")
    disk = svc.get("disk")
    assert disk is not None, "openclaw-gateway must have a persistent disk for pairing tokens"
    assert disk.get("mountPath") == "/root/.openclaw"
    assert disk.get("sizeGB", 0) >= 1


# ── Dockerfile.openclaw ───────────────────────────────────────────────────


def test_dockerfile_openclaw_exists():
    """Dockerfile.openclaw exists."""
    assert (REPO_ROOT / "Dockerfile.openclaw").is_file()


def test_dockerfile_openclaw_binds_to_port():
    """Dockerfile.openclaw exposes a port and respects $OPENCLAW_PORT."""
    content = (REPO_ROOT / "Dockerfile.openclaw").read_text()
    assert "EXPOSE" in content
    assert "OPENCLAW_PORT" in content


def test_dockerfile_openclaw_has_persistent_state_dir():
    """Dockerfile.openclaw creates /root/.openclaw for persistent state."""
    content = (REPO_ROOT / "Dockerfile.openclaw").read_text()
    assert "/root/.openclaw" in content


# ── Telegram fix: stale repo URL repointed ────────────────────────────────


def test_freebuff_repo_url_repointed(render_yaml):
    """All FREEBUFF_REPO_URL values point at autonomous-ai-agency (not local-llm-server)."""
    for svc in render_yaml["services"]:
        for e in svc.get("envVars", []):
            if e.get("key") == "FREEBUFF_REPO_URL":
                val = e.get("value", "")
                assert "autonomous-ai-agency" in val, (
                    f"FREEBUFF_REPO_URL on {svc['name']} is stale: {val}"
                )
                assert "local-llm-server" not in val, (
                    f"FREEBUFF_REPO_URL on {svc['name']} still references local-llm-server: {val}"
                )


def test_env_example_freebuff_repo_url_repointed():
    """ .env.example's FREEBUFF_REPO_URL points at autonomous-ai-agency."""
    content = (REPO_ROOT / ".env.example").read_text()
    # Find the FREEBUFF_REPO_URL line
    match = re.search(r"^#?\s*FREEBUFF_REPO_URL=(.+)$", content, re.MULTILINE)
    assert match, "FREEBUFF_REPO_URL not found in .env.example"
    val = match.group(1).strip()
    assert "autonomous-ai-agency" in val, (
        f".env.example FREEBUFF_REPO_URL is stale: {val}"
    )


def test_no_stale_local_llm_server_in_render_yaml(render_yaml):
    """No env var VALUE in render.yaml references strikersam/local-llm-server."""
    for svc in render_yaml["services"]:
        for e in svc.get("envVars", []):
            val = e.get("value", "")
            if isinstance(val, str) and "strikersam/local-llm-server" in val:
                pytest.fail(
                    f"{svc['name']}.{e['key']} references stale repo: {val}"
                )


# ── /api/telegram/diag endpoint ───────────────────────────────────────────


def test_telegram_diag_endpoint_exists():
    """backend/server.py has a GET /api/telegram/diag endpoint."""
    content = (REPO_ROOT / "backend" / "server.py").read_text()
    assert '@app.get("/api/telegram/diag")' in content
    assert "async def telegram_diag" in content


def test_telegram_diag_returns_config_snapshot():
    """The diag endpoint returns the expected fields."""
    content = (REPO_ROOT / "backend" / "server.py").read_text()
    # Check the endpoint returns a dict with the expected keys.
    expected_fields = [
        "run_telegram_bot",
        "poller_disabled",
        "bot_token_set",
        "bot_token_prefix",
        "chat_id",
        "allowed_user_ids",
        "freebuff_repo_url",
        "bot_keepalive",
        "diagnostic_hints",
    ]
    for field in expected_fields:
        assert f'"{field}"' in content, (
            f"telegram_diag endpoint missing field: {field}"
        )


# ── .env.example OpenClaw docs ────────────────────────────────────────────


def test_env_example_documents_openclaw():
    """ .env.example documents the OpenClaw env vars."""
    content = (REPO_ROOT / ".env.example").read_text()
    assert "OPENCLAW_AGENT_BASE_URL" in content
    assert "OPENCLAW_MCP_BASE_URL" in content
    assert "OPENCLAW_PAIRING_TOKEN" in content
    assert "OPENCLAW_MCP_SECRET_TOKEN" in content


# ── docs/runbooks/openclaw-setup.md updated ───────────────────────────────


def test_openclaw_setup_doc_mentions_ios():
    """The openclaw-setup.md doc mentions the iOS app + Render gateway."""
    content = (REPO_ROOT / "docs" / "runbooks" / "openclaw-setup.md").read_text()
    assert "iOS" in content
    assert "Render" in content
    assert "openclaw-gateway" in content
    assert "pair" in content.lower()


def test_openclaw_setup_doc_has_pairing_instructions():
    """The doc has pairing instructions (openclaw pair qr)."""
    content = (REPO_ROOT / "docs" / "runbooks" / "openclaw-setup.md").read_text()
    assert "openclaw pair qr" in content
    assert "OPENCLAW_PAIRING_TOKEN" in content
