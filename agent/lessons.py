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

Evidence is weighed, not just counted (adapted from Hindsight's observations,
which are refined as new evidence arrives rather than piling up). A later run
that succeeds on the same goal counts against that goal's lessons
(``record_run_success``). Ranking uses net evidence (hits minus resolutions),
halved every ``_HALF_LIFE_DAYS`` since the lesson last recurred. A lesson whose
evidence is fully contradicted is dropped from recall. Without this, a lesson
recorded 40 times in June outranked last week's failures forever.
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

from packages.security.redact import redact_secrets

log = logging.getLogger("qwen-agent")

_DEFAULT_DB = ".data/lessons.db"
_MAX_LESSON_CHARS = 300
_HALF_LIFE_DAYS = 14.0
# Rows considered when ranking. Bounded so recall stays O(1) on a store that
# has been collecting lessons for months.
_RANK_WINDOW = 500


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
            # Additive column for stores created before evidence weighting.
            columns = {row[1] for row in conn.execute("PRAGMA table_info(lessons)")}
            if "resolved" not in columns:
                conn.execute("ALTER TABLE lessons ADD COLUMN resolved INTEGER NOT NULL DEFAULT 0")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def record(self, *, phase: str, issue: str, goal: str = "") -> None:
        # Redact before truncating so a token cut in half still matches its pattern.
        issue = redact_secrets((issue or "").strip())[:_MAX_LESSON_CHARS]
        if not issue:
            return
        signature = hashlib.sha1(
            f"{phase}|{issue[:120]}".encode(), usedforsecurity=False
        ).hexdigest()[:16]
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO lessons (signature, phase, lesson, goal, hits, updated_at)
                   VALUES (?, ?, ?, ?, 1, ?)
                   ON CONFLICT(signature) DO UPDATE SET
                     hits = hits + 1, updated_at = excluded.updated_at""",
                (signature, phase, issue, redact_secrets(goal or "")[:200], time.time()),
            )

    def resolve_goal(self, goal: str) -> int:
        """Count a success against every lesson recorded for *goal*; return how many."""
        goal = redact_secrets(goal or "")[:200]
        if not goal:
            return 0
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "UPDATE lessons SET resolved = resolved + 1 "
                "WHERE goal = ? AND resolved < hits",
                (goal,),
            )
            return cur.rowcount

    def recent(self, limit: int = 5, *, now: float | None = None) -> list[dict[str, Any]]:
        """Live lessons, strongest current evidence first.

        ``signature`` is included so callers can cite a specific lesson: the
        harness spec (agent/harness_spec.py) refuses to write an entry it cannot
        trace back to one. Fully contradicted lessons are omitted, so a spec
        entry built on one stops verifying and drops out as well.
        """
        now = time.time() if now is None else now
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT signature, phase, lesson, hits, resolved, updated_at FROM lessons "
                "WHERE resolved < hits ORDER BY updated_at DESC LIMIT ?",
                (max(int(limit), _RANK_WINDOW),),
            ).fetchall()
        ranked = sorted(rows, key=lambda r: _evidence(r, now), reverse=True)
        return [
            {k: r[k] for k in ("signature", "phase", "lesson", "hits", "resolved")}
            for r in ranked[: int(limit)]
        ]


def _evidence(row: sqlite3.Row, now: float) -> float:
    """Net hits, halved for every half-life since the lesson last recurred."""
    age_days = max(now - float(row["updated_at"]), 0.0) / 86400.0
    return (int(row["hits"]) - int(row["resolved"])) * 0.5 ** (age_days / _HALF_LIFE_DAYS)


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


def record_run_success(goal: str, step_results: list[dict[str, Any]]) -> None:
    """Count a fully successful run against its goal's lessons. Never raises."""
    try:
        statuses = [s.get("status") for s in step_results or [] if isinstance(s, dict)]
        # An all-skipped run proves nothing, so at least one step must have done work.
        if "failed" not in statuses and ({"applied", "ok"} & set(statuses)):
            _get_store().resolve_goal(goal)
    except Exception as exc:  # lessons must never break the run itself
        log.debug("lesson resolution skipped: %s", exc)


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
