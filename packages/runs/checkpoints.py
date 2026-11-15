"""packages/runs/checkpoints.py — the durable mirror of agent checkpoints.

``agent/checkpoint.py`` writes numbered JSON files on the local disk, which a
worker on another host (or a fresh Render instance) cannot see. Each new latest
checkpoint is also mirrored here, in the ``run_checkpoints`` collection of the
shared storage backend, one document per session holding the latest and the
previous checkpoint. ``load_latest`` is the fallback when the files are gone.

Every function is best effort: it logs and returns rather than raise, so a
storage outage never breaks the agent loop.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from packages.runs.backend import DocTable, MemoryTable, table_for

log = logging.getLogger("qwen-proxy")

RUN_CHECKPOINTS = "run_checkpoints"

_memory: dict[str, MemoryTable] = {}
_table: DocTable | None = None


def _checkpoints() -> DocTable:
    global _table
    if _table is None:
        from packages.runs.store import get_run_store

        _table = table_for(get_run_store()._db, RUN_CHECKPOINTS, _memory)
    return _table


def reset() -> None:
    """Forget the cached table (tests, or after the run store was replaced)."""
    global _table
    _table = None
    _memory.clear()


async def save(checkpoint: dict[str, Any], *, run_id: str | None = None) -> bool:
    """Mirror *checkpoint* (``Checkpoint.to_dict()``) as its session's latest. Never raises."""
    session_id = str(checkpoint.get("session_id") or "")
    if not session_id:
        return False
    try:
        table = _checkpoints()
        doc = {"session_id": session_id, "run_id": run_id, "latest": checkpoint,
               "previous": None, "updated_at": time.time()}
        if await table.insert_if_absent(session_id, doc):
            return True
        current = await table.get(session_id) or {}
        doc["previous"] = current.get("latest")
        return await table.compare_and_set(session_id, {}, doc)
    except Exception:
        log.warning("checkpoint mirror: could not save session %s", session_id, exc_info=True)
        return False


async def load_latest(session_id: str) -> list[dict[str, Any]]:
    """The mirrored checkpoints of *session_id*, newest first (empty when none). Never raises."""
    try:
        doc = await _checkpoints().get(session_id)
    except Exception:
        log.warning("checkpoint mirror: could not load session %s", session_id, exc_info=True)
        return []
    if not doc:
        return []
    return [c for c in (doc.get("latest"), doc.get("previous")) if isinstance(c, dict)]


async def clear(session_id: str) -> None:
    """Drop the mirrored checkpoints of *session_id* (the session completed). Never raises."""
    try:
        await _checkpoints().compare_and_set(session_id, {}, {"latest": None, "previous": None,
                                                               "updated_at": time.time()})
    except Exception:
        log.warning("checkpoint mirror: could not clear session %s", session_id, exc_info=True)
