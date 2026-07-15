"""backend/local_brain_store.py — DB-persisted state for the local GLM 5.2 brain.

Implements the cross-machine toggle that the user requested: a button on the
Cloudflare-deployed providers page flips ``desired_state`` between ``on``
and ``off``; a small daemon running on the operator's machine (``scripts/local_controller.py``)
polls this store, starts the local llama-server.exe with the GLM-5.2 model,
and POSTs back its heartbeat.

Store schema (single sqlite row, id = 'local_brain'):

  desired_state      str    'on' | 'off'  (operator's intent)
  desired_machine_id str?   operator-pinned machine UUID (None = lease to first reporter)
  desired_provider   str    the provider_id we want the brain to resolve to
                            ('colibri' when on; 'auto' when off — i.e. fall back
                             to the existing recommended chain)
  desired_updated_at str    ISO-8601 timestamp of last toggle
  desired_updated_by str    who flipped it (actor string)

  lease_machine_id   str?   the first machine_id that reported a successful
                            heartbeat after the last toggle; ties the contract
  lease_acquired_at  str?
                             lease expires 90s after the last heartbeat

  last_machine_id   str?    most recent machine_id that reported
  last_status       str?    'ok' | 'starting' | 'unreachable' | 'error'
  last_port_state   str?    'listening' | 'dead'
  last_v1_models    str?    JSON list (decoded into a list[dict] when read)
  last_models_has_glm52 bool  did /v1/models include the literal 'glm-5.2'?
  last_heartbeat_at str?    ISO-8601 timestamp of the most recent heartbeat
  last_error        str?    last error reported by the daemon (truncated to 500 chars)

The store is intentionally tiny: one row, kept in the same brain_config_mirror.db
file the brain config already uses so the operator doesn't have to think about
yet another sqlite file. All writes are best-effort and non-raising — a DB
error returns the safe default so the admin SPA's GET cannot 500.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from typing import Any, Final

log = logging.getLogger("local_brain_store")

# The valid desired_state values. Operators typing anything else get coerced
# to the safe default ('off') so a corrupted row never breaks the admin UI.
_VALID_DESIRED: Final[frozenset[str]] = frozenset({"on", "off"})
_VALID_STATUS: Final[frozenset[str]] = frozenset(
    {"ok", "starting", "unreachable", "error"}
)
_VALID_PORT_STATE: Final[frozenset[str]] = frozenset({"listening", "dead", "unknown"})


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class LocalBrainStore:
    """SQLite-backed store for the local GLM brain toggle + heartbeat."""

    _DDL = (
        "CREATE TABLE IF NOT EXISTS local_brain_state ("
        "id TEXT PRIMARY KEY, "
        "desired_state TEXT NOT NULL DEFAULT 'off', "
        "desired_machine_id TEXT, "
        "desired_provider TEXT NOT NULL DEFAULT 'auto', "
        "desired_updated_at TEXT NOT NULL DEFAULT '', "
        "desired_updated_by TEXT NOT NULL DEFAULT '', "
        "lease_machine_id TEXT, "
        "lease_acquired_at TEXT, "
        "last_machine_id TEXT, "
        "last_status TEXT, "
        "last_port_state TEXT, "
        "last_v1_models TEXT, "
        "last_models_has_glm52 INTEGER NOT NULL DEFAULT 0, "
        "last_heartbeat_at TEXT, "
        "last_error TEXT"
        ")"
    )
    _ROW_ID: Final[str] = "local_brain"

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or self._default_db_path()

    @staticmethod
    def _default_db_path() -> str:
        """Same mirror file brain_config already uses. One file, fewer surprises."""
        base = os.environ.get("SQLITE_DB_PATH", ".data/agency.db")
        if base.endswith(".db"):
            return base[:-3] + "_brain.db"
        return base + "_brain.db"

    def _conn(self) -> sqlite3.Connection:
        if self._db_path:
            os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(self._DDL)
            conn.commit()
        except Exception:
            pass
        return conn

    # ── Public API ───────────────────────────────────────────────────────────

    def get_state(self) -> dict[str, Any]:
        """Return the desired + last-reported state for the admin UI."""
        try:
            conn = self._conn()
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT desired_state, desired_machine_id, desired_provider, "
                    "desired_updated_at, desired_updated_by, "
                    "lease_machine_id, lease_acquired_at, "
                    "last_machine_id, last_status, last_port_state, "
                    "last_v1_models, last_models_has_glm52, "
                    "last_heartbeat_at, last_error "
                    "FROM local_brain_state WHERE id = ?",
                    (self._ROW_ID,),
                )
                row = cur.fetchone()
                if not row:
                    return self._default_state()
                return self._row_to_state(row, now_iso=_now_iso())
            finally:
                conn.close()
        except Exception as exc:
            # Never 500 the admin UI on a store read failure.
            log.warning("local_brain_store.get_state failed: %s", exc)
            return self._default_state()

    def set_desired(
        self,
        *,
        state: str,
        provider: str,
        actor: str,
        machine_id: str | None = None,
    ) -> dict[str, Any]:
        """Operator flips the toggle. Persists + clears any prior lease.

        Returns the new full state so the admin UI can echo it back.
        """
        desired = state.strip().lower() if state else "off"
        if desired not in _VALID_DESIRED:
            desired = "off"
        prov = (provider or ("colibri" if desired == "on" else "auto")).strip() or (
            "colibri" if desired == "on" else "auto"
        )
        try:
            conn = self._conn()
            try:
                cur = conn.cursor()
                cur.execute(self._DDL)
                cur.execute(
                    "INSERT INTO local_brain_state ("
                    "id, desired_state, desired_provider, desired_updated_at, "
                    "desired_updated_by, desired_machine_id, "
                    "lease_machine_id, lease_acquired_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, NULL, NULL) "
                    "ON CONFLICT(id) DO UPDATE SET "
                    "desired_state=excluded.desired_state, "
                    "desired_provider=excluded.desired_provider, "
                    "desired_updated_at=excluded.desired_updated_at, "
                    "desired_updated_by=excluded.desired_updated_by, "
                    "desired_machine_id=excluded.desired_machine_id, "
                    "lease_machine_id=NULL, "
                    "lease_acquired_at=NULL",
                    (
                        self._ROW_ID,
                        desired,
                        prov,
                        _now_iso(),
                        (actor or "unknown")[:200],
                        (machine_id or None),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            log.warning("local_brain_store.set_desired failed: %s", exc)
        return self.get_state()

    def record_heartbeat(
        self,
        *,
        machine_id: str,
        status: str,
        port_state: str,
        v1_models: list[dict[str, Any]] | None,
        models_has_glm52: bool,
        error: str | None = None,
        grace_seconds: int = 90,
    ) -> dict[str, Any]:
        """Local daemon POSTs its heartbeat.

        If the operator's desired_state=on AND the heartbeat reports success
        (status='ok' AND port_state='listening' AND models_has_glm52=True)
        and no machine has the lease yet, this machine acquires the lease.

        Lease TTL is refreshed on every successful heartbeat and expires
        ``grace_seconds`` after the timestamp; the admin UI marks the lease
        expired when it reads a heartbeat older than that.
        """
        try:
            norm_status = (status or "").strip().lower() or "unknown"
            if norm_status not in _VALID_STATUS:
                norm_status = "unknown"
            norm_port = (port_state or "unknown").strip().lower()
            if norm_port not in _VALID_PORT_STATE:
                norm_port = "unknown"
            models_json = json.dumps(list(v1_models or []), ensure_ascii=False)[:8000]
            err = (error or "")[:500]
            now = _now_iso()
            conn = self._conn()
            try:
                cur = conn.cursor()
                cur.execute(self._DDL)
                # Read current desired state to decide lease acquisition.
                cur.execute(
                    "SELECT desired_state, lease_machine_id FROM local_brain_state WHERE id = ?",
                    (self._ROW_ID,),
                )
                cur_row = cur.fetchone()
                desired_state = cur_row[0] if cur_row else "off"
                current_lease = cur_row[1] if cur_row else None
                new_lease_machine = current_lease
                new_lease_at = None
                if (
                    desired_state == "on"
                    and current_lease in (None, "", machine_id)
                    and norm_status == "ok"
                    and norm_port == "listening"
                    and bool(models_has_glm52)
                ):
                    new_lease_machine = machine_id
                    new_lease_at = now

                cur.execute(
                    "INSERT INTO local_brain_state ("
                    "id, last_machine_id, last_status, last_port_state, "
                    "last_v1_models, last_models_has_glm52, last_heartbeat_at, last_error, "
                    "lease_machine_id, lease_acquired_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(id) DO UPDATE SET "
                    "last_machine_id=excluded.last_machine_id, "
                    "last_status=excluded.last_status, "
                    "last_port_state=excluded.last_port_state, "
                    "last_v1_models=excluded.last_v1_models, "
                    "last_models_has_glm52=excluded.last_models_has_glm52, "
                    "last_heartbeat_at=excluded.last_heartbeat_at, "
                    "last_error=excluded.last_error, "
                    "lease_machine_id=COALESCE(local_brain_state.lease_machine_id, excluded.lease_machine_id), "
                    "lease_acquired_at=COALESCE(local_brain_state.lease_acquired_at, excluded.lease_acquired_at)",
                    (
                        self._ROW_ID,
                        machine_id[:80],
                        norm_status,
                        norm_port,
                        models_json,
                        1 if models_has_glm52 else 0,
                        now,
                        err,
                        new_lease_machine,
                        new_lease_at,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            log.warning("local_brain_store.record_heartbeat failed: %s", exc)
        return self.get_state()

    @staticmethod
    def _row_to_state(row: tuple, *, now_iso: str | None = None, lease_grace_seconds: int = 90) -> dict[str, Any]:
        """
        `now_iso`: ISO-8601 string marking the reader's "now" — pass it in to stay
        testable. `lease_grace_seconds`: how long the lease survives after the
        most recent healthy heartbeat; once ``(now - last_heartbeat_at) > grace``,
        the lease is declared expired so a crashing/leasing machine doesn't pin
        the UI forever (reviewer flag #f).
        """
        (
            desired_state,
            desired_machine_id,
            desired_provider,
            desired_updated_at,
            desired_updated_by,
            lease_machine_id,
            lease_acquired_at,
            last_machine_id,
            last_status,
            last_port_state,
            last_v1_models,
            last_models_has_glm52,
            last_heartbeat_at,
            last_error,
        ) = row
        models_list: list[dict[str, Any]]
        try:
            parsed = json.loads(last_v1_models or "[]")
            models_list = parsed if isinstance(parsed, list) else []
        except Exception:
            models_list = []
        lease_valid = bool(
            lease_machine_id
            and lease_acquired_at
            and last_heartbeat_at
            and last_heartbeat_at >= lease_acquired_at
        )
        # Reviewer fix: also enforce a TTL — once the lease's last heartbeat is
        # older than ``lease_grace_seconds`` from now, the lease is treated as
        # expired so a crashed box doesn't pin the UI as "leased: …" until the
        # operator manually flips the toggle. Uses parsed timestamps when both
        # sides look like ISO-8601 ("2026-07-15T12:34:56Z" is lex-sortable);
        # malformed timestamps fall back to "valid" with the consistency check.
        lease_age_seconds: float | None = None
        if now_iso and last_heartbeat_at:
            try:
                from datetime import datetime, timezone
                now_dt = datetime.strptime(now_iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                last_dt = datetime.strptime(last_heartbeat_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                lease_age_seconds = (now_dt - last_dt).total_seconds()
                if lease_age_seconds > lease_grace_seconds:
                    lease_valid = False
            except ValueError:
                pass
        return {
            "desired": {
                "state": desired_state or "off",
                "provider": desired_provider or "auto",
                "machine_id": desired_machine_id,
                "updated_at": desired_updated_at or "",
                "updated_by": desired_updated_by or "",
            },
            "lease": {
                "machine_id": lease_machine_id,
                "acquired_at": lease_acquired_at,
                "valid": lease_valid,
            },
            "last_heartbeat": {
                "machine_id": last_machine_id,
                "status": last_status or "unknown",
                "port_state": last_port_state or "unknown",
                "v1_models": models_list,
                "models_has_glm52": bool(last_models_has_glm52),
                "at": last_heartbeat_at or "",
                "error": last_error or "",
            },
        }

    @staticmethod
    def _default_state() -> dict[str, Any]:
        return {
            "desired": {
                "state": "off",
                "provider": "auto",
                "machine_id": None,
                "updated_at": "",
                "updated_by": "",
            },
            "lease": {"machine_id": None, "acquired_at": None, "valid": False},
            "last_heartbeat": {
                "machine_id": None,
                "status": "unknown",
                "port_state": "unknown",
                "v1_models": [],
                "models_has_glm52": False,
                "at": "",
                "error": "",
            },
        }
