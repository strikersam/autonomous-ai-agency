"""Enhanced persistent memory system with auto-loading across AI coding tools.

This module extends the basic UserMemoryStore with:
1. Context-aware memory auto-loading
2. Semantic memory categorization
3. Tool-specific memory injection
4. Cross-session memory persistence
5. Memory versioning and migration
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

log = logging.getLogger("qwen-agent")

_DEFAULT_DB = ".data/agent.db"


class MemoryCategory(str, Enum):
    """Memory categories for semantic organization."""
    PREFERENCE = "preference"  # User preferences (theme, style, conventions)
    CONTEXT = "context"        # Project/workspace context
    LEARNING = "learning"      # Learned patterns and corrections
    HISTORY = "history"        # Historical decisions and rationale
    TOOL_CONFIG = "tool_config"  # Tool-specific configurations


class MemoryScope(str, Enum):
    """Memory scope determines when memory is auto-loaded."""
    GLOBAL = "global"          # Always loaded for this user
    WORKSPACE = "workspace"    # Loaded when in specific workspace
    SESSION = "session"        # Loaded only in specific session
    TOOL = "tool"             # Loaded for specific AI tool


@dataclass
class MemoryEntry:
    """Structured memory entry with metadata."""
    user_id: str
    key: str
    value: str
    category: MemoryCategory
    scope: MemoryScope
    workspace_id: str | None
    tool_name: str | None
    priority: int  # Higher priority loaded first (1-10)
    created_at: str
    updated_at: str
    access_count: int
    tags: list[str]
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "key": self.key,
            "value": self.value,
            "category": self.category,
            "scope": self.scope,
            "workspace_id": self.workspace_id,
            "tool_name": self.tool_name,
            "priority": self.priority,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "access_count": self.access_count,
            "tags": json.dumps(self.tags) if self.tags else "[]",
        }
    
    @classmethod
    def from_row(cls, row: sqlite3.Row) -> MemoryEntry:
        return cls(
            user_id=row["user_id"],
            key=row["key"],
            value=row["value"],
            category=MemoryCategory(row["category"]),
            scope=MemoryScope(row["scope"]),
            workspace_id=row["workspace_id"],
            tool_name=row["tool_name"],
            priority=row["priority"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            access_count=row["access_count"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
        )


class PersistentMemoryStore:
    """Enhanced persistent memory store with auto-loading support.
    
    Features:
    - Semantic categorization (preferences, context, learning, history)
    - Scope-based auto-loading (global, workspace, session, tool)
    - Priority-based memory ordering
    - Tool-specific memory injection
    - Memory versioning for schema migration
    """

    SCHEMA_VERSION = 1

    def __init__(self, db_path: str | Path | None = None) -> None:
        path = Path(db_path or os.environ.get("AGENT_DB_PATH") or _DEFAULT_DB)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = str(path)
        self._lock = threading.RLock()
        try:
            self._init_db()
        except sqlite3.OperationalError as exc:
            import tempfile
            fallback = Path(tempfile.gettempdir()) / ("persistent_memory_" + path.stem + ".db")
            log.warning(
                "PersistentMemoryStore: could not open DB at %s (%s). "
                "Falling back to %s — data will not persist across restarts.",
                self._db_path, exc, fallback,
            )
            self._db_path = str(fallback)
            self._init_db()
        log.info("PersistentMemoryStore initialized at %s", self._db_path)

    # ── internals ────────────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        for mode in ("MEMORY", "DELETE", "OFF"):
            try:
                result = conn.execute(f"PRAGMA journal_mode={mode}").fetchone()
                if result and result[0].upper() == mode:
                    break
            except sqlite3.OperationalError:
                continue
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            # Schema version tracking
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )
            
            # Enhanced memory table with categorization and scoping
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS persistent_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'context',
                    scope TEXT NOT NULL DEFAULT 'global',
                    workspace_id TEXT DEFAULT '',
                    tool_name TEXT DEFAULT '',
                    priority INTEGER NOT NULL DEFAULT 5,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    access_count INTEGER NOT NULL DEFAULT 0,
                    tags TEXT DEFAULT '[]',
                    UNIQUE(user_id, key, scope, workspace_id, tool_name)
                )
                """
            )
            
            # Indices for efficient querying
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memories_user_scope 
                ON persistent_memories (user_id, scope, priority DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memories_workspace 
                ON persistent_memories (user_id, workspace_id, scope)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memories_tool 
                ON persistent_memories (user_id, tool_name, scope)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memories_category 
                ON persistent_memories (user_id, category)
                """
            )
            
            # Memory access log for analytics
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_access_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    memory_key TEXT NOT NULL,
                    accessed_at TEXT NOT NULL,
                    context TEXT
                )
                """
            )
            
            conn.commit()
            
            # Check and update schema version
            current_version = conn.execute(
                "SELECT MAX(version) as v FROM schema_version"
            ).fetchone()["v"]
            
            if current_version is None:
                conn.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (self.SCHEMA_VERSION, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
                )
                conn.commit()

    # ── public API ────────────────────────────────────────────────────────────

    def save(
        self,
        user_id: str,
        key: str,
        value: str,
        *,
        category: MemoryCategory = MemoryCategory.CONTEXT,
        scope: MemoryScope = MemoryScope.GLOBAL,
        workspace_id: str | None = None,
        tool_name: str | None = None,
        priority: int = 5,
        tags: list[str] | None = None,
    ) -> None:
        """Save a memory entry with categorization and scoping."""
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        tags_json = json.dumps(tags or [])
        
        # Convert None to empty string for consistent UNIQUE constraint
        workspace_id = workspace_id or ''
        tool_name = tool_name or ''
        
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO persistent_memories 
                    (user_id, key, value, category, scope, workspace_id, tool_name, 
                     priority, created_at, updated_at, access_count, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                ON CONFLICT(user_id, key, scope, workspace_id, tool_name)
                DO UPDATE SET
                    value = excluded.value,
                    category = excluded.category,
                    priority = excluded.priority,
                    updated_at = excluded.updated_at,
                    tags = excluded.tags
                """,
                (user_id, key, value, category, scope, workspace_id, tool_name,
                 priority, now, now, tags_json),
            )
            conn.commit()
        
        log.debug(
            "memory saved: user=%s key=%s category=%s scope=%s",
            user_id, key, category, scope
        )

    def recall(
        self,
        user_id: str,
        key: str,
        *,
        workspace_id: str | None = None,
        tool_name: str | None = None,
        log_access: bool = True,
    ) -> str | None:
        """Recall a specific memory entry."""
        with self._lock, self._connect() as conn:
            # Try specific scope first, then fall back to global
            for scope in [MemoryScope.TOOL, MemoryScope.WORKSPACE, MemoryScope.GLOBAL]:
                query_workspace = workspace_id or '' if scope == MemoryScope.WORKSPACE else ''
                query_tool = tool_name or '' if scope == MemoryScope.TOOL else ''
                
                row = conn.execute(
                    """
                    SELECT value FROM persistent_memories
                    WHERE user_id = ? AND key = ? AND scope = ?
                        AND workspace_id = ? AND tool_name = ?
                    """,
                    (user_id, key, scope, query_workspace, query_tool),
                ).fetchone()
                
                if row:
                    if log_access:
                        self._log_access(conn, user_id, key)
                    return row["value"]
            
            return None

    def auto_load_memories(
        self,
        user_id: str,
        *,
        workspace_id: str | None = None,
        tool_name: str | None = None,
        max_memories: int = 50,
    ) -> dict[str, str]:
        """Auto-load relevant memories based on context.
        
        Returns memories prioritized by:
        1. Scope specificity (tool > workspace > global)
        2. Priority value
        3. Access frequency
        """
        with self._lock, self._connect() as conn:
            # Build scopes to query
            scopes = [MemoryScope.GLOBAL]
            if workspace_id:
                scopes.append(MemoryScope.WORKSPACE)
            if tool_name:
                scopes.append(MemoryScope.TOOL)
            
            memories: dict[str, str] = {}
            
            # Query in priority order: tool-specific, workspace-specific, global
            for scope in reversed(scopes):
                query_workspace = workspace_id or '' if scope == MemoryScope.WORKSPACE else ''
                query_tool = tool_name or '' if scope == MemoryScope.TOOL else ''
                
                rows = conn.execute(
                    """
                    SELECT key, value, priority, access_count
                    FROM persistent_memories
                    WHERE user_id = ? AND scope = ?
                        AND workspace_id = ? AND tool_name = ?
                    ORDER BY priority DESC, access_count DESC
                    LIMIT ?
                    """,
                    (user_id, scope, query_workspace, query_tool, max_memories),
                ).fetchall()
                
                for row in rows:
                    # Higher-specificity memories override lower-specificity ones
                    if row["key"] not in memories or scope != MemoryScope.GLOBAL:
                        memories[row["key"]] = row["value"]
                        self._log_access(conn, user_id, row["key"])
            
            conn.commit()
            
        log.debug(
            "auto-loaded %d memories for user=%s workspace=%s tool=%s",
            len(memories), user_id, workspace_id, tool_name
        )
        return memories

    def get_memories_by_category(
        self,
        user_id: str,
        category: MemoryCategory,
        *,
        workspace_id: str | None = None,
    ) -> dict[str, str]:
        """Get all memories in a specific category."""
        with self._lock, self._connect() as conn:
            query = """
                SELECT key, value FROM persistent_memories
                WHERE user_id = ? AND category = ?
            """
            params: list[Any] = [user_id, category]
            
            if workspace_id:
                query += " AND workspace_id = ?"
                params.append(workspace_id)
            else:
                # Get all if no workspace specified
                pass
            
            query += " ORDER BY priority DESC, updated_at DESC"
            
            rows = conn.execute(query, params).fetchall()
            return {row["key"]: row["value"] for row in rows}

    def search_memories(
        self,
        user_id: str,
        search_term: str,
        *,
        category: MemoryCategory | None = None,
        workspace_id: str | None = None,
        limit: int = 20,
    ) -> list[MemoryEntry]:
        """Search memories by key or value content."""
        with self._lock, self._connect() as conn:
            query = """
                SELECT * FROM persistent_memories
                WHERE user_id = ? 
                    AND (key LIKE ? OR value LIKE ?)
            """
            params: list[Any] = [user_id, f"%{search_term}%", f"%{search_term}%"]
            
            if category:
                query += " AND category = ?"
                params.append(category)
            
            if workspace_id:
                query += " AND (workspace_id IS NULL OR workspace_id = ?)"
                params.append(workspace_id)
            
            query += " ORDER BY priority DESC, access_count DESC LIMIT ?"
            params.append(limit)
            
            rows = conn.execute(query, params).fetchall()
            return [MemoryEntry.from_row(row) for row in rows]

    def delete(
        self,
        user_id: str,
        key: str,
        *,
        workspace_id: str | None = None,
        tool_name: str | None = None,
    ) -> bool:
        """Delete a memory entry."""
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """
                DELETE FROM persistent_memories
                WHERE user_id = ? AND key = ?
                    AND workspace_id = ? AND tool_name = ?
                """,
                (user_id, key, workspace_id or '', tool_name or ''),
            )
            conn.commit()
            return cur.rowcount > 0

    def bulk_import(
        self,
        user_id: str,
        memories: dict[str, str],
        *,
        category: MemoryCategory = MemoryCategory.CONTEXT,
        workspace_id: str | None = None,
    ) -> int:
        """Bulk import memories (useful for migrations)."""
        count = 0
        for key, value in memories.items():
            self.save(
                user_id=user_id,
                key=key,
                value=value,
                category=category,
                workspace_id=workspace_id,
            )
            count += 1
        return count

    def export_memories(
        self,
        user_id: str,
        *,
        workspace_id: str | None = None,
    ) -> dict[str, Any]:
        """Export all memories for a user (for backup/migration)."""
        with self._lock, self._connect() as conn:
            query = "SELECT * FROM persistent_memories WHERE user_id = ?"
            params: list[Any] = [user_id]
            
            if workspace_id:
                query += " AND workspace_id = ?"
                params.append(workspace_id)
            
            rows = conn.execute(query, params).fetchall()
            
            return {
                "user_id": user_id,
                "workspace_id": workspace_id,
                "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "count": len(rows),
                "memories": [
                    {
                        "key": row["key"],
                        "value": row["value"],
                        "category": row["category"],
                        "scope": row["scope"],
                        "workspace_id": row["workspace_id"],
                        "tool_name": row["tool_name"],
                        "priority": row["priority"],
                        "tags": json.loads(row["tags"]) if row["tags"] else [],
                    }
                    for row in rows
                ],
            }

    def get_memory_stats(self, user_id: str) -> dict[str, Any]:
        """Get statistics about stored memories."""
        with self._lock, self._connect() as conn:
            stats = conn.execute(
                """
                SELECT 
                    COUNT(*) as total_memories,
                    COUNT(DISTINCT category) as categories,
                    COUNT(DISTINCT workspace_id) as workspaces,
                    COUNT(DISTINCT tool_name) as tools,
                    SUM(access_count) as total_accesses,
                    AVG(priority) as avg_priority
                FROM persistent_memories
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
            
            category_breakdown = conn.execute(
                """
                SELECT category, COUNT(*) as count
                FROM persistent_memories
                WHERE user_id = ?
                GROUP BY category
                """,
                (user_id,),
            ).fetchall()
            
            return {
                "total_memories": stats["total_memories"],
                "categories": stats["categories"],
                "workspaces": stats["workspaces"],
                "tools": stats["tools"],
                "total_accesses": stats["total_accesses"],
                "avg_priority": round(stats["avg_priority"], 2) if stats["avg_priority"] else 0,
                "category_breakdown": {row["category"]: row["count"] for row in category_breakdown},
            }

    # ── private helpers ───────────────────────────────────────────────────────

    def _log_access(self, conn: sqlite3.Connection, user_id: str, key: str) -> None:
        """Log memory access for analytics."""
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn.execute(
            """
            INSERT INTO memory_access_log (user_id, memory_key, accessed_at, context)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, key, now, None),
        )
        conn.execute(
            """
            UPDATE persistent_memories
            SET access_count = access_count + 1
            WHERE user_id = ? AND key = ?
            """,
            (user_id, key),
        )
