"""services/orchestrator_checkpoint.py — Durable step-level checkpointing

Issue #522: Persist orchestrator run state to the shared durable store
(MongoDB/SQLite) so in-flight runs survive backend restarts.  On boot,
any run that was in-progress is rehydrated and resumes from its last
checkpointed step.

Integration: the WorkflowOrchestrator calls ``checkpoint_run()`` after
every phase transition; ``restore_in_flight_runs()`` at startup returns
runs that were mid-flight before the last shutdown.
"""

from __future__ import annotations

import logging
import time
from typing import Any

log = logging.getLogger("qwen-proxy")

_CHECKPOINT_COLLECTION = "orchestrator_checkpoints"


class OrchestratorCheckpointStore:
    """Persist orchestrator runs so they survive restarts."""

    def __init__(self) -> None:
        self._store = None  # lazy-init from get_db()

    async def _db(self):
        if self._store is not None:
            return self._store
        try:
            from backend.server import get_db
            self._store = get_db()
            return self._store
        except Exception:
            log.debug("OrchestratorCheckpointStore: DB not available — checkpoints are in-memory only")
            self._store = _NoopDB()
            return self._store

    async def save(self, run: Any) -> None:
        """Persist a WorkflowRun snapshot."""
        db = await self._db()
        if isinstance(db, _NoopDB):
            db._data[run.run_id] = run.as_dict() if hasattr(run, 'as_dict') else str(run)
            return

        doc = {
            "run_id": run.run_id,
            "status": getattr(run, "status", "unknown"),
            "current_phase": getattr(run, "current_phase", None),
            "last_heartbeat": getattr(run, "last_heartbeat", time.time()),
            "snapshot": run.as_dict() if hasattr(run, 'as_dict') else {},
            "updated_at": time.time(),
        }
        try:
            col = getattr(db, _CHECKPOINT_COLLECTION, None)
            if col is None:
                return
            await col.replace_one(
                {"run_id": run.run_id},
                doc,
                upsert=True,
            )
        except Exception as exc:
            log.debug("Checkpoint save failed for run_id=%s: %s", run.run_id, exc)

    async def load(self, run_id: str) -> dict[str, Any] | None:
        """Load a persisted run snapshot."""
        db = await self._db()
        if isinstance(db, _NoopDB):
            data = db._data.get(run_id)
            return {"run_id": run_id, "snapshot": data} if data else None

        try:
            col = getattr(db, _CHECKPOINT_COLLECTION, None)
            if col is None:
                return None
            doc = await col.find_one({"run_id": run_id})
            return dict(doc) if doc else None
        except Exception as exc:
            log.debug("Checkpoint load failed for run_id=%s: %s", run_id, exc)
            return None

    async def list_in_flight(self) -> list[dict[str, Any]]:
        """Return checkpoints for runs that were not in a terminal state."""
        db = await self._db()
        if isinstance(db, _NoopDB):
            return [
                {"run_id": k, "snapshot": v}
                for k, v in db._data.items()
                if isinstance(v, dict) and v.get("status") not in ("done", "failed", "cancelled")
            ]

        try:
            col = getattr(db, _CHECKPOINT_COLLECTION, None)
            if col is None:
                return []
            cursor = col.find({
                "status": {"$nin": ["done", "failed", "cancelled"]},
            })
            docs = await cursor.to_list(length=200)
            return [dict(d) for d in docs]
        except Exception as exc:
            log.debug("Checkpoint list_in_flight failed: %s", exc)
            return []

    async def delete(self, run_id: str) -> None:
        db = await self._db()
        if isinstance(db, _NoopDB):
            db._data.pop(run_id, None)
            return
        try:
            col = getattr(db, _CHECKPOINT_COLLECTION, None)
            if col is not None:
                await col.delete_one({"run_id": run_id})
        except Exception:
            pass

    async def restore_in_flight_runs(self) -> list[dict[str, Any]]:
        """Restore in-flight runs at startup.

        Called during backend bootstrap.  Returns a list of run snapshots that
        were mid-flight before the last shutdown — the orchestrator can re-queue
        them.
        """
        docs = await self.list_in_flight()
        log.info("OrchestratorCheckpointStore: restoring %d in-flight run(s)", len(docs))
        return docs


class _NoopDB:
    """Fallback in-memory store when no DB is available."""
    def __init__(self) -> None:
        self._data: dict[str, Any] = {}


# ── Singleton ─────────────────────────────────────────────────────────────────

_store: OrchestratorCheckpointStore | None = None


def get_orchestrator_checkpoint_store() -> OrchestratorCheckpointStore:
    global _store
    if _store is None:
        _store = OrchestratorCheckpointStore()
    return _store
