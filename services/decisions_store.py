from __future__ import annotations

"""services/decisions_store.py
DecisionsStore — lifecycle manager for generic `dec_<hex8>` decision IDs.

Why this exists:
  The existing inline-keyboard callback (`wfo:approve:<run_id>`) is hard-coded
  to a single workflow-orchestrator state. To support decision prompts from
  agent loop risky-module escalations, secret-touch confirmations, dependency
  bump alerts, and similar generic decisions, we need a stable, durable
  decision_id schema that:
    - survives ≥64-byte inline_keyboard payload budget (Telegram ceiling)
    - persists across pod restarts (so reply-to-message lookup keeps working)
    - is reachable from both `backend/server.py` and `telegram_bot.py`

Storage: SQLite file at $DECISIONS_DB_PATH (default `data/decisions.sqlite`).
Schema mirrors `workflow_runs` (workflow/engine.py:176-225) for consistency.

Public API:
  - DecisionsStore(db_path?) — explicit constructor (testable)
  - get_decisions_store() — process-wide singleton (cached on first use)
  - create(...) -> decision_id        (idempotent if decision_id given)
  - resolve(decision_id, outcome, resolver) -> bool
  - get(decision_id) -> Optional[dict]
  - list_pending() -> list[dict]
  - list_since(cutoff_utc) -> list[dict]
"""
import json
import logging
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)

_DEFAULT_DB_PATH = "data/decisions.sqlite"
_VALID_OUTCOMES = frozenset({"approved", "rejected", "redirected"})


class DecisionsStore:
    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or os.environ.get("DECISIONS_DB_PATH") or _DEFAULT_DB_PATH
        if not Path(self.db_path).is_absolute():
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, isolation_level=None, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_schema(self) -> None:
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS decisions (
                        decision_id        TEXT PRIMARY KEY,
                        parent_run_id      TEXT,
                        decision_type      TEXT NOT NULL,
                        context_json       TEXT NOT NULL DEFAULT '{}',
                        deadline_utc       TEXT,
                        created_utc        TEXT NOT NULL,
                        status             TEXT NOT NULL DEFAULT 'pending',
                        resolved_utc       TEXT,
                        resolver           TEXT,
                        resolution_outcome TEXT
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(status)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_decisions_created ON decisions(created_utc)"
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS bot_message_links (
                        chat_id              INTEGER NOT NULL,
                        telegram_message_id  INTEGER NOT NULL,
                        decision_id          TEXT NOT NULL,
                        run_id               TEXT,
                        created_utc          TEXT NOT NULL,
                        PRIMARY KEY (chat_id, telegram_message_id)
                    )
                    """
                )
                # NOTE: ``decision_id`` is NOT a SQL FOREIGN KEY here. The bot's
                # flow is decision-create-then-link across two transactions; an
                # enforced FK would require both rows in the same statement and
                # would block the bot's natural ordering. Orphaned links are
                # cleaned up via ``unlink_expired`` (TTL index in production).
                #
                # ``run_id`` is similarly unconstrained; an orchestrator restart
                # can drop in-flight runs from its in-memory map but the durable
                # link survives, so a reply-to lookup against a missing run is
                # handled by the inbound-router with a "Run not found" reply.
                # See telegram_inbound_handlers._resolve_reply_to_decision.
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_bot_message_links_decision "
                    "ON bot_message_links(decision_id)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_bot_message_links_run "
                    "ON bot_message_links(run_id)"
                )
        except sqlite3.OperationalError as exc:
            log.warning("decisions_store.init_schema_skipped db=%s exc=%s", self.db_path, exc)

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def create(
        self,
        *,
        decision_type: str,
        parent_run_id: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
        deadline_utc: Optional[str] = None,
        decision_id: Optional[str] = None,
    ) -> str:
        decision_id = decision_id or ("dec_" + secrets.token_hex(4))
        ctx_json = json.dumps(context or {}, separators=(",", ":"), sort_keys=True)
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO decisions "
                    "(decision_id, parent_run_id, decision_type, context_json, "
                    " deadline_utc, created_utc, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, 'pending')",
                    (
                        decision_id,
                        parent_run_id,
                        decision_type,
                        ctx_json,
                        deadline_utc,
                        self._now_iso(),
                    ),
                )
            return decision_id
        except sqlite3.OperationalError as exc:
            log.warning("decisions_store.create_failed decision_id=%s exc=%s", decision_id, exc)
            raise

    def resolve(
        self,
        decision_id: str,
        *,
        outcome: str,
        resolver: str,
    ) -> bool:
        if outcome not in _VALID_OUTCOMES:
            raise ValueError(f"invalid outcome {outcome!r}; must be one of {sorted(_VALID_OUTCOMES)}")
        try:
            with self._connect() as conn:
                cur = conn.execute(
                    "UPDATE decisions SET status='resolved', resolved_utc=?, resolver=?, "
                    "resolution_outcome=? "
                    "WHERE decision_id=? AND status='pending'",
                    (self._now_iso(), resolver, outcome, decision_id),
                )
                return cur.rowcount > 0
        except sqlite3.OperationalError as exc:
            log.warning("decisions_store.resolve_failed decision_id=%s exc=%s", decision_id, exc)
            return False

    def get(self, decision_id: str) -> Optional[dict[str, Any]]:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM decisions WHERE decision_id = ?", (decision_id,)
                ).fetchone()
                return dict(row) if row else None
        except sqlite3.OperationalError as exc:
            log.warning("decisions_store.get_failed decision_id=%s exc=%s", decision_id, exc)
            return None

    def list_pending(self) -> list[dict[str, Any]]:
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM decisions WHERE status='pending' ORDER BY created_utc DESC"
                ).fetchall()
                return [dict(r) for r in rows]
        except sqlite3.OperationalError as exc:
            log.warning("decisions_store.list_pending_failed exc=%s", exc)
            return []

    def list_since(self, cutoff_utc: str) -> list[dict[str, Any]]:
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM decisions WHERE created_utc >= ? "
                    "ORDER BY created_utc DESC",
                    (cutoff_utc,),
                ).fetchall()
                return [dict(r) for r in rows]
        except sqlite3.OperationalError as exc:
            log.warning("decisions_store.list_since_failed exc=%s", exc)
            return []

    # ── bot_message_links: durable ChatID-TelegramMessageID → decision mapping ─
    # Used by the Telegram inbound router so a reply to a decision prompt can
    # be looked up across bot restarts. (Telegram's webhook/poller is
    # eventually-delivered; if the bot crashes after sending a message but
    # before the user replies, the link must still be rehydratable on restart.)

    def link_message(
        self,
        *,
        chat_id: int,
        telegram_message_id: int,
        decision_id: str,
        run_id: Optional[str] = None,
    ) -> bool:
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO bot_message_links "
                    "(chat_id, telegram_message_id, decision_id, run_id, created_utc) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        int(chat_id),
                        int(telegram_message_id),
                        decision_id,
                        run_id,
                        self._now_iso(),
                    ),
                )
            return True
        except sqlite3.OperationalError as exc:
            log.warning(
                "decisions_store.link_message_failed chat_id=%s msg_id=%s exc=%s",
                chat_id, telegram_message_id, exc,
            )
            return False

    def lookup_by_message(
        self,
        chat_id: int,
        telegram_message_id: int,
    ) -> Optional[dict[str, Any]]:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM bot_message_links "
                    "WHERE chat_id = ? AND telegram_message_id = ?",
                    (int(chat_id), int(telegram_message_id)),
                ).fetchone()
                return dict(row) if row else None
        except sqlite3.OperationalError as exc:
            log.warning(
                "decisions_store.lookup_by_message_failed chat_id=%s msg_id=%s exc=%s",
                chat_id, telegram_message_id, exc,
            )
            return None

    def unlink_expired(self, older_than_iso: str) -> int:
        try:
            with self._connect() as conn:
                cur = conn.execute(
                    "DELETE FROM bot_message_links WHERE created_utc < ?",
                    (older_than_iso,),
                )
                return cur.rowcount
        except sqlite3.OperationalError as exc:
            log.warning("decisions_store.unlink_expired_failed exc=%s", exc)
            return 0


_singleton: Optional[DecisionsStore] = None


def get_decisions_store(db_path: Optional[str] = None) -> DecisionsStore:
    """Process-wide DecisionsStore singleton (resettable via db_path arg)."""
    global _singleton
    if _singleton is None:
        _singleton = DecisionsStore(db_path=db_path)
    return _singleton


def reset_decisions_store_singleton() -> None:
    """Test-only: clears the cached singleton so the next get_decisions_store()
    builds a fresh instance (with a fresh SQLite file if db_path changes)."""
    global _singleton
    _singleton = None
