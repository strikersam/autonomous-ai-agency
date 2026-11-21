"""packages/runs/task_binding.py — bind one task execution to its durable run and lease.

``TaskExecutionCoordinator.execute`` (and ``/api/autonomy/tick``) call into this
module so ``tasks/service.py`` stays small:

* ``bind`` starts a ``LeaseHeartbeat`` on the task's durable run lease and, when
  ``RUNS_LEDGER_ENABLED``, creates the task's ``RunRecord`` or resumes the one
  in ``Task.current_run_id`` (same ``run_id``, ``attempt`` incremented). It sets
  the ``current_run`` ContextVar that side effect recording reads.
* ``mark`` records a state transition; ``guard`` stops the work when the lease
  is lost (a newer holder took over: the stale worker must stop).
* ``settle`` is the fenced final write: the task's final status is written only
  after a renewal compare-and-set on ``(holder, token)`` succeeds. A successful
  renewal guarantees nobody else can take the lease for a whole TTL, so the
  write that follows cannot race a newer holder. A fenced out worker drops its
  result, logs a warning and records an event.
* ``unbind`` stops the heartbeat and records the run's final state.

Stores without a durable lease (memory mode, test doubles) get ``None`` from
``bind`` and every other function is then a no-op apart from ``settle``, which
falls back to a plain ``store.update``. Ledger failures never fail a task: they
are logged and execution continues. Fencing is the one exception.
"""
from __future__ import annotations

import asyncio
import logging
import weakref
from collections import deque
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any, Awaitable, TypeVar

from packages.config import runs_settings
from packages.config.autonomy_limits import kill_switch_engaged
from packages.lifecycle.registry import get_machine
from packages.runs.lease import LeaseHeartbeat, RunLease
from packages.runs.models import RunRecord, RunState
from packages.runs.store import FencedOut, RunStore

log = logging.getLogger("qwen-proxy")

T = TypeVar("T")

# States a binding may pass through on its way to a target; terminal and
# supervisory states are only used when they are the target itself.
_VIA = frozenset({"queued", "starting", "running", "verifying", "recovering", "retrying"})


@dataclass
class TaskRunBinding:
    """One live task execution: its lease, heartbeat and (when recording) its run."""

    task_id: str
    holder: str
    token: int
    lease: RunLease
    heartbeat: LeaseHeartbeat
    store: RunStore | None = None
    run_id: str | None = None
    # Read only handle on the task's current run, so a cancel is seen with the ledger off.
    watch_store: RunStore | None = None
    watch_run_id: str | None = None
    fenced: bool = False
    occurrences: dict[str, int] = field(default_factory=dict)
    cancel: asyncio.Event = field(default_factory=asyncio.Event)
    ctx_token: Token[Any] | None = None

    @property
    def lease_key(self) -> str:
        """Task runs are leased under their ``task_id``."""
        return self.task_id

    @property
    def recording(self) -> bool:
        """True when this execution writes to the run ledger."""
        return self.store is not None and self.run_id is not None


class RunCancelled(Exception):
    """The run's ``cancel_requested`` flag was seen; the worker must stop and settle it."""


current_run: ContextVar[TaskRunBinding | None] = ContextVar("current_run", default=None)

# Every binding live in this process, by task id (graceful shutdown walks it).
_ACTIVE: dict[str, TaskRunBinding] = {}

_run_stores: "weakref.WeakKeyDictionary[Any, RunStore]" = weakref.WeakKeyDictionary()


def active_bindings() -> list[TaskRunBinding]:
    """The bindings live in this process right now."""
    return list(_ACTIVE.values())


def run_store_for(task_store: Any) -> RunStore:
    """The ``RunStore`` on the same backend as *task_store* (cached per backend)."""
    db = getattr(task_store, "_db", None)
    if db is None:
        return RunStore()
    try:
        store = _run_stores.get(db)
        if store is None:
            store = RunStore(db)
            _run_stores[db] = store
        return store
    except TypeError:  # backend object not weak referenceable
        return RunStore(db)


def has_durable_lease(task_store: Any) -> bool:
    """True when *task_store* shares its run lease across processes."""
    try:
        return getattr(task_store, "has_durable_run_lease", False) is True
    except Exception:
        return False


def path_to(source: str, target: str) -> list[str]:
    """Shortest legal ``run`` lifecycle path from *source* to *target* (excluding source)."""
    machine = get_machine("run")
    queue: deque[tuple[str, list[str]]] = deque([(source, [])])
    seen = {source}
    while queue:
        state, path = queue.popleft()
        for nxt in machine.allowed(state):
            if nxt == target:
                return path + [nxt]
            if nxt in _VIA and nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, path + [nxt]))
    return []


async def walk(store: RunStore, run_id: str, target: RunState, *, token: int | None,
               reason: str | None = None, actor: str | None = None) -> RunRecord | None:
    """Move the run to *target* through legal intermediate states; ``None`` if no path."""
    run = await store.get(run_id)
    if run is None:
        return None
    if run.state is target:
        return run
    for step in path_to(run.state.value, target.value):
        run = await store.transition(run_id, RunState(step), token=token, reason=reason,
                                     actor=actor)
    return run if run.state is target else None


async def bind(task_store: Any, task: Any, *, actor: str = "system:dispatcher") -> TaskRunBinding | None:
    """Start the heartbeat and open the task's run; ``None`` without a durable lease."""
    from tasks import run_lease as claims

    token = claims.held_token(task.task_id)
    if not token or not has_durable_lease(task_store):
        return None
    lease = RunLease(getattr(task_store, "_db", None))
    holder = claims.holder_id()
    binding = TaskRunBinding(task_id=task.task_id, holder=holder, token=token, lease=lease,
                             heartbeat=LeaseHeartbeat(lease, task.task_id, holder, token))
    claims.pin_local_claim(task.task_id)
    if getattr(task, "current_run_id", None):
        binding.watch_store, binding.watch_run_id = run_store_for(task_store), task.current_run_id
    binding.heartbeat.start()
    if runs_settings.runs_ledger_enabled():
        try:
            await _open_run(binding, run_store_for(task_store), task, actor)
        except Exception:
            log.warning("run ledger: could not open the run of task %s; continuing without it",
                        task.task_id, exc_info=True)
            binding.store = binding.run_id = None
    binding.heartbeat.on_tick = lambda: _poll_cancel(binding)
    binding.ctx_token = current_run.set(binding)
    _ACTIVE[task.task_id] = binding
    return binding


async def _open_run(binding: TaskRunBinding, store: RunStore, task: Any, actor: str) -> None:
    run = await store.get(task.current_run_id) if task.current_run_id else None
    resumed = run is not None and not run.is_terminal
    if not resumed:
        run = await store.create(RunRecord(
            task_id=task.task_id, company_id=task.company_id, agent_id=task.agent_id,
            owner_id=task.owner_id, initiated_by=actor, lease_token=binding.token,
        ))
    if run is None:
        raise KeyError(binding.run_id)
    fields: dict[str, Any] = {"lease_token": binding.token}
    # A run the recovery tick queued already counted this attempt.
    if resumed and run.state is not RunState.QUEUED:
        fields["attempt"] = run.attempt + 1
    await store.update(run.run_id, fields)
    binding.store, binding.run_id = store, run.run_id
    await walk(store, run.run_id, RunState.STARTING, token=binding.token, actor=actor)
    current = await store.get(run.run_id)
    await store.append_event(run.run_id, "attempt_started", {
        "attempt": current.attempt if current else run.attempt, "token": binding.token,
        "resumed": resumed,
    }, actor=actor)
    task.current_run_id = run.run_id


async def _poll_cancel(binding: TaskRunBinding) -> None:
    """One cheap check per heartbeat: set ``binding.cancel`` on a kill switch or a cancel request."""
    if binding.cancel.is_set():
        return
    if kill_switch_engaged():
        # The operator's hard stop: guarded work ends within one heartbeat.
        log.warning("kill switch engaged; stopping task %s", binding.task_id)
        await _event(binding, "kill_switch", {"task_id": binding.task_id})
        binding.cancel.set()
        return
    store, run_id = ((binding.store, binding.run_id) if binding.recording
                     else (binding.watch_store, binding.watch_run_id))
    if store is None or run_id is None:
        return
    run = await store.get(run_id)
    if run is not None and run.cancel_requested:
        binding.cancel.set()


async def mark(binding: TaskRunBinding | None, state: RunState, reason: str | None = None) -> None:
    """Record a state transition of the bound run. Never raises."""
    if binding is None or not binding.recording or binding.fenced:
        return
    try:
        await walk(binding.store, binding.run_id, state, token=binding.token,  # type: ignore[arg-type]
                   reason=reason)
    except FencedOut:
        log.warning("run %s: transition to %s fenced out (token %s)", binding.run_id,
                    state.value, binding.token)
    except Exception:
        log.warning("run ledger: could not record %s for run %s", state.value, binding.run_id,
                    exc_info=True)


async def guard(binding: TaskRunBinding | None, work: Awaitable[T]) -> T:
    """Await *work*, but stop it the moment the lease is lost (``FencedOut``) or a cancel
    is requested (``RunCancelled``)."""
    if binding is None:
        return await work
    job = asyncio.ensure_future(work)
    lost = asyncio.ensure_future(binding.heartbeat.lost.wait())
    cancel = asyncio.ensure_future(binding.cancel.wait())
    try:
        await asyncio.wait({job, lost, cancel}, return_when=asyncio.FIRST_COMPLETED)
    except BaseException:
        job.cancel()
        lost.cancel()
        cancel.cancel()
        raise
    lost.cancel()
    cancel.cancel()
    if job.done():
        return job.result()
    job.cancel()
    try:
        await job
    except BaseException:  # noqa: BLE001 — the stopped work's own outcome is irrelevant now
        pass
    if binding.cancel.is_set() and not binding.heartbeat.lost.is_set():
        raise RunCancelled(f"task {binding.task_id}: run cancelled")
    binding.fenced = True
    raise FencedOut(f"task {binding.task_id}: run lease lost (token {binding.token}); stopping")


async def settle(task_store: Any, binding: TaskRunBinding | None, task: Any) -> bool:
    """Write the task's final state, fenced on the lease token; False when fenced out."""
    if binding is None:
        await task_store.update(task)
        return True
    if not binding.fenced and not binding.heartbeat.lost.is_set():
        try:
            ok = await binding.lease.renew(binding.lease_key, binding.holder, binding.token,
                                           float(runs_settings.lease_ttl_s()))
        except Exception:
            # The store is unreachable; keep today's behaviour and attempt the write.
            log.warning("Task %s: could not confirm the run lease before the final write",
                        task.task_id, exc_info=True)
            ok = True
        if ok:
            await task_store.update(task)
            return True
    binding.fenced = True
    log.warning("Task %s: run lease token %s is no longer current; dropping this worker's "
                "result (fenced out)", task.task_id, binding.token)
    await _event(binding, "fenced_out", {"token": binding.token,
                                         "dropped_status": getattr(task.status, "value", None)})
    return False


def final_state(task: Any) -> tuple[RunState | None, str | None]:
    """The run state a settled task maps to (``None`` to leave the run as it is)."""
    status = getattr(task.status, "value", task.status)
    if status in ("done", "in_review"):
        return RunState.SUCCEEDED, None
    if status == "failed":
        return RunState.FAILED, task.error_message or "task failed"
    if status == "blocked":
        return RunState.FAILED, task.blocked_reason or "task blocked"
    if status == "wont_do":
        return RunState.CANCELLED, None
    if task.pending_agent_run:
        return RunState.RETRYING, task.error_message
    return None, None


async def unbind(binding: TaskRunBinding | None, task: Any) -> None:
    """Stop the heartbeat and record the run's final state. Never raises."""
    if binding is None:
        return
    _ACTIVE.pop(binding.task_id, None)
    _reset_context(binding)
    await binding.heartbeat.stop()
    if binding.fenced:
        return
    state, reason = final_state(task)
    if state is not None:
        await mark(binding, state, reason)


def _reset_context(binding: TaskRunBinding) -> None:
    token, binding.ctx_token = binding.ctx_token, None
    if token is None:
        return
    try:
        current_run.reset(token)
    except ValueError:  # unbound from another context
        current_run.set(None)


async def _event(binding: TaskRunBinding, kind: str, data: dict[str, Any]) -> None:
    if not binding.recording:
        return
    try:
        await binding.store.append_event(binding.run_id, kind, data)  # type: ignore[union-attr,arg-type]
    except Exception:
        log.warning("run ledger: could not record %s for run %s", kind, binding.run_id,
                    exc_info=True)


async def shutdown_all(reason: str = "shutdown") -> int:
    """Graceful shutdown: every live binding goes to RECOVERING and drops its lease.

    One fast write per run, the heartbeat stopped, the lease released; the run
    is then free for the next claim at once instead of after a whole lease TTL
    (the recovery tick still waits a TTL after its last update). Returns the
    number of bindings handled. Never raises.
    """
    handled = 0
    for binding in active_bindings():
        handled += 1
        binding.fenced = True  # this worker must not write the task after this point
        await binding.heartbeat.stop()
        if binding.recording:
            try:
                await binding.store.transition(binding.run_id, RunState.RECOVERING,  # type: ignore[union-attr,arg-type]
                                               token=binding.token, reason=reason)
            except Exception:
                log.warning("shutdown: could not mark run %s recovering", binding.run_id,
                            exc_info=True)
        try:
            await binding.lease.release(binding.lease_key, binding.holder, binding.token)
        except Exception:
            log.warning("shutdown: could not release the lease of task %s", binding.task_id,
                        exc_info=True)
        _ACTIVE.pop(binding.task_id, None)
    return handled
