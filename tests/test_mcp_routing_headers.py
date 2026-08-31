"""tests/test_mcp_routing_headers.py — MCP 2026-07-28 Mcp-Method / Mcp-Name headers.

The 2026-07-28 MCP specification adds two informational HTTP headers so that
intermediaries (API gateways, rate-limiters, CDN rules) can route and throttle
at the HTTP layer without parsing the JSON-RPC body:

  - ``Mcp-Method: <rpc_method>`` — present on every outbound request.
  - ``Mcp-Name: <tool_name>``    — present on ``tools/call`` requests only.

Both are backward-compatible: servers/proxies that do not understand them ignore
them.  These tests verify that the client sends the right headers without
requiring a running MCP server.
2026-08-31 daily automation — MCP 2026-07-28 spec compliance.
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_client(base_url: str = "http://mcp:8008") -> "MCPClient":
    from agent.mcp_client import MCPClient
    return MCPClient(base_url)


def _captured_request_headers(
    mock_response: MagicMock,
    client: "MCPClient",
    method: str,
    params: dict[str, Any] | None = None,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, str]:
    """Run a single _rpc() call against a mock httpx.AsyncClient and return
    the headers dict that was passed to client.post()."""
    mock_response.status_code = 200
    mock_response.headers = MagicMock()
    mock_response.headers.get = lambda k, d=None: None  # no Mcp-Session-Id
    mock_response.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}
    mock_response.raise_for_status = MagicMock()
    mock_response.headers.items = lambda: []

    posted_headers: dict[str, str] = {}

    async def _fake_post(url, *, json=None, headers=None, **kw):
        posted_headers.update(headers or {})
        return mock_response

    fake_async_client = MagicMock()
    fake_async_client.__aenter__ = AsyncMock(return_value=fake_async_client)
    fake_async_client.__aexit__ = AsyncMock(return_value=False)
    fake_async_client.post = AsyncMock(side_effect=_fake_post)

    with patch("agent.mcp_client.httpx.AsyncClient", return_value=fake_async_client):
        kw = {}
        if extra_headers is not None:
            kw["extra_headers"] = extra_headers
        asyncio.run(client._rpc(method, params, **kw))

    return posted_headers


class TestMcpMethodHeader:
    """Every outbound _rpc() call must include Mcp-Method."""

    def test_tools_list_includes_mcp_method(self):
        client = _make_client()
        headers = _captured_request_headers(
            MagicMock(), client, "tools/list"
        )
        assert headers.get("Mcp-Method") == "tools/list"

    def test_initialize_includes_mcp_method(self):
        client = _make_client()
        headers = _captured_request_headers(
            MagicMock(), client, "initialize",
            params={"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {}},
        )
        assert headers.get("Mcp-Method") == "initialize"

    def test_tools_call_includes_mcp_method(self):
        client = _make_client()
        headers = _captured_request_headers(
            MagicMock(), client, "tools/call",
            params={"name": "read_file", "arguments": {}},
            extra_headers={"Mcp-Name": "read_file"},
        )
        assert headers.get("Mcp-Method") == "tools/call"

    def test_custom_method_echoed_in_header(self):
        client = _make_client()
        headers = _captured_request_headers(MagicMock(), client, "resources/list")
        assert headers.get("Mcp-Method") == "resources/list"


class TestMcpNameHeader:
    """tools/call requests must include Mcp-Name; other methods must not."""

    def _call_tool_headers(self, tool_name: str) -> dict[str, str]:
        """Run client.call_tool() and capture the request headers."""
        response = MagicMock()
        response.status_code = 200
        response.headers = MagicMock()
        response.headers.get = lambda k, d=None: None
        response.json.return_value = {
            "jsonrpc": "2.0", "id": 1,
            "result": {"content": [{"text": "ok"}], "isError": False},
        }
        response.raise_for_status = MagicMock()
        response.headers.items = lambda: []

        posted_headers: dict[str, str] = {}

        async def _fake_post(url, *, json=None, headers=None, **kw):
            posted_headers.update(headers or {})
            return response

        client = _make_client()
        fake_async_client = MagicMock()
        fake_async_client.__aenter__ = AsyncMock(return_value=fake_async_client)
        fake_async_client.__aexit__ = AsyncMock(return_value=False)
        fake_async_client.post = AsyncMock(side_effect=_fake_post)

        with patch("agent.mcp_client.httpx.AsyncClient", return_value=fake_async_client):
            asyncio.run(client.call_tool(tool_name, {}))

        return posted_headers

    def test_call_tool_sends_mcp_name(self):
        headers = self._call_tool_headers("read_file")
        assert headers.get("Mcp-Name") == "read_file"

    def test_call_tool_mcp_name_matches_tool_name(self):
        for tool_name in ("write_file", "web_search", "run_command"):
            headers = self._call_tool_headers(tool_name)
            assert headers.get("Mcp-Name") == tool_name, f"mismatch for {tool_name}"

    def test_call_tool_also_has_mcp_method(self):
        headers = self._call_tool_headers("any_tool")
        assert headers.get("Mcp-Method") == "tools/call"

    def test_tools_list_does_not_have_mcp_name(self):
        client = _make_client()
        headers = _captured_request_headers(MagicMock(), client, "tools/list")
        assert "Mcp-Name" not in headers

    def test_initialize_does_not_have_mcp_name(self):
        client = _make_client()
        headers = _captured_request_headers(MagicMock(), client, "initialize", params={})
        assert "Mcp-Name" not in headers


class TestMcpHeadersBackwardCompatibility:
    """Extra headers must not displace existing required headers."""

    def test_mcp_method_coexists_with_accept_header(self):
        client = _make_client()
        headers = _captured_request_headers(MagicMock(), client, "tools/list")
        assert "application/json" in headers.get("Accept", "")
        assert headers.get("Mcp-Method") == "tools/list"

    def test_mcp_method_coexists_with_bearer_auth(self):
        from agent.mcp_client import MCPClient
        client = MCPClient("http://mcp:8008", secret_token="tok")
        headers = _captured_request_headers(MagicMock(), client, "tools/list")
        assert headers.get("Authorization") == "Bearer tok"
        assert headers.get("Mcp-Method") == "tools/list"

    def test_extra_headers_not_sent_on_other_method(self):
        """extra_headers passed to _rpc are method-specific; this tests isolation."""
        client = _make_client()
        headers = _captured_request_headers(
            MagicMock(), client, "tools/list", extra_headers=None
        )
        assert "Mcp-Name" not in headers
