"""packages/runs/operations.py — the durable side effect ledger of a run.

Every side effecting call writes an ``OperationRecord`` keyed by ``(run_id, seq)``
(``seq`` from the run's atomic counter, so it is never reused across attempts).
``action_hash(tool, args)`` is an attribute, not the key, so legitimate repeats
of one call get their own records.

Executing a side effect (plan section 2.3):

1. The caller renews its lease and passes the time left; ``begin`` refuses when
   it is not more than the operation's timeout.
2. ``begin`` inserts the record as ``pending``, moves it to ``executing`` with the
   token and ``op_deadline = now + op_timeout + skew``, then checks the run is
   still fenced to that token. Any failure raises ``FencedOut``.
3. The caller re-checks ``now < op_deadline``, performs the effect under a hard
   timeout, then calls ``commit`` or ``fail``.

Recovering a run (``reconcile_run``): ``pending`` records never started and are
marked failed; ``executing`` records before their deadline are ``unknown`` (the
old holder may still be inside the call); after it, the tool's registered
reconciler decides. ``not_done`` is honoured only from a reconciler declared
``repeat_safe``. Any ``unknown`` means the run must park for a person.
"""
from __future__ import annotations

import inspect
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Union

from agent.action_hash import action_hash
from packages.config import runs_settings
from packages.runs.models import OperationRecord, OperationState
from packages.runs.redaction import redact_value
from packages.runs.store import FencedOut, RunStore

log = logging.getLogger("qwen-proxy")

DONE, NOT_DONE, UNKNOWN, NOT_STARTED = "done", "not_done", "unknown", "not_started"
_OUTCOMES = frozenset({DONE, NOT_DONE, UNKNOWN})

ReconcileFn = Callable[[OperationRecord], Union[str, Awaitable[str]]]


@dataclass(frozen=True)
class Reconciler:
    """Asks the outside world whether an operation took effect."""

    fn: ReconcileFn
    repeat_safe: bool = False


_RECONCILERS: dict[str, Reconciler] = {}


def register_reconciler(tool: str, fn: ReconcileFn, *, repeat_safe: bool = False) -> None:
    """Register the reconciler for *tool*; ``repeat_safe`` only when the remote end makes a repeat a no op."""
    _RECONCILERS[tool] = Reconciler(fn=fn, repeat_safe=repeat_safe)


def unregister_reconciler(tool: str) -> None:
    """Remove *tool*'s reconciler (tests and teardown)."""
    _RECONCILERS.pop(tool, None)


def ledger_enabled() -> bool:
    """The live ``RUNS_LEDGER_ENABLED`` control (default on)."""
    return runs_settings.runs_ledger_enabled()


@dataclass(frozen=True)
class OpOutcome:
    """What recovery decided for one operation."""

    op_id: str
    tool: str
    outcome: str


@dataclass
class ReconcileResult:
    """Every outcome of ``reconcile_run``; ``must_park`` when any is unknown."""

    outcomes: list[OpOutcome] = field(default_factory=list)

    @property
    def must_park(self) -> bool:
        """True when the run must wait for a person (reason ``uncertain_side_effect``)."""
        return any(o.outcome == UNKNOWN for o in self.outcomes)


class OperationLedger:
    """Writes and reconciles a run's ``OperationRecord``s through a ``RunStore``."""

    def __init__(self, store: RunStore) -> None:
        self._store = store
        self._ops = store.operations

    async def begin(self, run_id: str, tool: str, args: Any, target: dict[str, Any] | None,
                    token: int, op_timeout_s: float, *, lease_remaining_s: float,
                    now: float | None = None) -> OperationRecord:
        """Record a side effect about to run and move it to ``executing``; see the module doc."""
        if lease_remaining_s <= op_timeout_s:
            raise FencedOut(f"run {run_id}: lease has {lease_remaining_s:.0f}s left, "
                            f"operation needs {op_timeout_s:.0f}s")
        now = time.time() if now is None else now
        seq = await self._store.next_op_seq(run_id)
        op = OperationRecord(op_id=OperationRecord.make_id(run_id, seq), run_id=run_id, seq=seq,
                             tool=tool, action_hash=action_hash(tool, args),
                             target=redact_value(dict(target or {})), token=token,
                             created_at=now, updated_at=now)
        if not await self._ops.insert_if_absent(op.op_id, op.to_doc()):
            raise FencedOut(f"operation {op.op_id} already exists")
        deadline = now + op_timeout_s + runs_settings.op_skew_s()
        moved = await self._ops.compare_and_set(
            op.op_id, {"state": OperationState.PENDING.value},
            {"state": OperationState.EXECUTING.value, "token": token, "op_deadline": deadline,
             "updated_at": now},
        )
        if not moved:
            raise FencedOut(f"operation {op.op_id} changed before it started")
        if not await self._store.update(run_id, {}, token=token):
            await self.fail(op.model_copy(update={"state": OperationState.EXECUTING}),
                            "fenced out before the effect started")
            raise FencedOut(f"run {run_id}: lease token {token} is no longer current")
        return op.model_copy(update={"state": OperationState.EXECUTING, "op_deadline": deadline})

    async def commit(self, op: OperationRecord, result_ref: str | None = None) -> bool:
        """Mark an executing operation committed; False if it was settled meanwhile."""
        return await self._ops.compare_and_set(
            op.op_id, {"state": OperationState.EXECUTING.value},
            {"state": OperationState.COMMITTED.value, "result_ref": result_ref,
             "updated_at": time.time()},
        )

    async def fail(self, op: OperationRecord, error: str) -> bool:
        """Mark a pending or executing operation failed (it may run again)."""
        return await self._ops.compare_and_set(
            op.op_id, {},
            {"state": OperationState.FAILED.value, "error": redact_value(str(error)),
             "updated_at": time.time()},
            any_of=[{"state": OperationState.PENDING.value},
                    {"state": OperationState.EXECUTING.value}],
        )

    async def list(self, run_id: str) -> list[OperationRecord]:
        """Every operation of the run, by ``seq``."""
        docs = await self._ops.find({"run_id": run_id}, sort="seq")
        return [OperationRecord.model_validate(d) for d in docs]

    async def should_skip_replay(self, run_id: str, tool: str, args: Any, occurrence_k: int) -> bool:
        """True when the k-th call (1 based) with this action already committed k times."""
        digest = action_hash(tool, args)
        committed = sum(1 for op in await self.list(run_id)
                        if op.action_hash == digest and op.state is OperationState.COMMITTED)
        return committed >= occurrence_k

    async def reconcile_run(self, run_id: str, now: float | None = None) -> ReconcileResult:
        """Settle every pending or executing operation of the run before it resumes."""
        now = time.time() if now is None else now
        result = ReconcileResult()
        for op in await self.list(run_id):
            if op.state is OperationState.PENDING:
                await self.fail(op, "never started; recovered")
                result.outcomes.append(OpOutcome(op.op_id, op.tool, NOT_STARTED))
            elif op.state is OperationState.EXECUTING:
                outcome = await self._reconcile_executing(op, now)
                result.outcomes.append(OpOutcome(op.op_id, op.tool, outcome))
        return result

    async def _reconcile_executing(self, op: OperationRecord, now: float) -> str:
        if op.op_deadline is None or now < op.op_deadline:
            return UNKNOWN  # the old holder may still be inside the call
        outcome = await _ask(op)
        if outcome == DONE:
            await self.commit(op, op.result_ref or "reconciled")
            return DONE
        if outcome == NOT_DONE:
            await self.fail(op, "reconciled: not done")
            return NOT_DONE
        return UNKNOWN


async def _ask(op: OperationRecord) -> str:
    """The registered reconciler's answer, coerced to ``unknown`` when it cannot be trusted."""
    reconciler = _RECONCILERS.get(op.tool)
    if reconciler is None:
        return UNKNOWN
    try:
        answer = reconciler.fn(op)
        if inspect.isawaitable(answer):
            answer = await answer
    except Exception:
        log.warning("reconciler for %s failed on %s; treating as unknown", op.tool, op.op_id,
                    exc_info=True)
        return UNKNOWN
    if answer not in _OUTCOMES:
        return UNKNOWN
    if answer == NOT_DONE and not reconciler.repeat_safe:
        return UNKNOWN
    return answer
