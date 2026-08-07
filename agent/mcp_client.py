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

MCP spec 2025-11-05 §5.6.1 — tool annotations:

  - Tools may include an ``annotations`` object carrying behavioural hints:
    ``readOnlyHint`` (tool does not modify state), ``destructiveHint``
    (tool may irreversibly modify or delete), ``idempotentHint`` (safe to
    retry with the same arguments), ``openWorldHint`` (tool may interact
    with external services beyond the local environment).
  - ``get_tool_annotations(tools, name)`` extracts typed ``ToolAnnotations``
    for a named tool from a ``list_tools()`` result.
  - ``filter_safe_tools(tools)`` returns only tools where ``readOnlyHint``
    is ``True`` and ``destructiveHint`` is ``False`` — useful when the agent
    wants to explore without side-effects.

MCP spec 2026-07-28 RC — tools/list TTL caching:

  - Servers may include ``ttlMs`` in the ``tools/list`` response to signal
    that the tool list is stable for that duration.  ``list_tools()`` now
    caches the result and skips the RPC until the TTL expires, reducing
    round-trips for stable tool registries.
  - When the server does not supply ``ttlMs`` a conservative default of
    ``MCP_TOOLS_LIST_DEFAULT_TTL_MS`` (env, default 60 000 ms) is used.
  - Call ``invalidate_tools_cache()`` to force an immediate refresh (e.g.
    after deploying a new tool to the MCP server).

MCP spec 2025-03-26 — Streamable HTTP:

  - Requests advertise ``Accept: application/json, text/event-stream`` and the
    response is decoded from either media type, so the same client works
    against this repo's plain-JSON server at ``/mcp-internal`` *and* against
    third-party Streamable-HTTP servers such as the Render MCP server
    (``packages/integrations/render_mcp.py``).
  - A server-issued ``Mcp-Session-Id`` is captured and echoed on later
    requests; servers that don't use sessions never set it.
  - ``rpc_path`` controls the sub-path appended to ``base_url``. Pass ``""``
    when the URL already points at the JSON-RPC endpoint.

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

    # Tool annotations (MCP spec 2025-11-05 §5.6.1):
    annotations = get_tool_annotations(tools, "delete_file")
    if annotations.destructive_hint:
        ...  # require confirmation before calling
    safe = filter_safe_tools(tools)  # read-only, non-destructive tools only
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


@dataclass
class ToolAnnotations:
    """Typed representation of MCP tool annotations (spec 2025-11-05 §5.6.1).

    All hints default to ``None`` (unknown) when the server does not supply
    them, so callers can distinguish "definitely read-only" (True) from
    "unknown safety" (None) and handle each appropriately.

    Attributes:
        read_only_hint: Tool does not modify server state. Safe to call for
            information gathering without side-effects.
        destructive_hint: Tool may irreversibly modify or delete data.
            Callers should require explicit confirmation before calling.
        idempotent_hint: Calling with the same arguments multiple times has
            the same effect as calling once. Enables safe retry on transient
            errors without double-applying changes.
        open_world_hint: Tool may interact with external systems (HTTP calls,
            email, file system outside the workspace, etc.).
    """

    read_only_hint: bool | None = None
    destructive_hint: bool | None = None
    idempotent_hint: bool | None = None
    open_world_hint: bool | None = None

    @property
    def is_safe_to_explore(self) -> bool:
        """Return True only when the tool is definitively read-only and non-destructive.

        Both hints must be explicit: read_only_hint=True AND destructive_hint=False.
        An unknown (None) destructive hint is treated as potentially destructive —
        the conservative choice when safety cannot be confirmed.
        """
        return self.read_only_hint is True and self.destructive_hint is False


def get_tool_annotations(tools: list[dict[str, Any]], name: str) -> ToolAnnotations:
    """Extract ``ToolAnnotations`` for a named tool from a ``list_tools()`` result.

    Returns an all-``None`` ``ToolAnnotations`` when the tool is not found or
    carries no ``annotations`` field — callers receive "unknown" rather than an
    exception, matching the spec's intent that absent annotations mean unknown
    (not safe, not unsafe).
    """
    for tool in tools:
        if tool.get("name") == name:
            raw = tool.get("annotations") or {}
            return ToolAnnotations(
                read_only_hint=raw.get("readOnlyHint"),
                destructive_hint=raw.get("destructiveHint"),
                idempotent_hint=raw.get("idempotentHint"),
                open_world_hint=raw.get("openWorldHint"),
            )
    return ToolAnnotations()


def filter_safe_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return tools where ``readOnlyHint`` is True and ``destructiveHint`` is not True.

    Use this when the agent is exploring or gathering information and must not
    produce side-effects.  Tools with unknown annotations (``None``) are
    excluded — when safety is unknown the conservative choice is to skip them.
    """
    result = []
    for tool in tools:
        ann = get_tool_annotations(tools, tool.get("name", ""))
        if ann.is_safe_to_explore:
            result.append(tool)
    return result


class MCPClient:
    """Thin async MCP client with open/close circuit breaker.

    Thread-safe only within a single asyncio event loop (no cross-loop sharing).
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 30.0,
        secret_token: str | None = None,
        rpc_path: str = "/mcp",
    ) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.timeout = timeout
        self._secret_token = secret_token or os.environ.get("MCP_SECRET_TOKEN") or None
        self._id_counter = itertools.count(1)
        # Sub-path appended to ``base_url`` to reach the JSON-RPC endpoint.
        # Defaults to "/mcp" (the in-process server mounted at /mcp-internal).
        # Pass "" when ``base_url`` already points at the endpoint itself, as
        # it does for a Streamable-HTTP server whose URL ends in /mcp.
        self._rpc_path = rpc_path
        # Streamable-HTTP session id (MCP spec 2025-03-26). Servers that manage
        # sessions return ``Mcp-Session-Id`` on initialize and expect it echoed
        # on every later request; servers that don't simply never set it.
        self._session_id: str | None = None
        # Circuit breaker state
        self._failures = 0
        self._opened_at: float | None = None
        # Tools-list TTL cache (MCP spec 2026-07-28 RC)
        self._tools_cache: list[dict[str, Any]] | None = None
        self._tools_cache_expires_at: float = 0.0

    @property
    def endpoint(self) -> str:
        """Full URL of the JSON-RPC endpoint this client posts to."""
        return f"{self.base_url}{self._rpc_path}"

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

    def _headers(self) -> dict[str, str]:
        """Build the request headers shared by ``_rpc`` and ``notify``.

        ``Accept`` lists both media types because a Streamable-HTTP server
        (MCP spec 2025-03-26) may answer either with a plain JSON body or with
        a one-shot SSE stream, and rejects requests that don't accept both.
        Servers that only ever return JSON — including this repo's in-process
        server at /mcp-internal — ignore the header entirely.
        """
        headers = {"Accept": "application/json, text/event-stream"}
        if self._secret_token:
            headers["Authorization"] = f"Bearer {self._secret_token}"
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        headers.update(self._identity_headers())
        return headers

    def _identity_headers(self) -> dict[str, str]:
        """Propagate the calling agent's identity across the process boundary.

        The MCP server governs its own tool surface (threat-model T11), but it
        is a separate process and cannot see who is calling. Without these
        headers every MCP-executed action would be audited as
        ``agent:unknown`` — the action would still be *governed* (baseline
        rules apply regardless of identity) but it would not be *attributable*,
        which is half the point of the audit trail.

        These are a hint, not a credential: anyone holding ``MCP_SECRET_TOKEN``
        could send any values. That is fine, because the policy engine's
        baseline rules are evaluated before any group and cannot be loosened by
        one — a spoofed identity can move a caller between groups, never past
        the baseline. See ``mcp_server/governance.py``.

        Returns an empty dict when no identity is attached, which resolves
        server-side to the least-privileged default group.
        """
        identity = getattr(self, "_governance_identity", None)
        if identity is None:
            return {}
        mapping = {
            "X-Agent-Id": "agent_id",
            "X-Agent-Name": "display_name",
            "X-Agent-Owner": "owner",
            "X-Agent-Session": "session_id",
            "X-Agent-Task": "task_id",
            "X-Agent-Repo": "repo",
            "X-Agent-Branch": "branch",
        }
        headers: dict[str, str] = {}
        for header, attr in mapping.items():
            value = getattr(identity, attr, None)
            # Header values must be latin-1 encodable; an agent display name
            # with an em-dash would otherwise raise inside httpx and take out
            # the whole tool call for the sake of a label.
            if value:
                try:
                    text = str(value)
                    text.encode("latin-1")
                    headers[header] = text
                except (UnicodeEncodeError, TypeError):
                    continue
        return headers

    def attach_identity(self, identity: Any) -> None:
        """Attach the agent identity whose actions this client executes."""
        self._governance_identity = identity

    def _capture_session(self, resp: "httpx.Response") -> None:
        """Remember a server-issued ``Mcp-Session-Id`` for subsequent requests."""
        session_id = resp.headers.get("Mcp-Session-Id") or resp.headers.get("mcp-session-id")
        if session_id and session_id != self._session_id:
            self._session_id = session_id
            log.debug("MCP session established (%s…)", session_id[:8])

    @staticmethod
    def _parse_body(resp: "httpx.Response") -> dict[str, Any]:
        """Decode a JSON-RPC response body from either JSON or an SSE stream.

        Streamable-HTTP servers reply to a POST with ``text/event-stream`` and
        push the JSON-RPC response as one or more ``data:`` lines. The last
        frame carrying a JSON object with our ``jsonrpc`` envelope is the
        response; earlier frames may be progress notifications, which we skip.
        """
        content_type = (resp.headers.get("content-type") or "").lower()
        if "text/event-stream" not in content_type:
            return resp.json()

        result: dict[str, Any] | None = None
        buffer: list[str] = []

        def _flush() -> None:
            """Decode one complete event and keep it if it is our response."""
            nonlocal result, buffer
            chunk = "\n".join(buffer).strip()
            buffer = []
            if not chunk or chunk == "[DONE]":
                return
            try:
                frame = json.loads(chunk)
            except ValueError:
                return
            # Notifications carry no "id"; the response to our request does.
            if isinstance(frame, dict) and ("result" in frame or "error" in frame):
                result = frame

        # One SSE event may span several ``data:`` lines, which the receiver
        # joins with "\n" before decoding. Parsing each line on its own would
        # fail every json.loads for a response the server chose to split,
        # raising here and opening the circuit breaker — and Render's log and
        # metric payloads are exactly the large responses a server splits.
        # Accumulate until the blank line that terminates the event.
        for raw_line in resp.text.splitlines():
            line = raw_line.rstrip("\r")
            if not line:
                _flush()
                continue
            if line.startswith("data:"):
                buffer.append(line[len("data:"):].lstrip())
        _flush()  # a final event needs no trailing blank line

        if result is None:
            raise ValueError("SSE stream carried no JSON-RPC response frame")
        return result

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
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(self.endpoint, json=payload, headers=self._headers())
                resp.raise_for_status()
            self._capture_session(resp)
            body = self._parse_body(resp)
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

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        """Send a JSON-RPC notification (no ``id``, no response body expected).

        Used for the ``notifications/initialized`` handshake step that
        Streamable-HTTP servers expect before they will serve tool calls.
        Failures are swallowed: a notification the server ignores must not
        take down the caller, and the circuit breaker still records genuine
        transport failures via the next real RPC.
        """
        if not self.base_url:
            return
        payload = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(self.endpoint, json=payload, headers=self._headers())
            self._capture_session(resp)
            # A rejected handshake notification leaves the session degraded but
            # the caller proceeding, so the *next* tool call fails for a reason
            # nothing explains. Report the degraded state rather than hiding it
            # at DEBUG.
            if resp.status_code >= 400:
                log.warning(
                    "MCP notification %s rejected with HTTP %d (ignored)",
                    method, resp.status_code,
                )
        except Exception as exc:  # noqa: BLE001 - notifications are best-effort
            log.warning("MCP notification %s failed (ignored): %s", method, exc)

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
