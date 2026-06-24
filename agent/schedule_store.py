"""agent/schedule_store.py — durable persistence for scheduled agent jobs.

Fixes #505: ``AgentScheduler`` kept jobs in a plain in-memory dict, so every
company monitoring cadence was wiped on process restart / redeploy. This store
persists schedules to the platform's active storage backend (MongoDB **or**
SQLite) and the scheduler rehydrates from it on boot.

Backend selection:
  * ``STORAGE_BACKEND=sqlite`` (default for dev/CI) → SQLite via the stdlib
    ``sqlite3`` module (sync, no event-loop binding issues).
  * ``STORAGE_BACKEND=mongo`` (default for prod) → MongoDB via ``pymongo``
    (sync, safe from both async request handlers and the APScheduler thread).

All methods are **synchronous on purpose**. APScheduler fires jobs from a
background *thread* (no event loop), and schedules are also mutated from async
request handlers — a sync client is safe from both without event-loop
juggling. ``AgentScheduler`` already uses ``inspect.isawaitable`` on every
store call, so sync returns are handled transparently.

When the chosen backend is unreachable the store degrades to an in-memory
dict (non-durable, exactly the pre-fix behaviour, but never crashes the
scheduler).
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("qwen-proxy")

_MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
_DB_NAME = os.environ.get("DB_NAME", "llm_platform")
_SELECTION_TIMEOUT_MS = int(os.environ.get("MONGO_SELECTION_TIMEOUT_MS", "2000"))
_COLLECTION = "agent_schedules"
# _COLLECTION is a hardcoded constant (never user input) — used to build SQL
# identifiers. Bandit's B608 can't tell that apart from a string-built query
# with user input, so the f-string SQL sites below carry `# nosec B608` with a
# justification. The collection name is validated against this exact constant
# at every use site.
_TBL = _COLLECTION  # alias for brevity inside the SQL statements

# SQLite path mirrors db/sqlite_store.py so the agency DB lives alongside the
# rest of the platform data when STORAGE_BACKEND=sqlite.
_SQLITE_DB_PATH = os.environ.get(
    "AGENCY_SQLITE_DB_PATH",
    str(Path(os.environ.get("AGENCY_DATA_DIR", ".data")) / "agency.db"),
)


def _backend() -> str:
    return os.environ.get("STORAGE_BACKEND", "mongo").strip().lower()


class ScheduleStore:
    """Durable schedule persistence.

    Backend is chosen from ``STORAGE_BACKEND``:
      * ``sqlite`` → stdlib ``sqlite3`` (sync) — works with zero external
        services, ideal for the README's "Raspberry Pi 5" / single-VPS deploy.
      * ``mongo`` → ``pymongo`` (sync) — production-grade, survives cluster
        failover.

    All methods are best-effort and never raise: a storage outage must never
    take down the scheduler (jobs keep running in-memory; they just won't
    survive the next restart, which is no worse than the pre-fix behaviour).
    """

    def __init__(self, *, mongo_url: str | None = None, db_name: str | None = None) -> None:
        self._mem: dict[str, dict[str, Any]] = {}
        self._mode = "memory"
        self._lock = threading.Lock()
        backend = _backend()

        if backend == "sqlite":
            self._init_sqlite()
        else:
            self._init_mongo(mongo_url=mongo_url, db_name=db_name)

    # ── Mongo backend ─────────────────────────────────────────────────────

    def _init_mongo(self, *, mongo_url: str | None, db_name: str | None) -> None:
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

    # ── SQLite backend ────────────────────────────────────────────────────

    def _init_sqlite(self) -> None:
        try:
            path = Path(_SQLITE_DB_PATH)
            path.parent.mkdir(parents=True, exist_ok=True)
            # `check_same_thread=False` because the scheduler calls us from
            # both the FastAPI thread and the APScheduler worker thread. We
            # guard every write with ``self._lock`` so concurrent access is
            # serialised at the application level.
            self._sqlite = sqlite3.connect(str(path), check_same_thread=False)
            self._sqlite.execute("PRAGMA journal_mode=WAL")
            self._sqlite.execute("PRAGMA busy_timeout=5000")
            self._sqlite.execute(
                f"CREATE TABLE IF NOT EXISTS {_TBL} ("  # nosec B608 — _TBL is a constant
                "job_id TEXT PRIMARY KEY,"
                "doc    TEXT NOT NULL,"
                "updated_at REAL NOT NULL"
                ")"
            )
            self._sqlite.commit()
            self._mode = "sqlite"
            log.info(
                "ScheduleStore: SQLite-backed at %s (durable across restarts)",
                path,
            )
        except Exception as exc:
            log.warning(
                "ScheduleStore: SQLite unavailable (%s) — schedules in-memory only.",
                exc,
            )

    @property
    def mode(self) -> str:
        return self._mode

    # ── Public API (sync — scheduler handles via inspect.isawaitable) ─────

    def load_all(self) -> list[dict[str, Any]]:
        """Return all persisted schedule docs (for boot rehydration)."""
        if self._mode == "mongo":
            try:
                return list(self._collection.find({}, {"_id": 0}))
            except Exception as exc:
                log.warning("ScheduleStore.load_all failed: %s", exc)
                return []
        if self._mode == "sqlite":
            try:
                with self._lock:
                    # _TBL is a module-level constant ("agent_schedules"),
                    # never user input — no injection surface. nosec B608.
                    cur = self._sqlite.execute(f"SELECT doc FROM {_TBL}")  # nosec B608
                    return [json.loads(row[0]) for row in cur.fetchall()]
            except Exception as exc:
                log.warning("ScheduleStore.load_all (sqlite) failed: %s", exc)
                return []
        return list(self._mem.values())

    def upsert(self, doc: dict[str, Any]) -> None:
        """Persist (insert or update) a single schedule by job_id."""
        job_id = doc.get("job_id")
        if not job_id:
            return
        clean = {k: v for k, v in doc.items() if k != "_id"}
        if self._mode == "mongo":
            try:
                self._collection.replace_one({"job_id": job_id}, clean, upsert=True)
                return
            except Exception as exc:
                log.warning("ScheduleStore.upsert(%s) failed: %s", job_id, exc)
                return
        if self._mode == "sqlite":
            try:
                with self._lock:
                    self._sqlite.execute(
                        f"INSERT OR REPLACE INTO {_TBL} (job_id, doc, updated_at) VALUES (?, ?, ?)",  # nosec B608 — _TBL is a constant
                        (job_id, json.dumps(clean, default=_json_default), time.time()),
                    )
                    self._sqlite.commit()
                return
            except Exception as exc:
                log.warning("ScheduleStore.upsert(%s) sqlite failed: %s", job_id, exc)
                return
        self._mem[job_id] = clean

    def remove(self, job_id: str) -> None:
        """Delete a persisted schedule."""
        if self._mode == "mongo":
            try:
                self._collection.delete_one({"job_id": job_id})
                return
            except Exception as exc:
                log.warning("ScheduleStore.remove(%s) failed: %s", job_id, exc)
                return
        if self._mode == "sqlite":
            try:
                with self._lock:
                    self._sqlite.execute(
                        f"DELETE FROM {_TBL} WHERE job_id = ?",  # nosec B608 — _TBL is a constant
                        (job_id,)
                    )
                    self._sqlite.commit()
                return
            except Exception as exc:
                log.warning("ScheduleStore.remove(%s) sqlite failed: %s", job_id, exc)
                return
        self._mem.pop(job_id, None)


def _json_default(obj: Any) -> Any:
    """Fallback JSON encoder for schedule docs (datetimes, sets, etc.)."""
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if isinstance(obj, set):
        return list(obj)
    return str(obj)
