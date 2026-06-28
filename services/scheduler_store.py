"""services/scheduler_store.py — Durable scheduler persistence.

Issue #505: AgentScheduler was entirely in-memory — all schedules were
wiped on every redeploy.  This module provides a Mongo/SQLite-backed
store that persists and rehydrates scheduled jobs so company cadences
and recurring tasks survive restarts.

Usage::
    store = get_scheduler_store()
    await store.save(job)          # persist a new/updated job
    jobs = await store.load_all()   # rehydrate all on boot
    await store.delete(job_id)     # remove a job
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

log = logging.getLogger("qwen-proxy")

_SCHEDULER_COLLECTION = "scheduled_jobs"


class SchedulerStore:
    """Durable store for AgentScheduler jobs.

    Delegates to the shared DB (MongoDB or SQLite) so schedules survive
    across server restarts and redeploys.  Falls back to in-memory when
    no DB is available.
    """

    def __init__(self) -> None:
        self._db = None
        self._mem: dict[str, dict[str, Any]] = {}

    async def _ensure_db(self):
        if self._db is not None:
            return self._db
        try:
            from backend.server import get_db
            self._db = get_db()
            # Ensure the collection exists (SQLite needs explicit schema init)
            try:
                col = getattr(self._db, _SCHEDULER_COLLECTION, None)
                if col is None:
                    setattr(self._db, _SCHEDULER_COLLECTION, _MemCollection())
            except Exception:
                pass
            return self._db
        except Exception:
            log.debug("SchedulerStore: DB not available — jobs are in-memory only")
            self._db = _MemDB()
            return self._db

    async def _collection(self):
        db = await self._ensure_db()
        if isinstance(db, _MemDB):
            return None
        try:
            col = getattr(db, _SCHEDULER_COLLECTION, None)
            return col
        except Exception:
            return None

    async def save(self, job: Any) -> None:
        """Persist a scheduled job (create or update)."""
        doc = job.as_dict() if hasattr(job, 'as_dict') else dict(job)
        doc["updated_at"] = time.time()

        col = await self._collection()
        if col is None:
            self._mem[doc.get("job_id", doc.get("id", ""))] = doc
            log.debug("SchedulerStore: saved job %s to memory", doc.get("job_id"))
            return

        job_id = doc.get("job_id") or doc.get("id")
        if not job_id:
            return
        try:
            await col.replace_one(
                {"job_id": job_id},
                {**doc, "_id": job_id},
                upsert=True,
            )
            log.debug("SchedulerStore: saved job %s", job_id)
        except Exception as exc:
            log.warning("SchedulerStore: save failed for %s: %s", job_id, exc)
            self._mem[job_id] = doc

    async def load_all(self) -> list[dict[str, Any]]:
        """Load all persisted jobs (rehydrate on boot)."""
        col = await self._collection()
        if col is None:
            return list(self._mem.values())

        try:
            cursor = col.find({})
            docs = await cursor.to_list(length=10000)
            result = [dict(d) for d in docs]
            log.info("SchedulerStore: loaded %d persisted job(s)", len(result))
            return result
        except Exception as exc:
            log.warning("SchedulerStore: load_all failed: %s — using memory fallback", exc)
            return list(self._mem.values())

    async def delete(self, job_id: str) -> bool:
        """Delete a persisted job."""
        col = await self._collection()
        if col is None:
            existed = job_id in self._mem
            self._mem.pop(job_id, None)
            return existed

        try:
            result = await col.delete_one({"job_id": job_id})
            return result.deleted_count > 0
        except Exception as exc:
            log.warning("SchedulerStore: delete failed for %s: %s", job_id, exc)
            self._mem.pop(job_id, None)
            return False

    async def count(self) -> int:
        """Return the total number of persisted jobs."""
        col = await self._collection()
        if col is None:
            return len(self._mem)

        try:
            if hasattr(col, "count_documents"):
                return await col.count_documents({})
            cursor = col.find({})
            docs = await cursor.to_list(length=100_000)
            return len(docs)
        except Exception as exc:
            log.warning("SchedulerStore: count failed: %s", exc)
            return len(self._mem)

    async def delete_stale(self, retention_days: int | None = None) -> int:
        """Delete jobs older than *retention_days* (default from env
        ``SCHEDULER_JOB_RETENTION_DAYS``, or 30).

        Returns the number of deleted documents.
        """
        if retention_days is None:
            retention_days = int(os.environ.get("SCHEDULER_JOB_RETENTION_DAYS", "30"))
        cutoff = time.time() - (retention_days * 86_400)

        col = await self._collection()
        if col is None:
            stale_ids = [
                k for k, v in self._mem.items()
                if v.get("updated_at", 0) < cutoff
            ]
            for k in stale_ids:
                del self._mem[k]
            if stale_ids:
                log.info(
                    "SchedulerStore: deleted %d stale job(s) from memory "
                    "(retention=%dd)", len(stale_ids), retention_days,
                )
            return len(stale_ids)

        try:
            if hasattr(col, "delete_many"):
                result = await col.delete_many({"updated_at": {"$lt": cutoff}})
                deleted = result.deleted_count
            else:
                cursor = col.find({})
                docs = await cursor.to_list(length=100_000)
                deleted = 0
                for doc in docs:
                    if doc.get("updated_at", 0) < cutoff:
                        jid = doc.get("job_id") or doc.get("_id")
                        if jid:
                            await col.delete_one({"job_id": jid})
                            deleted += 1
            if deleted:
                log.info(
                    "SchedulerStore: deleted %d stale job(s) (retention=%dd)",
                    deleted, retention_days,
                )
            return deleted
        except Exception as exc:
            log.warning("SchedulerStore: delete_stale failed: %s", exc)
            return 0


class _MemDB:
    def __init__(self) -> None:
        self._collections: dict[str, _MemCollection] = {}

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        if name not in self._collections:
            self._collections[name] = _MemCollection()
        return self._collections[name]


class _MemCollection:
    def __init__(self) -> None:
        self._docs: dict[str, dict] = {}

    async def replace_one(self, query: dict, doc: dict, upsert: bool = False) -> None:
        key = query.get("job_id", query.get("_id", ""))
        if key:
            self._docs[key] = doc

    async def find_one(self, query: dict) -> dict | None:
        key = query.get("job_id", query.get("_id", ""))
        return self._docs.get(key)

    async def find(self, query: dict) -> "_MemCursor":
        return _MemCursor(list(self._docs.values()))

    async def delete_one(self, query: dict) -> "_MemDeleteResult":
        key = query.get("job_id", query.get("_id", ""))
        existed = key in self._docs
        self._docs.pop(key, None)
        return _MemDeleteResult(existed)

    async def count_documents(self, query: dict) -> int:
        return len(self._docs)

    async def delete_many(self, query: dict) -> "_MemDeleteResult":
        cutoff = query.get("updated_at", {}).get("$lt", float("inf"))
        stale = [
            k for k, v in self._docs.items()
            if v.get("updated_at", 0) < cutoff
        ]
        for k in stale:
            del self._docs[k]
        return _MemDeleteResult(len(stale) > 0, count=len(stale))


class _MemCursor:
    def __init__(self, docs: list[dict]) -> None:
        self._docs = docs

    async def to_list(self, length: int) -> list[dict]:
        return self._docs[:length]


class _MemDeleteResult:
    def __init__(self, deleted: bool, count: int | None = None) -> None:
        self.deleted_count = count if count is not None else (1 if deleted else 0)


# ── Singleton ─────────────────────────────────────────────────────────────────

_store: SchedulerStore | None = None


def get_scheduler_store() -> SchedulerStore:
    global _store
    if _store is None:
        _store = SchedulerStore()
    return _store
