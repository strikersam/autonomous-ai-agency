# Render MCP — autonomous platform debugging and environment monitoring

The agency runs on Render, but until this integration nothing inside the process
could see the *platform* view of itself.

`agent/log_monitor.py` — the front of the self-heal chain — works by attaching a
`logging.Handler` to the root logger. That means it can only ever observe
failures that a **running Python process wrote to a log**. Everything the
platform does around the process is invisible to it:

| Failure | Seen by `log_monitor.py`? |
|---|---|
| An unhandled exception in a request handler | Yes |
| A build that failed, so no container ever started | No — nothing was running to log |
| An OOM kill | No — the process was killed, not notified |
| A restart loop | No |
| Memory or CPU pinned at the plan ceiling | No |
| A deploy stuck in `build_in_progress` | No |
| Edge 5xx served before any handler ran | No |

Six of those seven rows are exactly the failures that take production down
hardest, and the self-heal loop was blind to all of them. The
[Render MCP server](https://github.com/render-oss/render-mcp-server) exposes that
missing view as MCP tools; this integration consumes it.

## Two consumers, two transports

The Render MCP server supports both MCP transports, and this repo uses each one
where it fits.

### 1. Coding sessions — stdio, via `.mcp.json`

`.mcp.json` at the repo root registers the server for any MCP-aware harness
working in this repository (Claude Code, Codex, Cursor, …). It runs the upstream
container over stdio:

```json
{
  "mcpServers": {
    "render": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "-e", "RENDER_API_KEY",
               "ghcr.io/render-oss/render-mcp-server:latest"],
      "env": { "RENDER_API_KEY": "${RENDER_API_KEY}" }
    }
  }
}
```

Export `RENDER_API_KEY` (Render dashboard → Account Settings → API Keys) before
starting the session. With it set, an agent debugging a production issue can
read deploy history and platform logs directly instead of asking a human to
paste them.

### 2. The running agency — Streamable HTTP

The backend is a long-lived async service, not a per-session subprocess host, so
it does **not** use stdio. `packages/integrations/render_mcp.py` speaks MCP
JSON-RPC over Streamable HTTP to `RENDER_MCP_URL`, authenticating with
`Authorization: Bearer $RENDER_API_KEY`.

The default URL assumes you run the upstream server yourself in HTTP mode —
`render-mcp-server -t http` binds `:10000` and serves `/mcp`. Point
`RENDER_MCP_URL` elsewhere to use a different endpoint.

## Configuration

All settings live in `packages/config/settings.py` (the only module that reads
environment variables) and are declared in `render.yaml`.

| Variable | Default | Purpose |
|---|---|---|
| `RENDER_API_KEY` | *(unset)* | Render API key. Nothing works without it. |
| `RENDER_MCP_URL` | `http://127.0.0.1:10000/mcp` | Streamable-HTTP endpoint of a Render MCP server |
| `RENDER_WORKSPACE_ID` | *(unset)* | Workspace (owner) ID, passed explicitly on every resource call |
| `RENDER_SERVICE_IDS` | *(unset)* | Comma-separated services to watch. Empty = discover all |
| `RENDER_OPS_ENABLED` | `false` | Master switch for the autonomous monitoring loop |
| `RENDER_OPS_INTERVAL_SECONDS` | `900` | Poll interval (floored at 60s) |
| `RENDER_MCP_ALLOW_WRITES` | `false` | Permit mutating Render tools |

`RENDER_OPS_ENABLED` is only honoured when `RENDER_API_KEY` is also set — an
enabled loop with no credentials would fail every tick, so the two conditions are
combined in `settings.is_render_ops_enabled` rather than rediscovered at each
call site.

Upstream deprecated implicit session-scoped workspace selection, so
`RENDER_WORKSPACE_ID` is passed as `workspaceId` on every workspace-scoped tool
call when it is known.

## The monitoring loop

`services/render_ops.py` runs as an autonomy daemon alongside `LogMonitor` and
`SelfHealingAgent` (registered in `services/background.py`, catalogued in
`loops/registry.yaml` as `render-ops-monitor`). Each tick it checks every watched
service and emits findings:

| Finding | Trigger | Severity |
|---|---|---|
| `deploy_failed` | Latest deploy is `build_failed` / `update_failed` / `pre_deploy_failed` / `canceled` / `deactivated` | critical |
| `deploy_stalled` | A deploy has been in progress > 30 minutes | high |
| `error_logs` | More than 10 platform ERROR lines in the last 30 minutes | high |
| `memory_pressure` | Memory usage above 90% of the plan limit | medium |

Findings are filed through `ImprovementLoop.register_external_issue` — the
**same** intake the log monitor and GitHub issue triage already use — so they
flow into the existing plan→execute→verify machinery rather than into a second,
parallel issue pipeline.

Dedup is by `sha256(kind + service_id + discriminator)` with a 6-hour cooldown,
so a deploy that keeps failing for one commit is one issue, and a sustained
error spike files once per hour rather than once per tick.

The loop never raises. Render being unreachable is recorded in `last_error` and
surfaced through `GET /api/render/ops/status`; a monitor that dies on an
unreachable dependency stops monitoring exactly when it matters most.

## Write safety

Reading production state is what autonomous debugging needs. Changing production
is a different privilege, and this integration keeps them apart in two layers:

1. **`RenderMCPClient` refuses mutating tools by default.** `trigger_deploy`,
   `update_environment_variables`, and every `create_*` raise
   `RenderWriteBlockedError` unless `RENDER_MCP_ALLOW_WRITES` is on. The gate is
   an explicit deny-list of tool names, not a heuristic, so a new upstream *read*
   tool is never accidentally blocked.
2. **The ops loop is read-only regardless of that flag.** It diagnoses; it does
   not redeploy or reconfigure. Nothing that runs on a timer should be able to
   restart production because a flag was left at its default.

`backend/render_router.py` exposes no write route at all — a test asserts the
router's method set is exactly `{"GET"}`. Mutating Render is reachable only from
Python, with the flag on, deliberately.

Note that `update_environment_variables` replaces the service's **complete**
variable list upstream; a partial list silently drops everything not included.

## HTTP API

All routes are admin-only. Render deploy history and platform logs describe the
whole deployment — including other tenants' service names in a shared workspace —
so they are not per-user data.

```
GET /api/render/health                     MCP reachability + tool count
GET /api/render/services                   services in the workspace
GET /api/render/services/{id}/deploys      deploy history, newest first
GET /api/render/services/{id}/logs         platform logs (?level=error&limit=50)
GET /api/render/services/{id}/metrics      metrics (?metrics=memory_usage,cpu_usage)
GET /api/render/ops/status                 loop counters, last tick, last error
GET /api/render/ops/scan                   run one scan now; reports without filing
```

`/ops/scan` answers "what does Render think is wrong right now?" without waiting
for the next tick and without adding to the issue backlog. Only the loop's
`tick()` files.

A transport failure returns **503**, not 500 — the dashboard needs to tell
"Render is unreachable, retry" apart from "this endpoint is broken".

## Transport notes

`agent/mcp_client.py` was extended rather than duplicated, so one client serves
both this repo's in-process server at `/mcp-internal` and third-party
Streamable-HTTP servers:

- Requests advertise `Accept: application/json, text/event-stream`. A
  Streamable-HTTP server may answer with either, and rejects requests that don't
  accept both; servers that only return JSON ignore the header.
- Responses are decoded from either media type. SSE frames that carry
  notifications are skipped; the frame carrying `result` or `error` is the
  response.
- A server-issued `Mcp-Session-Id` is captured and echoed on later requests.
- `rpc_path=""` lets a caller pass a URL that already names the endpoint, as
  Render's does. The default `"/mcp"` preserves existing behaviour.
- `RenderMCPClient` completes the handshake (`initialize` then
  `notifications/initialized`) once per instance, cached only on success.

## Enabling it

1. Create a Render API key: dashboard → Account Settings → API Keys.
2. Set `RENDER_API_KEY` in the Render dashboard (it is `sync: false` in
   `render.yaml`, so it is never committed).
3. Make an MCP endpoint reachable — run `render-mcp-server -t http` beside the
   service, or point `RENDER_MCP_URL` at another endpoint.
4. Set `RENDER_OPS_ENABLED=true`.
5. Confirm with `GET /api/render/health`, then `GET /api/render/ops/scan`.

Leave `RENDER_MCP_ALLOW_WRITES` at `false` unless you specifically intend the
agency to be able to change your deployment.
