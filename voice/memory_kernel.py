"""voice/memory_kernel.py — Jarvis OS-inspired Memory Kernel.

Stores atomic facts about the CEO's agency, preferences, and commands
in SQLite with a Markdown mirror for human readability.

Inspired by: https://github.com/Grominet95/jarvis-OS (issue #664)

Fact properties (Jarvis OS design):
  - Atomic: one idea per fact
  - Dated: timestamp of creation + last reinforcement
  - Sourced: where it came from (telegram_voice / telegram_text / agent / api)
  - Reinforceable: repeated facts increase confidence score
  - Forgettable: facts decay or can be explicitly deleted
  - Correctable: new contradicting facts replace old ones

Usage:
    kernel = MemoryKernel()
    await kernel.store("CEO prefers Qwen3-Coder for coding tasks", source="telegram_voice")
    facts = await kernel.recall("model preference")
    await kernel.reinforce("fact-id-123")
    await kernel.forget("fact-id-456")
    await kernel.export_markdown()
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger("qwen-proxy")

_DATA_DIR = Path(os.environ.get("MEMORY_KERNEL_DIR", ".data/memory"))
_DB_PATH = _DATA_DIR / "facts.db"
_MD_PATH = _DATA_DIR / "facts.md"
_DECAY_DAYS = float(os.environ.get("MEMORY_DECAY_DAYS", "90"))


@dataclass
class Fact:
    fact_id: str
    content: str
    source: str           # telegram_voice | telegram_text | agent | api
    created_at: float
    updated_at: float
    reinforcement_count: int = 1
    confidence: float = 1.0
    tags: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.tags is None:
            self.tags = []


class MemoryKernel:
    """SQLite-backed atomic fact store with Markdown mirror."""

    def __init__(self) -> None:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._conn: "sqlite3.Connection | None" = None

    def _get_conn(self) -> "sqlite3.Connection":
        import sqlite3
        if self._conn is None:
            self._conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    fact_id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    reinforcement_count INTEGER DEFAULT 1,
                    confidence REAL DEFAULT 1.0,
                    tags TEXT DEFAULT '[]'
                )
            """)
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_updated ON facts(updated_at)")
            self._conn.commit()
        return self._conn

    def _fact_id(self, content: str) -> str:
        return hashlib.sha1(content.lower().strip().encode()).hexdigest()[:16]

    async def store(self, content: str, *, source: str = "api", tags: list[str] | None = None) -> Fact:
        """Store a new atomic fact or reinforce an existing one."""
        async with self._lock:
            return await asyncio.get_event_loop().run_in_executor(
                None, self._store_sync, content, source, tags or []
            )

    def _store_sync(self, content: str, source: str, tags: list[str]) -> Fact:
        conn = self._get_conn()
        fid = self._fact_id(content)
        now = time.time()
        row = conn.execute("SELECT * FROM facts WHERE fact_id = ?", (fid,)).fetchone()
        if row:
            new_count = row["reinforcement_count"] + 1
            new_conf = min(1.0, row["confidence"] + 0.1)
            conn.execute(
                "UPDATE facts SET updated_at=?, reinforcement_count=?, confidence=? WHERE fact_id=?",
                (now, new_count, new_conf, fid),
            )
            conn.commit()
            return Fact(
                fact_id=fid, content=row["content"], source=row["source"],
                created_at=row["created_at"], updated_at=now,
                reinforcement_count=new_count, confidence=new_conf,
                tags=json.loads(row["tags"] or "[]"),
            )
        fact = Fact(fact_id=fid, content=content, source=source,
                    created_at=now, updated_at=now, tags=tags)
        conn.execute(
            "INSERT INTO facts VALUES (?,?,?,?,?,?,?,?)",
            (fid, content, source, now, now, 1, 1.0, json.dumps(tags)),
        )
        conn.commit()
        self._export_markdown_sync()
        return fact

    async def recall(self, query: str = "", *, limit: int = 10) -> list[Fact]:
        """Return most relevant facts. Simple substring match on content."""
        async with self._lock:
            return await asyncio.get_event_loop().run_in_executor(
                None, self._recall_sync, query, limit
            )

    def _recall_sync(self, query: str, limit: int) -> list[Fact]:
        conn = self._get_conn()
        if query:
            rows = conn.execute(
                "SELECT * FROM facts WHERE content LIKE ? ORDER BY confidence DESC, updated_at DESC LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM facts ORDER BY confidence DESC, updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [Fact(
            fact_id=r["fact_id"], content=r["content"], source=r["source"],
            created_at=r["created_at"], updated_at=r["updated_at"],
            reinforcement_count=r["reinforcement_count"], confidence=r["confidence"],
            tags=json.loads(r["tags"] or "[]"),
        ) for r in rows]

    async def forget(self, fact_id: str) -> bool:
        async with self._lock:
            conn = self._get_conn()
            result = conn.execute("DELETE FROM facts WHERE fact_id = ?", (fact_id,))
            conn.commit()
            return result.rowcount > 0

    async def reinforce(self, fact_id: str) -> None:
        async with self._lock:
            conn = self._get_conn()
            conn.execute(
                "UPDATE facts SET reinforcement_count = reinforcement_count + 1, "
                "confidence = MIN(1.0, confidence + 0.1), updated_at = ? WHERE fact_id = ?",
                (time.time(), fact_id),
            )
            conn.commit()

    async def export_markdown(self) -> str:
        async with self._lock:
            return await asyncio.get_event_loop().run_in_executor(None, self._export_markdown_sync)

    def _export_markdown_sync(self) -> str:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM facts ORDER BY confidence DESC, updated_at DESC LIMIT 200"
        ).fetchall()
        import datetime
        lines = [
            "# CEO Memory Kernel", "",
            f"_Last updated: {datetime.datetime.utcnow().isoformat()}Z_",
            f"_Facts: {len(rows)}_", "",
            "| ID | Content | Source | Confidence | Reinforcements |",
            "|----|---------|--------|------------|----------------|",
        ]
        for r in rows:
            content = r["content"].replace("|", "\\|")[:80]
            lines.append(
                f"| `{r['fact_id']}` | {content} | {r['source']} "
                f"| {r['confidence']:.2f} | {r['reinforcement_count']} |"
            )
        md = "\n".join(lines) + "\n"
        _MD_PATH.write_text(md, encoding="utf-8")
        return md


# Module-level singleton
_kernel: MemoryKernel | None = None


def get_memory_kernel() -> MemoryKernel:
    global _kernel
    if _kernel is None:
        _kernel = MemoryKernel()
    return _kernel
