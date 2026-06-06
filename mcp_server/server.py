"""mcp_server/server.py — MCP (Model Context Protocol) server (F2 roadmap item).

Exposes workspace and GitHub tools via JSON-RPC 2.0 over HTTP.

F2 enhancements: proxy capability tools so AI coding tools can orchestrate
  the proxy as an MCP tool — run agent tasks, query models, check health.

Endpoints:
  GET  /health             — liveness probe
  POST /mcp                — JSON-RPC 2.0 dispatch (all MCP methods)

MCP methods implemented:
  initialize               — handshake, returns server info + capabilities
  tools/list               — list all available tools with input schemas
  tools/call               — call a tool by name with arguments

Tools exposed:
  (Workspace) clone_repo, read_file, write_file, list_files, search_code,
              run_command, git_status, git_diff, git_create_branch,
              git_commit, git_push, delete_workspace
  (Proxy F2)  proxy_run_agent, proxy_list_models, proxy_check_health,
              proxy_model_stats
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from mcp_server.workspace import Workspace

log = logging.getLogger("mcp-server")

app = FastAPI(title="MCP Server", version="1.0.0")

_SECRET_TOKEN: str | None = os.environ.get("MCP_SECRET_TOKEN") or None


def _check_auth(request: Request) -> None:
    """Raise 401 if MCP_SECRET_TOKEN is set and the request doesn't present it."""
    if not _SECRET_TOKEN:
        return
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or auth[7:] != _SECRET_TOKEN:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Unauthorized")

# ── Tool registry ────────────────────────────────────────────────────────────

_TOOLS: list[dict[str, Any]] = [
    {
        "name": "clone_repo",
        "description": "Clone a GitHub repository into an isolated workspace. Returns workspace_id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Unique ID for this workspace (alphanum/dash/underscore, ≤128 chars)"},
                "repo_url": {"type": "string", "description": "HTTPS URL of the repository"},
                "branch": {"type": "string", "default": "main", "description": "Branch to clone"},
            },
            "required": ["workspace_id", "repo_url"],
        },
    },
    {
        "name": "read_file",
        "description": "Read a file from a workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "path": {"type": "string", "description": "Relative path within the workspace"},
            },
            "required": ["workspace_id", "path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write (create or overwrite) a file in a workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["workspace_id", "path", "content"],
        },
    },
    {
        "name": "list_files",
        "description": "List files in a workspace directory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "sub": {"type": "string", "default": ".", "description": "Subdirectory to list (relative)"},
                "limit": {"type": "integer", "default": 200},
            },
            "required": ["workspace_id"],
        },
    },
    {
        "name": "search_code",
        "description": "Search for a string across all files in a workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 30},
            },
            "required": ["workspace_id", "query"],
        },
    },
    {
        "name": "run_command",
        "description": "Run a shell command in the workspace. Returns stdout, stderr, exit_code.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "cmd": {"type": "string"},
                "timeout": {"type": "integer", "default": 60},
            },
            "required": ["workspace_id", "cmd"],
        },
    },
    {
        "name": "git_status",
        "description": "Return `git status --short` for a workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
            },
            "required": ["workspace_id"],
        },
    },
    {
        "name": "git_diff",
        "description": "Return `git diff HEAD` for a workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
            },
            "required": ["workspace_id"],
        },
    },
    {
        "name": "git_create_branch",
        "description": "Create and checkout a new git branch in a workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "branch_name": {"type": "string"},
            },
            "required": ["workspace_id", "branch_name"],
        },
    },
    {
        "name": "git_commit",
        "description": "Stage all changes (or specific paths) and commit in a workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "message": {"type": "string"},
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific files to stage. Omit to stage all.",
                },
            },
            "required": ["workspace_id", "message"],
        },
    },
    {
        "name": "git_push",
        "description": "Push the current branch to remote origin.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "branch": {"type": "string", "description": "Branch name (uses current branch if omitted)"},
            },
            "required": ["workspace_id"],
        },
    },
    {
        "name": "delete_workspace",
        "description": "Delete a workspace directory and all its contents.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
            },
            "required": ["workspace_id"],
        },
    },
    # ── F2: Proxy capability tools ────────────────────────────────────────
    {
        "name": "proxy_run_agent",
        "description": "Run an agent task on the proxy and return the result. The proxy orchestrates the plan→execute→verify loop.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "instruction": {"type": "string", "description": "Task description for the agent"},
                "model": {"type": "string", "description": "Model to use (defaults to qwen3-coder:30b)"},
                "max_steps": {"type": "integer", "default": 10, "description": "Maximum execution steps"},
            },
            "required": ["instruction"],
        },
    },
    {
        "name": "proxy_list_models",
        "description": "List all available models registered in the proxy's routing table.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "proxy_check_health",
        "description": "Check the health of the proxy and its dependencies (Ollama, MongoDB, etc.).",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "proxy_model_stats",
        "description": "Return per-model cost attribution and usage statistics.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Specific model to query (optional, all if omitted)"},
            },
        },
    },
]

_TOOL_MAP = {t["name"]: t for t in _TOOLS}


# ── Tool handlers ────────────────────────────────────────────────────────────

async def _handle_tool(name: str, arguments: dict[str, Any]) -> Any:
    ws_id: str = arguments.get("workspace_id", "")
    ws = Workspace(ws_id)

    if name == "clone_repo":
        repo_url = str(arguments.get("repo_url", ""))
        branch = str(arguments.get("branch", "main"))
        return await ws.clone(repo_url, branch)

    if name == "read_file":
        return ws.read_file(str(arguments.get("path", "")))

    if name == "write_file":
        return ws.write_file(
            str(arguments.get("path", "")),
            str(arguments.get("content", "")),
        )

    if name == "list_files":
        return ws.list_files(
            str(arguments.get("sub", ".")),
            int(arguments.get("limit", 200)),
        )

    if name == "search_code":
        return ws.search_code(
            str(arguments.get("query", "")),
            int(arguments.get("limit", 30)),
        )

    if name == "run_command":
        return await ws.run_command(
            str(arguments.get("cmd", "")),
            int(arguments.get("timeout", 60)),
        )

    if name == "git_status":
        return await ws.status()

    if name == "git_diff":
        return await ws.diff()

    if name == "git_create_branch":
        return await ws.create_branch(str(arguments.get("branch_name", "")))

    if name == "git_commit":
        return await ws.commit(
            str(arguments.get("message", "agent commit")),
            arguments.get("paths"),
        )

    if name == "git_push":
        return await ws.push(arguments.get("branch"))

    if name == "delete_workspace":
        ws.delete()
        return {"deleted": True, "workspace_id": ws_id}

    # ── F2: Proxy capability tools ──────────────────────────────────────
    if name == "proxy_run_agent":
        instruction = str(arguments.get("instruction", ""))
        model = str(arguments.get("model", "qwen3-coder:30b"))
        max_steps = int(arguments.get("max_steps", 10))
        try:
            import os as _os
            # Use WorkflowOrchestrator to avoid AgentRunner deprecation gate
            try:
                from services.workflow_orchestrator import (
                    WorkflowOrchestrator,
                    ExecutionRequest,
                )
                wfo = WorkflowOrchestrator()
                req = ExecutionRequest(
                    request=instruction,
                    auto_approve=True,
                    max_steps=max_steps,
                )
                wf_run = await wfo.execute(req)
                result = {
                    "goal": instruction[:200],
                    "summary": wf_run.summary.summary if wf_run.summary else "",
                    "applied_steps": len([s for s in (wf_run.plan.steps if wf_run.plan else []) if getattr(s, "id", 0) > 0]),
                    "changed_files": wf_run.execution.changed_files if wf_run.execution else [],
                }
            except Exception:
                # Fallback to AgentRunner if orchestrator unavailable
                from agent.loop import AgentRunner
                runner = AgentRunner(
                    ollama_base=_os.environ.get("OLLAMA_BASE", "http://localhost:11434"),
                    workspace_root=_os.getcwd(),
                )
                result = await runner.run(
                    instruction=instruction,
                    history=[],
                    requested_model=model,
                    auto_commit=False,
                    max_steps=max_steps,
                )
            return {
                "goal": result.get("goal", ""),
                "summary": result.get("summary", ""),
                "applied_steps": sum(1 for s in result.get("steps", []) if s.get("status") == "applied"),
                "changed_files": result.get("steps", []),
            }
        except Exception as exc:
            return {"error": f"Agent execution failed: {exc}"}

    if name == "proxy_list_models":
        try:
            from router.registry import get_registry
            reg = get_registry()
            return {
                "models": [
                    {
                        "name": cap.name,
                        "type": cap.type,
                        "context_window": cap.context_window,
                        "cost_tier": cap.cost_tier,
                        "strengths": cap.strengths,
                    }
                    for cap in reg.values()
                ]
            }
        except Exception as exc:
            return {"error": f"Model listing failed: {exc}"}

    if name == "proxy_check_health":
        try:
            from router.health import check_all_providers
            provider_health = await check_all_providers()
            return {
                "status": "ok" if all(provider_health.values()) else "degraded",
                "providers": provider_health,
            }
        except Exception as exc:
            return {"error": f"Health check failed: {exc}"}

    if name == "proxy_model_stats":
        try:
            from services.cost_attribution import get_cost_attributor
            attr = get_cost_attributor()
            report = attr.generate_report()
            target_model = arguments.get("model", "")
            if target_model:
                per_model = [m for m in report.per_model if m["model"] == target_model]
                return {"model": per_model[0] if per_model else None}
            return report.as_dict()
        except Exception as exc:
            return {"error": f"Cost stats failed: {exc}"}

    raise ValueError(f"Unknown tool: {name!r}")


# ── JSON-RPC helpers ─────────────────────────────────────────────────────────

def _ok(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "mcp-server"}


@app.post("/mcp")
async def mcp_dispatch(request: Request) -> JSONResponse:
    _check_auth(request)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(_err(None, -32700, "Parse error"), status_code=400)

    req_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params", {})

    log.debug("MCP %s id=%s", method, req_id)

    # ── initialize ───────────────────────────────────────────────────────
    if method == "initialize":
        return JSONResponse(_ok(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "local-llm-mcp-server", "version": "1.0.0"},
        }))

    # ── notifications/initialized (no response needed) ───────────────────
    if method == "notifications/initialized":
        return JSONResponse({"jsonrpc": "2.0"}, status_code=204)

    # ── tools/list ───────────────────────────────────────────────────────
    if method == "tools/list":
        return JSONResponse(_ok(req_id, {"tools": _TOOLS}))

    # ── tools/call ───────────────────────────────────────────────────────
    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        if tool_name not in _TOOL_MAP:
            return JSONResponse(_err(req_id, -32601, f"Tool not found: {tool_name}"))
        try:
            result = await _handle_tool(tool_name, arguments)
            text = result if isinstance(result, str) else json.dumps(result, default=str)
            return JSONResponse(_ok(req_id, {
                "content": [{"type": "text", "text": text}],
                "isError": False,
            }))
        except Exception as exc:
            # Log the full exception internally but never forward it to the caller:
            # exception messages may contain internal paths or stack-trace fragments.
            log.warning("tool %r failed: %s", tool_name, exc, exc_info=True)
            return JSONResponse(_ok(req_id, {
                "content": [{"type": "text", "text": "[tool error: internal error — check server logs]"}],
                "isError": True,
            }))

    # ── unknown method ───────────────────────────────────────────────────
    return JSONResponse(_err(req_id, -32601, f"Method not found: {method}"))


# ── Entrypoint (docker run) ──────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    port = int(os.environ.get("PORT", "8008"))
    uvicorn.run("mcp_server.server:app", host="0.0.0.0", port=port, reload=False)
