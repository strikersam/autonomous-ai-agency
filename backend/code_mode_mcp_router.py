"""backend/code_mode_mcp_router.py — the agency as a Code Mode MCP server (phase 7).

    POST /api/code-mode/mcp — JSON-RPC 2.0 MCP endpoint (initialize, tools/list, tools/call)

Exposes the agency's whole HTTP API to an MCP client (Claude Code, Cursor,
Codex) through two tools, the way Cloudflare's API MCP server does:

* ``search(code)`` — a ``run_code`` program over ``agency.spec()``, a compact
  index of the agency's OpenAPI document (path, method, summary, parameters).
  The full document never enters the client's context; only what the program
  returns does.
* ``execute(code)`` — a program that may also call
  ``agency.request("GET", "/api/...", query={...})``.

The tool surface is fixed at two tools, however many endpoints exist. Programs
run in the same interpreter as ``run_code`` (never exec'd). Requests are made
in-process with the caller's own ``Authorization``/``Cookie`` headers, so a
program can reach exactly what its caller could reach directly, no more. Only
GET is allowed, only paths under ``/api/`` that the spec declares, never this
endpoint itself. Text results are capped at ~6,000 tokens like Cloudflare's.
Switched off with ``CODE_MODE_MCP_SERVER_ENABLED=false`` (404).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from agent.code_mode import CodeModeError, CodeModeLimits, run_code

log = logging.getLogger("qwen-proxy")

MCP_PATH = "/api/code-mode/mcp"
PROTOCOL_VERSION = "2025-11-25"
_RESULT_CHARS = 24_000  # ~6,000 tokens
_FORWARDED_HEADERS = ("authorization", "cookie")

_CODE_SCHEMA = {
    "type": "object",
    "properties": {"code": {"type": "string", "description": "A Python-subset program; assign the answer to `result`."}},
    "required": ["code"],
}
TOOLS = [
    {
        "name": "search",
        "description": (
            "Search the agency API. Write a small Python-subset program over agency.spec() "
            "(a list of {path, method, summary, parameters}) and assign what you need to `result`, "
            "e.g. result = [op for op in agency.spec() if 'task' in op['path']][:20]. "
            "No imports, def, lambda or while."
        ),
        "inputSchema": _CODE_SCHEMA,
        "annotations": {"readOnlyHint": True, "destructiveHint": False},
    },
    {
        "name": "execute",
        "description": (
            "Call the agency API from a Python-subset program. agency.request('GET', '/api/...', "
            "query={...}) returns the JSON body; agency.spec() is available too. GET only, with your "
            "own permissions. Return only what you need in `result`."
        ),
        "inputSchema": _CODE_SCHEMA,
        "annotations": {"readOnlyHint": True, "destructiveHint": False},
    },
]


class JsonRpcRequest(BaseModel):
    """One JSON-RPC 2.0 request."""

    jsonrpc: str = "2.0"
    id: Any = None
    method: str = Field(..., max_length=100)
    params: dict[str, Any] = Field(default_factory=dict)


class JsonRpcResponse(BaseModel):
    """One JSON-RPC 2.0 response."""

    jsonrpc: str = "2.0"
    id: Any = None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None


def server_enabled() -> bool:
    try:
        from packages.config import settings

        return settings.code_mode_mcp_server
    except Exception as exc:  # noqa: BLE001 - unreadable setting keeps the endpoint off
        log.debug("CODE_MODE_MCP_SERVER_ENABLED unreadable: %s", exc)
        return False


def compact_spec(document: dict[str, Any]) -> list[dict[str, Any]]:
    """The OpenAPI document as a short list a program can filter."""
    ops = []
    for path, item in (document.get("paths") or {}).items():
        if not isinstance(item, dict) or path.startswith(MCP_PATH):
            continue
        for method, op in item.items():
            if not isinstance(op, dict) or method not in ("get", "post", "put", "patch", "delete"):
                continue
            ops.append({
                "path": path,
                "method": method.upper(),
                "summary": str(op.get("summary") or "")[:160],
                "parameters": [p.get("name") for p in op.get("parameters") or [] if isinstance(p, dict)],
            })
    return ops


class AgencyNamespace:
    """``agency.spec()`` and, for execute, ``agency.request('GET', path, query=...)``."""

    def __init__(self, spec: list[dict[str, Any]], send: Callable[..., Any] | None) -> None:
        self._spec = spec
        self._get_paths = {op["path"] for op in spec if op["method"] == "GET"}
        self._send = send

    async def call(self, path: tuple[str, ...], args: list[Any], kwargs: dict[str, Any], interp: Any) -> Any:
        if path == ("spec",):
            return [dict(op) for op in self._spec]
        if path != ("request",) or self._send is None:
            raise CodeModeError("use agency.spec()" + (" or agency.request('GET', path, query={...})" if self._send else ""))
        method = str(args[0] if args else kwargs.get("method", "")).upper()
        target = str(args[1] if len(args) > 1 else kwargs.get("path", ""))
        query = kwargs.get("query") or {}
        if method != "GET":
            raise CodeModeError("only GET requests are allowed")
        if not isinstance(query, dict):
            raise CodeModeError("query must be a dict")
        if any(ch in target for ch in "%\\?#"):
            # Starlette decodes %2F after routing is matched here, so an encoded
            # slash would reach a route the spec check never saw (verifier on PR).
            raise CodeModeError("paths may not contain '%', '\\', '?' or '#'; pass values via query={...}")
        if not target.startswith("/api/") or target.startswith(MCP_PATH) or not _matches_spec(target, self._get_paths):
            raise CodeModeError(f"{target!r} is not a GET endpoint of the agency API (see agency.spec())")
        return await self._send(target, {str(k): str(v) for k, v in query.items()})


def _matches_spec(path: str, templates: set[str]) -> bool:
    """True when *path* fills one of the spec's path templates ('/api/tasks/{id}')."""
    parts = path.split("?")[0].strip("/").split("/")
    for template in templates:
        tparts = template.strip("/").split("/")
        if len(tparts) == len(parts) and all(t.startswith("{") or t == p for t, p in zip(tparts, parts)):
            return all(p not in ("", ".", "..") for p in parts)
    return False


def _load_app() -> Any:
    from backend.server import app

    return app


def _in_process_sender(request: Request) -> Callable[[str, dict[str, str]], Any]:
    """GET against this app in-process, with the caller's own credentials."""
    import httpx

    headers = {k: v for k, v in request.headers.items() if k.lower() in _FORWARDED_HEADERS}

    async def send(path: str, query: dict[str, str]) -> Any:
        transport = httpx.ASGITransport(app=_load_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://agency.internal", timeout=30.0) as client:
            resp = await client.get(path, params=query, headers=headers)
        try:
            body: Any = resp.json()
        except ValueError:
            body = resp.text[:5000]
        return body if resp.status_code < 400 else {"status": resp.status_code, "error": body}

    return send


async def _run_tool(name: str, code: str, request: Request) -> dict[str, Any]:
    spec = compact_spec(_load_app().openapi())
    sender = _in_process_sender(request) if name == "execute" else None

    async def no_tools(_name: str, _args: dict[str, Any]) -> Any:
        raise CodeModeError("only agency.* is available here")

    outcome = await run_code(code, no_tools, {}, CodeModeLimits(), namespaces={"agency": AgencyNamespace(spec, sender)})
    # render() bounds the serialised size first: an aliased result can be huge as text.
    text, truncated = outcome.render(_RESULT_CHARS)
    if truncated:
        text += "\n--- TRUNCATED ---"
        is_error = not outcome.ok
    else:
        is_error = not json.loads(text)["ok"]  # render() turns a too-large result into ok=false
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


async def _dispatch(rpc: JsonRpcRequest, request: Request) -> JsonRpcResponse:
    if rpc.method == "initialize":
        return JsonRpcResponse(id=rpc.id, result={
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "agency-code-mode", "version": "1.0.0"},
        })
    if rpc.method in ("notifications/initialized", "ping"):
        return JsonRpcResponse(id=rpc.id, result={})
    if rpc.method == "tools/list":
        return JsonRpcResponse(id=rpc.id, result={"tools": TOOLS})
    if rpc.method == "tools/call":
        name = str(rpc.params.get("name", ""))
        arguments = rpc.params.get("arguments") or {}
        if name not in ("search", "execute") or not isinstance(arguments, dict):
            return JsonRpcResponse(id=rpc.id, error={"code": -32602, "message": "expected name search|execute and an arguments object"})
        code = arguments.get("code", "")
        return JsonRpcResponse(id=rpc.id, result=await _run_tool(name, str(code), request))
    return JsonRpcResponse(id=rpc.id, error={"code": -32601, "message": f"method not found: {rpc.method}"})


def build_code_mode_mcp_router(get_current_user: Callable) -> APIRouter:
    """Build the router, bound to the app's auth dependency (avoids an import cycle)."""
    router = APIRouter(tags=["code-mode"])

    @router.post(MCP_PATH, response_model=JsonRpcResponse, response_model_exclude_none=True)
    async def code_mode_mcp(
        rpc: JsonRpcRequest, request: Request, user: dict = Depends(get_current_user),
    ) -> JsonRpcResponse:
        """MCP JSON-RPC: search/execute over the agency API with the caller's permissions."""
        if not server_enabled():
            raise HTTPException(status_code=404, detail="Not found")
        try:
            return await _dispatch(rpc, request)
        except Exception:
            log.exception("code mode MCP request failed")
            return JsonRpcResponse(id=rpc.id, error={"code": -32603, "message": "Internal error"})

    return router
