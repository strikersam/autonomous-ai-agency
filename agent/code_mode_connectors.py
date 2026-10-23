from __future__ import annotations

"""Code Mode phases 3-5: what a ``run_code`` program can reach beyond ``tools``.

Each class here is a *namespace*: a global the interpreter exposes to the
program (``tools`` discovery, ``mcp``, ``api``, ``snippets``). The interpreter
calls ``await ns.call(path, args, kwargs, interp)`` for ``ns.a.b(...)``; every
such call counts against the same per-program call budget as ``tools.*``.

All of it is read-only:

* **Discovery** (phase 3) — ``tools.search(query)`` ranks the tools this
  prompt offers; ``tools.describe(name)`` returns one tool's signature and
  text. With ``AGENT_CODE_MODE_COMPACT_CATALOG`` on, the prompt carries only a
  one-line tool index and the model pulls details on demand.
* **MCP** (phase 4) — ``mcp.<server>.<tool>(...)`` for configured MCP servers.
  Only tools whose annotations say read-only and non-destructive, or whose name
  starts with ``list_``/``get_`` and that are not marked destructive, are
  callable. Results pass ``redact_secrets`` before the program sees them.
* **OpenAPI** (phase 4) — ``api.<name>.search/describe/call`` for connectors in
  ``config/code_mode_openapi.yaml``. The spec is read host-side; only GET
  operations are callable; every URL passes ``unsafe_target_reason`` (rule 14)
  and redirects are refused; the token stays host-side.
* **Snippets** (phase 5) — ``snippets.list()`` / ``snippets.run(name, **args)``
  replays a saved program with the caller's remaining call and time budget.

Every external call goes through the caller-supplied ``governed`` callback, so
the governance gate sees ``mcp.render.list_services`` the way it sees a tool.
"""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field, replace
from typing import Any, Awaitable, Callable
from urllib.parse import quote, urlsplit

from agent.code_mode import CodeModeError

log = logging.getLogger("qwen-proxy")

Governed = Callable[[str, dict[str, Any], Callable[[], Awaitable[Any]]], Awaitable[Any]]

_ENTRY_RE = re.compile(r"^- ([a-z][a-z0-9_]*)\(([^)]*)\)(?::\s*(.*))?$")
_WORD_RE = re.compile(r"[a-z0-9]+")
_READ_PREFIXES = ("list_", "get_")
_MAX_RESULTS = 10
_SPEC_TTL_S = 3600.0
_MAX_RESPONSE_CHARS = 50_000


def _setting(name: str) -> bool:
    try:
        from packages.config import settings

        return bool(getattr(settings, name))
    except Exception as exc:  # noqa: BLE001 - unreadable setting keeps the feature off
        log.debug("code mode setting %s unreadable: %s", name, exc)
        return False


def redact(value: Any) -> Any:
    """Redact secret-shaped text anywhere in a JSON-like value."""
    from packages.security.redact import redact_secrets

    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    return value


def _rank(query: Any, entries: dict[str, str]) -> list[str]:
    """Names whose name+text share the most words with *query*."""
    words = set(_WORD_RE.findall(str(query).lower()))
    scored = []
    for name, text in entries.items():
        hay = set(_WORD_RE.findall(f"{name.replace('_', ' ')} {text}".lower()))
        score = len(words & hay) + (2 if str(query).lower() in name else 0)
        if score:
            scored.append((-score, name))
    return [name for _, name in sorted(scored)[:_MAX_RESULTS]]


# ── phase 3: discovery over this prompt's tools ─────────────────────────────


def tool_catalogue(prompt_text: str) -> dict[str, dict[str, str]]:
    """``- name(params): text`` lines (plus indented continuations) -> {name: {signature, description}}."""
    catalogue: dict[str, dict[str, str]] = {}
    current: str | None = None
    for line in prompt_text.splitlines():
        match = _ENTRY_RE.match(line)
        if match:
            name, params, text = match.groups()
            current = name if name not in catalogue else None
            if current:
                catalogue[name] = {"signature": f"{name}({params})", "description": (text or "").strip()}
        elif current and line.startswith("  ") and not line.lstrip().startswith("- "):
            catalogue[current]["description"] = f"{catalogue[current]['description']} {line.strip()}".strip()
        else:
            current = None
    return catalogue


@dataclass
class ToolsDiscovery:
    """``tools.search`` / ``tools.describe`` over the tools a program may call."""

    catalogue: dict[str, dict[str, str]]

    async def call(self, path: tuple[str, ...], args: list[Any], kwargs: dict[str, Any], interp: Any) -> Any:
        op = path[0] if len(path) == 1 else ""
        target = (args or [kwargs.get("query") or kwargs.get("name") or ""])[0]
        if op == "search":
            texts = {n: e["description"] for n, e in self.catalogue.items()}
            return [{"name": n, **self.catalogue[n]} for n in _rank(target, texts)]
        if op == "describe":
            entry = self.catalogue.get(str(target))
            if entry is None:
                raise CodeModeError(f"tools.describe: no callable tool named {target!r}")
            return {"name": target, **entry}
        raise CodeModeError("tools.<name>: only search(query) and describe(name) besides the listed tools")


def compact_prompt(prompt_text: str, callable_names: list[str]) -> str:
    """Swap the full tool catalogue for a one-line index (AGENT_CODE_MODE_COMPACT_CATALOG)."""
    start = prompt_text.find("Available tools:\n")
    end = prompt_text.find("Return ONLY a JSON object")
    if start < 0 or end < 0 or end <= start:
        return prompt_text
    index = (
        "Available tools:\n"
        "Call tools directly as JSON, or batch read-only ones with run_code(code).\n"
        f"Read-only tools: {', '.join(sorted(callable_names))}.\n"
        "Other tools: edit_file(path, old_string, new_string), finish(reason).\n"
        "Arguments: run_code with `result = tools.describe('<name>')`, or\n"
        "`result = tools.search('<what you need>')` to find a tool.\n\n"
    )
    return prompt_text[:start] + index + prompt_text[end:]


def compact_catalog_enabled() -> bool:
    return _setting("agent_code_mode_compact_catalog")


# ── phase 4: MCP servers ────────────────────────────────────────────────────


@dataclass
class McpServer:
    """One MCP server a program may read from."""

    name: str
    list_tools: Callable[[], Awaitable[list[dict[str, Any]]]]
    call_tool: Callable[[str, dict[str, Any]], Awaitable[Any]]
    _tools: list[dict[str, Any]] | None = None

    async def readable_tools(self) -> dict[str, dict[str, Any]]:
        if self._tools is None:
            self._tools = await self.list_tools()
        return {t["name"]: t for t in self._tools if isinstance(t, dict) and is_read_only_tool(t)}


def is_read_only_tool(tool: dict[str, Any]) -> bool:
    """Annotated read-only and non-destructive, or a list_/get_ tool not marked destructive."""
    ann = tool.get("annotations") or {}
    if ann.get("destructiveHint") is True:
        return False
    if ann.get("readOnlyHint") is True and ann.get("destructiveHint") is False:
        return True
    return str(tool.get("name", "")).startswith(_READ_PREFIXES) and ann.get("readOnlyHint") is not False


def default_mcp_servers() -> dict[str, McpServer]:
    """Configured MCP servers the backend can dial (Render today)."""
    servers: dict[str, McpServer] = {}
    try:
        from packages.config import settings

        if settings.render_api_key and settings.render_mcp_url:
            from packages.integrations.render_mcp import get_render_mcp

            client = get_render_mcp()
            servers["render"] = McpServer("render", client.list_tools, client.call)
    except Exception as exc:  # noqa: BLE001 - no connector beats a broken run
        log.debug("code mode: MCP connectors unavailable: %s", exc)
    return servers


@dataclass
class McpNamespace:
    """``mcp.<server>.<tool>(...)``, plus ``mcp.<server>.search`` / ``describe``."""

    servers: dict[str, McpServer]
    governed: Governed

    async def call(self, path: tuple[str, ...], args: list[Any], kwargs: dict[str, Any], interp: Any) -> Any:
        if len(path) != 2:
            raise CodeModeError("use mcp.<server>.<tool>(...)")
        server_name, op = path
        server = self.servers.get(server_name)
        if server is None:
            raise CodeModeError(f"no MCP server {server_name!r}; available: {', '.join(sorted(self.servers)) or '(none)'}")
        tools = await server.readable_tools()
        if op in ("search", "describe") and op not in tools:
            return self._discover(server_name, tools, op, args, kwargs)
        if op not in tools:
            raise CodeModeError(f"mcp.{server_name}.{op} is not a read-only tool on that server")
        if args:
            raise CodeModeError(f"mcp.{server_name}.{op} takes keyword arguments only")
        label = f"mcp.{server_name}.{op}"
        result = await self.governed(label, kwargs, lambda: server.call_tool(op, kwargs))
        return redact(result)

    @staticmethod
    def _discover(server: str, tools: dict[str, dict[str, Any]], op: str, args: list[Any], kwargs: dict[str, Any]) -> Any:
        target = (args or [kwargs.get("query") or kwargs.get("name") or ""])[0]
        if op == "search":
            texts = {n: str(t.get("description", "")) for n, t in tools.items()}
            return [{"name": n, "description": texts[n][:200]} for n in _rank(target, texts)]
        tool = tools.get(str(target))
        if tool is None:
            raise CodeModeError(f"mcp.{server}.describe: no read-only tool {target!r}")
        return {"name": target, "description": tool.get("description", ""), "input_schema": tool.get("inputSchema", {})}


# ── phase 4: OpenAPI connectors ─────────────────────────────────────────────


@dataclass
class OpenApiConnector:
    """One API described by an OpenAPI document; GET operations only."""

    spec: Any  # packages.config.code_mode_connectors.OpenApiConnectorSpec
    fetch_spec: Callable[[str], Awaitable[dict[str, Any]]]
    send: Callable[[str, dict[str, str], dict[str, str]], Awaitable[Any]]
    _ops: dict[str, dict[str, Any]] | None = None
    _loaded_at: float = 0.0

    async def operations(self) -> dict[str, dict[str, Any]]:
        if self._ops is None or time.monotonic() - self._loaded_at > _SPEC_TTL_S:
            self._ops = index_operations(await self.fetch_spec(self.spec.spec_url))
            self._loaded_at = time.monotonic()
        return self._ops


def index_operations(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """GET operations of an OpenAPI document keyed by operationId (or a derived id)."""
    ops: dict[str, dict[str, Any]] = {}
    for path, item in (document.get("paths") or {}).items():
        get = item.get("get") if isinstance(item, dict) else None
        if not isinstance(get, dict) or not isinstance(path, str):
            continue
        op_id = str(get.get("operationId") or "get_" + re.sub(r"[^a-z0-9]+", "_", path.lower()).strip("_"))
        params = [p for p in (item.get("parameters") or []) + (get.get("parameters") or []) if isinstance(p, dict)]
        ops[op_id] = {
            "path": path,
            "summary": str(get.get("summary") or get.get("description") or "")[:200],
            "parameters": [
                {"name": p.get("name"), "in": p.get("in"), "required": bool(p.get("required"))}
                for p in params if p.get("in") in ("path", "query")
            ],
        }
    return ops


def build_url(base_url: str, path: str, params: dict[str, Any], op: dict[str, Any]) -> tuple[str, dict[str, str]]:
    """Fill path parameters, keep declared query parameters, refuse anything else."""
    declared = {p["name"]: p["in"] for p in op["parameters"]}
    unknown = set(params) - set(declared)
    if unknown:
        raise CodeModeError(f"unknown parameter(s): {', '.join(sorted(unknown))}")
    missing = [p["name"] for p in op["parameters"] if p["required"] and p["name"] not in params]
    if missing:
        raise CodeModeError(f"missing required parameter(s): {', '.join(missing)}")
    filled = path
    for name, where in declared.items():
        if where == "path" and name in params:
            filled = filled.replace("{" + name + "}", quote(str(params[name]), safe=""))
    if "{" in filled:
        raise CodeModeError("a path parameter was not supplied")
    query = {k: str(v) for k, v in params.items() if declared.get(k) == "query"}
    return base_url + filled, query


@dataclass
class ApiNamespace:
    """``api.<name>.search(q)`` / ``describe(operation_id)`` / ``call(operation_id, **params)``."""

    connectors: dict[str, OpenApiConnector]
    governed: Governed

    async def call(self, path: tuple[str, ...], args: list[Any], kwargs: dict[str, Any], interp: Any) -> Any:
        if len(path) != 2 or path[1] not in ("search", "describe", "call"):
            raise CodeModeError("use api.<name>.search(query), .describe(operation_id) or .call(operation_id, **params)")
        name, op = path
        connector = self.connectors.get(name)
        if connector is None:
            raise CodeModeError(f"no API connector {name!r}; available: {', '.join(sorted(self.connectors)) or '(none)'}")
        ops = await connector.operations()
        target = str((args or [kwargs.pop("query", None) or kwargs.pop("operation_id", "")])[0])
        if op == "search":
            texts = {k: f"{v['path']} {v['summary']}" for k, v in ops.items()}
            return [{"operation_id": k, "path": ops[k]["path"], "summary": ops[k]["summary"]} for k in _rank(target, texts)]
        if target not in ops:
            raise CodeModeError(f"api.{name}: no GET operation {target!r}")
        if op == "describe":
            return {"operation_id": target, **ops[target]}
        url, query = build_url(connector.spec.base_url, ops[target]["path"], kwargs, ops[target])
        result = await self.governed(f"api.{name}.{target}", {"url": url, **query}, lambda: connector.send(url, query, {}))
        return redact(result)


async def _guarded_get(url: str, query: dict[str, str], headers: dict[str, str], allowed_host: str | None) -> Any:
    """One GET: SSRF-checked, no redirects, bounded body; JSON when it parses."""
    import httpx

    from agent.web_reach import unsafe_target_reason

    if allowed_host and urlsplit(url).hostname != allowed_host:
        raise CodeModeError("refused URL: host differs from the connector's base_url")
    reason = unsafe_target_reason(url)
    if reason:
        raise CodeModeError(f"refused URL: {reason}")
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=False) as client:
        resp = await client.get(url, params=query, headers=headers)
    if resp.is_redirect:
        raise CodeModeError("refused: the API answered with a redirect")
    text = resp.text[:_MAX_RESPONSE_CHARS]
    if resp.status_code >= 400:
        return {"status": resp.status_code, "error": text[:500]}
    try:
        return json.loads(text)
    except ValueError:
        return text


def openapi_connectors_from_config() -> dict[str, OpenApiConnector]:
    """Connectors declared in config/code_mode_openapi.yaml."""
    from packages.config.code_mode_connectors import connector_token, openapi_connectors

    out: dict[str, OpenApiConnector] = {}
    for spec in openapi_connectors():
        host = urlsplit(spec.base_url).hostname

        async def fetch(url: str) -> dict[str, Any]:
            doc = await _guarded_get(url, {}, {}, None)
            if not isinstance(doc, dict):
                raise CodeModeError("the OpenAPI document is not JSON")
            return doc

        async def send(url: str, query: dict[str, str], _h: dict[str, str], _spec=spec, _host=host) -> Any:
            token = connector_token(_spec)
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            return await _guarded_get(url, query, headers, _host)

        out[spec.name] = OpenApiConnector(spec, fetch, send)
    return out


# ── phase 5: saved snippets ─────────────────────────────────────────────────


@dataclass
class SnippetsNamespace:
    """``snippets.list()`` and ``snippets.run(name, **args)`` (the program sees ``args``)."""

    scope: str
    run_program: Callable[[str, dict[str, Any], Any], Awaitable[Any]]
    depth: int = 0

    async def call(self, path: tuple[str, ...], args: list[Any], kwargs: dict[str, Any], interp: Any) -> Any:
        from agent.code_mode_snippets import get_snippet_store

        store = get_snippet_store()
        if path == ("list",):
            return store.list(self.scope)
        if path != ("run",) or not args:
            raise CodeModeError("use snippets.list() or snippets.run('<name>', **args)")
        if self.depth >= 1:
            raise CodeModeError("a snippet cannot run another snippet")
        snippet = await store.get_async(self.scope, str(args[0]))
        if snippet is None:
            raise CodeModeError(f"no saved snippet {args[0]!r}; see snippets.list()")
        outcome = await self.run_program(snippet.code, dict(kwargs), interp)
        if not outcome.ok:
            raise CodeModeError(f"snippet {snippet.name!r} failed: {outcome.error}")
        return outcome.result


# ── assembly ────────────────────────────────────────────────────────────────


@dataclass
class ConnectorContext:
    """What a run needs to build its namespaces."""

    prompt_text: str
    callable_tools: dict[str, list[str]]
    call_tool: Callable[[str, dict[str, Any]], Awaitable[Any]]
    governed: Governed
    scope: str
    mcp_servers: dict[str, McpServer] | None = None
    api_connectors: dict[str, OpenApiConnector] | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def build_namespaces(ctx: ConnectorContext, depth: int = 0) -> dict[str, Any]:
    """The namespaces a program gets, each only while its live control is on."""
    catalogue = {n: e for n, e in tool_catalogue(ctx.prompt_text).items() if n in ctx.callable_tools}
    namespaces: dict[str, Any] = {"tools": ToolsDiscovery(catalogue)}
    if _setting("agent_code_mode_mcp"):
        servers = ctx.mcp_servers if ctx.mcp_servers is not None else default_mcp_servers()
        if servers:
            namespaces["mcp"] = McpNamespace(servers, ctx.governed)
    if _setting("agent_code_mode_openapi"):
        apis = ctx.api_connectors if ctx.api_connectors is not None else openapi_connectors_from_config()
        if apis:
            namespaces["api"] = ApiNamespace(apis, ctx.governed)
    if _setting("agent_code_mode_snippets"):
        namespaces["snippets"] = SnippetsNamespace(ctx.scope, _snippet_runner(ctx), depth)
    return namespaces


def _snippet_runner(ctx: ConnectorContext) -> Callable[[str, dict[str, Any], Any], Awaitable[Any]]:
    """Run a snippet with what is left of the caller's call and time budget."""
    from agent.code_mode import CodeModeLimits, run_code

    async def run(code: str, args: dict[str, Any], interp: Any) -> Any:
        limits = replace(
            CodeModeLimits(),
            max_tool_calls=max(interp.remaining_calls(), 0),
            timeout_s=max(interp.remaining_seconds(), 0.1),
        )
        outcome = await run_code(
            code, ctx.call_tool, ctx.callable_tools, limits,
            namespaces=build_namespaces(ctx, depth=1), initial_env={"args": args},
        )
        interp.calls.extend(f"snippet:{c}" for c in outcome.calls)
        return outcome

    return run


def namespace_prompt_lines() -> str:
    """Tool-prompt lines for the namespaces switched on (rule 19)."""
    lines = [
        "  Discover: tools.search('<need>') ranks tools; tools.describe('<name>') gives arguments.\n",
    ]
    if _setting("agent_code_mode_mcp") and default_mcp_servers():
        names = ", ".join(sorted(default_mcp_servers()))
        lines.append(f"  MCP (read-only): mcp.<server>.search('<need>'), mcp.<server>.<tool>(key=value); servers: {names}.\n")
    if _setting("agent_code_mode_openapi") and openapi_connectors_from_config():
        names = ", ".join(sorted(openapi_connectors_from_config()))
        lines.append(f"  APIs (GET only): api.<name>.search(q), .describe(op_id), .call(op_id, key=value); APIs: {names}.\n")
    if _setting("agent_code_mode_snippets"):
        lines.append("  Saved programs: snippets.list(), snippets.run('<name>', key=value) (the saved program reads them as `args`).\n")
    return "".join(lines)


def snippet_prompt_lines() -> str:
    """Advertise save_snippet only while snippets are on (rule 19)."""
    if not _setting("agent_code_mode_snippets"):
        return ""
    return (
        "- save_snippet(name, code, description=''): Save a run_code program that worked, to re-run later\n"
        "  with snippets.run(name, key=value). name: lowercase_with_underscores.\n"
    )
