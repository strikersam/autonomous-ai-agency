from __future__ import annotations

"""Chat History Persistence + Retrieval (C4 roadmap item).

Server-side SQLite store for chat conversation history, enabling session
continuity across restarts.  Supports session_id, CRUD operations, history
trimming, export/import, and per-session message limits.

Usage::

    store = ChatHistoryStore()
    store.save_message("sess-abc", {"role": "user", "content": "write a test"})
    store.save_message("sess-abc", {"role": "assistant", "content": "def test..."})

    history = store.get_history("sess-abc")
    # → list of message dicts

    store.trim_history("sess-abc", max_messages=50)
"""

import json
import logging
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

log = logging.getLogger("qwen-proxy")

# ── Configuration ──────────────────────────────────────────────────────────────

_DB_PATH = os.environ.get("CHAT_HISTORY_DB", ".data/chat_history.db")
_MAX_MESSAGES = int(os.environ.get("CHAT_HISTORY_MAX_MESSAGES", "1000"))
_MAX_SESSIONS = int(os.environ.get("CHAT_HISTORY_MAX_SESSIONS", "500"))
_DEFAULT_MAX_MESSAGES_PER_SESSION = int(
    os.environ.get("CHAT_HISTORY_PER_SESSION_MAX", "200")
)


class ChatHistoryStore:
    """Persistent SQLite-backed chat history store.

    Messages are stored with session_id, sequence number, timestamp,
    and JSON-serialised message content.  Supports trimming,
    export, and per-session limits.

    Usage::

        store = ChatHistoryStore()
        session_id = store.create_session(model="qwen3-coder:30b")

        store.append(session_id, {"role": "user", "content": "hello"})
        store.append(session_id, {"role": "assistant", "content": "hi!"})

        history = store.get_messages(session_id)
    """

    def __init__(
        self,
        *,
        db_path: str = _DB_PATH,
        max_sessions: int = _MAX_SESSIONS,
        default_max_messages: int = _DEFAULT_MAX_MESSAGES_PER_SESSION,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_sessions = max_sessions
        self.default_max_messages = default_max_messages
        self._conn: sqlite3.Connection | None = None
        self._ensure_schema()

    # ── Session management ──────────────────────────────────────────────────

    def create_session(
        self,
        *,
        model: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create a new session and return its ID."""
        session_id = f"sess_{uuid.uuid4().hex[:16]}"
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn = self._get_conn()

        conn.execute(
            """
            INSERT INTO sessions (session_id, model, created_at, updated_at, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, model, now, now, json.dumps(metadata or {})),
        )
        conn.commit()

        self._enforce_session_limit()
        log.debug("Created chat session: %s (model=%s)", session_id, model)
        return session_id

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its messages. Returns True if deleted."""
        conn = self._get_conn()
        cursor = conn.execute(
            "DELETE FROM sessions WHERE session_id = ?", (session_id,)
        )
        deleted = cursor.rowcount > 0
        if deleted:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.commit()
            log.debug("Deleted chat session: %s", session_id)
        return deleted

    def list_sessions(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List sessions ordered by most recently updated."""
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT session_id, model, created_at, updated_at,
                   (SELECT COUNT(*) FROM messages WHERE messages.session_id = sessions.session_id) AS message_count
            FROM sessions
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()

        return [
            {
                "session_id": row[0],
                "model": row[1],
                "created_at": row[2],
                "updated_at": row[3],
                "message_count": row[4],
            }
            for row in rows
        ]

    def session_counts(self) -> dict[str, int]:
        """Return total session and message counts."""
        conn = self._get_conn()
        sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone() or (0,)
        messages = conn.execute("SELECT COUNT(*) FROM messages").fetchone() or (0,)
        return {"sessions": int(sessions[0]), "messages": int(messages[0])}

    # ── Message CRUD ────────────────────────────────────────────────────────

    def append(
        self,
        session_id: str,
        message: dict[str, Any],
        *,
        max_messages: int = 0,
    ) -> int:
        """Append a message to the session. Returns the message's sequence number.

        Automatically updates the session's updated_at timestamp.
        If *max_messages* is set and the session exceeds it, oldest messages
        are trimmed first.

        The message dict should have at least ``role`` and ``content`` keys.
        """
        max_msgs = max_messages or self.default_max_messages
        conn = self._get_conn()
        seq = self._next_seq(conn, session_id)

        # Ensure the session exists
        exists = conn.execute(
            "SELECT 1 FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if not exists:
            # create_session() has keyword-only args after *; pass model as kwarg
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            conn.execute(
                """
                INSERT INTO sessions (session_id, model, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, "", now, now, "{}"),
            )
            conn.commit()

        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        conn.execute(
            """
            INSERT INTO messages (session_id, seq, role, content, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session_id,
                seq,
                message.get("role", "unknown"),
                message.get("content", ""),
                now,
            ),
        )

        # Update session timestamp
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
            (now, session_id),
        )
        conn.commit()

        # Trim if over limit
        if max_msgs > 0:
            self._trim_to_limit(conn, session_id, max_msgs)

        log.debug(
            "Chat message appended: session=%s seq=%d role=%s",
            session_id,
            seq,
            message.get("role"),
        )
        return seq

    def append_bulk(
        self,
        session_id: str,
        messages: list[dict[str, Any]],
        *,
        max_messages: int = 0,
    ) -> int:
        """Append multiple messages at once. Returns number of messages appended."""
        count = 0
        for msg in messages:
            self.append(session_id, msg, max_messages=0)
            count += 1
        max_msgs = max_messages or self.default_max_messages
        if max_msgs > 0:
            conn = self._get_conn()
            self._trim_to_limit(conn, session_id, max_msgs)
        return count

    def get_messages(
        self,
        session_id: str,
        *,
        limit: int = 0,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Return messages for a session, ordered by sequence number."""
        conn = self._get_conn()
        if limit > 0:
            rows = conn.execute(
                """
                SELECT seq, role, content, created_at
                FROM messages
                WHERE session_id = ?
                ORDER BY seq ASC
                LIMIT ? OFFSET ?
                """,
                (session_id, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT seq, role, content, created_at
                FROM messages
                WHERE session_id = ?
                ORDER BY seq ASC
                """,
                (session_id,),
            ).fetchall()

        return [
            {
                "role": row[1],
                "content": row[2],
                "_seq": row[0],
                "_created_at": row[3],
            }
            for row in rows
        ]

    def get_history(
        self, session_id: str, *, max_messages: int = 0
    ) -> list[dict[str, str]]:
        """Return messages as clean role/content dicts (no internal keys).

        This is the format expected by LLM clients.
        """
        messages = self.get_messages(session_id, limit=max_messages)
        return [{"role": m["role"], "content": m["content"]} for m in messages]

    def update_message(
        self,
        session_id: str,
        seq: int,
        content: str,
    ) -> bool:
        """Update a message's content. Returns True if found and updated."""
        conn = self._get_conn()
        cursor = conn.execute(
            "UPDATE messages SET content = ? WHERE session_id = ? AND seq = ?",
            (content, session_id, seq),
        )
        conn.commit()
        return cursor.rowcount > 0

    def message_count(self, session_id: str) -> int:
        """Return the number of messages in a session."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id = ?", (session_id,)
        ).fetchone()
        return int(row[0]) if row else 0

    # ── Trimming ────────────────────────────────────────────────────────────

    def trim_history(
        self,
        session_id: str,
        *,
        max_messages: int = 0,
    ) -> int:
        """Trim the oldest messages so total stays under *max_messages*.

        Returns the number of messages removed.
        """
        max_msgs = max_messages or self.default_max_messages
        conn = self._get_conn()
        return self._trim_to_limit(conn, session_id, max_msgs)

    def _trim_to_limit(
        self, conn: sqlite3.Connection, session_id: str, max_messages: int
    ) -> int:
        """Remove oldest messages until session is within the limit."""
        row = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id = ?", (session_id,)
        ).fetchone()
        count = int(row[0]) if row else 0
        excess = count - max_messages
        if excess <= 0:
            return 0

        # Delete the oldest *excess* messages
        cursor = conn.execute(
            """
            DELETE FROM messages
            WHERE session_id = ? AND seq IN (
                SELECT seq FROM messages
                WHERE session_id = ?
                ORDER BY seq ASC
                LIMIT ?
            )
            """,
            (session_id, session_id, excess),
        )
        conn.commit()
        log.debug(
            "Trimmed %d messages from session %s (was %d, limit %d)",
            excess,
            session_id,
            count,
            max_messages,
        )
        return cursor.rowcount

    # ── Export / Import ─────────────────────────────────────────────────────

    def export_session(self, session_id: str) -> dict[str, Any] | None:
        """Export a full session with all messages as a JSON-serialisable dict."""
        conn = self._get_conn()
        session_row = conn.execute(
            "SELECT session_id, model, created_at, updated_at, metadata FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if not session_row:
            return None

        messages = self.get_messages(session_id)
        return {
            "session_id": session_row[0],
            "model": session_row[1],
            "created_at": session_row[2],
            "updated_at": session_row[3],
            "metadata": json.loads(session_row[4]) if session_row[4] else {},
            "messages": messages,
        }

    def import_session(self, data: dict[str, Any]) -> str | None:
        """Import a session from an export dict. Returns the new session_id."""
        session_id = data.get("session_id") or self.create_session(
            model=data.get("model", ""),
            metadata=data.get("metadata"),
        )
        for msg in data.get("messages", []):
            self.append(session_id, msg, max_messages=0)
        return session_id

    # ── Housekeeping ────────────────────────────────────────────────────────

    def _enforce_session_limit(self) -> None:
        """Drop oldest sessions if we exceed the maximum."""
        conn = self._get_conn()
        row = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
        count = int(row[0]) if row else 0
        excess = count - self.max_sessions
        if excess <= 0:
            return

        # Delete oldest sessions (by updated_at)
        conn.execute(
            """
            DELETE FROM sessions WHERE session_id IN (
                SELECT session_id FROM sessions
                ORDER BY updated_at ASC
                LIMIT ?
            )
            """,
            (excess,),
        )
        # Cascade delete messages
        conn.execute(
            """
            DELETE FROM messages WHERE session_id NOT IN (
                SELECT session_id FROM sessions
            )
            """
        )
        conn.commit()
        log.info("Enforced session limit: removed %d oldest sessions", excess)

    def vacuum(self) -> None:
        """Run SQLite VACUUM to reclaim disk space."""
        conn = self._get_conn()
        conn.execute("VACUUM")
        log.info("Chat history database vacuumed")

    def stats(self) -> dict[str, Any]:
        """Return store statistics."""
        counts = self.session_counts()
        conn = self._get_conn()
        size_bytes = self.db_path.stat().st_size if self.db_path.exists() else 0
        return {
            "db_path": str(self.db_path),
            "total_sessions": counts["sessions"],
            "total_messages": counts["messages"],
            "max_sessions": self.max_sessions,
            "default_max_messages": self.default_max_messages,
            "db_size_bytes": size_bytes,
            "db_size_mb": round(size_bytes / (1024 * 1024), 2),
        }

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── Internals ───────────────────────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create the database connection (thread-unsafe; use from one thread)."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def _ensure_schema(self) -> None:
        """Create tables if they don't exist."""
        conn = self._get_conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id  TEXT PRIMARY KEY,
                model       TEXT NOT NULL DEFAULT '',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                metadata    TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                seq         INTEGER NOT NULL,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                UNIQUE(session_id, seq)
            );

            CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id, seq);

            CREATE INDEX IF NOT EXISTS idx_sessions_updated
                ON sessions(updated_at DESC);
            """
        )
        conn.commit()

    @staticmethod
    def _next_seq(conn: sqlite3.Connection, session_id: str) -> int:
        row = conn.execute(
            "SELECT COALESCE(MAX(seq), 0) + 1 FROM messages WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return int(row[0]) if row else 1


# ── Module-level singleton ─────────────────────────────────────────────────────

_store: ChatHistoryStore | None = None


def get_chat_history() -> ChatHistoryStore:
    """Return the module-level ChatHistoryStore singleton."""
    global _store
    if _store is None:
        _store = ChatHistoryStore()
    return _store
