"""Entry points the task paths call. Every function here is best-effort: memory
must never break or delay a task, so failures are logged and swallowed.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from packages.config.agent_memory import (
    agent_dream_enabled, agent_dream_interval_minutes, agent_dream_max_agents,
    agent_memory_enabled, agent_memory_index_lines, agent_memory_recall_k,
)
from services.agent_memory.capture import record_episode
from services.agent_memory.dream import LLM, dream_agent
from services.agent_memory.recall import build_memory_block
from services.agent_memory.store import AgentMemoryStore, get_agent_memory_store

log = logging.getLogger("qwen-proxy")

ROLE_PREFIX = "role:"
OWNER_SEP = "|"
_AGENCY_OWNER = "system"  # tasks the agency creates for itself (tasks/store.py)
_last_cycle_at: float | None = None
_cycle_task: asyncio.Task | None = None


def memory_key_for(
    agent_id: str | None = None, role: str | None = None, *,
    task_owner: str | None = None, agent_owner: str | None = None,
) -> str | None:
    """agent_id for an agency agent; ``role:<role>`` for a CEO specialist.

    Memory never crosses users: a public agent run by someone other than its
    owner gets ``<agent_id>|<task_owner>``, and a CEO specialist working a
    user's directive gets ``role:<role>|<task_owner>``. Only the agency's own
    (``system`` or owner-less) work shares the bare key.
    """
    if agent_id:
        if task_owner and agent_owner and task_owner not in (agent_owner, _AGENCY_OWNER):
            return f"{agent_id}{OWNER_SEP}{task_owner}"
        return agent_id
    if not role:
        return None
    if task_owner and task_owner != _AGENCY_OWNER:
        return f"{ROLE_PREFIX}{role}{OWNER_SEP}{task_owner}"
    return f"{ROLE_PREFIX}{role}"


async def _user_identities(identity: str) -> set[str]:
    """Every id a user is known by. Tasks record owners by ``_id``, agents by email.

    Uses the storage layer directly rather than ``backend.server``, whose import
    starts schedulers — wrong in a standalone worker process.
    """
    from db import get_store

    try:
        from bson import ObjectId

        id_filter = {"_id": ObjectId(identity)}
    except Exception:  # noqa: BLE001 - SQLite / non-ObjectId ids are plain strings
        id_filter = {"_id": identity}
    users = get_store().users
    doc = await users.find_one(id_filter) or await users.find_one({"email": identity})
    if not doc:
        return {identity}
    return {identity, str(doc.get("_id") or ""), str(doc.get("email") or "")} - {""}


async def resolve_memory_key(
    agent_id: str | None, *, task_owner: str | None, agent_owner: str | None,
) -> str | None:
    """``memory_key_for`` with the task owner matched to the agent owner across id forms.

    Without this an owner whose task carries their ``_id`` while the agent carries
    their email would be treated as a stranger. A failed lookup keeps the
    per-user key, which never shares memory.
    """
    if agent_id and task_owner and agent_owner and task_owner not in (agent_owner, _AGENCY_OWNER):
        try:
            if agent_owner in await _user_identities(task_owner):
                task_owner = agent_owner
        except Exception as exc:  # noqa: BLE001 - fall back to the isolated key
            log.debug("agent_memory: owner lookup failed for %s: %s", task_owner, exc)
    return memory_key_for(agent_id, task_owner=task_owner, agent_owner=agent_owner)


async def with_agent_memory(instruction: str, memory_key: str | None, query: str) -> str:
    """*instruction* followed by the agent's memory block; unchanged on any failure."""
    if not memory_key or not agent_memory_enabled():
        return instruction
    try:
        block = await build_memory_block(
            get_agent_memory_store(), memory_key, query,
            index_lines=agent_memory_index_lines(), recall_k=agent_memory_recall_k(),
        )
    except Exception as exc:  # noqa: BLE001 - memory never blocks a task
        log.warning("agent_memory: recall failed for %s: %s", memory_key, exc)
        return instruction
    return f"{instruction}\n\n{block}"


async def record_task_outcome(
    memory_key: str | None, *, task_id: str, title: str, success: bool,
    output: str, verdict: str | None = None,
) -> None:
    """Record the run as an episode and keep any REMEMBER notes it wrote."""
    if not memory_key or not agent_memory_enabled():
        return
    try:
        await record_episode(get_agent_memory_store(), memory_key, task_id=task_id, title=title,
                             success=success, output=output or "", verdict=verdict)
    except Exception as exc:  # noqa: BLE001 - memory never fails a task
        log.warning("agent_memory: capture failed for %s/%s: %s", memory_key, task_id, exc)


async def default_llm(system: str, user: str) -> str:
    """One router-backed completion with the judge-role model (CLAUDE.md rule 2)."""
    from agent.loop import _resolve_role_model
    from packages.ai.failover_client import failover_chat_completion

    payload = {
        "model": _resolve_role_model("judge"),
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "stream": False,
    }
    result = await failover_chat_completion(payload, timeout_sec=120.0)
    return result.text or ""


async def agent_context_for(memory_key: str) -> str:
    """Who this memory belongs to and what it is for — focuses dreaming on the agent's job."""
    if memory_key.startswith(ROLE_PREFIX):
        return f"CEO specialist role '{memory_key[len(ROLE_PREFIX):].split(OWNER_SEP, 1)[0]}'."
    try:
        from agents.store import get_agent_store

        agent = await get_agent_store().get(memory_key.split(OWNER_SEP, 1)[0], owner_id=None)
    except Exception:  # noqa: BLE001 - context is a nice-to-have
        agent = None
    if agent is None:
        return f"Agent {memory_key}."
    return (f"{agent.name} — {agent.role or 'agent'}. {agent.description}\n"
            f"Its instructions: {(agent.system_prompt or '')[:800]}")


async def dream_one(memory_key: str, *, store: AgentMemoryStore | None = None,
                    llm: LLM | None = None) -> dict[str, Any]:
    """Run one dreaming pass now for *memory_key*."""
    return await dream_agent(
        store or get_agent_memory_store(), memory_key, await agent_context_for(memory_key),
        llm=llm or default_llm, index_cap=agent_memory_index_lines(),
    )


async def run_dream_cycle(*, store: AgentMemoryStore | None = None,
                          llm: LLM | None = None) -> list[dict[str, Any]]:
    """Dream for the agents with the most new episodes, up to the per-cycle cap."""
    from packages.config.autonomy_limits import kill_switch_engaged

    if kill_switch_engaged() or not (agent_memory_enabled() and agent_dream_enabled()):
        return []
    store = store or get_agent_memory_store()
    pending = await store.keys_with_undreamed()
    ranked = sorted(pending, key=lambda k: -pending[k])[: agent_dream_max_agents()]
    results: list[dict[str, Any]] = []
    for key in ranked:
        try:
            results.append(await dream_one(key, store=store, llm=llm))
        except Exception as exc:  # noqa: BLE001 - one agent's failure must not stop the cycle
            log.warning("agent_memory: dream failed for %s: %s", key, exc)
            results.append({"memory_key": key, "status": "error"})
    if results:
        log.info("agent_memory: dream cycle finished for %d agent(s)", len(results))
    return results


def maybe_spawn_dream_cycle() -> bool:
    """Start a background dream cycle when the interval has elapsed. Cheap to call every poll."""
    global _last_cycle_at, _cycle_task
    if not (agent_memory_enabled() and agent_dream_enabled()):
        return False
    now = time.monotonic()
    if _cycle_task is not None and not _cycle_task.done():
        return False
    if _last_cycle_at is not None and now - _last_cycle_at < agent_dream_interval_minutes() * 60:
        return False
    try:
        _cycle_task = asyncio.get_running_loop().create_task(run_dream_cycle())
    except RuntimeError:  # no running loop — never let memory break the caller
        return False
    _last_cycle_at = now
    return True
