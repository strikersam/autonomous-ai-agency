"""tests/test_daily_automation_2026_08_23.py — Daily automation tests (2026-08-23).

Covers the MCP 2026-07-28 specification improvements applied today:
  1. ``initialize()`` advertises protocolVersion "2026-07-28" (was "2024-11-05").
  2. ``_routing_headers()`` emits ``Mcp-Method`` on every RPC and ``Mcp-Name``
     on tool calls — enabling gateway-level routing without body inspection.
  3. ``notify()`` carries the ``Mcp-Method`` header for routing parity.
  4. ``list_tools()`` reads and logs ``cacheScope`` from the server response.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.mcp_client import MCPClient, MCPUnavailableError  # noqa: E402


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_client(url: str = "http://mcp-server:8008") -> MCPClient:
    return MCPClient(base_url=url)


def _fake_headers(extra: dict | None = None) -> MagicMock:
    """MagicMock that behaves like httpx.Headers for our client's usage.

    The client calls ``resp.headers.get("content-type")`` and
    ``resp.headers.get("Mcp-Session-Id")``.  Real dicts don't support attribute
    assignment (``resp.headers.get = ...`` raises), so we return a MagicMock
    whose ``.get()`` follows the real lookup logic.
    """
    extra = extra or {}
    h = MagicMock()

    def _get(key: str, default=None):
        key_lc = key.lower()
        if key_lc == "content-type":
            return "application/json"
        return extra.get(key_lc, extra.get(key, default))

    h.get = _get
    return h


def _make_resp(result: dict, req_id: int) -> MagicMock:
    """Return a response mock for a successful JSON-RPC reply."""
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = _fake_headers()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"jsonrpc": "2.0", "id": req_id, "result": result}
    resp.text = ""
    return resp


def _patch_http(fake_post_fn):
    """Context manager that patches httpx.AsyncClient with a custom post handler."""
    mock_cls = patch("httpx.AsyncClient")

    class _Ctx:
        def __enter__(self):
            self._patcher = mock_cls.__enter__(mock_cls)
            self._mock_cls = patch("httpx.AsyncClient").start()
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_http.post = AsyncMock(side_effect=fake_post_fn)
            self._mock_cls.return_value = mock_http
            return self._mock_cls

        def __exit__(self, *args):
            patch.stopall()

    return _Ctx()


# ── 1. initialize() protocol version ─────────────────────────────────────────

class TestInitializeProtocolVersion:
    """initialize() must advertise protocolVersion "2026-07-28"."""

    @pytest.mark.asyncio
    async def test_initialize_advertises_2026_07_28(self) -> None:
        client = _make_client()
        captured: list[dict] = []

        async def fake_post(url, *, json, headers, **kw):
            captured.append(json)
            return _make_resp({"protocolVersion": "2026-07-28", "capabilities": {}}, json["id"])

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_http.post = AsyncMock(side_effect=fake_post)
            mock_cls.return_value = mock_http
            await client.initialize()

        assert captured, "initialize() sent no request"
        payload = captured[0]
        assert payload["method"] == "initialize"
        assert payload["params"]["protocolVersion"] == "2026-07-28", (
            f"Expected '2026-07-28', got {payload['params']['protocolVersion']!r}"
        )

    @pytest.mark.asyncio
    async def test_initialize_sends_client_info(self) -> None:
        client = _make_client()
        captured: list[dict] = []

        async def fake_post(url, *, json, headers, **kw):
            captured.append(json)
            return _make_resp({}, json["id"])

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_http.post = AsyncMock(side_effect=fake_post)
            mock_cls.return_value = mock_http
            await client.initialize()

        params = captured[0]["params"]
        assert "clientInfo" in params
        assert params["clientInfo"]["name"] == "local-llm-server"

    @pytest.mark.asyncio
    async def test_initialize_carries_mcp_method_header(self) -> None:
        """The Mcp-Method routing header is present on the initialize RPC itself."""
        client = _make_client()
        sent_headers: list[dict] = []

        async def fake_post(url, *, json, headers, **kw):
            sent_headers.append(dict(headers))
            return _make_resp({}, json["id"])

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_http.post = AsyncMock(side_effect=fake_post)
            mock_cls.return_value = mock_http
            await client.initialize()

        assert sent_headers[0].get("Mcp-Method") == "initialize"


# ── 2. _routing_headers() — Mcp-Method and Mcp-Name ──────────────────────────

class TestRoutingHeaders:
    """_routing_headers() must emit Mcp-Method on all calls and Mcp-Name on tool calls."""

    def test_mcp_method_present_on_tools_list(self) -> None:
        client = _make_client()
        headers = client._routing_headers("tools/list", None)
        assert headers.get("Mcp-Method") == "tools/list"

    def test_mcp_method_present_on_initialize(self) -> None:
        client = _make_client()
        headers = client._routing_headers("initialize", {})
        assert headers.get("Mcp-Method") == "initialize"

    def test_mcp_name_present_on_tool_call(self) -> None:
        client = _make_client()
        headers = client._routing_headers("tools/call", {"name": "clone_repo", "arguments": {}})
        assert headers.get("Mcp-Method") == "tools/call"
        assert headers.get("Mcp-Name") == "clone_repo"

    def test_mcp_name_absent_when_not_tool_call(self) -> None:
        client = _make_client()
        headers = client._routing_headers("tools/list", {})
        assert "Mcp-Name" not in headers

    def test_mcp_name_absent_when_no_name_param(self) -> None:
        client = _make_client()
        headers = client._routing_headers("tools/call", {"arguments": {}})
        assert "Mcp-Name" not in headers

    def test_mcp_name_absent_when_params_none(self) -> None:
        client = _make_client()
        headers = client._routing_headers("tools/call", None)
        assert "Mcp-Name" not in headers

    @pytest.mark.asyncio
    async def test_rpc_sends_mcp_method_header(self) -> None:
        """_rpc() must merge routing headers into the outgoing request."""
        client = _make_client()
        sent_headers: list[dict] = []

        async def fake_post(url, *, json, headers, **kw):
            sent_headers.append(dict(headers))
            return _make_resp({"tools": []}, json["id"])

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_http.post = AsyncMock(side_effect=fake_post)
            mock_cls.return_value = mock_http
            await client.list_tools()

        assert sent_headers, "No request was sent"
        assert sent_headers[0].get("Mcp-Method") == "tools/list"

    @pytest.mark.asyncio
    async def test_tool_call_sends_mcp_name_header(self) -> None:
        """call_tool() for a named tool must carry Mcp-Name in the request headers."""
        client = _make_client()
        sent_headers: list[dict] = []

        async def fake_post(url, *, json, headers, **kw):
            sent_headers.append(dict(headers))
            return _make_resp({"content": [{"text": "ok"}]}, json["id"])

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_http.post = AsyncMock(side_effect=fake_post)
            mock_cls.return_value = mock_http
            await client.call_tool("delete_file", {"path": "/tmp/x"})

        assert sent_headers, "No request was sent"
        assert sent_headers[0].get("Mcp-Method") == "tools/call"
        assert sent_headers[0].get("Mcp-Name") == "delete_file"


# ── 3. notify() Mcp-Method header ─────────────────────────────────────────────

class TestNotifyRoutingHeader:
    """notify() must carry Mcp-Method for gateway routing parity with _rpc()."""

    @pytest.mark.asyncio
    async def test_notify_sends_mcp_method_header(self) -> None:
        client = _make_client()
        sent_headers: list[dict] = []

        async def fake_post(url, *, json, headers, **kw):
            sent_headers.append(dict(headers))
            resp = MagicMock()
            resp.status_code = 200
            resp.headers = _fake_headers()
            return resp

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_http.post = AsyncMock(side_effect=fake_post)
            mock_cls.return_value = mock_http
            await client.notify("notifications/initialized")

        assert sent_headers, "notify() sent no request"
        assert sent_headers[0].get("Mcp-Method") == "notifications/initialized"

    @pytest.mark.asyncio
    async def test_notify_does_not_send_mcp_name(self) -> None:
        """Notifications carry Mcp-Method only — Mcp-Name is for tool-call RPCs."""
        client = _make_client()
        sent_headers: list[dict] = []

        async def fake_post(url, *, json, headers, **kw):
            sent_headers.append(dict(headers))
            resp = MagicMock()
            resp.status_code = 200
            resp.headers = _fake_headers()
            return resp

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_http.post = AsyncMock(side_effect=fake_post)
            mock_cls.return_value = mock_http
            await client.notify("notifications/initialized")

        assert "Mcp-Name" not in sent_headers[0]


# ── 4. list_tools() cacheScope handling ──────────────────────────────────────

class TestToolsListCacheScope:
    """list_tools() must read cacheScope from the server response."""

    @pytest.mark.asyncio
    async def test_list_tools_handles_global_cache_scope(self, caplog) -> None:
        client = _make_client()

        async def fake_post(url, *, json, headers, **kw):
            return _make_resp(
                {"tools": [{"name": "list_files"}], "ttlMs": 30000, "cacheScope": "global"},
                json["id"],
            )

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_http.post = AsyncMock(side_effect=fake_post)
            mock_cls.return_value = mock_http

            with caplog.at_level(logging.DEBUG, logger="qwen-proxy"):
                tools = await client.list_tools()

        assert tools == [{"name": "list_files"}]
        assert any("global" in record.message for record in caplog.records), (
            "Expected a debug log mentioning 'global' cacheScope"
        )

    @pytest.mark.asyncio
    async def test_list_tools_handles_absent_cache_scope(self) -> None:
        """Absent cacheScope (treated as 'local') must not raise."""
        client = _make_client()

        async def fake_post(url, *, json, headers, **kw):
            return _make_resp(
                {"tools": [{"name": "read_file"}], "ttlMs": 60000},
                json["id"],
            )

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_http.post = AsyncMock(side_effect=fake_post)
            mock_cls.return_value = mock_http
            tools = await client.list_tools()

        assert tools == [{"name": "read_file"}]

    @pytest.mark.asyncio
    async def test_list_tools_caches_regardless_of_scope(self) -> None:
        """Even a global-scope result must be cached in-process for TTL duration."""
        client = _make_client()
        call_count = 0

        async def fake_post(url, *, json, headers, **kw):
            nonlocal call_count
            call_count += 1
            return _make_resp(
                {"tools": [{"name": "create_file"}], "ttlMs": 120000, "cacheScope": "global"},
                json["id"],
            )

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_http.post = AsyncMock(side_effect=fake_post)
            mock_cls.return_value = mock_http
            await client.list_tools()
            await client.list_tools()  # should hit cache

        assert call_count == 1, f"Expected 1 RPC call (cached), got {call_count}"

    @pytest.mark.asyncio
    async def test_list_tools_local_scope_also_cached(self) -> None:
        """cacheScope='local' (or absent) also caches for TTL."""
        client = _make_client()
        call_count = 0

        async def fake_post(url, *, json, headers, **kw):
            nonlocal call_count
            call_count += 1
            return _make_resp(
                {"tools": [{"name": "write_file"}], "ttlMs": 90000, "cacheScope": "local"},
                json["id"],
            )

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_http.post = AsyncMock(side_effect=fake_post)
            mock_cls.return_value = mock_http
            await client.list_tools()
            await client.list_tools()

        assert call_count == 1, f"Expected 1 RPC call (cached), got {call_count}"
