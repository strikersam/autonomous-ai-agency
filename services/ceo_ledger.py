"""services/ceo_ledger.py — durable record of what the CEO is driving to closure.

The CEO cannot micro-manage work it cannot remember. Before this ledger, a
delegation's state lived only in the coroutine that started it: a redeploy, a
Render cold start, or an unhandled exception mid-fan-out left the work in limbo
with nothing tracking that it never finished. The agency looked busy and
quietly dropped tasks.

The ledger records every goal the CEO takes on, every subtask it splits that
goal into, and every attempt at every subtask. It is what the 24x7 supervisor
sweeps to find work that stalled, work that failed, and work that is genuinely
done — and it is what makes "drive to closure" a checkable claim rather than an
aspiration.

Storage follows the same contract as ``agent/schedule_store.py``: synchronous,
dual-backend (MongoDB in production, SQLite in dev/CI), degrading to an
in-memory dict when neither is reachable. Sync matters because the ledger is
written from async request handlers *and* from the supervisor's background
thread; a sync client is safe from both without event-loop juggling. No method
raises — a storage outage must never take down the agency.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("agency.ceo.ledger")

_MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
_DB_NAME = os.environ.get("DB_NAME", "llm_platform")
_COLLECTION = "ceo_ledger"
# _TBL is a module-level constant, never user input, so the f-string SQL below
# has no injection surface. Bandit cannot distinguish that from a query built
# with user data, hence the `# nosec B608` markers at each use site.
_TBL = _COLLECTION


def _selection_timeout_ms() -> int:
    """Mongo server-selection timeout, read and clamped at call time.

    Parsing this at import time with a bare ``int()`` means
    ``MONGO_SELECTION_TIMEOUT_MS=abc`` raises ``ValueError`` while importing this
    module, which takes down the whole CEO subsystem — and anything importing it
    — instead of degrading. Every other env read in this subsystem is clamped and
    defaulted; this one is too.
    """
    raw = os.environ.get("MONGO_SELECTION_TIMEOUT_MS", "").strip()
    if not raw:
        return 2000
    try:
        return max(50, min(30000, int(raw)))
    except ValueError:
        log.warning("MONGO_SELECTION_TIMEOUT_MS=%r is not an integer; using 2000", raw)
        return 2000


def _sqlite_path() -> str:
    """Resolve the SQLite path at construction time, not import time.

    ``agent/schedule_store.py`` freezes this into a module constant, which means
    the path can only be changed by restarting the process — and makes the store
    impossible to point somewhere else in a test without reloading the module.
    Reading it per-construction costs nothing and removes both problems.
    """
    explicit = os.environ.get("AGENCY_SQLITE_DB_PATH", "").strip()
    if explicit:
        return explicit
    # Under TESTING, never fall back to the shared on-disk default. Any test
    # that exercises a code path which writes to the ledger — CEODispatcher's
    # delegate() now does — would otherwise share one `.data/agency.db` with
    # every other test in the session, and with the developer's real database.
    # Tests that genuinely need durability set AGENCY_SQLITE_DB_PATH (or pass
    # sqlite_path=) and are unaffected.
    if os.environ.get("TESTING", "").strip().lower() in {"1", "true", "yes", "on"}:
        return ":memory:"
    return str(Path(os.environ.get("AGENCY_DATA_DIR", ".data")) / "agency.db")


def _backend() -> str:
    return os.environ.get("STORAGE_BACKEND", "mongo").strip().lower()


def _now() -> float:
    return time.time()


# ── Records ───────────────────────────────────────────────────────────────────

#: Terminal goal states. A goal in any other state is the supervisor's problem.
CLOSED_STATES = {"closed", "abandoned"}


@dataclass
class Attempt:
    """One delegation of one subtask to one tier."""

    tier: str
    started_at: float
    finished_at: float | None = None
    status: str = "running"  # running | accepted | rejected | error
    runtime_id: str = ""
    summary: str = ""
    error: str = ""
    quality: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
            "runtime_id": self.runtime_id,
            "summary": self.summary[:2000],
            "error": self.error[:1000],
            "quality": self.quality,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Attempt":
        return cls(
            tier=str(d.get("tier") or "midlevel"),
            started_at=float(d.get("started_at") or 0.0),
            finished_at=d.get("finished_at"),
            status=str(d.get("status") or "running"),
            runtime_id=str(d.get("runtime_id") or ""),
            summary=str(d.get("summary") or ""),
            error=str(d.get("error") or ""),
            quality=dict(d.get("quality") or {}),
        )


@dataclass
class SubtaskRecord:
    """A subtask's full history: what it is, and every attempt at it."""

    subtask_id: str
    title: str
    role: str = "dev"
    tier: str = "midlevel"
    status: str = "pending"  # pending | running | done | failed
    dependencies: list[str] = field(default_factory=list)
    writes_code: bool = True
    attempts: list[Attempt] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)

    @property
    def attempts_used(self) -> int:
        return len(self.attempts)

    def as_dict(self) -> dict[str, Any]:
        return {
            "subtask_id": self.subtask_id,
            "title": self.title,
            "role": self.role,
            "tier": self.tier,
            "status": self.status,
            "dependencies": list(self.dependencies),
            "writes_code": self.writes_code,
            "attempts": [a.as_dict() for a in self.attempts],
            "changed_files": list(self.changed_files),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SubtaskRecord":
        return cls(
            subtask_id=str(d.get("subtask_id") or ""),
            title=str(d.get("title") or ""),
            role=str(d.get("role") or "dev"),
            tier=str(d.get("tier") or "midlevel"),
            status=str(d.get("status") or "pending"),
            dependencies=[str(x) for x in (d.get("dependencies") or [])],
            writes_code=bool(d.get("writes_code", True)),
            attempts=[Attempt.from_dict(a) for a in (d.get("attempts") or [])],
            changed_files=[str(x) for x in (d.get("changed_files") or [])],
        )


@dataclass
class GoalRecord:
    """One piece of work the CEO has taken ownership of.

    ``state`` is the supervisor's contract:
      * ``open``       — subtasks still running or pending.
      * ``closed``     — every subtask reached ``done``.
      * ``abandoned``  — the attempt budget or deadline was exhausted; a human
        needs to look. Deliberately distinct from ``closed`` so a failure can
        never be mistaken for success in the dashboard.
    """

    goal_id: str
    goal: str
    request: str = ""
    state: str = "open"
    complexity: str = "medium"
    domain: str = "general"
    strategy: str = "fallback"  # llm | fallback — how the split was produced
    #: Workspace the goal was originally executed against. A supervisor re-drive
    #: replays it so the intervention edits the same checkout the first attempt
    #: did, rather than falling back to the process working directory.
    workspace_root: str = ""
    #: Who the goal was run for. Replayed so a re-drive keeps the same task
    #: attribution. **Credentials are deliberately not stored** — a durable
    #: ledger is the wrong place for a token, and the constitution forbids
    #: writing secrets to disk. A re-drive therefore runs with the server's own
    #: repo access, not the original caller's; see the note in ``_redrive``.
    user_id: str = ""
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)
    #: Monotonic-ish wall clock of the last observed progress. The supervisor
    #: uses it to spot a goal that is "running" but has not moved in a long time.
    last_progress_at: float = field(default_factory=_now)
    subtasks: list[SubtaskRecord] = field(default_factory=list)
    #: How many times the supervisor has intervened on this goal. Bounded so a
    #: permanently broken goal cannot consume the agency's budget forever.
    interventions: int = 0
    verdict: str = ""
    notes: list[str] = field(default_factory=list)

    def subtask(self, subtask_id: str) -> SubtaskRecord | None:
        for s in self.subtasks:
            if s.subtask_id == subtask_id:
                return s
        return None

    @property
    def is_closed(self) -> bool:
        return self.state in CLOSED_STATES

    def progress(self) -> tuple[int, int]:
        """Return ``(done, total)`` subtask counts."""
        return sum(1 for s in self.subtasks if s.status == "done"), len(self.subtasks)

    def as_dict(self) -> dict[str, Any]:
        done, total = self.progress()
        return {
            "goal_id": self.goal_id,
            "goal": self.goal,
            "request": self.request[:4000],
            "state": self.state,
            "complexity": self.complexity,
            "domain": self.domain,
            "strategy": self.strategy,
            "workspace_root": self.workspace_root,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_progress_at": self.last_progress_at,
            "subtasks": [s.as_dict() for s in self.subtasks],
            "interventions": self.interventions,
            "verdict": self.verdict,
            "notes": self.notes[-20:],
            "progress": {"done": done, "total": total},
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "GoalRecord":
        return cls(
            goal_id=str(d.get("goal_id") or ""),
            goal=str(d.get("goal") or ""),
            request=str(d.get("request") or ""),
            state=str(d.get("state") or "open"),
            complexity=str(d.get("complexity") or "medium"),
            domain=str(d.get("domain") or "general"),
            strategy=str(d.get("strategy") or "fallback"),
            workspace_root=str(d.get("workspace_root") or ""),
            user_id=str(d.get("user_id") or ""),
            created_at=float(d.get("created_at") or _now()),
            updated_at=float(d.get("updated_at") or _now()),
            last_progress_at=float(d.get("last_progress_at") or _now()),
            subtasks=[SubtaskRecord.from_dict(s) for s in (d.get("subtasks") or [])],
            interventions=int(d.get("interventions") or 0),
            verdict=str(d.get("verdict") or ""),
            notes=[str(n) for n in (d.get("notes") or [])],
        )


# ── Store ─────────────────────────────────────────────────────────────────────


class CEOLedger:
    """Durable store for :class:`GoalRecord`s.

    Every method is best-effort and never raises. When no backend is reachable
    the ledger keeps goals in memory: the agency still runs and still
    micro-manages within the process, it just loses history on restart — the
    same degradation contract ``ScheduleStore`` uses.
    """

    def __init__(
        self,
        *,
        mongo_url: str | None = None,
        db_name: str | None = None,
        sqlite_path: str | None = None,
    ) -> None:
        self._mem: dict[str, dict[str, Any]] = {}
        self._mode = "memory"
        self._lock = threading.Lock()
        self._sqlite: sqlite3.Connection | None = None
        self._collection: Any = None

        if _backend() == "sqlite":
            self._init_sqlite(sqlite_path or _sqlite_path())
        else:
            self._init_mongo(mongo_url=mongo_url, db_name=db_name)

    # ── Backends ──────────────────────────────────────────────────────────

    def _init_mongo(self, *, mongo_url: str | None, db_name: str | None) -> None:
        try:
            import pymongo

            client = pymongo.MongoClient(
                mongo_url or _MONGO_URL,
                serverSelectionTimeoutMS=_selection_timeout_ms(),
            )
            client.admin.command("ping")  # fail fast into memory mode when offline
            self._collection = client[db_name or _DB_NAME][_COLLECTION]
            try:
                existing = self._collection.index_information() or {}
                if not any(
                    tuple(idx.get("key") or ()) == (("goal_id", 1),) for idx in existing.values()
                ):
                    self._collection.create_index([("goal_id", 1)], unique=True, background=True)
                if not any(
                    tuple(idx.get("key") or ()) == (("state", 1),) for idx in existing.values()
                ):
                    self._collection.create_index([("state", 1)], background=True)
            except Exception as exc:  # noqa: BLE001 — indexes are best-effort
                log.warning("CEOLedger index creation failed: %s", exc)
            self._mode = "mongo"
            log.info("CEOLedger: MongoDB-backed (durable across restarts)")
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "CEOLedger: Mongo unavailable (%s) — goals in-memory only "
                "(supervision still runs; history is lost on restart).",
                exc,
            )

    def _init_sqlite(self, sqlite_path: str) -> None:
        try:
            path = Path(sqlite_path)
            if sqlite_path != ":memory:":
                path.parent.mkdir(parents=True, exist_ok=True)
            # check_same_thread=False: written from the FastAPI loop and from
            # the supervisor thread. Every write is serialised on self._lock.
            self._sqlite = sqlite3.connect(str(path), check_same_thread=False)
            self._sqlite.execute("PRAGMA journal_mode=WAL")
            self._sqlite.execute("PRAGMA busy_timeout=5000")
            self._sqlite.execute(
                f"CREATE TABLE IF NOT EXISTS {_TBL} ("  # nosec B608 — _TBL is a constant
                "goal_id TEXT PRIMARY KEY,"
                "state   TEXT NOT NULL,"
                "doc     TEXT NOT NULL,"
                "updated_at REAL NOT NULL,"
                "last_progress_at REAL NOT NULL DEFAULT 0"
                ")"
            )
            # Existing databases predate the column; ADD COLUMN is a no-op
            # once it exists, so this migrates in place without a version check.
            try:
                self._sqlite.execute(
                    f"ALTER TABLE {_TBL} ADD COLUMN last_progress_at REAL NOT NULL DEFAULT 0"  # nosec B608 — _TBL is a constant
                )
            except sqlite3.OperationalError:
                pass  # column already present
            self._sqlite.execute(
                f"CREATE INDEX IF NOT EXISTS {_TBL}_progress_idx ON {_TBL} (state, last_progress_at)"  # nosec B608 — _TBL is a constant
            )
            self._sqlite.commit()
            self._mode = "sqlite"
            log.info("CEOLedger: SQLite-backed at %s", path)
        except Exception as exc:  # noqa: BLE001
            log.warning("CEOLedger: SQLite unavailable (%s) — goals in-memory only.", exc)

    @property
    def mode(self) -> str:
        return self._mode

    # ── Public API ────────────────────────────────────────────────────────

    def upsert(self, goal: GoalRecord) -> None:
        """Persist *goal*, stamping ``updated_at``."""
        goal.updated_at = _now()
        doc = goal.as_dict()
        if self._mode == "mongo":
            try:
                self._collection.replace_one({"goal_id": goal.goal_id}, doc, upsert=True)
                return
            except Exception as exc:  # noqa: BLE001
                log.warning("CEOLedger.upsert failed: %s", exc)
                return
        if self._mode == "sqlite" and self._sqlite is not None:
            try:
                with self._lock:
                    self._sqlite.execute(
                        f"INSERT OR REPLACE INTO {_TBL} (goal_id, state, doc, updated_at, last_progress_at) "  # nosec B608 — _TBL is a constant
                        "VALUES (?, ?, ?, ?, ?)",
                        (goal.goal_id, goal.state, json.dumps(doc), doc["updated_at"],
                         doc["last_progress_at"]),
                    )
                    self._sqlite.commit()
                return
            except Exception as exc:  # noqa: BLE001
                log.warning("CEOLedger.upsert (sqlite) failed: %s", exc)
                return
        self._mem[goal.goal_id] = doc

    def get(self, goal_id: str) -> GoalRecord | None:
        """Return one goal by id, or ``None``."""
        doc: dict[str, Any] | None = None
        if self._mode == "mongo":
            try:
                doc = self._collection.find_one({"goal_id": goal_id}, {"_id": 0})
            except Exception as exc:  # noqa: BLE001
                log.warning("CEOLedger.get failed: %s", exc)
                return None
        elif self._mode == "sqlite" and self._sqlite is not None:
            try:
                with self._lock:
                    cur = self._sqlite.execute(
                        f"SELECT doc FROM {_TBL} WHERE goal_id = ?", (goal_id,)  # nosec B608 — _TBL is a constant
                    )
                    row = cur.fetchone()
                doc = json.loads(row[0]) if row else None
            except Exception as exc:  # noqa: BLE001
                log.warning("CEOLedger.get (sqlite) failed: %s", exc)
                return None
        else:
            doc = self._mem.get(goal_id)
        return GoalRecord.from_dict(doc) if doc else None

    def open_goals(self, *, limit: int = 100) -> list[GoalRecord]:
        """Return goals the supervisor still owns, oldest progress first.

        Ordering by ``last_progress_at`` puts the most-stalled goal at the head
        of the sweep, so the goal most likely to be stuck is the one the
        supervisor looks at first even when the limit truncates the list.
        """
        docs: list[dict[str, Any]] = []
        if self._mode == "mongo":
            try:
                docs = list(
                    self._collection.find(
                        {"state": {"$nin": list(CLOSED_STATES)}}, {"_id": 0}
                    )
                    .sort("last_progress_at", 1)
                    .limit(limit)
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("CEOLedger.open_goals failed: %s", exc)
                return []
        elif self._mode == "sqlite" and self._sqlite is not None:
            try:
                with self._lock:
                    cur = self._sqlite.execute(
                        f"SELECT doc FROM {_TBL} WHERE state NOT IN ('closed','abandoned') "  # nosec B608 — _TBL is a constant
                        "ORDER BY last_progress_at ASC LIMIT ?",
                        (limit,),
                    )
                    rows = cur.fetchall()
                docs = [json.loads(r[0]) for r in rows]
            except Exception as exc:  # noqa: BLE001
                log.warning("CEOLedger.open_goals (sqlite) failed: %s", exc)
                return []
        else:
            docs = [d for d in self._mem.values() if d.get("state") not in CLOSED_STATES]
            docs.sort(key=lambda d: d.get("last_progress_at", 0.0))
            docs = docs[:limit]
        # Every backend now orders by last_progress_at inside the query, so
        # the limit keeps the most-stalled goals rather than truncating them
        # away. Re-sorting the returned page here would not have fixed that:
        # it only reorders rows the LIMIT already chose.
        return [GoalRecord.from_dict(d) for d in docs]

    def recent(self, *, limit: int = 25) -> list[GoalRecord]:
        """Return the most recently updated goals regardless of state."""
        docs: list[dict[str, Any]] = []
        if self._mode == "mongo":
            try:
                docs = list(
                    self._collection.find({}, {"_id": 0}).sort("updated_at", -1).limit(limit)
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("CEOLedger.recent failed: %s", exc)
                return []
        elif self._mode == "sqlite" and self._sqlite is not None:
            try:
                with self._lock:
                    cur = self._sqlite.execute(
                        f"SELECT doc FROM {_TBL} ORDER BY updated_at DESC LIMIT ?", (limit,)  # nosec B608 — _TBL is a constant
                    )
                    rows = cur.fetchall()
                docs = [json.loads(r[0]) for r in rows]
            except Exception as exc:  # noqa: BLE001
                log.warning("CEOLedger.recent (sqlite) failed: %s", exc)
                return []
        else:
            docs = sorted(self._mem.values(), key=lambda d: d.get("updated_at", 0.0), reverse=True)[
                :limit
            ]
        return [GoalRecord.from_dict(d) for d in docs]

    def claim_intervention(self, goal_id: str, *, expected: int) -> bool:
        """Atomically bump ``interventions`` from *expected* to *expected + 1*.

        Returns ``True`` only for the caller that won the race; everyone else
        gets ``False`` and must not start work.

        This exists because the supervisor's in-process ``_driving`` set is not
        enough. ``RUN_BACKGROUND_IN_WEB`` defaults to true, so a deployment that
        also runs the dedicated worker has **two** processes sweeping the same
        shared ledger. Both would classify the same stalled goal, both would
        spawn a re-drive, and the intervention counter would race — duplicating
        edits and doubling token spend on exactly the goals already in trouble.
        A compare-and-set on the shared store is the only claim both processes
        can see.
        """
        now = _now()
        if self._mode == "mongo":
            try:
                res = self._collection.update_one(
                    {"goal_id": goal_id, "interventions": expected},
                    {"$inc": {"interventions": 1}, "$set": {"last_progress_at": now}},
                )
                return bool(res.matched_count)
            except Exception as exc:  # noqa: BLE001
                log.warning("CEOLedger.claim_intervention failed: %s", exc)
                return False
        if self._mode == "sqlite" and self._sqlite is not None:
            try:
                with self._lock:
                    # BEGIN IMMEDIATE takes the write lock up front, so a second
                    # process reading the same file cannot interleave between the
                    # read and the write below.
                    self._sqlite.execute("BEGIN IMMEDIATE")
                    try:
                        cur = self._sqlite.execute(
                            f"SELECT doc FROM {_TBL} WHERE goal_id = ?", (goal_id,)  # nosec B608 — _TBL is a constant
                        )
                        row = cur.fetchone()
                        if not row:
                            self._sqlite.execute("ROLLBACK")
                            return False
                        doc = json.loads(row[0])
                        if int(doc.get("interventions") or 0) != expected:
                            self._sqlite.execute("ROLLBACK")
                            return False
                        doc["interventions"] = expected + 1
                        doc["last_progress_at"] = now
                        doc["updated_at"] = now
                        self._sqlite.execute(
                            f"UPDATE {_TBL} SET doc = ?, updated_at = ?, last_progress_at = ? "  # nosec B608 — _TBL is a constant
                            "WHERE goal_id = ?",
                            (json.dumps(doc), now, now, goal_id),
                        )
                        self._sqlite.execute("COMMIT")
                        return True
                    except Exception:
                        self._sqlite.execute("ROLLBACK")
                        raise
            except Exception as exc:  # noqa: BLE001
                log.warning("CEOLedger.claim_intervention (sqlite) failed: %s", exc)
                return False
        doc = self._mem.get(goal_id)
        if doc is None or int(doc.get("interventions") or 0) != expected:
            return False
        doc["interventions"] = expected + 1
        doc["last_progress_at"] = now
        return True

    def stats(self) -> dict[str, Any]:
        """Aggregate counts for the dashboard and the health endpoint."""
        recent = self.recent(limit=200)
        by_state: dict[str, int] = {}
        for g in recent:
            by_state[g.state] = by_state.get(g.state, 0) + 1
        open_goals = [g for g in recent if not g.is_closed]
        stalest = min((g.last_progress_at for g in open_goals), default=None)
        return {
            "mode": self._mode,
            "sampled": len(recent),
            "by_state": by_state,
            "open": len(open_goals),
            "oldest_open_progress_age_s": (round(_now() - stalest, 1) if stalest else None),
        }


# ── Singleton ─────────────────────────────────────────────────────────────────

_ledger: CEOLedger | None = None
_ledger_lock = threading.Lock()


def get_ceo_ledger() -> CEOLedger:
    """Return the shared :class:`CEOLedger`, constructing it on first use."""
    global _ledger
    if _ledger is None:
        with _ledger_lock:
            if _ledger is None:
                _ledger = CEOLedger()
    return _ledger


def reset_ceo_ledger() -> None:
    """Drop the singleton (test helper)."""
    global _ledger
    with _ledger_lock:
        _ledger = None
