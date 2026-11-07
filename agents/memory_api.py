"""agents/memory_api.py — inspect and maintain an agent's memory.

Endpoints (all authenticated at include time with ``get_current_user``):
  GET    /api/agents/{agent_id}/memory              notes + recent episodes
  POST   /api/agents/{agent_id}/memory/dream        run a dreaming pass now
  DELETE /api/agents/{agent_id}/memory/{note_id}    forget one note

The agent's owner or an admin may use them. ``role:<role>`` memories (the CEO
dispatcher's specialists) belong to no user and are admin-only.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from agents.store import get_agent_store
from packages.auth.rbac import UserRole, audit, get_user_role
from services.agent_memory.models import Episode, MemoryNote
from services.agent_memory.service import ROLE_PREFIX, dream_one
from services.agent_memory.store import get_agent_memory_store

log = logging.getLogger("qwen-proxy")

agent_memory_router = APIRouter(prefix="/api/agents", tags=["agent-memory"])


class AgentMemoryView(BaseModel):
    memory_key: str
    notes: list[MemoryNote]
    episodes: list[Episode]
    undreamed_episodes: int


class DreamResult(BaseModel):
    memory_key: str
    status: str
    details: dict[str, Any] = {}


def _user(request: Request) -> Any:
    return getattr(request.state, "user", None) or {}


def _user_id(user: Any) -> str:
    if isinstance(user, dict):
        return str(user.get("email") or user.get("_id") or "unknown")
    return str(getattr(user, "email", None) or getattr(user, "_id", "unknown"))


async def _authorize(agent_id: str, request: Request) -> None:
    """404 unless the caller owns the agent or is an admin."""
    user = _user(request)
    is_admin = get_user_role(user) == UserRole.ADMIN
    if agent_id.startswith(ROLE_PREFIX):
        if not is_admin:
            raise HTTPException(status_code=404, detail="Agent not found.")
        return
    agent = await get_agent_store().get(agent_id, owner_id=None if is_admin else _user_id(user))
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found.")


@agent_memory_router.get("/{agent_id}/memory", response_model=AgentMemoryView)
async def get_agent_memory(agent_id: str, request: Request) -> AgentMemoryView:
    """The agent's notes (every layer and status) and its 20 most recent episodes."""
    await _authorize(agent_id, request)
    store = get_agent_memory_store()
    try:
        notes = await store.list_notes(agent_id)
        episodes = await store.list_episodes(agent_id)
    except Exception:
        log.exception("agent_memory: read failed for %s", agent_id)
        raise HTTPException(status_code=500, detail="Could not read agent memory.")
    return AgentMemoryView(memory_key=agent_id, notes=notes, episodes=episodes[:20],
                           undreamed_episodes=sum(1 for e in episodes if not e.dreamed))


@agent_memory_router.post("/{agent_id}/memory/dream", response_model=DreamResult)
async def dream_agent_memory(agent_id: str, request: Request) -> DreamResult:
    """Run one dreaming pass over this agent's memory now."""
    await _authorize(agent_id, request)
    try:
        result = await dream_one(agent_id)
    except Exception:
        log.exception("agent_memory: dream failed for %s", agent_id)
        raise HTTPException(status_code=502, detail="Dreaming failed; no model was available.")
    audit("agent.memory.dream", _user(request), resource="agent", resource_id=agent_id)
    details = {k: v for k, v in result.items() if k not in ("memory_key", "status")}
    return DreamResult(memory_key=agent_id, status=str(result.get("status")), details=details)


@agent_memory_router.delete("/{agent_id}/memory/{note_id}", status_code=204)
async def delete_agent_memory_note(agent_id: str, note_id: str, request: Request) -> None:
    """Forget one note (e.g. one the operator knows is wrong)."""
    await _authorize(agent_id, request)
    if not await get_agent_memory_store().delete_note(agent_id, note_id):
        raise HTTPException(status_code=404, detail="Note not found.")
    audit("agent.memory.delete", _user(request), resource="agent", resource_id=agent_id)
