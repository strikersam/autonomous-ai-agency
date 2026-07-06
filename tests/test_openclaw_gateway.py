"""tests/test_openclaw_gateway.py — OpenClaw Gateway + Telegram fix tests.

Covers:
  * render.yaml topology: OpenClaw env vars on the existing web service
    (single-service free-tier deploy — no separate openclaw-gateway service).
  * Dockerfile.backend installs Node.js + OpenClaw CLI.
  * docker/start_web_with_openclaw.sh startup wrapper exists.
  * /api/openclaw/status, /api/openclaw/qr, /openclaw/* reverse-proxy endpoints.
  * Stale FREEBUFF_REPO_URL references are repointed to autonomous-ai-agency.
  * .env.example documents the OpenClaw env vars.
"""
from __future__ import annotations

import os
import re
import yaml
import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def render_yaml():
    path = REPO_ROOT / "render.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def test_openclaw_env_vars_on_web_service(render_yaml):
    svc = next(s for s in render_yaml["services"] if s.get("name") == "local-llm-server")
    env_keys = {e["key"] for e in svc.get("envVars", [])}
    assert "OPENCLAW_AGENT_BASE_URL" in env_keys
    assert "OPENCLAW_AGENT_API_KEY" in env_keys
    assert "OPENCLAW_MCP_BASE_URL" in env_keys
    assert "OPENCLAW_MCP_SECRET_TOKEN" in env_keys
    assert "OPENCLAW_PAIRING_TOKEN" in env_keys


def test_no_separate_openclaw_service(render_yaml):
    names = [s.get("name") for s in render_yaml["services"]]
    assert "openclaw-gateway" not in names


def test_openclaw_agent_base_url_points_at_agency(render_yaml):
    svc = next(s for s in render_yaml["services"] if s.get("name") == "local-llm-server")
    env = {e["key"]: e.get("value", "") for e in svc.get("envVars", [])}
    assert "local-llm-server.onrender.com" in env["OPENCLAW_AGENT_BASE_URL"]
    assert "/v1" in env["OPENCLAW_AGENT_BASE_URL"]


def test_openclaw_mcp_base_url_points_at_mcp(render_yaml):
    svc = next(s for s in render_yaml["services"] if s.get("name") == "local-llm-server")
    env = {e["key"]: e.get("value", "") for e in svc.get("envVars", [])}
    assert "/mcp-internal" in env["OPENCLAW_MCP_BASE_URL"]


def test_dockerfile_backend_installs_nodejs():
    content = (REPO_ROOT / "Dockerfile.backend").read_text()
    assert "nodejs" in content.lower() or "node:" in content.lower()


def test_dockerfile_backend_installs_openclaw_cli():
    content = (REPO_ROOT / "Dockerfile.backend").read_text()
    assert "@openclaw/cli" in content


def test_dockerfile_backend_uses_startup_wrapper():
    content = (REPO_ROOT / "Dockerfile.backend").read_text()
    assert "start_web_with_openclaw.sh" in content


def test_startup_wrapper_exists():
    path = REPO_ROOT / "docker" / "start_web_with_openclaw.sh"
    assert path.is_file()
    assert os.access(path, os.X_OK)


def test_startup_wrapper_launches_openclaw():
    content = (REPO_ROOT / "docker" / "start_web_with_openclaw.sh").read_text()
    assert "openclaw" in content.lower()
    assert "uvicorn" in content


def test_openclaw_status_endpoint_exists():
    content = (REPO_ROOT / "backend" / "server.py").read_text()
    assert '@app.get("/api/openclaw/status")' in content
    assert "async def openclaw_status" in content


def test_openclaw_qr_endpoint_exists():
    content = (REPO_ROOT / "backend" / "server.py").read_text()
    assert '@app.get("/api/openclaw/qr")' in content
    assert "async def openclaw_qr" in content


def test_openclaw_reverse_proxy_exists():
    content = (REPO_ROOT / "backend" / "server.py").read_text()
    assert "/openclaw/{path:path}" in content
    assert "async def openclaw_reverse_proxy" in content


def test_freebuff_repo_url_repointed(render_yaml):
    for svc in render_yaml["services"]:
        for e in svc.get("envVars", []):
            if e.get("key") == "FREEBUFF_REPO_URL":
                val = e.get("value", "")
                assert "autonomous-ai-agency" in val
                assert "local-llm-server" not in val


def test_env_example_freebuff_repo_url_repointed():
    content = (REPO_ROOT / ".env.example").read_text()
    match = re.search(r"^#?\s*FREEBUFF_REPO_URL=(.+)$", content, re.MULTILINE)
    assert match
    val = match.group(1).strip()
    assert "autonomous-ai-agency" in val


def test_no_stale_local_llm_server_in_render_yaml(render_yaml):
    for svc in render_yaml["services"]:
        for e in svc.get("envVars", []):
            val = e.get("value", "")
            if isinstance(val, str) and "strikersam/local-llm-server" in val:
                pytest.fail(f"{svc['name']}.{e['key']} references stale repo: {val}")


def test_telegram_diag_endpoint_exists():
    content = (REPO_ROOT / "backend" / "server.py").read_text()
    assert '@app.get("/api/telegram/diag")' in content


def test_env_example_documents_openclaw():
    content = (REPO_ROOT / ".env.example").read_text()
    assert "OPENCLAW_AGENT_BASE_URL" in content
    assert "OPENCLAW_MCP_BASE_URL" in content
    assert "OPENCLAW_PAIRING_TOKEN" in content
    assert "OPENCLAW_MCP_SECRET_TOKEN" in content


def test_openclaw_setup_doc_mentions_ios():
    content = (REPO_ROOT / "docs" / "runbooks" / "openclaw-setup.md").read_text()
    assert "iOS" in content
    assert "Render" in content
