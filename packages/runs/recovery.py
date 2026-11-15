"""packages/runs/recovery.py — take over crashed task runs, wake parked parents, enforce deadlines.

``RecoveryService.tick()`` runs from the task dispatcher's poll loop (at the
``RUNS_RECOVERY_TICK_SEC`` cadence) when ``RUNS_RECOVERY_ENABLED`` is on and the
kill switch is off. Each tick (plan section 2.3):

1. **Abandoned runs.** A task run in an active state whose lease is expired or
   absent, and whose record has not changed for a whole TTL, is claimed (a new,
   higher fencing token), moved to ``recovering`` and its side effect ledger
   reconciled. An operation with an unknown outcome parks the run in
   ``waiting_for_approval`` (reason ``uncertain_side_effect``) and its task at the
   execution approval gate. Otherwise the attempt is counted: past
   ``RUNS_MAX_ATTEMPTS`` the run is dead lettered and its task failed; below it
   the run is queued with an exponential backoff (``not_before``). The lease is
   released at the end either way.
2. **Parked parents.** A run in ``waiting_for_agent`` whose children are all
   terminal is queued again (level triggered: a crash between a child's final
   write and the wake cannot strand the parent).
3. **Deadlines.** A non terminal run past ``deadline_at`` is timed out and its
   cancel requested.
4. **Due requeues.** A queued run whose ``not_before`` has passed gets its task
   put back on the dispatch queue, the same way the stranded task reconciler
   does it (``TODO``, ``pending_agent_run``).

Runs without a ``task_id`` (orchestrator mirrors) hold no lease in phase 2 and
are left alone. Memory mode has no shared lease and recovers nothing.
"""
from __future__ import annotations

import logging
import os
import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from packages.config import runs_settings
from packages.runs.lease import RunLease, remaining_s
from packages.runs.models import TERMINAL_STATES, RunRecord, RunState
from packages.runs.operations import UNKNOWN, OperationLedger, ReconcileResult
from packages.runs.store import RunStore
from packages.runs.task_binding import final_state, run_store_for, walk

log = logging.getLogger("qwen-proxy")

ACTOR = "system:run-recovery"
_ACTIVE = (RunState.STARTING, RunState.RUNNING, RunState.VERIFYING, RunState.RECOVERING)
_NON_TERMINAL = tuple(s for s in RunState if s not in TERMINAL_STATES)
_SETTLED_TASK = frozenset({"done", "in_review", "failed", "blocked", "wont_do"})
_SCAN_LIMIT = 200


@dataclass
class RecoveryReport:
    """What one tick did (run ids per outcome)."""

    skipped: str | None = None
    recovered: list[str] = field(default_factory=list)
    parked: list[str] = field(default_factory=list)
    dead_lettered: list[str] = field(default_factory=list)
    settled: list[str] = field(default_factory=list)
    woken: list[str] = field(default_factory=list)
    timed_out: list[str] = field(default_factory=list)
    requeued: list[str] = field(default_factory=list)


def backoff_s(attempt: int, *, rand: Callable[[], float] = random.random) -> float:
    """Wait before attempt *attempt* (2 and up): ``base * 2^(attempt-2)`` plus up to 25% jitter."""
    base = runs_settings.retry_backoff_base_s()
    if base <= 0:
        return 0.0
    return min(base * 2 ** max(attempt - 2, 0), 24 * 3600) * (1 + 0.25 * rand())


class RecoveryService:
    """Recovers the task runs of one task store's backend."""

    def __init__(self, task_store: Any, *, run_store: RunStore | None = None,
                 clock: Callable[[], float] = time.time, holder: str | None = None) -> None:
        from packages.runs.reconcilers import register_builtin_reconcilers

        register_builtin_reconcilers()
        self._tasks = task_store
        self._runs = run_store or run_store_for(task_store)
        self._lease = RunLease(getattr(task_store, "_db", None))
        self._ledger = OperationLedger(self._runs)
        self._clock = clock
        self.holder = holder or f"recovery-{os.getpid()}-{uuid.uuid4().hex[:8]}"

    async def tick(self, now: float | None = None) -> RecoveryReport:
        """One recovery pass (see the module docstring). Never raises."""
        report = RecoveryReport()
        from packages.config.autonomy_limits import kill_switch_engaged

        if not runs_settings.runs_recovery_enabled():
            report.skipped = "disabled"
        elif kill_switch_engaged():
            report.skipped = "kill_switch"
        elif not self._lease.durable:
            report.skipped = "no_durable_lease"
        if report.skipped:
            return report
        now = self._clock() if now is None else now
        for step in (self._recover_abandoned, self._wake_parked_parents,
                     self._enforce_deadlines, self._requeue_due):
            try:
                await step(now, report)
            except Exception:
                log.warning("run recovery: %s failed", step.__name__, exc_info=True)
        return report

    async def _scan(self, states: tuple[RunState, ...]) -> list[RunRecord]:
        runs: list[RunRecord] = []
        for state in states:
            runs.extend(await self._runs.list(state=state, limit=_SCAN_LIMIT))
        return runs

    async def _lease_live(self, task_id: str, now: float) -> bool:
        return remaining_s(await self._lease.current(task_id), now) > 0

    # ── 1. abandoned runs ─────────────────────────────────────────────────────

    async def _recover_abandoned(self, now: float, report: RecoveryReport) -> None:
        ttl = runs_settings.lease_ttl_s()
        for run in await self._scan(_ACTIVE):
            if not run.task_id or run.updated_at > now - ttl:
                continue
            if await self._lease_live(run.task_id, now):
                continue
            try:
                await self._recover_one(run, now, report)
            except Exception:
                log.warning("run recovery: could not recover run %s", run.run_id, exc_info=True)

    async def _recover_one(self, run: RunRecord, now: float, report: RecoveryReport) -> None:
        task_id = str(run.task_id)
        token = await self._lease.acquire(task_id, self.holder, runs_settings.lease_ttl_s(),
                                          run.run_id, now=now)
        if token is None:
            return  # another worker or recovery got there first
        try:
            await self._runs.update(run.run_id, {"lease_token": token})
            if run.state is not RunState.RECOVERING:
                await self._runs.transition(run.run_id, RunState.RECOVERING, token=token,
                                            reason="lease_expired", actor=ACTOR)
            log.warning("run recovery: took over run %s of task %s (token %s)", run.run_id,
                        task_id, token)
            task = await self._tasks.get(task_id)
            if task is None:
                await walk(self._runs, run.run_id, RunState.FAILED, token=token,
                           reason="task deleted", actor=ACTOR)
                return
            if await self._settle_from_task(run, task, token, report):
                return
            result = await self._ledger.reconcile_run(run.run_id, now=now)
            if result.must_park:
                await self._park(run, task, token, result, report)
            else:
                fresh = await self._runs.get(run.run_id) or run
                await self._retry(fresh, task, token, now, report)
        finally:
            await self._lease.release(task_id, self.holder, token)

    async def _settle_from_task(self, run: RunRecord, task: Any, token: int,
                                report: RecoveryReport) -> bool:
        """The worker died after writing the task's final state: settle the run to match."""
        if getattr(task.status, "value", task.status) not in _SETTLED_TASK:
            return False
        state, reason = final_state(task)
        if state is not None:
            await walk(self._runs, run.run_id, state, token=token, reason=reason, actor=ACTOR)
        report.settled.append(run.run_id)
        return True

    async def _park(self, run: RunRecord, task: Any, token: int, result: ReconcileResult,
                    report: RecoveryReport) -> None:
        await self._runs.transition(run.run_id, RunState.WAITING_FOR_APPROVAL, token=token,
                                    reason="uncertain_side_effect", actor=ACTOR)
        unknown = [o.op_id for o in result.outcomes if o.outcome == UNKNOWN]
        await self._runs.append_event(run.run_id, "parked", {
            "reason": "uncertain_side_effect", "operations": unknown}, actor=ACTOR)
        # The execution approval gate: no dispatcher or reconciler picks it up
        # until a person approves (TaskWorkflowService.approve_execution).
        task.requires_approval = True
        task.execution_approved = False
        task.pending_agent_run = False
        task.review_reason = ("⏸ Awaiting human approval: a side effect of the crashed run "
                              "has an unknown outcome.")
        task.add_log("Run recovery parked the task: a side effect of the crashed run has an "
                     "unknown outcome; check it, then approve to resume.", level="warning",
                     event_type="run_parked", actor=ACTOR, task_status=task.status,
                     metadata={"run_id": run.run_id, "operations": unknown})
        await self._tasks.update(task)
        report.parked.append(run.run_id)

    async def _retry(self, run: RunRecord, task: Any, token: int, now: float,
                     report: RecoveryReport) -> None:
        attempt = run.attempt + 1
        if attempt > runs_settings.max_attempts():
            await self._dead_letter(run, task, token, report)
            return
        not_before = now + backoff_s(attempt)
        history = run.recovery_history + [{"at": now, "token": token, "attempt": attempt,
                                           "reason": "lease_expired"}]
        await self._runs.update(run.run_id, {"attempt": attempt, "not_before": not_before,
                                             "recovery_history": history}, token=token)
        await self._runs.transition(run.run_id, RunState.QUEUED, token=token, reason="recovered",
                                    actor=ACTOR)
        report.recovered.append(run.run_id)
        if not_before <= now:
            await self._requeue(run.run_id, task, report)

    async def _dead_letter(self, run: RunRecord, task: Any, token: int,
                           report: RecoveryReport) -> None:
        reason = f"dead letter: {run.attempt} attempts used (RUNS_MAX_ATTEMPTS)"
        await walk(self._runs, run.run_id, RunState.FAILED, token=token, reason=reason, actor=ACTOR)
        await self._runs.transition(run.run_id, RunState.DEAD_LETTER, token=token, reason=reason,
                                    actor=ACTOR)
        task.status = _task_status("failed")
        task.pending_agent_run = False
        task.error_message = f"Run {run.run_id} dead lettered after {run.attempt} attempts."
        # At the cap, so neither the FAILED reconciler pass nor the blocked
        # auto retry starts it again behind the dead letter's back.
        task.auto_retry_count = max(task.auto_retry_count, runs_settings.task_auto_retry_cap())
        task.add_log(task.error_message, level="error", event_type="dead_letter", actor=ACTOR,
                     task_status=task.status, metadata={"run_id": run.run_id})
        await self._tasks.update(task)
        report.dead_lettered.append(run.run_id)

    async def _requeue(self, run_id: str, task: Any, report: RecoveryReport) -> None:
        """Put the task back on the dispatch queue (as the stranded task reconciler does)."""
        task.status = _task_status("todo")
        task.pending_agent_run = True
        task.current_run_id = run_id
        task.waiting_on_children = False
        task.add_log(f"Task re-queued by run recovery (run {run_id})", event_type="reconciled",
                     actor=ACTOR, task_status=task.status)
        await self._tasks.update(task)
        await self._runs.update(run_id, {"not_before": None})
        report.requeued.append(run_id)

    # ── 2-4. parked parents, deadlines, due requeues ──────────────────────────

    async def _wake_parked_parents(self, now: float, report: RecoveryReport) -> None:
        for run in await self._scan((RunState.WAITING_FOR_AGENT,)):
            children = await self._runs.list(parent_run_id=run.run_id, limit=500)
            if not children or not all(c.is_terminal for c in children):
                continue
            await self._runs.update(run.run_id, {"not_before": now})
            await self._runs.transition(run.run_id, RunState.QUEUED, reason="children_terminal",
                                        actor=ACTOR)
            report.woken.append(run.run_id)

    async def _enforce_deadlines(self, now: float, report: RecoveryReport) -> None:
        for run in await self._scan(_NON_TERMINAL):
            if run.deadline_at is None or run.deadline_at >= now:
                continue
            await self._runs.update(run.run_id, {"cancel_requested": True})
            await walk(self._runs, run.run_id, RunState.TIMED_OUT, token=None,
                       reason="deadline passed", actor=ACTOR)
            report.timed_out.append(run.run_id)
            task = await self._tasks.get(run.task_id) if run.task_id else None
            if task is not None and task.waiting_on_children:
                task.waiting_on_children = False
                task.status = _task_status("failed")
                task.error_message = f"Run {run.run_id} passed its deadline."
                task.add_log(task.error_message, level="error", event_type="run_timed_out",
                             actor=ACTOR, task_status=task.status)
                await self._tasks.update(task)

    async def _requeue_due(self, now: float, report: RecoveryReport) -> None:
        for run in await self._scan((RunState.QUEUED,)):
            if run.not_before is None or run.not_before > now or not run.task_id:
                continue
            if await self._lease_live(run.task_id, now):
                continue
            task = await self._tasks.get(run.task_id)
            if task is not None:
                await self._requeue(run.run_id, task, report)


def _task_status(value: str) -> Any:
    from tasks.models import TaskStatus

    return TaskStatus(value)
