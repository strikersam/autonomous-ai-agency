"""tests/test_openclaw_gateway.py — OpenClaw in-process WebSocket gateway tests."""
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


def test_gateway_module_exists():
    assert (REPO_ROOT / "services" / "openclaw_gateway.py").is_file()


def test_mobile_ui_module_exists():
    assert (REPO_ROOT / "services" / "openclaw_mobile.py").is_file()


def test_websocket_endpoint_in_server():
    content = (REPO_ROOT / "backend" / "server.py").read_text()
    assert '@app.websocket("/openclaw/ws")' in content
    assert "async def openclaw_websocket" in content


def test_mobile_route_in_server():
    content = (REPO_ROOT / "backend" / "server.py").read_text()
    assert '@app.get("/mobile"' in content
    assert "async def openclaw_mobile_ui" in content


def test_status_endpoint_reflects_in_process_gateway():
    content = (REPO_ROOT / "backend" / "server.py").read_text()
    assert "is_gateway_alive" in content
    assert "websocket_url" in content


def test_dockerfile_backend_no_openclaw_cli():
    """Dockerfile.backend does NOT install @openclaw/cli (in-process gateway now)."""
    content = (REPO_ROOT / "Dockerfile.backend").read_text()
    assert "@openclaw/cli" not in content
    assert "start_web_with_openclaw.sh" not in content


def test_freebuff_repo_url_repointed(render_yaml):
    for svc in render_yaml["services"]:
        for e in svc.get("envVars", []):
            if e.get("key") == "FREEBUFF_REPO_URL":
                val = e.get("value", "")
                assert "autonomous-ai-agency" in val
                assert "local-llm-server" not in val


def test_env_example_documents_openclaw():
    content = (REPO_ROOT / ".env.example").read_text()
    assert "OPENCLAW_PAIRING_TOKEN" in content
    assert "OPENCLAW_MCP_SECRET_TOKEN" in content
