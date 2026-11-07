"""Persistence for agent memory notes and episodes.

Uses the platform storage backend (``db.get_store()``: Mongo in production,
SQLite in dev) so memory survives redeploys; Render's local disk does not.
An instance built with ``db=None`` keeps everything in process memory, which
is what tests inject.
"""
from __future__ import annotations

import logging
from typing import Any

from services.agent_memory.models import Episode, MemoryNote

log = logging.getLogger("qwen-proxy")

NOTES = "agent_memory_notes"
EPISODES = "agent_memory_episodes"
_MAX_NOTES_PER_KEY = 400
_MAX_EPISODES_SCANNED = 200


class AgentMemoryStore:
    """Notes and episodes keyed by ``memory_key``."""

    def __init__(self, db: Any = None) -> None:
        self._db = db
        self._mem: dict[str, dict[str, dict]] = {NOTES: {}, EPISODES: {}}

    # ── notes ────────────────────────────────────────────────────────────
    async def list_notes(self, memory_key: str) -> list[MemoryNote]:
        docs = await self._find(NOTES, {"memory_key": memory_key}, _MAX_NOTES_PER_KEY)
        return [MemoryNote(**d) for d in docs]

    async def save_note(self, note: MemoryNote) -> None:
        await self._upsert(NOTES, "note_id", note.note_id, note.model_dump(mode="json"))

    async def delete_note(self, memory_key: str, note_id: str) -> bool:
        return await self._delete(NOTES, {"memory_key": memory_key, "note_id": note_id})

    # ── episodes ─────────────────────────────────────────────────────────
    async def add_episode(self, episode: Episode) -> None:
        await self._upsert(EPISODES, "episode_id", episode.episode_id, episode.model_dump(mode="json"))

    async def list_episodes(self, memory_key: str, *, undreamed_only: bool = False) -> list[Episode]:
        query: dict[str, Any] = {"memory_key": memory_key}
        if undreamed_only:
            query["dreamed"] = False
        docs = await self._find(EPISODES, query, _MAX_EPISODES_SCANNED)
        return [Episode(**d) for d in docs]

    async def mark_dreamed(self, episodes: list[Episode]) -> None:
        for ep in episodes:
            ep.dreamed = True
            await self.add_episode(ep)

    async def keys_with_undreamed(self) -> dict[str, int]:
        """memory_key → count of episodes not yet dreamed over."""
        docs = await self._find(EPISODES, {"dreamed": False}, 5000)
        counts: dict[str, int] = {}
        for d in docs:
            key = d.get("memory_key")
            if key:
                counts[key] = counts.get(key, 0) + 1
        return counts

    # ── backend plumbing ─────────────────────────────────────────────────
    async def _find(self, coll: str, query: dict, limit: int) -> list[dict]:
        if self._db is None:
            rows = [d for d in self._mem[coll].values() if all(d.get(k) == v for k, v in query.items())]
            rows.sort(key=lambda d: d.get("created_at", 0), reverse=True)
            return [dict(r) for r in rows[:limit]]
        cursor = self._db[coll].find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [{k: v for k, v in d.items() if k != "_id"} for d in docs]

    async def _upsert(self, coll: str, id_field: str, id_value: str, doc: dict) -> None:
        if self._db is None:
            self._mem[coll][id_value] = dict(doc)
            return
        await self._db[coll].update_one({id_field: id_value}, {"$set": doc}, upsert=True)

    async def _delete(self, coll: str, query: dict) -> bool:
        if self._db is None:
            for k, d in list(self._mem[coll].items()):
                if all(d.get(f) == v for f, v in query.items()):
                    del self._mem[coll][k]
                    return True
            return False
        result = await self._db[coll].delete_one(query)
        return bool(getattr(result, "deleted_count", 0))


_store: AgentMemoryStore | None = None


def get_agent_memory_store() -> AgentMemoryStore:
    """Process-wide store on the platform storage backend."""
    global _store
    if _store is None:
        from db import get_store

        _store = AgentMemoryStore(get_store())
    return _store
