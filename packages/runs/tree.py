"""packages/runs/tree.py — walk and cancel a run's descendants.

Shared by the composer (parent cancel, deadline, fail fast), the budget (an
exhausted root stops the whole tree) and the cancel API. Cancelling a run
sets ``cancel_requested`` on it and on every non terminal descendant, settles
the ones that have no worker at once (``cancelled``, their task ``wont_do``),
and leaves a running one to its worker, whose heartbeat or watcher sees the flag.
"""
from __future__ import annotations

import logging
from typing import Any

from packages.lifecycle.machine import IllegalTransition
from packages.runs.models import RunRecord, RunState
from packages.runs.store import FencedOut, RunStore

log = logging.getLogger("qwen-proxy")

# No worker holds a run in one of these states, so a cancel can settle it on the spot.
SETTLE_NOW = frozenset({
    RunState.CREATED, RunState.QUEUED, RunState.WAITING_FOR_AGENT, RunState.WAITING_FOR_APPROVAL,
    RunState.RETRYING, RunState.RECOVERING,
})
_TASK_FINAL = frozenset({"done", "failed", "wont_do"})
_PAGE = 500


async def descendants(store: RunStore, run_id: str) -> list[RunRecord]:
    """Every run below *run_id* (children, grandchildren, ...), breadth first."""
    found: list[RunRecord] = []
    queue = [run_id]
    seen = {run_id}
    while queue:
        parent = queue.pop(0)
        for child in await store.list(parent_run_id=parent, limit=_PAGE):
            if child.run_id not in seen:
                seen.add(child.run_id)
                found.append(child)
                queue.append(child.run_id)
    return found


async def cancel_task(task_store: Any, task_id: str | None, actor: str, message: str) -> None:
    """Move a task to ``wont_do`` through the task service. Best effort, never raises."""
    if not task_id or task_store is None:
        return
    from tasks.models import TaskStatus
    from tasks.service import TaskRuleError, TaskWorkflowService

    try:
        task = await task_store.get(task_id)
        if task is None or task.status.value in _TASK_FINAL:
            return
        TaskWorkflowService(store=task_store).transition(
            task, TaskStatus.WONT_DO, actor=actor, message=message)
        await task_store.update(task)
    except TaskRuleError:
        log.warning("run tree: task %s could not be cancelled", task_id)
    except Exception:
        log.warning("run tree: could not cancel task %s", task_id, exc_info=True)


async def cancel_run(store: RunStore, run: RunRecord, *, reason: str, actor: str,
                     task_store: Any = None) -> bool:
    """Flag one run for cancellation and settle it when it has no worker.

    Returns True when this call set the flag (False: it was already set or the run ended).
    """
    current = await store.get(run.run_id)
    if current is None or current.is_terminal:
        return False
    fresh = not current.cancel_requested
    if fresh:
        await store.update(run.run_id, {"cancel_requested": True})
        await store.append_event(run.run_id, "cancel_requested",
                                 {"state": current.state.value, "reason": reason}, actor=actor)
    if current.state in SETTLE_NOW:
        try:
            await store.transition(run.run_id, RunState.CANCELLED, reason=reason, actor=actor)
            await cancel_task(task_store, current.task_id, actor, reason)
        except (FencedOut, IllegalTransition, KeyError):
            pass  # a worker moved it first; its own cancel check settles it
    return fresh


async def cancel_tree(store: RunStore, run_id: str, *, reason: str, actor: str,
                      task_store: Any = None, include_self: bool = True) -> list[str]:
    """Cancel *run_id* (unless ``include_self`` is False) and every descendant.

    Returns the ids of the runs this call newly flagged.
    """
    targets: list[RunRecord] = []
    if include_self:
        root = await store.get(run_id)
        if root is not None:
            targets.append(root)
    targets.extend(await descendants(store, run_id))
    flagged = []
    for run in targets:
        if await cancel_run(store, run, reason=reason, actor=actor, task_store=task_store):
            flagged.append(run.run_id)
    return flagged


async def settle_descendants(store: RunStore, run_id: str, *, reason: str, actor: str,
                             task_store: Any = None) -> int:
    """Cancel and settle every non terminal descendant of *run_id*, running ones included.

    For the composer, after it cancelled in-process work that owned these runs: no worker is
    left to observe ``cancel_requested``, so they are set to ``cancelled`` and their tasks to
    ``wont_do`` here. Returns how many runs were settled.
    """
    settled = 0
    for run in await descendants(store, run_id):
        current = await store.get(run.run_id)
        if current is None or current.is_terminal:
            continue
        if not current.cancel_requested:
            await store.update(run.run_id, {"cancel_requested": True})
        try:
            await store.transition(run.run_id, RunState.CANCELLED, reason=reason, actor=actor)
        except (FencedOut, IllegalTransition, KeyError):
            continue
        await cancel_task(task_store, current.task_id, actor, reason)
        settled += 1
    return settled
