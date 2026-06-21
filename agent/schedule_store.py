"""agent/schedule_store.py — durable persistence for scheduled agent jobs.

Fixes #505: ``AgentScheduler`` kept jobs in a plain in-memory dict, so every
company monitoring cadence was wiped on process restart / redeploy. This store
persists schedules to MongoDB (the same durable backend as companies/tasks) and
the scheduler rehydrates from it on boot.

Synchronous on purpose: APScheduler fires jobs from a background *thread* (no
event loop), and schedules are also mutated from async request handlers — a
sync pymongo client is safe from both without event-loop juggling. When Mongo is
unreachable it degrades to an in-memory dict so dev/test/offline still work
(non-durable, exactly the old behaviour, but never crashes the scheduler).
"""
from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger("qwen-proxy")

_MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
_DB_NAME = os.environ.get("DB_NAME", "llm_platform")
_SELECTION_TIMEOUT_MS = int(os.environ.get("MONGO_SELECTION_TIMEOUT_MS", "2000"))
_COLLECTION = "agent_schedules"


class ScheduleStore:
    """Durable schedule persistence. Mongo-backed with in-memory fallback.

    All methods are best-effort and never raise: a storage outage must never
    take down the scheduler (jobs keep running in-memory; they just won't
    survive the next restart, which is no worse than the pre-fix behaviour).
    """

    def __init__(self, *, mongo_url: str | None = None, db_name: str | None = None) -> None:
        self._mem: dict[str, dict[str, Any]] = {}
        self._collection: Any = None
        self._mode = "memory"
        try:
            import pymongo

            client = pymongo.MongoClient(
                mongo_url or _MONGO_URL,
                serverSelectionTimeoutMS=_SELECTION_TIMEOUT_MS,
            )
            # Force a round-trip so we fail fast into memory mode when offline.
            client.admin.command("ping")
            self._collection = client[db_name or _DB_NAME][_COLLECTION]
            try:
                # background=True (default behaviour on MongoDB 4.2+ but honored
                # as an explicit kwarg) keeps the index build off the foreground
                # request thread so a freshly-populated collection does not block
                # FastAPI lifespan / first request. Skip the call if the index
                # already exists \u2014 re-creating that unique index serialises
                # writes against the collection for the entire build duration.
                existing = self._collection.index_information() or {}
                if not any(
                    tuple(idx.get("key") or ()) == (("job_id", 1),)
                    for idx in existing.values()
                ):
                    self._collection.create_index([("job_id", 1)], unique=True, background=True)
            except Exception as exc:  # index best-effort
                log.warning("Index creation for %s.job_id failed: %s", _COLLECTION, exc)
            self._mode = "mongo"
            log.info("ScheduleStore: MongoDB-backed (durable across restarts)")
        except Exception as exc:
            log.warning(
                "ScheduleStore: Mongo unavailable (%s) — schedules in-memory only "
                "(will not survive restart). Set MONGO_URL for durability.",
                exc,
            )

    @property
    def mode(self) -> str:
        return self._mode

    def load_all(self) -> list[dict[str, Any]]:
        """Return all persisted schedule docs (for boot rehydration)."""
        if self._mode == "mongo" and self._collection is not None:
            try:
                return list(self._collection.find({}, {"_id": 0}))
            except Exception as exc:
                log.warning("ScheduleStore.load_all failed: %s", exc)
                return []
        return list(self._mem.values())

    def upsert(self, doc: dict[str, Any]) -> None:
        """Persist (insert or update) a single schedule by job_id."""
        job_id = doc.get("job_id")
        if not job_id:
            return
        clean = {k: v for k, v in doc.items() if k != "_id"}
        if self._mode == "mongo" and self._collection is not None:
            try:
                self._collection.replace_one({"job_id": job_id}, clean, upsert=True)
                return
            except Exception as exc:
                log.warning("ScheduleStore.upsert(%s) failed: %s", job_id, exc)
                return
        self._mem[job_id] = clean

    def remove(self, job_id: str) -> None:
        """Delete a persisted schedule."""
        if self._mode == "mongo" and self._collection is not None:
            try:
                self._collection.delete_one({"job_id": job_id})
                return
            except Exception as exc:
                log.warning("ScheduleStore.remove(%s) failed: %s", job_id, exc)
                return
        self._mem.pop(job_id, None)
