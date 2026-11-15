"""packages/runs/orchestrator_binding.py — mirror a ``WorkflowRun`` into the durable run ledger.

``services/workflow_orchestrator.py`` keeps its own in memory ``WorkflowRun`` and
checkpoint store; this module mirrors each run into a ``RunRecord`` (same
``run_id``, ``workflow_id`` set) at start, on every checkpoint and at its terminal
status, so the run ledger shows orchestrator work beside task runs. When the
orchestrator runs inside a bound task execution, the mirror's parent is that
task's run.

A mirror has no ``task_id`` and holds no lease, so the recovery tick leaves it
alone (phase 2). ``mirror_run`` never raises and is a no op with
``RUNS_LEDGER_ENABLED`` off.
"""
from __future__ import annotations

import logging
from typing import Any

from packages.config import runs_settings
from packages.runs.models import RunRecord, RunState

log = logging.getLogger("qwen-proxy")

ACTOR = "system:workflow-orchestrator"

# WorkflowRun.status → run state (unknown statuses are left as they are).
STATUS_TO_STATE: dict[str, RunState] = {
    "pending": RunState.QUEUED,
    "queued": RunState.QUEUED,
    "running": RunState.RUNNING,
    "executing": RunState.RUNNING,
    "awaiting_approval": RunState.WAITING_FOR_APPROVAL,
    "done": RunState.SUCCEEDED,
    "failed": RunState.FAILED,
}


def _parent_run_id() -> str | None:
    from packages.runs.task_binding import current_run

    binding = current_run.get()
    return binding.run_id if binding is not None and binding.recording else None


async def _ensure(store: Any, run: Any) -> RunRecord:
    record = await store.get(run.run_id)
    if record is None:
        record = await store.create(RunRecord(
            run_id=run.run_id, workflow_id=run.run_id, parent_run_id=_parent_run_id(),
            company_id=run.company_id, owner_id=run.user_id, initiated_by=ACTOR,
        ))
    return record


async def mirror_run(run: Any) -> None:
    """Bring the ``RunRecord`` of *run* (a ``WorkflowRun``) up to date. Never raises."""
    if not runs_settings.runs_ledger_enabled():
        return
    try:
        from packages.runs.store import get_run_store
        from packages.runs.task_binding import walk

        store = get_run_store()
        record = await _ensure(store, run)
        if record.is_terminal:
            return
        await store.update(run.run_id, {"phase": getattr(run, "current_phase", None)})
        target = STATUS_TO_STATE.get(str(getattr(run, "status", "")))
        if target is None or record.state is target:
            return
        reason = {RunState.WAITING_FOR_APPROVAL: "approval_gate",
                  RunState.FAILED: getattr(run, "error", None) or "workflow failed"}.get(target)
        await walk(store, run.run_id, target, token=None, reason=reason, actor=ACTOR)
    except Exception:
        log.warning("run ledger: could not mirror workflow run %s",
                    getattr(run, "run_id", "?"), exc_info=True)
