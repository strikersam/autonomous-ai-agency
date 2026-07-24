"""agent/mcp_client.py — Async MCP client for the mcp-server Docker container.

Talks to the MCP server at MCP_SERVER_BASE_URL via JSON-RPC 2.0 over HTTP.
Implements a simple open/close circuit breaker so a crashed or missing
MCP server never stalls the agent loop — callers get a clear "unavailable"
error and can fall back to local tools.

Supports MCP spec 2025-11-05 structured output:

  - ``list_tools()`` returns the full tool descriptor including ``outputSchema``
    when the server provides one.
  - ``call_tool_structured()`` extracts the ``structuredContent`` field from
    the tool result (MCP spec 2025-11-25) in addition to the text content,
    returning an ``MCPToolResult``.

MCP spec 2026-07-28 RC — tools/list TTL caching:

  - Servers may include ``ttlMs`` in the ``tools/list`` response to signal
    that the tool list is stable for that duration.  ``list_tools()`` now
    caches the result and skips the RPC until the TTL expires, reducing
    round-trips for stable tool registries.
  - When the server does not supply ``ttlMs`` a conservative default of
    ``MCP_TOOLS_LIST_DEFAULT_TTL_MS`` (env, default 60 000 ms) is used.
  - Call ``invalidate_tools_cache()`` to force an immediate refresh (e.g.
    after deploying a new tool to the MCP server).

Usage::

    client = MCPClient("http://mcp-server:8008")
    await client.initialize()
    tools = await client.list_tools()
    # Each tool dict may include "outputSchema" (JSON Schema) for typed results.

    # Legacy text-only call (unchanged):
    text = await client.call_tool("clone_repo", {"workspace_id": "...", ...})

    # Structured call (MCP spec 2025-11-25):
    result = await client.call_tool_structured("clone_repo", {"workspace_id": "...", ...})
    if result.structured is not None:
        process(result.structured)   # validated typed dict
    else:
        process(result.text)         # fallback text
"""
from __future__ import annotations

import itertools
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

log = logging.getLogger("qwen-proxy")

# Circuit breaker constants
_CB_FAILURE_THRESHOLD = 3    # consecutive failures before opening
_CB_RECOVERY_TIMEOUT = 30.0  # seconds before trying again (half-open)

# Tools-list TTL caching (MCP spec 2026-07-28 RC).
# When the server omits ``ttlMs`` fall back to this env-configurable default.
_DEFAULT_TOOLS_TTL_MS = int(os.environ.get("MCP_TOOLS_LIST_DEFAULT_TTL_MS", "60000"))


class MCPUnavailableError(RuntimeError):
    """Raised when the MCP server is unreachable or the circuit is open."""


@dataclass
class MCPToolResult:
    """Result from ``call_tool_structured()``.

    ``structured`` is populated when the MCP server returns a ``structuredContent``
    field (MCP spec 2025-11-25).  ``text`` always contains the plain-text content
    for backward compatibility.  ``is_error`` mirrors the MCP ``isError`` flag.
    """

    text: str
    structured: dict[str, Any] | None = field(default=None)
    is_error: bool = field(default=False)

    @property
    def content(self) -> dict[str, Any] | str:
        """Prefer structured data; fall back to text when unavailable."""
        return self.structured if self.structured is not None else self.text


class MCPClient:
    """Thin async MCP client with open/close circuit breaker.

    Thread-safe only within a single asyncio event loop (no cross-loop sharing).
    """

    def __init__(self, base_url: str | None = None, timeout: float = 30.0, secret_token: str | None = None) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.timeout = timeout
        self._secret_token = secret_token or os.environ.get("MCP_SECRET_TOKEN") or None
        self._id_counter = itertools.count(1)
        # Circuit breaker state
        self._failures = 0
        self._opened_at: float | None = None
        # Tools-list TTL cache (MCP spec 2026-07-28 RC)
        self._tools_cache: list[dict[str, Any]] | None = None
        self._tools_cache_expires_at: float = 0.0

    # ── circuit breaker ──────────────────────────────────────────────────────

    def _is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if time.monotonic() - self._opened_at >= _CB_RECOVERY_TIMEOUT:
            # Half-open: let one request through
            self._opened_at = None
            return False
        return True

    def _on_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def _on_failure(self) -> None:
        self._failures += 1
        if self._failures >= _CB_FAILURE_THRESHOLD:
            self._opened_at = time.monotonic()
            log.warning(
                "MCP circuit breaker OPEN after %d failures (recovery in %ds)",
                self._failures, int(_CB_RECOVERY_TIMEOUT),
            )

    # ── low-level RPC ────────────────────────────────────────────────────────

    async def _rpc(self, method: str, params: dict[str, Any] | None = None) -> Any:
        if not self.base_url:
            raise MCPUnavailableError(
                "MCP server not reachable — set MCP_SERVER_BASE_URL to the /mcp-internal endpoint "
                "(e.g. https://local-llm-server.onrender.com/mcp-internal)"
            )
        if self._is_open():
            raise MCPUnavailableError("MCP server circuit breaker is open; using local tools")

        req_id = next(self._id_counter)
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {},
        }
        headers: dict[str, str] = {}
        if self._secret_token:
            headers["Authorization"] = f"Bearer {self._secret_token}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}/mcp", json=payload, headers=headers)
                resp.raise_for_status()
            body = resp.json()
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            self._on_failure()
            raise MCPUnavailableError(f"MCP server unreachable: {exc}") from exc
        except (ValueError, Exception) as exc:
            self._on_failure()
            raise MCPUnavailableError(f"MCP server returned invalid JSON: {exc}") from exc

        self._on_success()
        if "error" in body:
            err = body["error"]
            raise RuntimeError(f"MCP error {err.get('code')}: {err.get('message')}")
        return body.get("result")

    # ── public API ───────────────────────────────────────────────────────────

    async def initialize(self) -> dict[str, Any]:
        """Perform MCP handshake. Optional — tools/call works without it."""
        return await self._rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "local-llm-server", "version": "1.0.0"},
        })

    def invalidate_tools_cache(self) -> None:
        """Force the next ``list_tools()`` call to fetch a fresh tool list from the server.

        Use this after deploying a new tool to the MCP server so agents pick up
        the change without waiting for the TTL to expire.
        """
        self._tools_cache = None
        self._tools_cache_expires_at = 0.0
        log.debug("MCP tools-list cache invalidated")

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return the list of tools available on the MCP server.

        Implements tools/list TTL caching per MCP spec 2026-07-28 RC.  When the
        cached entry is still valid (``ttlMs`` not yet elapsed), the RPC is
        skipped and the cached result returned immediately.  The cache is per
        ``MCPClient`` instance; call ``invalidate_tools_cache()`` for a forced
        refresh.
        """
        now = time.monotonic()
        if self._tools_cache is not None and now < self._tools_cache_expires_at:
            log.debug("MCP tools-list cache hit (%.1fs remaining)", self._tools_cache_expires_at - now)
            return self._tools_cache

        result = await self._rpc("tools/list")
        tools = result.get("tools", [])

        # Honour the server-supplied TTL (milliseconds) or fall back to the default.
        ttl_ms = result.get("ttlMs")
        if isinstance(ttl_ms, (int, float)) and ttl_ms > 0:
            ttl_sec = ttl_ms / 1000.0
        else:
            ttl_sec = _DEFAULT_TOOLS_TTL_MS / 1000.0

        self._tools_cache = tools
        self._tools_cache_expires_at = now + ttl_sec
        log.debug("MCP tools-list cached for %.1fs (%d tools)", ttl_sec, len(tools))
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Call a tool and return the text content of the first content item."""
        result = await self._rpc("tools/call", {"name": name, "arguments": arguments})
        content = result.get("content", [])
        if content:
            text = content[0].get("text", "")
            is_error = result.get("isError", False)
            if is_error:
                raise RuntimeError(text)
            return text
        return json.dumps(result, default=str)

    async def call_tool_structured(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> MCPToolResult:
        """Call a tool and return an ``MCPToolResult`` with both text and structured data.

        Implements MCP spec 2025-11-25: when the server includes a
        ``structuredContent`` field in the response the typed dict is extracted
        and exposed via ``MCPToolResult.structured``.  The text content is always
        extracted for backward compatibility.

        Raises ``RuntimeError`` on tool errors (``isError: true``), same as
        ``call_tool()``.  Raises ``MCPUnavailableError`` if the server is
        unreachable.
        """
        raw = await self._rpc("tools/call", {"name": name, "arguments": arguments})
        is_error = bool(raw.get("isError", False))

        # ── Text content (backward compat) ────────────────────────────────────
        content = raw.get("content", [])
        if content and isinstance(content[0], dict):
            text = content[0].get("text", "")
        else:
            text = json.dumps(raw, default=str)

        if is_error:
            raise RuntimeError(text)

        # ── Structured content (MCP spec 2025-11-25) ─────────────────────────
        structured: dict[str, Any] | None = raw.get("structuredContent") or None
        if structured is not None and not isinstance(structured, dict):
            log.debug("MCP structuredContent is not a dict — discarding (got %s)", type(structured))
            structured = None

        return MCPToolResult(text=text, structured=structured, is_error=False)

    async def health(self) -> bool:
        """Return True if the MCP server is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False


# Module-level singleton — created lazily when MCP_SERVER_BASE_URL is set.
_client: MCPClient | None = None


def get_mcp_client(base_url: str | None = None) -> MCPClient:
    """Return the module-level MCPClient.

    Reads MCP_SERVER_BASE_URL at call time (not import time) so env vars set
    after module load are honoured.  When neither argument nor env var is set,
    constructs a localhost URL using PORT (default 8001) since the MCP server
    is mounted in-process at /mcp-internal on the same port as the main app.
    """
    global _client
    explicit = base_url or os.environ.get("MCP_SERVER_BASE_URL")
    if not explicit:
        port = os.environ.get("PORT", "8001")
        explicit = f"http://127.0.0.1:{port}/mcp-internal"
    url = explicit
    if _client is None or _client.base_url != url.rstrip("/"):
        _client = MCPClient(url)
    return _client
