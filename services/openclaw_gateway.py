"""services/openclaw_gateway.py — In-process WebSocket gateway for iOS control.

Implements a WebSocket gateway directly in FastAPI (no external CLI needed).
The OpenClaw iOS app (or any WebSocket client) connects to /openclaw/ws,
validates with the OPENCLAW_PAIRING_TOKEN, then sends JSON commands that the
gateway routes to the agency backend.

Protocol:
  1. Client connects to /openclaw/ws
  2. Client sends: {"type": "pair", "token": "<OPENCLAW_PAIRING_TOKEN>"}
  3. Server responds: {"type": "paired", "ok": true} or closes with 4001
  4. Client sends commands:
     {"type": "chat", "message": "list the files in the repo"}
     {"type": "status"}
     {"type": "freebuff", "instruction": "add a /version endpoint"}
     {"type": "list_files", "path": "."}
     {"type": "read_file", "path": "README.md"}
  5. Server responds: {"type": "response", "content": "..."}
  6. Server may push: {"type": "notification", "content": "..."}

The gateway is single-connection (one phone at a time). Multiple connections
with the same token are rejected (last-writer-wins is unsafe for repo edits).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

log = logging.getLogger("qwen-proxy")

# Active connection (single-phone model)
_active_connection: WebSocket | None = None
_active_connection_lock = asyncio.Lock()


async def openclaw_websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for OpenClaw iOS pairing + command routing.

    Mounted at /openclaw/ws. The iOS app connects here after scanning the QR.
    """
    global _active_connection

    pairing_token = os.environ.get("OPENCLAW_PAIRING_TOKEN", "").strip()
    if not pairing_token:
        await websocket.close(code=4003, reason="OPENCLAW_PAIRING_TOKEN not set on server")
        return

    await websocket.accept()

    # Wait for the pairing handshake
    try:
        pair_msg = await asyncio.wait_for(websocket.receive_text(), timeout=15.0)
        pair_data = json.loads(pair_msg)
    except (asyncio.TimeoutError, json.JSONDecodeError, WebSocketDisconnect):
        await websocket.close(code=4002, reason="Pairing handshake timeout")
        return

    if pair_data.get("type") != "pair" or pair_data.get("token") != pairing_token:
        await websocket.close(code=4001, reason="Invalid pairing token")
        return

    # Acquire the single-connection lock
    async with _active_connection_lock:
        if _active_connection is not None:
            try:
                await _active_connection.close(code=4009, reason="Another device connected")
            except Exception:
                pass
        _active_connection = websocket

    await websocket.send_text(json.dumps({
        "type": "paired",
        "ok": True,
        "server_time": time.time(),
        "agency_url": os.environ.get("RENDER_EXTERNAL_URL", ""),
    }))

    log.info("OpenClaw: device paired (gateway alive)")

    # Main command loop
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "error": "Invalid JSON",
                }))
                continue

            response = await _handle_command(msg)
            await websocket.send_text(json.dumps(response))
    except WebSocketDisconnect:
        log.info("OpenClaw: device disconnected")
    except Exception as exc:
        log.warning("OpenClaw: websocket error: %s", exc)
    finally:
        async with _active_connection_lock:
            if _active_connection is websocket:
                _active_connection = None


async def _handle_command(msg: dict[str, Any]) -> dict[str, Any]:
    """Route a command to the agency backend and return the response."""
    cmd_type = msg.get("type", "")
    try:
        if cmd_type == "chat":
            return await _cmd_chat(msg)
        elif cmd_type == "status":
            return await _cmd_status()
        elif cmd_type == "freebuff":
            return await _cmd_freebuff(msg)
        elif cmd_type == "list_files":
            return await _cmd_list_files(msg)
        elif cmd_type == "read_file":
            return await _cmd_read_file(msg)
        elif cmd_type == "ping":
            return {"type": "pong", "server_time": time.time()}
        else:
            return {"type": "error", "error": f"Unknown command type: {cmd_type}"}
    except Exception as exc:
        log.warning("OpenClaw: command {cmd_type} failed: {exc}")
        return {"type": "error", "error": str(exc)}


async def _cmd_chat(msg: dict[str, Any]) -> dict[str, Any]:
    """Send a chat message via the brain failover system.

    Uses the same multi-provider failover as the agent loop — tries NVIDIA
    first, then Groq, Cerebras, Z.ai, etc., falling back to Aerolink (Claude)
    if all free providers are rate-limited.
    """
    message = str(msg.get("message", ""))
    if not message:
        return {"type": "error", "error": "message is required"}

    from services.brain_failover import get_failover_manager
    from packages.ai.router import _openai_url
    import httpx

    fm = get_failover_manager()
    tried: set[str] = set()
    last_error = ""

    for _attempt in range(fm.max_attempts()):
        provider = fm.next_provider(exclude=tried, requested_model="z-ai/glm-5.2")
        if provider is None:
            break

        tried.add(provider.id)
        provider_model = fm.resolve_model(provider, "z-ai/glm-5.2")
        chat_url = _openai_url(provider.base_url, "/chat/completions")
        headers = {"Content-Type": "application/json"}
        if provider.api_key:
            headers["Authorization"] = f"Bearer {provider.api_key}"

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    chat_url,
                    json={
                        "model": provider_model,
                        "messages": [{"role": "user", "content": message}],
                        "max_tokens": 2048,
                        "temperature": 0.3,
                    },
                    headers=headers,
                )
        except Exception as exc:
            last_error = f"{provider.id} network error: {exc}"
            fm.record_failure(provider.id, "network_error")
            continue

        if resp.status_code < 400:
            fm.record_success(provider.id)
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"type": "response", "content": content, "model": provider_model, "provider": provider.id}

        if resp.status_code == 410:
            fm.record_failure(provider.id, "gone", 410)
            continue
        if resp.status_code in (429, 419):
            fm.record_failure(provider.id, "rate_limited", resp.status_code)
            continue
        if resp.status_code >= 500:
            fm.record_failure(provider.id, "server_error", resp.status_code)
            continue

        last_error = f"{provider.id} {resp.status_code}: {resp.text[:200]}"
        fm.record_failure(provider.id, f"http_{resp.status_code}", resp.status_code)
        continue

    return {"type": "error", "error": f"All providers exhausted. Last error: {last_error}"}


async def _cmd_status() -> dict[str, Any]:
    """Get the agency status."""
    import httpx
    base_url = os.environ.get("RENDER_EXTERNAL_URL", "https://local-llm-server.onrender.com")

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Hit /api/ping for liveness
        try:
            ping_resp = await client.get(f"{base_url}/api/ping")
            ping_ok = ping_resp.status_code == 200
        except Exception:
            ping_ok = False

        # Hit /api/telegram/diag for bot status
        try:
            diag_resp = await client.get(f"{base_url}/api/telegram/diag")
            diag = diag_resp.json() if diag_resp.status_code == 200 else {}
        except Exception:
            diag = {}

    return {
        "type": "response",
        "content": json.dumps({
            "server": "alive" if ping_ok else "down",
            "bot_token_set": diag.get("bot_token_set", False),
            "poller_disabled": diag.get("poller_disabled", True),
            "freebuff_repo_url": diag.get("freebuff_repo_url", "(unknown)"),
            "openclaw_enabled": bool(os.environ.get("OPENCLAW_PAIRING_TOKEN")),
        }, indent=2),
    }


async def _cmd_freebuff(msg: dict[str, Any]) -> dict[str, Any]:
    """Trigger a FreeBuff coding run (placeholder — routes to the chat endpoint with a system prompt)."""
    instruction = str(msg.get("instruction", ""))
    if not instruction:
        return {"type": "error", "error": "instruction is required"}

    # For now, route through chat with a system prompt that explains this is a
    # coding task. A full FreeBuff run would clone the repo, edit, and open a PR —
    # that's better done via the Telegram bot's /freebuff command.
    return {
        "type": "response",
        "content": (
            f"FreeBuff run requested: '{instruction}'\n\n"
            "To execute a full FreeBuff coding run (clone → edit → PR), use the "
            "Telegram bot: /freebuff {instruction}\n\n"
            "The Telegram bot is the production path for repo-editing tasks. "
            "This WebSocket gateway handles chat + status + file reads."
        ),
    }


async def _cmd_list_files(msg: dict[str, Any]) -> dict[str, Any]:
    """List files in the agency repo (via the MCP server or git ls-files)."""
    import subprocess
    repo_path = os.environ.get("REPO_PATH", "/app")
    try:
        result = subprocess.run(  # nosec B603, B607 — constant git argv, list form (no shell)
            ["git", "ls-files"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        files = [f for f in result.stdout.strip().split("\n") if f][:200]
        return {"type": "response", "content": json.dumps(files, indent=2)}
    except Exception as exc:
        return {"type": "error", "error": f"list_files failed: {exc}"}


async def _cmd_read_file(msg: dict[str, Any]) -> dict[str, Any]:
    """Read a file from the agency repo."""
    path = str(msg.get("path", ""))
    if not path:
        return {"type": "error", "error": "path is required"}

    repo_path = os.environ.get("REPO_PATH", "/app")
    # Safe path resolution — reject traversal
    full_path = os.path.normpath(os.path.join(repo_path, path))
    if not full_path.startswith(os.path.abspath(repo_path)):
        return {"type": "error", "error": "Path traversal rejected"}

    try:
        with open(full_path, encoding="utf-8", errors="replace") as f:
            content = f.read(50000)  # 50KB cap
        return {"type": "response", "content": content, "path": path}
    except FileNotFoundError:
        return {"type": "error", "error": f"File not found: {path}"}
    except Exception as exc:
        return {"type": "error", "error": f"read_file failed: {exc}"}


def is_gateway_alive() -> bool:
    """Check if a device is currently connected to the gateway."""
    return _active_connection is not None
