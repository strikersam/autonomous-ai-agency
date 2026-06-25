"""services/harness_registry.py — Persistent Harness Registry

Tracks which AI coding harnesses are active across sessions and their
performance history.  Persisted to the shared store (Mongo/SQLite) so
metrics survive restarts.

Inspired by ECC's harness registry pattern.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

log = logging.getLogger("qwen-proxy")


class HarnessSessionRecord(BaseModel):
    harness_id: str
    session_id: str
    model: str | None = None
    started_at: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    ended_at: str | None = None
    duration_sec: int = 0
    tasks_completed: int = 0
    success_rate: float = 1.0
    errors: list[str] = Field(default_factory=list)

    def close(self) -> None:
        self.ended_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class HarnessMetrics(BaseModel):
    harness_id: str
    total_sessions: int = 0
    total_tasks: int = 0
    total_duration_sec: int = 0
    success_rate: float = 1.0
    last_active: str | None = None
    preferred_model: str | None = None

    def update_from_session(self, session: HarnessSessionRecord) -> None:
        self.total_sessions += 1
        self.total_tasks += session.tasks_completed
        self.total_duration_sec += session.duration_sec
        self.last_active = session.ended_at or session.started_at
        # Weighted success rate
        if self.total_sessions > 1:
            self.success_rate = (
                (self.success_rate * (self.total_sessions - 1) + session.success_rate)
                / self.total_sessions
            )
        else:
            self.success_rate = session.success_rate
        if session.model:
            self.preferred_model = session.model


class HarnessRegistry:
    """Persistent registry of harnesses and their performance history.

    Stores session records in-memory (process scope) with optional
    persistence to the shared store (MongoDB/SQLite).  The registry is
    lightweight by design — full history lives in the store; this holds
    the current-process view plus aggregated metrics.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, HarnessSessionRecord] = {}
        self._metrics: dict[str, HarnessMetrics] = {}
        self._active: set[str] = set()
        self._db = None  # lazy-init shared store

    def register_session(self, harness_id: str, session_id: str, model: str | None = None) -> HarnessSessionRecord:
        record = HarnessSessionRecord(harness_id=harness_id, session_id=session_id, model=model)
        self._sessions[session_id] = record
        self._active.add(harness_id)
        log.info("Harness session registered: %s/%s model=%s", harness_id, session_id, model)
        return record

    async def _ensure_db(self):
        if self._db is not None:
            return self._db
        try:
            from backend.server import get_db
            self._db = get_db()
            return self._db
        except Exception:
            self._db = _NoopDB()
            return self._db

    async def _persist_session(self, record: HarnessSessionRecord) -> None:
        try:
            db = await self._ensure_db()
            col = getattr(db, 'harness_sessions', None)
            if col is None:
                return
            await col.replace_one(
                {"session_id": record.session_id},
                record.model_dump(),
                upsert=True,
            )
        except Exception:
            pass

    async def _persist_metrics(self, harness_id: str, metrics: HarnessMetrics) -> None:
        try:
            db = await self._ensure_db()
            col = getattr(db, 'harness_metrics', None)
            if col is None:
                return
            await col.replace_one(
                {"harness_id": harness_id},
                metrics.model_dump(),
                upsert=True,
            )
        except Exception:
            pass

    def close_session(self, session_id: str, *, tasks_completed: int = 0, success: bool = True, errors: list[str] | None = None) -> None:
        record = self._sessions.get(session_id)
        if record is None:
            return
        record.close()
        record.tasks_completed = tasks_completed
        record.success_rate = 1.0 if success else 0.0
        record.errors = list(errors or [])

        metrics = self._metrics.get(record.harness_id)
        if metrics is None:
            metrics = HarnessMetrics(harness_id=record.harness_id)
            self._metrics[record.harness_id] = metrics
        metrics.update_from_session(record)

        # Persist to shared store (fire-and-forget). Safe for sync callers.
        import asyncio
        try:
            asyncio.create_task(self._persist_session(record))
            asyncio.create_task(self._persist_metrics(record.harness_id, metrics))
        except RuntimeError:
            pass  # no event loop (sync caller, test fixture, shutdown)

        log.info(
            "Harness session closed: %s tasks=%d success_rate=%.2f",
            session_id, tasks_completed, record.success_rate,
        )

    def get_metrics(self, harness_id: str | None = None) -> dict[str, Any]:
        if harness_id:
            m = self._metrics.get(harness_id)
            return m.model_dump() if m else {"harness_id": harness_id, "total_sessions": 0}
        return {hid: m.model_dump() for hid, m in self._metrics.items()}

    @property
    def active_harnesses(self) -> list[str]:
        return sorted(self._active)

    def as_dict(self) -> dict[str, Any]:
        return {
            "active_harnesses": self.active_harnesses,
            "metrics": {hid: m.model_dump() for hid, m in self._metrics.items()},
            "active_sessions": len(self._sessions),
        }


# ── Singleton ─────────────────────────────────────────────────────────────────

class _NoopDB:
    pass


_registry: HarnessRegistry | None = None


def get_harness_registry() -> HarnessRegistry:
    global _registry
    if _registry is None:
        _registry = HarnessRegistry()
    return _registry
