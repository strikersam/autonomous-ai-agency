"""tests/test_mcp_protocol_version.py — client/server MCP handshake stay in sync.

`agent/mcp_client.py` and `mcp_server/server.py` are separate deployables (the
server ships in its own Docker image, see `mcp_server/Dockerfile`, and does not
import `agent/`) so they cannot share a single physical constant. Each declares
its own module-level `MCP_PROTOCOL_VERSION`; this test is the guard that keeps
them from drifting apart again the way they did when both were hardcoded to the
stale literal `"2024-11-05"` — the oldest version MCP has ever had, while the
docstrings of both modules already documented support for several later spec
revisions (2025-03-26, 2025-11-05, 2025-11-25, 2026-07-28 RC).
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def test_client_and_server_constants_match():
    from agent.mcp_client import MCP_PROTOCOL_VERSION as client_version
    from mcp_server.server import MCP_PROTOCOL_VERSION as server_version

    assert client_version == server_version


def test_constant_is_not_the_stale_2024_version():
    from agent.mcp_client import MCP_PROTOCOL_VERSION as client_version

    assert client_version != "2024-11-05"


def test_client_initialize_sends_the_constant():
    from agent.mcp_client import MCPClient, MCP_PROTOCOL_VERSION

    client = MCPClient("http://mcp:8008")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = MagicMock()
    mock_response.headers.get = lambda k, d=None: None
    mock_response.headers.items = lambda: []
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"protocolVersion": MCP_PROTOCOL_VERSION},
    }

    sent_payload: dict = {}

    async def _fake_post(url, *, json=None, headers=None, **kw):
        sent_payload.update(json or {})
        return mock_response

    fake_async_client = MagicMock()
    fake_async_client.__aenter__ = AsyncMock(return_value=fake_async_client)
    fake_async_client.__aexit__ = AsyncMock(return_value=False)
    fake_async_client.post = AsyncMock(side_effect=_fake_post)

    with patch("agent.mcp_client.httpx.AsyncClient", return_value=fake_async_client):
        asyncio.run(client.initialize())

    assert sent_payload["params"]["protocolVersion"] == MCP_PROTOCOL_VERSION


@pytest.fixture()
def mcp_server_client(tmp_path):
    import mcp_server.workspace as ws_mod
    original = ws_mod.WORKSPACE_BASE
    ws_mod.WORKSPACE_BASE = tmp_path
    from mcp_server.server import app
    with TestClient(app) as client:
        yield client
    ws_mod.WORKSPACE_BASE = original


def test_server_initialize_returns_the_constant(mcp_server_client):
    from mcp_server.server import MCP_PROTOCOL_VERSION

    resp = mcp_server_client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {},
    })
    assert resp.status_code == 200
    assert resp.json()["result"]["protocolVersion"] == MCP_PROTOCOL_VERSION
