"""packages/runs/composer.py — persistence aware composition of runs. Not an engine.

A composition is a root run whose children are ordinary tasks, each with its own
child ``RunRecord`` (``parent_run_id``, ``root_run_id``, ``depth + 1``). The composer
decides order, concurrency and failure handling; the work itself runs through a
``ChildExecutor`` (default: ``TaskExecutionCoordinator`` via ``composer_tasks``).

* Steps run in sequence or in parallel (at most ``RUNS_MAX_PARALLEL`` at once);
  a group's failure policy is fail_fast, continue, require_all or quorum.
* A conditional step runs only when its condition holds over earlier results.
* An approval step parks the parent in ``waiting_for_approval``; ``approve`` records
  the decision and ``run`` again resumes it.
* A guardian watches the parent: a cancel request, the kill switch or the deadline
  cancels every outstanding child. Each child also watches itself.
* A spawn past ``RUNS_MAX_CHILDREN`` or ``RUNS_MAX_DEPTH`` is refused, with an event.
* Restart safe: a child's run id derives from ``(parent, step key)``, so running the
  composition again finds the finished children and reuses their recorded results.
* Every spawn and settle writes a run event; every child charges the root budget.
* A composition of the root run reserves each child's estimated cost on the root cap before
  the child starts (``budget.try_reserve``; estimate rule in ``budget.py``). A child that does
  not fit waits for in flight children to release; with none in flight it is cancelled with a
  ``budget_exhausted`` event and the composition ends failed, budget exhausted.
* When the composer cancels a child's in-process work it also settles that child's
  non terminal descendants (cancelled, tasks ``wont_do``).
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from packages.config import runs_settings
from packages.config.autonomy_limits import kill_switch_engaged
from packages.lifecycle.machine import IllegalTransition
from packages.runs import budget as run_budget
from packages.runs.composition import (ChildExecutor, ChildJob, ChildOutcome, CompositionResult,
                                       CompositionSpec, FailurePolicy, Step, StepResult,
                                       child_run_id, child_task_id)
from packages.runs.models import RunRecord, RunState
from packages.runs.store import FencedOut, RunStore
from packages.runs.task_binding import walk
from packages.runs.tree import cancel_run, cancel_task, cancel_tree, settle_descendants

log = logging.getLogger("qwen-proxy")

ACTOR = "system:composer"
_EVENTS = 1000
ApprovalHook = Callable[[RunRecord, Step], Awaitable[bool | None]]


class SpawnRefused(RuntimeError):
    """A child could not be spawned: the child cap or the depth cap was reached."""


@dataclass
class _Group:
    """Stop flag and child registry of one group (a stop cascades to nested groups)."""

    parent: "_Group | None" = None
    stopped: bool = False
    child_ids: set[str] = field(default_factory=set)

    def is_stopped(self) -> bool:
        return self.stopped or (self.parent is not None and self.parent.is_stopped())

    def register(self, run_id: str) -> None:
        self.child_ids.add(run_id)
        if self.parent is not None:
            self.parent.register(run_id)


@dataclass
class _Ctx:
    """State of one ``Composer.run`` pass."""

    parent: RunRecord
    sem: asyncio.Semaphore
    results: dict[str, StepResult] = field(default_factory=dict)
    spawn_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    stop: str | None = None
    # Budget reservation (root compositions with a cost cap only).
    reserving: bool = False
    cond: asyncio.Condition = field(default_factory=asyncio.Condition)
    inflight: int = 0
    cost_seen: int = 0
    starved: str | None = None


class Composer:
    """Runs compositions over one ``RunStore``; *executor* does each child's work."""

    def __init__(self, store: RunStore, executor: ChildExecutor | None = None, *,
                 task_store: Any = None, cancel_poll_s: float = 1.0,
                 approval_hook: ApprovalHook | None = None,
                 clock: Callable[[], float] = time.time) -> None:
        self._store, self._task_store = store, task_store
        self._executor = executor
        self._poll_s, self._approval_hook, self._clock = cancel_poll_s, approval_hook, clock

    # ── entry points ──────────────────────────────────────────────────────────

    async def start(self, spec: CompositionSpec, *, initiated_by: str = ACTOR) -> RunRecord:
        """Create the root run of *spec* (queued; nothing executes until ``run``)."""
        deadline = self._clock() + spec.deadline_s if spec.deadline_s else None
        run = await self._store.create(RunRecord(
            company_id=spec.company_id, owner_id=spec.owner_id, initiated_by=initiated_by,
            workflow_id=spec.name, budget=dict(spec.budget), deadline_at=deadline,
            state=RunState.QUEUED))
        await self._store.append_event(run.run_id, "composition_created", {
            "name": spec.name, "steps": len(spec.steps)}, actor=initiated_by)
        return run

    async def run(self, parent_run_id: str, spec: CompositionSpec) -> CompositionResult:
        """Execute (or resume) the composition rooted at *parent_run_id*."""
        parent = await self._store.get(parent_run_id)
        if parent is None:
            raise KeyError(parent_run_id)
        if parent.is_terminal:
            return CompositionResult(run_id=parent.run_id, state=parent.state.value)
        await walk(self._store, parent_run_id, RunState.RUNNING, token=None, actor=ACTOR)
        parent = await self._store.get(parent_run_id) or parent
        ctx = _Ctx(parent=parent, sem=asyncio.Semaphore(runs_settings.max_parallel()))
        await self._init_reservation(ctx)
        guardian = asyncio.create_task(self._guard(ctx))
        try:
            outcome, results = await self._exec_group(
                ctx, spec.steps, spec.mode, spec.policy, spec.quorum, _Group())
        finally:
            guardian.cancel()
            await asyncio.gather(guardian, return_exceptions=True)
        return await self._settle_parent(ctx, spec, outcome, results)

    async def approve(self, parent_run_id: str, step_key: str, *, approved: bool = True,
                      actor: str = "operator") -> None:
        """Record the decision on an approval step; call ``run`` again to resume."""
        kind = "approval_granted" if approved else "approval_denied"
        await self._store.append_event(parent_run_id, kind, {"step": step_key}, actor=actor)

    # ── group execution ───────────────────────────────────────────────────────

    async def _exec_group(self, ctx: _Ctx, steps: list[Step], mode: str, policy: FailurePolicy,
                          quorum: int | None, parent_grp: _Group) -> tuple[str, list[StepResult]]:
        grp = _Group(parent=parent_grp)
        if mode == "parallel":
            results = list(await asyncio.gather(
                *(self._exec_step(ctx, s, policy, grp) for s in steps)))
        else:
            results = []
            for step in steps:
                results.append(await self._exec_step(ctx, step, policy, grp))
                if results[-1].state == "waiting" or grp.is_stopped():
                    results.extend(self._unrun(steps[len(results):], ctx))
                    break
        return _group_state(results, policy, quorum), results

    def _unrun(self, steps: list[Step], ctx: _Ctx) -> list[StepResult]:
        reason = ctx.stop or "stopped"
        out = []
        for s in steps:
            result = StepResult(key=s.key, state="skipped", error=reason)
            ctx.results[s.key] = result
            out.append(result)
        return out

    async def _exec_step(self, ctx: _Ctx, step: Step, policy: FailurePolicy,
                         grp: _Group) -> StepResult:
        if ctx.stop or grp.is_stopped():
            return self._record(ctx, StepResult(key=step.key, state="skipped",
                                                error=ctx.stop or "fail_fast"))
        if not self._condition_holds(ctx, step):
            await self._store.append_event(ctx.parent.run_id, "step_skipped",
                                           {"step": step.key}, actor=ACTOR)
            return self._record(ctx, StepResult(key=step.key, state="skipped",
                                                error="condition not met"))
        if step.kind == "group":
            result = await self._exec_nested(ctx, step, grp)
        elif step.kind == "approval":
            result = await self._exec_approval(ctx, step)
        else:
            result = await self._exec_task(ctx, step, grp)
        if result.state in ("failed", "cancelled") and policy is FailurePolicy.FAIL_FAST:
            await self._stop_group(grp, f"step {step.key} failed")
        return self._record(ctx, result)

    async def _exec_nested(self, ctx: _Ctx, step: Step, grp: _Group) -> StepResult:
        state, results = await self._exec_group(ctx, step.steps, step.mode, step.policy,
                                                step.quorum, grp)
        outputs = [r.output for r in results if r.state == "succeeded"]
        error = "; ".join(f"{r.key}: {r.error}" for r in results if r.state == "failed") or None
        return StepResult(key=step.key, state=state, output=outputs, error=error)  # type: ignore[arg-type]

    @staticmethod
    def _record(ctx: _Ctx, result: StepResult) -> StepResult:
        ctx.results[result.key] = result
        return result

    @staticmethod
    def _condition_holds(ctx: _Ctx, step: Step) -> bool:
        if step.when is not None:
            prior = ctx.results.get(step.when.step)
            if prior is None or prior.state != step.when.outcome:
                return False
        if step.predicate is not None:
            return bool(step.predicate(dict(ctx.results)))
        return True

    async def _stop_group(self, grp: _Group, reason: str) -> None:
        """Fail fast: no more launches in the group, and its running children are cancelled."""
        grp.stopped = True
        for run_id in list(grp.child_ids):
            run = await self._store.get(run_id)
            if run is not None:
                await cancel_run(self._store, run, reason=reason, actor=ACTOR,
                                 task_store=self._task_store)

    # ── approval steps ────────────────────────────────────────────────────────

    async def _exec_approval(self, ctx: _Ctx, step: Step) -> StepResult:
        decision = await self._recorded_decision(ctx.parent.run_id, step.key)
        if decision is None and self._approval_hook is not None:
            decision = await self._approval_hook(ctx.parent, step)
            if decision is not None:
                await self.approve(ctx.parent.run_id, step.key, approved=decision, actor="hook")
        if decision is None:
            await self._store.append_event(ctx.parent.run_id, "approval_requested",
                                           {"step": step.key}, actor=ACTOR)
            return StepResult(key=step.key, state="waiting")
        if decision:
            return StepResult(key=step.key, state="succeeded")
        return StepResult(key=step.key, state="failed", error="approval denied")

    async def _recorded_decision(self, run_id: str, key: str) -> bool | None:
        decision = None
        for event in await self._store.list_events(run_id, limit=_EVENTS):
            if event.data.get("step") == key and event.kind in ("approval_granted",
                                                                "approval_denied"):
                decision = event.kind == "approval_granted"
        return decision

    # ── task steps (one child run each) ───────────────────────────────────────

    async def _exec_task(self, ctx: _Ctx, step: Step, grp: _Group) -> StepResult:
        try:
            child, created = await self._spawn(ctx, step)
        except SpawnRefused as exc:
            return StepResult(key=step.key, state="failed", error=str(exc))
        grp.register(child.run_id)
        if child.is_terminal:
            return await self._recorded_result(child, step.key)
        async with ctx.sem:
            if ctx.stop or grp.is_stopped():
                return await self._cancel_unstarted(child, step.key)
            reserved = await self._reserve(ctx, step, grp)
            if reserved is None:
                return await self._refuse_start(ctx, child, step.key)
            try:
                return await self._run_child(ctx, step, child)
            finally:
                await self._release(ctx, reserved)

    async def _init_reservation(self, ctx: _Ctx) -> None:
        """A root composition with a cost cap reserves; a crashed pass's reservations are dropped."""
        parent = ctx.parent
        if (parent.root_run_id or parent.run_id) != parent.run_id:
            return  # nested: the root composer's estimate already covers this subtree
        ctx.reserving = run_budget.cost_cap_micro(parent) is not None
        if ctx.reserving:
            await self._store.update(parent.run_id, {"reserved_micro_usd": 0})

    async def _reserve(self, ctx: _Ctx, step: Step, grp: _Group) -> int | None:
        """Reserve the step's estimated cost; ``None`` means do not start the child."""
        if not ctx.reserving:
            return 0
        async with ctx.cond:
            while not (ctx.stop or grp.is_stopped()):
                est = (round(step.estimated_cost * 1_000_000) if step.estimated_cost is not None
                       else ctx.cost_seen or None)
                got = await run_budget.try_reserve(self._store, ctx.parent.run_id, est)
                if got is not None:
                    ctx.inflight += 1
                    return got
                if ctx.inflight == 0:
                    ctx.starved = "budget_exhausted:max_cost_usd"
                    return None
                await ctx.cond.wait()
        return None

    async def _release(self, ctx: _Ctx, reserved: int) -> None:
        if not ctx.reserving:
            return
        async with ctx.cond:
            ctx.inflight -= 1
            await run_budget.release_reservation(self._store, ctx.parent.run_id, reserved)
            ctx.cond.notify_all()

    async def _refuse_start(self, ctx: _Ctx, child: RunRecord, key: str) -> StepResult:
        if not ctx.starved:
            return await self._cancel_unstarted(child, key)
        await self._store.append_event(ctx.parent.run_id, "budget_exhausted", {
            "limit": "max_cost_usd", "step": key, "reason": "reservation does not fit",
            "child_run_id": child.run_id}, actor=ACTOR)
        await self._to_state(child.run_id, RunState.CANCELLED, "budget_exhausted")
        await cancel_task(self._task_store, child.task_id, ACTOR, "Run cancelled: budget exhausted")
        return StepResult(key=key, state="cancelled", error="budget_exhausted", run_id=child.run_id)

    async def _spawn(self, ctx: _Ctx, step: Step) -> tuple[RunRecord, bool]:
        parent = ctx.parent
        run_id = child_run_id(parent.run_id, step.key)
        async with ctx.spawn_lock:
            existing = await self._store.get(run_id)
            if existing is not None:
                return existing, False
            children = await self._store.list(parent_run_id=parent.run_id, limit=1000)
            refusal = _spawn_refusal(parent, len(children))
            if refusal:
                await self._store.append_event(parent.run_id, "spawn_refused", {
                    "step": step.key, "reason": refusal, "depth": parent.depth + 1,
                    "children": len(children)}, actor=ACTOR)
                raise SpawnRefused(refusal)
            child = await self._store.create(RunRecord(
                run_id=run_id, parent_run_id=parent.run_id,
                root_run_id=parent.root_run_id or parent.run_id, depth=parent.depth + 1,
                task_id=child_task_id(parent.run_id, step.key), company_id=parent.company_id,
                owner_id=parent.owner_id, agent_id=step.agent_id, phase=f"step:{step.key}",
                state=RunState.QUEUED, deadline_at=parent.deadline_at, initiated_by=ACTOR))
            await self._store.append_event(parent.run_id, "child_spawned", {
                "step": step.key, "child_run_id": run_id, "depth": child.depth}, actor=ACTOR)
        return child, True

    async def _run_child(self, ctx: _Ctx, step: Step, child: RunRecord) -> StepResult:
        parent = ctx.parent
        await walk(self._store, child.run_id, RunState.RUNNING, token=None, actor=ACTOR)
        job = ChildJob(run_id=child.run_id, task_id=child.task_id or "", parent_run_id=parent.run_id,
                       depth=child.depth, step=step, company_id=parent.company_id,
                       owner_id=parent.owner_id,
                       prior={k: r.output for k, r in ctx.results.items() if r.state == "succeeded"})
        outcome = await self._execute(job)
        result = await self._settle_child(child, step.key, outcome)
        if outcome is not None:
            ctx.cost_seen = max(ctx.cost_seen, round(outcome.cost_usd * 1_000_000))
        if outcome is not None and (outcome.cost_usd or outcome.tokens or outcome.steps):
            await self._charge(ctx, child.run_id, outcome)
        return result

    async def _execute(self, job: ChildJob) -> ChildOutcome | None:
        """Run the executor beside a watcher; ``None`` means the child was cancelled."""
        work = asyncio.create_task(self._executor_for()(job))
        watch = asyncio.create_task(self._watch_child(job.run_id))
        try:
            await asyncio.wait({work, watch}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            watch.cancel()
            if not work.done():
                work.cancel()
            await asyncio.gather(work, watch, return_exceptions=True)
        if work.cancelled() or not work.done():
            return None
        exc = work.exception()
        if exc is not None:
            log.warning("composer: child %s raised %s", job.run_id, type(exc).__name__)
            return ChildOutcome(success=False, error=f"{type(exc).__name__}: {exc}"[:500], steps=0)
        return work.result()

    def _executor_for(self) -> ChildExecutor:
        if self._executor is not None:
            return self._executor
        from packages.runs.composer_tasks import TaskChildExecutor

        self._executor = TaskChildExecutor(self._task_store)
        return self._executor

    async def _watch_child(self, run_id: str) -> None:
        """Return when the child's cancel flag is set or the kill switch is on."""
        while True:
            if kill_switch_engaged():
                await cancel_run(self._store, RunRecord(run_id=run_id), reason="kill switch",
                                 actor=ACTOR, task_store=self._task_store)
                return
            run = await self._store.get(run_id)
            if run is None or run.cancel_requested or run.is_terminal:
                return
            await asyncio.sleep(self._poll_s)

    async def _settle_child(self, child: RunRecord, key: str,
                            outcome: ChildOutcome | None) -> StepResult:
        store = self._store
        if outcome is None:
            await store.append_event(child.run_id, "step_result", {"key": key, "state": "cancelled"})
            # the child's in-process work is gone, so nothing else will settle what it spawned
            await settle_descendants(store, child.run_id, reason="parent cancelled", actor=ACTOR,
                                     task_store=self._task_store)
            await self._to_state(child.run_id, RunState.CANCELLED, "cancelled")
            await cancel_task(self._task_store, child.task_id, ACTOR, "Run cancelled")
            return StepResult(key=key, state="cancelled", error="cancelled", run_id=child.run_id)
        state = "succeeded" if outcome.success else "failed"
        await store.append_event(child.run_id, "step_result", {
            "key": key, "state": state, "output": outcome.output, "error": outcome.error})
        target = RunState.SUCCEEDED if outcome.success else RunState.FAILED
        await self._to_state(child.run_id, target, outcome.error)
        return StepResult(key=key, state=state, output=outcome.output, error=outcome.error,
                          run_id=child.run_id)

    async def _to_state(self, run_id: str, target: RunState, reason: str | None) -> None:
        try:
            await walk(self._store, run_id, target, token=None, reason=reason, actor=ACTOR)
        except (IllegalTransition, FencedOut):
            log.warning("composer: run %s could not move to %s", run_id, target.value)

    async def _cancel_unstarted(self, child: RunRecord, key: str) -> StepResult:
        await self._to_state(child.run_id, RunState.CANCELLED, "stopped before start")
        await cancel_task(self._task_store, child.task_id, ACTOR, "Run cancelled")
        return StepResult(key=key, state="cancelled", error="stopped before start",
                          run_id=child.run_id)

    async def _recorded_result(self, child: RunRecord, key: str) -> StepResult:
        """Rebuild a finished child's result from its last ``step_result`` event."""
        data: dict[str, Any] = {}
        for event in await self._store.list_events(child.run_id, limit=_EVENTS):
            if event.kind == "step_result":
                data = event.data
        state = data.get("state") or ("succeeded" if child.state is RunState.SUCCEEDED
                                      else "cancelled" if child.state is RunState.CANCELLED
                                      else "failed")
        return StepResult(key=key, state=state, output=data.get("output"),
                          error=data.get("error") or child.failure_reason, run_id=child.run_id)

    async def _charge(self, ctx: _Ctx, run_id: str, outcome: ChildOutcome) -> None:
        try:
            await run_budget.charge(self._store, run_id, cost_usd=outcome.cost_usd,
                                    tokens=outcome.tokens, steps=outcome.steps,
                                    task_store=self._task_store)
        except run_budget.BudgetExhausted as exc:
            ctx.stop = ctx.stop or f"budget_exhausted:{exc.limit}"

    # ── guardian and settle ───────────────────────────────────────────────────

    async def _guard(self, ctx: _Ctx) -> None:
        """Stop the whole composition on cancel, kill switch or deadline."""
        while True:
            reason = await self._stop_reason(ctx)
            if reason:
                ctx.stop = ctx.stop or reason
                await cancel_tree(self._store, ctx.parent.run_id, reason=reason, actor=ACTOR,
                                  task_store=self._task_store, include_self=False)
            await asyncio.sleep(self._poll_s)

    async def _stop_reason(self, ctx: _Ctx) -> str | None:
        if ctx.stop:
            return ctx.stop
        if kill_switch_engaged():
            return "kill_switch"
        parent = await self._store.get(ctx.parent.run_id)
        if parent is None or parent.cancel_requested:
            over = run_budget.exceeded(parent) if parent is not None else None
            return f"budget_exhausted:{over}" if over else "cancelled"
        if parent.deadline_at is not None and parent.deadline_at <= self._clock():
            return "timed_out"
        return None

    async def _settle_parent(self, ctx: _Ctx, spec: CompositionSpec, outcome: str,
                             results: list[StepResult]) -> CompositionResult:
        run_id = ctx.parent.run_id
        if ctx.stop:
            await cancel_tree(self._store, run_id, reason="parent stopped", actor=ACTOR,
                              task_store=self._task_store, include_self=False)
        result = _build_result(run_id, ctx.results, results)
        target, reason = self._final_state(ctx, outcome, result)
        result.state, result.error = target.value, reason
        waiting = target is RunState.WAITING_FOR_APPROVAL
        await self._store.append_event(run_id, "composition_finished", {
            "state": target.value, "failed": result.failed, "skipped": result.skipped,
            "waiting_on": result.waiting_on, "partial": result.partial}, actor=ACTOR)
        await self._to_state(run_id, target, reason if not waiting else f"approval:{result.waiting_on}")
        return result

    @staticmethod
    def _final_state(ctx: _Ctx, outcome: str, result: CompositionResult) -> tuple[RunState, str | None]:
        stop = ctx.stop
        if stop == "timed_out":
            return RunState.TIMED_OUT, "deadline passed"
        if stop and stop.startswith("budget_exhausted"):
            return RunState.FAILED, stop.replace(":", " (") + ")"
        if stop:
            return RunState.CANCELLED, stop
        if ctx.starved:
            return RunState.FAILED, "budget_exhausted (max_cost_usd)"
        if outcome == "waiting":
            return RunState.WAITING_FOR_APPROVAL, None
        if outcome == "succeeded":
            return RunState.SUCCEEDED, None
        return RunState.FAILED, "failed steps: " + ", ".join(result.failed or ["(none)"])


def _spawn_refusal(parent: RunRecord, children: int) -> str | None:
    if parent.depth + 1 > runs_settings.max_depth():
        return f"depth cap reached: RUNS_MAX_DEPTH={runs_settings.max_depth()}"
    if children >= runs_settings.max_children():
        return f"child cap reached: RUNS_MAX_CHILDREN={runs_settings.max_children()}"
    return None


def _group_state(results: list[StepResult], policy: FailurePolicy, quorum: int | None) -> str:
    """The outcome of a group from its children's results and its failure policy."""
    if any(r.state == "waiting" for r in results):
        return "waiting"
    ran = [r for r in results if r.state != "skipped"]
    ok = sum(1 for r in ran if r.state == "succeeded")
    bad = len(ran) - ok
    if policy is FailurePolicy.QUORUM:
        return "succeeded" if ok >= (quorum or 1) else "failed"
    if policy is FailurePolicy.CONTINUE:
        return "failed" if ran and ok == 0 else "succeeded"
    return "failed" if bad else "succeeded"  # fail_fast and require_all


def _build_result(run_id: str, all_results: dict[str, StepResult],
                  top: list[StepResult]) -> CompositionResult:
    failed = [k for k, r in all_results.items() if r.state in ("failed", "cancelled")]
    skipped = [k for k, r in all_results.items() if r.state == "skipped"]
    waiting = next((r.key for r in all_results.values() if r.state == "waiting"), None)
    return CompositionResult(
        run_id=run_id, state="", results=dict(all_results), failed=failed, skipped=skipped,
        aggregate=[r.output for r in top if r.state == "succeeded"], waiting_on=waiting,
        partial=bool(failed) and any(r.state == "succeeded" for r in top))
