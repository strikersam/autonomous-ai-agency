"""packages/runs/store.py — durable runs, their timelines and idempotency keys.

``RunStore`` sits on the shared storage backend (``packages.storage.factory``,
Mongo or SQLite) or, with no backend, on process local memory for tests. Every
write that must not interleave is one atomic operation (``packages/runs/backend.py``):

* ``create`` inserts if absent on ``run_id``.
* ``update`` with a ``token`` applies only while the run's ``lease_token`` still
  equals it, so a worker whose lease was taken over cannot overwrite the run.
* ``append_event`` and ``next_op_seq`` take their sequence numbers from an
  atomic increment on the run, monotonic and never reused across attempts.
* Idempotency keys insert if absent on ``"<company_id>:<key>"``.

Event data and failure reasons are passed through ``redact_secrets`` first.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from packages.lifecycle.registry import get_machine
from packages.runs.backend import MemoryTable, ensure_index, table_for
from packages.runs.models import TERMINAL_STATES, RunEvent, RunRecord, RunState
from packages.runs.redaction import redact_value
from packages.storage.state_persistence import EXPIRES_TS, expiry_fields

log = logging.getLogger("qwen-proxy")

RUNS = "runs"
RUN_EVENTS = "run_events"
RUN_OPERATIONS = "run_operations"
RUN_IDEMPOTENCY = "run_idempotency"
IDEMPOTENCY_TTL_S = 24 * 3600
_IMMUTABLE = frozenset({"_id", "run_id", "op_seq", "event_seq", "schema_version"})


def _plain(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value


class FencedOut(RuntimeError):
    """A write was refused because a newer lease token owns the run."""


class RunStore:
    """Runs, events and idempotency keys over one storage backend (``None`` = memory)."""

    def __init__(self, db: Any = None) -> None:
        self._db = db
        self._memory: dict[str, MemoryTable] = {}
        self.runs = table_for(db, RUNS, self._memory)
        self.events = table_for(db, RUN_EVENTS, self._memory)
        self.operations = table_for(db, RUN_OPERATIONS, self._memory)
        self.idempotency = table_for(db, RUN_IDEMPOTENCY, self._memory)
        self._indexed = False

    @property
    def backend(self) -> str:
        """``mongo``, ``sqlite`` or ``memory``."""
        return self.runs.kind

    async def ensure_indexes(self) -> None:
        """Create the Mongo indexes (no op elsewhere). Idempotent; never raises."""
        db = self._db
        await ensure_index(db, RUNS, [("company_id", 1), ("state", 1)])
        await ensure_index(db, RUNS, [("task_id", 1)])
        await ensure_index(db, RUNS, [("parent_run_id", 1)])
        await ensure_index(db, RUN_EVENTS, [("run_id", 1), ("seq", 1)], unique=True)
        await ensure_index(db, RUN_OPERATIONS, [("run_id", 1), ("seq", 1)], unique=True)
        await ensure_index(db, RUN_IDEMPOTENCY, [("company_id", 1), ("key", 1)], unique=True)
        await ensure_index(db, RUN_IDEMPOTENCY, [("expires_at", 1)], expireAfterSeconds=0)
        self._indexed = True

    async def _ready(self) -> None:
        if not self._indexed:
            await self.ensure_indexes()

    async def create(self, run: RunRecord) -> RunRecord:
        """Store *run* unless its ``run_id`` exists; return the stored record either way."""
        await self._ready()
        if run.failure_reason:
            run.failure_reason = redact_value(run.failure_reason)
        if await self.runs.insert_if_absent(run.run_id, run.to_doc()):
            await self.append_event(run.run_id, "created", {"state": run.state.value})
            return run
        existing = await self.get(run.run_id)
        return existing if existing is not None else run

    async def get(self, run_id: str) -> RunRecord | None:
        """The run, or ``None``."""
        doc = await self.runs.get(run_id)
        return RunRecord.model_validate(doc) if doc else None

    async def list(self, *, company_id: str | None = None, state: RunState | str | None = None,
                   parent_run_id: str | None = None, task_id: str | None = None,
                   limit: int = 50) -> list[RunRecord]:
        """Runs matching every given filter, newest first."""
        query = {k: _plain(v) for k, v in {
            "company_id": company_id, "state": state, "parent_run_id": parent_run_id,
            "task_id": task_id,
        }.items() if v is not None}
        docs = await self.runs.find(query, sort="created_at", descending=True,
                                    limit=max(1, min(int(limit), 500)))
        return [RunRecord.model_validate(d) for d in docs]

    async def update(self, run_id: str, fields: dict[str, Any], *, token: int | None = None,
                     expect: dict[str, Any] | None = None) -> bool:
        """Set *fields* on the run; with *token*, only while ``lease_token == token``.

        Returns False when the run is missing or the fence (or *expect*) did not hold.
        """
        values = {k: _plain(v) for k, v in fields.items() if k not in _IMMUTABLE}
        if "failure_reason" in values and values["failure_reason"]:
            values["failure_reason"] = redact_value(values["failure_reason"])
        values["updated_at"] = time.time()
        conditions = dict(expect or {})
        if token is not None:
            conditions["lease_token"] = token
        return await self.runs.compare_and_set(run_id, conditions, values)

    async def transition(self, run_id: str, to_state: RunState, *, token: int | None = None,
                         reason: str | None = None, actor: str | None = None) -> RunRecord:
        """Move the run to *to_state* if the ``run`` lifecycle allows it.

        Raises ``IllegalTransition`` for an undeclared move, ``KeyError`` for an
        unknown run and ``FencedOut`` when the token or the state changed under us.
        """
        run = await self.get(run_id)
        if run is None:
            raise KeyError(run_id)
        get_machine("run").require(run.state.value, to_state.value)
        now = time.time()
        fields: dict[str, Any] = {"state": to_state}
        if to_state in TERMINAL_STATES:
            fields["completed_at"] = now
        if to_state is RunState.RUNNING and run.started_at is None:
            fields["started_at"] = now
        if reason and to_state in (RunState.FAILED, RunState.TIMED_OUT, RunState.DEAD_LETTER):
            fields["failure_reason"] = reason
        if to_state in (RunState.WAITING_FOR_AGENT, RunState.WAITING_FOR_APPROVAL):
            fields["waiting_reason"] = reason
        if not await self.update(run_id, fields, token=token, expect={"state": run.state.value}):
            raise FencedOut(f"run {run_id}: state or lease changed; transition refused")
        await self.append_event(run_id, "state_changed", {
            "from": run.state.value, "to": to_state.value, "reason": reason,
        }, actor=actor)
        updated = await self.get(run_id)
        assert updated is not None
        return updated

    async def append_event(self, run_id: str, kind: str, data: dict[str, Any] | None = None,
                           actor: str | None = None) -> RunEvent:
        """Append one event with the run's next ``seq``. ``KeyError`` for an unknown run."""
        seq = await self.runs.increment(run_id, "event_seq")
        if seq is None:
            raise KeyError(run_id)
        event = RunEvent(event_id=f"{run_id}:{seq}", run_id=run_id, seq=seq, kind=kind,
                         actor=actor, data=redact_value(dict(data or {})))
        await self.events.insert_if_absent(event.event_id, event.model_dump(mode="json"))
        return event

    async def list_events(self, run_id: str, after_seq: int = 0, limit: int = 100) -> list[RunEvent]:
        """Events with ``seq > after_seq``, oldest first."""
        docs = await self.events.find({"run_id": run_id}, sort="seq")
        events = [RunEvent.model_validate(d) for d in docs if int(d.get("seq", 0)) > after_seq]
        return events[: max(1, min(int(limit), 1000))]

    async def next_op_seq(self, run_id: str) -> int:
        """The run's next operation sequence number. ``KeyError`` for an unknown run."""
        seq = await self.runs.increment(run_id, "op_seq")
        if seq is None:
            raise KeyError(run_id)
        return seq

    async def get_or_create(self, company_id: str, key: str, run_factory: Callable[[], RunRecord],
                            *, ttl_s: float = IDEMPOTENCY_TTL_S) -> tuple[RunRecord, bool]:
        """The run bound to idempotency *key* in *company_id*, creating it once.

        Returns ``(run, created)``. Keys are scoped per company, so two tenants
        never share a run. An expired key is rebound to a new run.
        """
        await self._ready()
        doc_id = f"{company_id}:{key}"
        now = time.time()
        run = run_factory()
        run.company_id, run.idempotency_key = company_id, key
        if await self.idempotency.insert_if_absent(doc_id, self._key_doc(company_id, key, run.run_id, now, ttl_s)):
            return await self.create(run), True
        bound = await self.idempotency.get(doc_id) or {}
        old = bound.get("run_id")
        if float(bound.get(EXPIRES_TS) or 0) < now:
            rebound = await self.idempotency.compare_and_set(
                doc_id, {"run_id": old, EXPIRES_TS: ("lt", now)},
                self._key_doc(company_id, key, run.run_id, now, ttl_s),
            )
            if rebound:
                return await self.create(run), True
            old = (await self.idempotency.get(doc_id) or {}).get("run_id", old)
        existing = await self.get(old) if old else None
        if existing is None and old:
            # The creator stopped between binding the key and storing the run.
            run.run_id = old
            existing = await self.create(run)
        return existing or run, False

    @staticmethod
    def _key_doc(company_id: str, key: str, run_id: str, now: float, ttl_s: float) -> dict[str, Any]:
        # expires_at is a datetime for the Mongo TTL index; the numeric twin is what
        # every backend compares (SQLite stores the datetime as a string).
        expires = expiry_fields(datetime.fromtimestamp(now + ttl_s, tz=timezone.utc))
        return {"company_id": company_id, "key": key, "run_id": run_id, "created_at": now, **expires}


_store: RunStore | None = None


def get_run_store() -> RunStore:
    """The process wide ``RunStore``: memory under tests, the shared backend otherwise."""
    global _store
    if _store is None:
        from packages.config import settings

        if settings.is_testing:
            _store = RunStore()
        else:
            from packages.storage.factory import get_storage

            _store = RunStore(get_storage())
    return _store


def set_run_store(store: RunStore | None) -> None:
    """Replace (or with ``None`` reset) the process wide store; for startup and tests."""
    global _store
    _store = store
