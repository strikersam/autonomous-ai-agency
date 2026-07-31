"""packages/integrations/render_mcp.py — Render platform access over MCP.

The agency is deployed on Render, but until now nothing inside the process
could see the *platform* view of itself. ``agent/log_monitor.py`` only ever
observes log records this Python process emitted, so everything that happens
around the process is invisible to it:

  * a build that failed and never produced a running container,
  * an OOM kill or a restart loop,
  * memory/CPU sitting at the plan ceiling,
  * a deploy that is stuck in ``build_in_progress``,
  * request-level 5xx that never reached a Python handler.

The Render MCP server (https://github.com/render-oss/render-mcp-server) exposes
exactly that view as MCP tools. This module is the agency's client for it.

Transport
---------
Talks MCP JSON-RPC over Streamable HTTP to ``settings.render_mcp_url``,
authenticating with ``Authorization: Bearer $RENDER_API_KEY``. Two ways to get
an endpoint:

  1. Run the upstream server yourself in HTTP mode — ``render-mcp-server -t
     http`` binds ``:10000`` and serves ``/mcp``. This is the default
     (``http://127.0.0.1:10000/mcp``).
  2. Point ``RENDER_MCP_URL`` at Render's hosted MCP endpoint.

The stdio transport (the default for desktop MCP clients, and what this repo's
``.mcp.json`` uses for coding sessions) is deliberately *not* used here: the
backend is a long-lived async service, not a per-session subprocess host.

Write safety
------------
Read tools are always available — that is what autonomous debugging needs.
Mutating tools (``trigger_deploy``, ``update_environment_variables``,
``create_*``) are refused unless ``RENDER_MCP_ALLOW_WRITES`` is on. A monitoring
loop must not be able to restart or reconfigure production because a flag was
left at its default.

Usage::

    client = get_render_mcp()
    if client.is_configured:
        services = await client.list_services()
        deploys = await client.list_deploys(service_id)
        errors = await client.list_logs([service_id], level=["error"], limit=50)
        metrics = await client.get_metrics(service_id, ["memory_usage"])
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, ClassVar

from agent.mcp_client import MCPClient, MCPUnavailableError
from packages.config import settings

log = logging.getLogger("qwen-agent")

# Tools that change state on Render. Gated behind RENDER_MCP_ALLOW_WRITES.
# Kept as an explicit allow-list of *denied* names rather than a heuristic on
# the tool name so a new upstream read tool is never accidentally blocked.
WRITE_TOOLS: frozenset[str] = frozenset(
    {
        "trigger_deploy",
        "update_environment_variables",
        "update_web_service",
        "update_static_site",
        "update_cron_job",
        "create_web_service",
        "create_static_site",
        "create_cron_job",
        "create_postgres",
        "create_key_value",
    }
)

# Resource tools that accept the optional ``workspaceId`` argument. Upstream
# deprecated implicit session-scoped workspace selection, so the workspace is
# passed explicitly on every one of these when it is configured.
_WORKSPACE_SCOPED_TOOLS: frozenset[str] = frozenset(
    {
        "list_services", "get_service",
        "list_deploys", "get_deploy", "trigger_deploy",
        "list_logs", "list_log_label_values",
        "get_metrics",
        "list_postgres_instances", "get_postgres", "query_render_postgres",
        "list_key_value", "get_key_value",
    }
    | WRITE_TOOLS
)


class RenderWriteBlockedError(RuntimeError):
    """Raised when a mutating Render tool is called with writes disabled."""


@dataclass
class RenderDeploy:
    """One deploy, normalised from whatever shape the tool returned."""

    deploy_id: str
    status: str
    commit: str = ""
    created_at: str = ""
    finished_at: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    # Render deploy statuses that mean "this deploy did not ship". ClassVar so
    # the dataclass treats it as a constant, not a seventh constructor field.
    FAILED_STATUSES: ClassVar[frozenset[str]] = frozenset(
        {"build_failed", "update_failed", "pre_deploy_failed", "canceled", "deactivated"}
    )

    @property
    def failed(self) -> bool:
        return self.status in self.FAILED_STATUSES

    @property
    def live(self) -> bool:
        return self.status == "live"

    def as_dict(self) -> dict[str, Any]:
        return {
            "deploy_id": self.deploy_id,
            "status": self.status,
            "commit": self.commit,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "failed": self.failed,
        }


def _coerce_payload(raw: Any) -> Any:
    """Return tool output as Python data.

    MCP tool results arrive either as ``structuredContent`` (already a dict) or
    as a text block that happens to contain JSON. Both are common across
    upstream tools, so both are handled here instead of at every call site.
    A payload that is neither is returned unchanged so the caller can still see
    what the server said.
    """
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("{") or text.startswith("["):
            try:
                return json.loads(text)
            except ValueError:
                return raw
    return raw


def _as_list(payload: Any, *keys: str) -> list[dict[str, Any]]:
    """Normalise a tool payload into a list of dicts.

    Upstream tools variously return a bare JSON array, or an object wrapping
    the array under a key such as ``services`` / ``deploys`` / ``logs``. Rather
    than pin one shape (which would silently return nothing the day upstream
    changes), try the known keys and fall back to the first list-valued field.
    """
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    for value in payload.values():
        if isinstance(value, list) and all(isinstance(i, dict) for i in value):
            return value
    return []


def _unwrap(item: dict[str, Any], *keys: str) -> dict[str, Any]:
    """Unwrap a nested envelope such as ``{"service": {...}}`` when present."""
    for key in keys:
        inner = item.get(key)
        if isinstance(inner, dict):
            return inner
    return item


class RenderMCPClient:
    """Typed facade over the Render MCP server's tools.

    Every method returns plain Python data and raises ``MCPUnavailableError``
    when Render cannot be reached, so callers can degrade instead of crashing.
    """

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        workspace_id: str | None = None,
        allow_writes: bool | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.url = (url if url is not None else settings.render_mcp_url).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.render_api_key
        self.workspace_id = (
            workspace_id if workspace_id is not None else settings.render_workspace_id
        )
        self.allow_writes = (
            allow_writes if allow_writes is not None else settings.is_render_mcp_write_allowed
        )
        # rpc_path="" because RENDER_MCP_URL already names the /mcp endpoint.
        self._client = MCPClient(
            base_url=self.url,
            timeout=timeout,
            secret_token=self.api_key or None,
            rpc_path="",
        )
        self._handshaked = False

    # ── plumbing ─────────────────────────────────────────────────────────────

    @property
    def is_configured(self) -> bool:
        """True when there is both an API key and an endpoint to reach."""
        return bool(self.api_key and self.url)

    async def _ensure_handshake(self) -> None:
        """Run the MCP handshake once per client instance.

        Streamable-HTTP servers create their session on ``initialize`` and
        expect ``notifications/initialized`` before serving tool calls. The
        result is cached so ordinary calls cost one round-trip, and a failed
        handshake is not cached — the next call retries it.
        """
        if self._handshaked:
            return
        await self._client.initialize()
        await self._client.notify("notifications/initialized")
        self._handshaked = True

    async def call(self, tool: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call a Render MCP tool and return its decoded payload.

        Raises ``RenderWriteBlockedError`` for mutating tools when writes are
        disabled, and ``MCPUnavailableError`` when Render is unreachable.
        """
        if not self.is_configured:
            raise MCPUnavailableError(
                "Render MCP is not configured — set RENDER_API_KEY (and "
                "RENDER_MCP_URL if you are not running render-mcp-server locally)"
            )
        if tool in WRITE_TOOLS and not self.allow_writes:
            raise RenderWriteBlockedError(
                f"Render MCP tool '{tool}' mutates production and is disabled. "
                "Set RENDER_MCP_ALLOW_WRITES=true to permit it."
            )

        args = dict(arguments or {})
        if self.workspace_id and tool in _WORKSPACE_SCOPED_TOOLS:
            args.setdefault("workspaceId", self.workspace_id)

        await self._ensure_handshake()
        result = await self._client.call_tool_structured(tool, args)
        return _coerce_payload(result.content)

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return the tool descriptors the connected Render MCP server offers."""
        if not self.is_configured:
            raise MCPUnavailableError("Render MCP is not configured — set RENDER_API_KEY")
        await self._ensure_handshake()
        return await self._client.list_tools()

    async def health(self) -> dict[str, Any]:
        """Report reachability without raising.

        Used by the ``/api/render/health`` endpoint and by the ops loop's
        preflight, both of which want a status object rather than an exception.
        """
        if not self.is_configured:
            return {"configured": False, "reachable": False, "reason": "RENDER_API_KEY not set"}
        try:
            tools = await self.list_tools()
        except (MCPUnavailableError, RuntimeError) as exc:
            return {"configured": True, "reachable": False, "reason": str(exc)}
        return {
            "configured": True,
            "reachable": True,
            "tool_count": len(tools),
            "url": self.url,
            "writes_allowed": self.allow_writes,
        }

    # ── workspaces ───────────────────────────────────────────────────────────

    async def list_workspaces(self) -> list[dict[str, Any]]:
        """List the Render workspaces this API key can see."""
        return _as_list(await self.call("list_workspaces"), "workspaces", "owners")

    # ── services ─────────────────────────────────────────────────────────────

    async def list_services(self, include_previews: bool = False) -> list[dict[str, Any]]:
        """List services in the workspace, unwrapping Render's ``{service: …}``."""
        payload = await self.call("list_services", {"includePreviews": include_previews})
        return [_unwrap(item, "service") for item in _as_list(payload, "services")]

    async def get_service(self, service_id: str) -> dict[str, Any]:
        """Fetch one service's full detail."""
        payload = await self.call("get_service", {"serviceId": service_id})
        return _unwrap(payload if isinstance(payload, dict) else {}, "service")

    async def resolve_service_ids(self) -> list[str]:
        """Return the service IDs the ops loop should watch.

        Prefers the explicit ``RENDER_SERVICE_IDS`` allow-list; when that is
        empty, discovers every service in the workspace. Discovery is the
        convenient default, but pinning the list is what keeps a shared
        workspace from turning one agency's monitor into everyone's.
        """
        configured = settings.render_service_id_list
        if configured:
            return configured
        return [s["id"] for s in await self.list_services() if isinstance(s.get("id"), str)]

    # ── deploys ──────────────────────────────────────────────────────────────

    async def list_deploys(self, service_id: str) -> list[RenderDeploy]:
        """List a service's deploy history, newest first as Render returns it."""
        payload = await self.call("list_deploys", {"serviceId": service_id})
        return [_to_deploy(_unwrap(item, "deploy")) for item in _as_list(payload, "deploys")]

    async def get_deploy(self, service_id: str, deploy_id: str) -> RenderDeploy:
        """Fetch one deploy by ID."""
        payload = await self.call(
            "get_deploy", {"serviceId": service_id, "deployId": deploy_id}
        )
        return _to_deploy(_unwrap(payload if isinstance(payload, dict) else {}, "deploy"))

    async def latest_deploy(self, service_id: str) -> RenderDeploy | None:
        """Return the most recent deploy, or ``None`` when there are none."""
        deploys = await self.list_deploys(service_id)
        return deploys[0] if deploys else None

    async def trigger_deploy(self, service_id: str, clear_cache: bool = False) -> Any:
        """Trigger a deploy. Blocked unless ``RENDER_MCP_ALLOW_WRITES`` is on."""
        return await self.call(
            "trigger_deploy", {"serviceId": service_id, "clearCache": clear_cache}
        )

    # ── logs ─────────────────────────────────────────────────────────────────

    async def list_logs(
        self,
        resources: list[str],
        *,
        level: list[str] | None = None,
        text: list[str] | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Query platform logs for one or more resources.

        ``resources`` is required by the upstream tool. ``level`` filters by
        severity (e.g. ``["error"]``), and times are RFC3339 strings.
        """
        args: dict[str, Any] = {"resource": resources, "limit": limit}
        if level:
            args["level"] = level
        if text:
            args["text"] = text
        if start_time:
            args["startTime"] = start_time
        if end_time:
            args["endTime"] = end_time
        return _as_list(await self.call("list_logs", args), "logs")

    # ── metrics ──────────────────────────────────────────────────────────────

    async def get_metrics(
        self,
        resource_id: str,
        metric_types: list[str],
        *,
        start_time: str | None = None,
        end_time: str | None = None,
        resolution: int | None = None,
    ) -> Any:
        """Fetch performance metrics for a service, Postgres, or key-value store.

        Metrics may legitimately come back empty when a metric does not apply
        to the resource type — upstream documents that, so an empty result is
        not treated as a failure.
        """
        args: dict[str, Any] = {"resourceId": resource_id, "metricTypes": metric_types}
        if start_time:
            args["startTime"] = start_time
        if end_time:
            args["endTime"] = end_time
        if resolution:
            args["resolution"] = resolution
        return await self.call("get_metrics", args)

    # ── environment ──────────────────────────────────────────────────────────

    async def update_environment_variables(
        self, service_id: str, env_vars: list[dict[str, str]]
    ) -> Any:
        """Replace a service's environment variables.

        Upstream replaces the *complete* list, so a partial list silently drops
        every variable not included. Blocked unless writes are enabled.
        """
        return await self.call(
            "update_environment_variables", {"serviceId": service_id, "envVars": env_vars}
        )


def _to_deploy(item: dict[str, Any]) -> RenderDeploy:
    """Build a ``RenderDeploy`` from an upstream deploy object."""
    commit = item.get("commit") or {}
    return RenderDeploy(
        deploy_id=str(item.get("id", "")),
        status=str(item.get("status", "")),
        commit=str(commit.get("id", "")) if isinstance(commit, dict) else str(commit),
        created_at=str(item.get("createdAt", "")),
        finished_at=str(item.get("finishedAt", "")),
        raw=item,
    )


# Module-level singleton, built lazily so env vars set after import are honoured.
_client: RenderMCPClient | None = None


def get_render_mcp() -> RenderMCPClient:
    """Return the shared ``RenderMCPClient``."""
    global _client
    if _client is None:
        _client = RenderMCPClient()
    return _client


def reset_render_mcp() -> None:
    """Drop the cached singleton. Used by tests and after a config change."""
    global _client
    _client = None
