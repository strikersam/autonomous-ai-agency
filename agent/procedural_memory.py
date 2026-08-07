"""agent/procedural_memory.py — Skill/Procedural Memory for the agent loop (★4).

Agents learn from their own successful steps.  After a step is verified as
passing, ``record_success`` stores the step description and the key action
taken.  Before planning a new task, ``retrieve_relevant`` finds stored patterns
that overlap the current task description and returns them as examples the
planner can draw on.

Storage is intentionally simple: a list of records keyed by a short TF-IDF-
style keyword score.  No vector DB, no external dependencies.  Records are held
in memory (fast) with optional durable persistence to the platform's
MongoDB/SQLite store so they survive process restarts.

Persistence is opt-in: pass ``store=None`` to disable it (useful in tests).
"""
from __future__ import annotations

import hashlib
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("agent.procedural_memory")

# Maximum records kept in memory.  Records beyond this are evicted (oldest first)
# to bound memory use in long-running processes.
MAX_RECORDS = 500

# Maximum number of records returned by a single retrieve call.
MAX_RETRIEVE = 5

# Minimum keyword-overlap score for a record to be included in results.
MIN_SCORE = 0.15


# ── helpers ──────────────────────────────────────────────────────────────────

def _tokenize(text: str) -> set[str]:
    """Case-fold and split text into word tokens, filtering short stopwords."""
    _STOP = frozenset({"a", "an", "the", "in", "on", "of", "to", "and", "or",
                       "is", "it", "be", "as", "at", "by", "for", "do"})
    tokens = set(re.findall(r"[a-z0-9_]+", text.lower()))
    return tokens - _STOP


def _overlap_score(query_tokens: set[str], record_tokens: set[str]) -> float:
    """Jaccard-style overlap normalised by query length to reward recall."""
    if not query_tokens or not record_tokens:
        return 0.0
    intersection = len(query_tokens & record_tokens)
    return intersection / len(query_tokens)


def _record_id(goal: str, step_description: str) -> str:
    digest = hashlib.sha1(f"{goal}|{step_description}".encode(), usedforsecurity=False).hexdigest()[:12]
    return f"pm_{digest}"


# ── core dataclass ────────────────────────────────────────────────────────────

@dataclass
class ProceduralRecord:
    """One stored skill pattern."""

    id: str
    goal_summary: str        # one-sentence goal the step belonged to
    step_description: str    # what the planner wanted this step to do
    action_summary: str      # concise description of what actually worked
    tokens: set[str] = field(default_factory=set, repr=False)
    created_at: float = field(default_factory=time.time)
    use_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "goal_summary": self.goal_summary,
            "step_description": self.step_description,
            "action_summary": self.action_summary,
            "created_at": self.created_at,
            "use_count": self.use_count,
        }


# ── store ─────────────────────────────────────────────────────────────────────

class ProceduralMemoryStore:
    """In-memory skill store with optional durable persistence.

    Thread-safe: a single ``threading.Lock`` guards all mutations.
    """

    def __init__(self, store: Any = None) -> None:
        self._records: list[ProceduralRecord] = []
        self._lock = threading.Lock()
        self._store = store  # optional platform storage backend
        self._loaded = False

    # ── write ─────────────────────────────────────────────────────────────────

    def record_success(
        self,
        *,
        goal_summary: str,
        step_description: str,
        action_summary: str,
    ) -> str:
        """Store a successful step pattern and return its record id.

        Duplicate step descriptions for the same goal are deduplicated so the
        store doesn't grow without bound during long runs.
        """
        rid = _record_id(goal_summary, step_description)
        combined_tokens = _tokenize(goal_summary) | _tokenize(step_description)
        rec = ProceduralRecord(
            id=rid,
            goal_summary=goal_summary,
            step_description=step_description,
            action_summary=action_summary,
            tokens=combined_tokens,
        )
        with self._lock:
            existing_ids = {r.id for r in self._records}
            if rid in existing_ids:
                return rid  # already recorded — skip
            self._records.append(rec)
            if len(self._records) > MAX_RECORDS:
                # Evict the oldest records first (list is roughly insertion-ordered)
                self._records = self._records[-MAX_RECORDS:]
        self._persist(rec)
        log.debug("procedural_memory: recorded %s (goal=%r)", rid, goal_summary[:60])
        return rid

    # ── read ──────────────────────────────────────────────────────────────────

    def retrieve_relevant(self, query: str, *, limit: int = MAX_RETRIEVE) -> list[dict[str, Any]]:
        """Return up to *limit* stored patterns relevant to *query*.

        Relevance is scored by keyword overlap between *query* and each
        record's (goal + step) token set.  Ties are broken by recency and
        use count (frequently-retrieved patterns rank higher).
        """
        self._maybe_load()
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []
        candidates: list[tuple[float, ProceduralRecord]] = []
        with self._lock:
            for rec in self._records:
                score = _overlap_score(query_tokens, rec.tokens)
                if score >= MIN_SCORE:
                    candidates.append((score, rec))
        candidates.sort(key=lambda t: (-t[0], -t[1].use_count, -t[1].created_at))
        results = []
        with self._lock:
            for _, rec in candidates[:min(limit, MAX_RETRIEVE)]:
                rec.use_count += 1
                results.append(rec.as_dict())
        return results

    def all_records(self) -> list[dict[str, Any]]:
        """Return all stored records (for admin/debug)."""
        with self._lock:
            return [r.as_dict() for r in self._records]

    def clear(self) -> int:
        """Remove all in-memory records.  Returns the count removed."""
        with self._lock:
            n = len(self._records)
            self._records.clear()
            self._loaded = False
            return n

    # ── persistence ───────────────────────────────────────────────────────────

    def _persist(self, rec: ProceduralRecord) -> None:
        if self._store is None:
            return
        try:
            self._store.upsert_one(
                "procedural_memories",
                {"_id": rec.id},
                {"$set": rec.as_dict()},
            )
        except Exception as exc:
            log.debug("procedural_memory: persist failed (non-fatal): %s", exc)

    def _maybe_load(self) -> None:
        if self._loaded or self._store is None:
            return
        try:
            docs = list(self._store.find("procedural_memories", {}, limit=MAX_RECORDS))
            with self._lock:
                if self._loaded:
                    return  # another thread won the race
                for doc in docs:
                    step_desc = doc.get("step_description", "")
                    goal = doc.get("goal_summary", "")
                    rec = ProceduralRecord(
                        id=doc.get("id", _record_id(goal, step_desc)),
                        goal_summary=goal,
                        step_description=step_desc,
                        action_summary=doc.get("action_summary", ""),
                        tokens=_tokenize(goal) | _tokenize(step_desc),
                        created_at=float(doc.get("created_at", 0)),
                        use_count=int(doc.get("use_count", 0)),
                    )
                    self._records.append(rec)
                self._loaded = True
        except Exception as exc:
            log.debug("procedural_memory: load failed (non-fatal): %s", exc)
            self._loaded = True  # don't retry on every read


# ── module-level singleton ────────────────────────────────────────────────────

_store: ProceduralMemoryStore | None = None
_store_lock = threading.Lock()


def get_procedural_memory(store: Any = None) -> ProceduralMemoryStore:
    """Return the process-wide ``ProceduralMemoryStore``, creating it if needed."""
    global _store
    with _store_lock:
        if _store is None:
            _store = ProceduralMemoryStore(store=store)
        elif store is not None and _store._store is None:
            _store._store = store
    return _store
