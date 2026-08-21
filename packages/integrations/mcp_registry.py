"""packages/integrations/mcp_registry.py — the one catalogue of MCP servers.

Before this module there were three unrelated ideas of "an MCP server" in the
repo, and none of them knew about the others:

  1. ``mcp_servers`` (Mongo/SQLite) — a per-user CRUD table behind
     ``/api/mcp/servers``, rendered by Providers → MCP. Purely descriptive:
     nothing ever read it, and its ``status``/``tools`` were values a human
     typed in, not measurements. When empty the dashboard substituted four
     hardcoded fakes (filesystem, github, postgres, brave-search) shown as
     "connected".
  2. ``MCP_SERVER_BASE_URL`` — the real in-process server at ``/mcp-internal``,
     invisible to that screen.
  3. ``RENDER_MCP_URL`` — the real Render client, also invisible to it.

So the screen showed servers that did not exist while omitting the ones that
did. This module is the single source of truth: every MCP server the platform
knows about is declared here once, its reachability is *measured* rather than
asserted, and both the dashboard and the agents read from it.

Adding a server means adding one ``MCPServerSpec`` below. Nothing else.

Health is measured, never assumed:

  * ``configured`` — the server's required settings are present.
  * ``reachable`` — an actual ``tools/list`` round-trip succeeded just now.
  * ``tool_count`` — how many tools it really advertised.

A server that is declared but unconfigured reports ``configured: False`` with
the reason, which is the honest state and the one an operator can act on.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from packages.config import settings

log = logging.getLogger("qwen-agent")

# How long a health probe may take before it is called unreachable. Short: this
# runs behind a dashboard request, and a hung MCP server must not hang the page.
HEALTH_TIMEOUT_SECONDS: float = 8.0


@dataclass
class MCPServerSpec:
    """A declared MCP server, independent of whether it is currently up.

    ``transport`` is informational for the UI; ``probe`` is what actually
    determines health, so a stdio server (which the backend cannot dial) simply
    reports why it is not measurable rather than pretending.
    """

    server_id: str
    name: str
    description: str
    category: str
    transport: str                      # "http" | "stdio" | "in-process"
    command: str = ""                   # display form: URL or argv
    requires: tuple[str, ...] = ()      # env/setting names an operator must set
    # False for servers the backend structurally cannot dial (stdio ones live
    # in a coding session, not in this process). Their "not reachable" is a
    # property of the transport, not a fault, so it must not render as an error.
    dialable: bool = True
    # True when an undialable server's capability is still served to agents by
    # another path in this process (github → agent/github_tools.py). Such a
    # server is genuinely usable, so it reports "available" (green) rather than
    # the muted "unavailable" a server with no alternate path would get.
    served_by_backend: bool = False
    # Returns (configured, reason). Kept a callable so it reads live settings
    # rather than whatever they were at import time.
    is_configured: Callable[[], tuple[bool, str]] = lambda: (True, "")
    # Optional async probe returning (reachable, tool_count, reason).
    probe: Callable[[], Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.server_id,
            "name": self.name,
            "desc": self.description,
            "category": self.category,
            "transport": self.transport,
            "cmd": self.command,
            "requires": list(self.requires),
        }


# ── probes ───────────────────────────────────────────────────────────────────

async def _probe_http(url: str, token: str | None, rpc_path: str = "") -> tuple[bool, int, str]:
    """Round-trip ``tools/list`` against a Streamable-HTTP MCP server."""
    from agent.mcp_client import MCPClient, MCPUnavailableError

    client = MCPClient(
        base_url=url, timeout=HEALTH_TIMEOUT_SECONDS, secret_token=token, rpc_path=rpc_path
    )
    try:
        await client.initialize()
        await client.notify("notifications/initialized")
        tools = await client.list_tools()
    except (MCPUnavailableError, RuntimeError) as exc:
        return False, 0, str(exc)
    return True, len(tools), ""


async def _probe_internal() -> tuple[bool, int, str]:
    """Probe this process's own MCP server mounted at /mcp-internal."""
    from agent.mcp_client import get_mcp_client, MCPUnavailableError

    client = get_mcp_client()
    try:
        tools = await client.list_tools()
    except (MCPUnavailableError, RuntimeError) as exc:
        return False, 0, str(exc)
    return True, len(tools), ""


async def _probe_render() -> tuple[bool, int, str]:
    """Probe the Render MCP server through the shared client."""
    from packages.integrations.render_mcp import get_render_mcp

    health = await get_render_mcp().health()
    if not health.get("reachable"):
        return False, 0, str(health.get("reason", "unreachable"))
    return True, int(health.get("tool_count", 0)), ""


def _not_dialable(reason: str) -> Callable[[], Any]:
    """Report a server the backend structurally cannot reach.

    These servers are real and useful — a stdio one runs inside a coding
    session via `.mcp.json` — but the long-lived backend is not a subprocess
    host. Pair this with ``dialable=False`` (and ``served_by_backend=True`` when
    the capability is reached another way) so the row renders with the reason —
    green ``available`` or muted ``unavailable`` — rather than as a red error an
    operator would waste time investigating.
    """
    async def _probe() -> tuple[bool, int, str]:
        return False, 0, reason
    return _probe


# ── configuration predicates ─────────────────────────────────────────────────

def _render_configured() -> tuple[bool, str]:
    if not settings.render_api_key:
        return False, "RENDER_API_KEY is not set"
    if not settings.render_mcp_url:
        return False, "RENDER_MCP_URL is not set"
    return True, ""


def _playwright_configured() -> tuple[bool, str]:
    # Name the fix, not just the missing variable — an operator reading this
    # row wants to know what to do next, and "X is not set" leaves them to
    # go and find that out somewhere else. Two ways to a working browser: the
    # low-RAM Browserbase path (recommended) or an external Playwright MCP.
    if not settings.playwright_mcp_url:
        return False, (
            "No browser configured — set BROWSER_AUTOMATION_ENABLED=true with a "
            "BROWSERBASE_API_KEY for the low-RAM cloud browser (recommended), or "
            "run `npx @playwright/mcp@latest --port 8931` somewhere reachable and "
            "set PLAYWRIGHT_MCP_URL to that /mcp URL"
        )
    return True, ""


def _playwright_spec() -> MCPServerSpec:
    """Build the browser-automation row from live settings.

    Three shapes, in priority order, so the dashboard tells the truth about
    how agents get a browser right now:

      1. ``PLAYWRIGHT_MCP_URL`` set → dial that external Playwright MCP server
         (green ``connected`` / red ``error``).
      2. else Browserbase configured + enabled → agents get a real browser
         in-process via ``agent/browser.py`` (low-RAM remote CDP). Undialable
         but genuinely served, so a green ``available``.
      3. else → ``unconfigured``, with a reason that names both fixes.
    """
    description = (
        "Drive a real browser: navigate, click, fill forms, and read the "
        "rendered page. Lets agents verify a deployed UI actually works and "
        "read JavaScript-rendered pages the plain fetch cannot."
    )
    if settings.playwright_mcp_url:
        return MCPServerSpec(
            server_id="playwright", name="playwright", description=description,
            category="browser", transport="http",
            command=settings.playwright_mcp_url,
            requires=("PLAYWRIGHT_MCP_URL",),
            is_configured=lambda: (True, ""),
            probe=lambda: _probe_http(settings.playwright_mcp_url, None),
        )
    if settings.browser_automation_enabled and settings.browserbase_configured:
        return MCPServerSpec(
            server_id="playwright", name="playwright", description=description,
            category="browser", transport="in-process",
            command="agent/browser.py → Browserbase (remote CDP)",
            requires=(),
            is_configured=lambda: (True, ""),
            dialable=False,
            served_by_backend=True,
            probe=_not_dialable(
                "browser served in-process by agent/browser.py via Browserbase "
                "(remote, low-RAM) — no external Playwright MCP server needed"
            ),
        )
    return MCPServerSpec(
        server_id="playwright", name="playwright", description=description,
        category="browser", transport="http",
        command="(PLAYWRIGHT_MCP_URL unset)",
        requires=("PLAYWRIGHT_MCP_URL",),
        is_configured=_playwright_configured,
        probe=lambda: _probe_http(settings.playwright_mcp_url, None),
    )


def _internal_configured() -> tuple[bool, str]:
    # The in-process server is mounted by backend/server.py at /mcp-internal
    # and needs no operator configuration.
    return True, ""


# ── the catalogue ────────────────────────────────────────────────────────────

def _specs() -> list[MCPServerSpec]:
    """Build the catalogue against current settings.

    A function, not a module constant, so tests and a running process both see
    configuration changes without reimporting.
    """
    return [
        MCPServerSpec(
            server_id="internal",
            name="workspace (in-process)",
            description=(
                "This platform's own MCP server: clone repos, read/write files, "
                "search code, run commands, and drive git. Agents use it for "
                "every code change."
            ),
            category="core",
            transport="in-process",
            command="mounted at /mcp-internal",
            is_configured=_internal_configured,
            probe=_probe_internal,
        ),
        MCPServerSpec(
            server_id="render",
            name="render",
            description=(
                "The platform Render runs on: services, deploys, platform logs, "
                "and metrics. Feeds the autonomous ops monitor that heals build "
                "failures, OOM kills, and restart loops."
            ),
            category="infrastructure",
            transport="http",
            command=settings.render_mcp_url or "(RENDER_MCP_URL unset)",
            requires=("RENDER_API_KEY", "RENDER_MCP_URL"),
            is_configured=_render_configured,
            probe=_probe_render,
        ),
        _playwright_spec(),
        MCPServerSpec(
            server_id="github",
            name="github",
            description=(
                "Issues, pull requests, commits, and Actions runs. The backend "
                "reaches GitHub through agent/github_tools.py rather than MCP, "
                "so this entry is for coding sessions via .mcp.json."
            ),
            category="vcs",
            transport="stdio",
            command="npx -y @modelcontextprotocol/server-github",
            requires=("GH_PAT",),
            is_configured=lambda: (
                (True, "") if settings.gh_pat else (False, "GH_PAT is not set")
            ),
            dialable=False,
            served_by_backend=True,
            probe=_not_dialable(
                "stdio transport — used by coding sessions via .mcp.json. The "
                "backend reaches GitHub through agent/github_tools.py instead, "
                "so nothing is broken here."
            ),
        ),
    ]


# ── status assembly ──────────────────────────────────────────────────────────

async def _status_for(spec: MCPServerSpec) -> dict[str, Any]:
    """Measure one server. Never raises — a probe failure is a status, not an error."""
    entry = spec.as_dict()
    configured, reason = spec.is_configured()
    entry["configured"] = configured
    entry["tools"] = 0
    entry["managed"] = True          # platform-declared, not a user CRUD row
    entry["editable"] = False        # the dashboard must not offer to delete it

    if not configured:
        entry["status"] = "unconfigured"
        entry["reason"] = reason
        return entry

    if spec.probe is None:
        entry["status"] = "idle"
        entry["reason"] = "no health probe defined"
        return entry

    try:
        reachable, tool_count, probe_reason = await asyncio.wait_for(
            spec.probe(), timeout=HEALTH_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        entry["status"] = "error"
        entry["reason"] = f"health probe timed out after {HEALTH_TIMEOUT_SECONDS:.0f}s"
        return entry
    except Exception as exc:  # noqa: BLE001 - a probe must never break the page
        entry["status"] = "error"
        entry["reason"] = str(exc)
        return entry

    if reachable:
        entry["status"] = "connected"
    elif not spec.dialable:
        # Configured, but the backend structurally cannot dial it (a stdio
        # server lives in a coding session, not in this long-lived process).
        # If its capability is served another way — github through
        # agent/github_tools.py — that is a working state, so report
        # "available" (green). Otherwise it is genuinely out of reach here:
        # "unavailable" (muted), still not a red fault.
        entry["status"] = "available" if spec.served_by_backend else "unavailable"
    else:
        # A server we expected to reach and could not is the only real fault.
        entry["status"] = "error"
    entry["tools"] = tool_count
    entry["reason"] = probe_reason
    return entry


async def status_all() -> list[dict[str, Any]]:
    """Measure every declared server concurrently and return dashboard rows.

    Probes run in parallel because they are independent network round-trips and
    the dashboard waits on all of them; serially, four servers would cost four
    timeouts on a bad day instead of one.
    """
    specs = _specs()
    results = await asyncio.gather(
        *(_status_for(s) for s in specs), return_exceptions=True
    )
    rows: list[dict[str, Any]] = []
    for spec, result in zip(specs, results):
        if isinstance(result, BaseException):
            log.warning("MCP registry: status for %s failed: %s", spec.server_id, result)
            row = spec.as_dict()
            row.update(
                {"status": "error", "reason": str(result), "tools": 0,
                 "configured": False, "managed": True, "editable": False}
            )
            rows.append(row)
        else:
            rows.append(result)
    return rows


def list_specs() -> list[dict[str, Any]]:
    """Return the catalogue without probing. Cheap; used by tests and docs."""
    return [s.as_dict() for s in _specs()]
