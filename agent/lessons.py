"""Failure lessons: turn failed runs into context for the next run.

The supervisor already re-files failed work (retry), but nothing fed the
*cause* of a failure back into the planner, so the same mistake could recur
forever. This module closes that loop with the smallest durable mechanism:

1. ``record_step_failures(...)`` — called by AgentRunner after a run —
   persists one deduplicated lesson per failed step (SQLite, same ``.data/``
   convention as ``agent/persistent_memory.py``).
2. ``recent_lessons_block(...)`` — called during planning — returns a short
   system-prompt block of the most recent, most-hit lessons, or "".

Lessons are deduplicated by an error signature (phase + first issue line),
and a ``hits`` counter tracks recurring failures so the block surfaces the
most persistent problems first.
"""
from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("qwen-agent")

_DEFAULT_DB = ".data/lessons.db"
_MAX_LESSON_CHARS = 300


class LessonStore:
    """SQLite-backed store of failure lessons. Thread-safe, zero deps."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = Path(db_path or os.environ.get("AGENT_LESSONS_DB", _DEFAULT_DB))
        self._lock = threading.Lock()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS lessons (
                    signature TEXT PRIMARY KEY,
                    phase TEXT NOT NULL,
                    lesson TEXT NOT NULL,
                    goal TEXT NOT NULL DEFAULT '',
                    hits INTEGER NOT NULL DEFAULT 1,
                    updated_at REAL NOT NULL
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def record(self, *, phase: str, issue: str, goal: str = "") -> None:
        issue = (issue or "").strip()[:_MAX_LESSON_CHARS]
        if not issue:
            return
        signature = hashlib.sha1(f"{phase}|{issue[:120]}".encode()).hexdigest()[:16]
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO lessons (signature, phase, lesson, goal, hits, updated_at)
                   VALUES (?, ?, ?, ?, 1, ?)
                   ON CONFLICT(signature) DO UPDATE SET
                     hits = hits + 1, updated_at = excluded.updated_at""",
                (signature, phase, issue, (goal or "")[:200], time.time()),
            )

    def recent(self, limit: int = 5) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT phase, lesson, hits FROM lessons ORDER BY hits DESC, updated_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [dict(r) for r in rows]


_store: LessonStore | None = None


def _get_store() -> LessonStore:
    global _store
    if _store is None:
        _store = LessonStore()
    return _store


def record_step_failures(goal: str, step_results: list[dict[str, Any]]) -> None:
    """Persist a lesson for every failed step in a run. Never raises."""
    try:
        store = _get_store()
        for step in step_results or []:
            if not isinstance(step, dict) or step.get("status") != "failed":
                continue
            issues = step.get("issues") or []
            issue = str(issues[0]) if issues else "step failed without a reported issue"
            store.record(
                phase=str(step.get("failure_phase") or "execute"),
                issue=issue,
                goal=goal,
            )
    except Exception as exc:  # lessons must never break the run itself
        log.debug("lesson recording skipped: %s", exc)


def recent_lessons_block(limit: int = 5) -> str:
    """Formatted prompt block of recent lessons, or '' when none exist."""
    try:
        lessons = _get_store().recent(limit)
    except Exception as exc:
        log.debug("lesson recall skipped: %s", exc)
        return ""
    if not lessons:
        return ""
    lines = [
        "Lessons from recent failed runs — avoid repeating these mistakes:",
    ]
    for entry in lessons:
        hits = f" (seen {entry['hits']}x)" if entry.get("hits", 1) > 1 else ""
        lines.append(f"- [{entry['phase']}] {entry['lesson']}{hits}")
    return "\n".join(lines)
