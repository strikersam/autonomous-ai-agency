"""packages/knowledge/store.py — Knowledge store (short + long term memory).

Provides a unified interface for storing and retrieving knowledge:
  - Short-term: conversation context, current task state
  - Long-term: persistent knowledge across sessions

Inspired by Onyx (knowledge management, conversation memory) and
anywhere-agents (agent memory, knowledge synchronization), implemented
natively using the existing packages/storage/ architecture.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("knowledge.store")


@dataclass
class KnowledgeEntry:
    """A single piece of knowledge."""
    id: str
    content: str
    source: str = ""  # Where this knowledge came from
    agent_id: str = ""  # Which agent created it
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    access_count: int = 0
    quality_score: float = 0.5  # 0.0 - 1.0, updated by the reflector


class KnowledgeStore:
    """Unified knowledge store for all agents.

    Short-term memory lives in-process (fast, ephemeral).
    Long-term memory persists to the database (slow, durable).

    Every agent shares the same knowledge store — no agent has its own
    private memory. This enables knowledge synchronization and prevents
    duplicated knowledge.
    """

    def __init__(self) -> None:
        # Short-term: in-process dict
        self._short_term: dict[str, KnowledgeEntry] = {}
        # Long-term: delegated to the database
        self._long_term_cache: dict[str, KnowledgeEntry] = {}

    async def remember(
        self,
        content: str,
        *,
        source: str = "",
        agent_id: str = "",
        tags: list[str] | None = None,
        long_term: bool = False,
    ) -> str:
        """Store a piece of knowledge.

        Args:
            content: The knowledge text
            source: Where it came from (agent name, URL, etc.)
            agent_id: Which agent created it
            tags: Categorization tags
            long_term: If True, persists to DB; if False, stays in-process

        Returns:
            The knowledge entry ID
        """
        import secrets
        entry_id = f"know_{secrets.token_hex(6)}"
        entry = KnowledgeEntry(
            id=entry_id,
            content=content,
            source=source,
            agent_id=agent_id,
            tags=tags or [],
        )

        if long_term:
            await self._persist_long_term(entry)
            self._long_term_cache[entry_id] = entry
        else:
            self._short_term[entry_id] = entry

        log.info("Knowledge stored: id=%s, long_term=%s, tags=%s", entry_id, long_term, entry.tags)
        return entry_id

    async def recall(self, query: str, limit: int = 5) -> list[KnowledgeEntry]:
        """Retrieve relevant knowledge.

        Simple keyword matching for now — semantic search will be added
        in the next iteration using embeddings.

        Args:
            query: What to search for
            limit: Maximum results

        Returns:
            List of matching knowledge entries
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())

        results: list[tuple[float, KnowledgeEntry]] = []

        # Search short-term
        for entry in self._short_term.values():
            score = self._relevance_score(query_words, entry)
            if score > 0:
                results.append((score, entry))

        # Search long-term cache
        for entry in self._long_term_cache.values():
            score = self._relevance_score(query_words, entry)
            if score > 0:
                results.append((score, entry))

        # Sort by relevance + quality
        results.sort(key=lambda x: x[0] * x[1].quality_score, reverse=True)

        # Update access counts
        for _, entry in results[:limit]:
            entry.access_count += 1

        return [entry for _, entry in results[:limit]]

    async def forget(self, entry_id: str) -> bool:
        """Remove a piece of knowledge."""
        removed = self._short_term.pop(entry_id, None)
        if removed is None:
            removed = self._long_term_cache.pop(entry_id, None)
        if removed:
            log.info("Knowledge forgotten: id=%s", entry_id)
            return True
        return False

    async def prune(self, max_entries: int = 1000) -> int:
        """Remove low-quality, rarely-accessed knowledge.

        Keeps the most relevant + highest-quality entries.
        Returns the number of entries pruned.
        """
        all_entries = list(self._short_term.values()) + list(self._long_term_cache.values())
        if len(all_entries) <= max_entries:
            return 0

        # Sort by (access_count * quality_score) ascending — worst first
        all_entries.sort(key=lambda e: e.access_count * e.quality_score)

        to_prune = len(all_entries) - max_entries
        for entry in all_entries[:to_prune]:
            await self.forget(entry.id)

        log.info("Pruned %d knowledge entries", to_prune)
        return to_prune

    def _relevance_score(self, query_words: set[str], entry: KnowledgeEntry) -> float:
        """Calculate relevance of an entry to a query (simple keyword overlap)."""
        content_words = set(entry.content.lower().split())
        tag_words = set(t.lower() for t in entry.tags)
        all_words = content_words | tag_words

        overlap = len(query_words & all_words)
        if overlap == 0:
            return 0.0

        return overlap / len(query_words)

    async def _persist_long_term(self, entry: KnowledgeEntry) -> None:
        """Persist a knowledge entry to the database."""
        try:
            from db import get_store
            store = get_store()
            col = getattr(store, "knowledge", None)
            if col is not None:
                await col.insert_one(entry.__dict__)
        except Exception as exc:
            log.debug("Long-term persist failed (non-fatal): %s", exc)


# Singleton
_store: KnowledgeStore | None = None


def get_knowledge_store() -> KnowledgeStore:
    """Return the global knowledge store singleton."""
    global _store
    if _store is None:
        _store = KnowledgeStore()
    return _store
