"""packages/config/mcp_protocol.py — single source of truth for the MCP handshake version.

Both `agent/mcp_client.py` (client `initialize()`) and `mcp_server/server.py`
(server `initialize` response) import this constant so the two sides of the
handshake can never drift apart independently.
"""
from __future__ import annotations

# Pinned to 2025-11-25 — the newest MCP spec revision this codebase's client
# and server actually implement (structured content, tool annotations) while
# still running the classic stateful `initialize`/`Mcp-Session-Id` handshake.
# The 2026-07-28 revision replaces that handshake with a stateless
# request/response core; adopting it is a breaking protocol change tracked
# separately (see CLAUDE.md rule 40) and is not reflected here.
MCP_PROTOCOL_VERSION = "2025-11-25"
