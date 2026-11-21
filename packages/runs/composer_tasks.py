"""packages/runs/composer_tasks.py — the default composer executor: a child is a task.

``TaskChildExecutor`` creates the child's task (once: its ``source_id`` is the child
run id, so a restart finds the same task), links it to the child run and executes it
through the existing ``TaskExecutionCoordinator``. Nothing here is a second engine.
"""
from __future__ import annotations

import logging
from typing import Any

from packages.runs.composition import ChildJob, ChildOutcome

log = logging.getLogger("qwen-proxy")

_OK = frozenset({"done", "in_review"})


class TaskChildExecutor:
    """Callable ``ChildExecutor`` over a task store (default: the process task store)."""

    def __init__(self, task_store: Any = None, coordinator: Any = None) -> None:
        self._store = task_store
        self._coordinator = coordinator

    async def __call__(self, job: ChildJob) -> ChildOutcome:
        from tasks.models import Task
        from tasks.service import TaskExecutionCoordinator
        from tasks.store import get_task_store

        store = self._store or get_task_store()
        coordinator = self._coordinator or TaskExecutionCoordinator(store=store)
        task = Task(task_id=job.task_id, owner_id=job.owner_id or "system:composer",
                    title=job.step.title or job.step.key, prompt=job.step.prompt,
                    description=job.step.prompt, agent_id=job.step.agent_id,
                    company_id=job.company_id, source_id=job.run_id,
                    requires_approval=False, pending_agent_run=True)
        task.current_run_id = job.run_id
        task = await store.create(task)
        done = await coordinator.execute(task.task_id)
        status = done.status.value
        return ChildOutcome(success=status in _OK, output=done.result,
                            error=None if status in _OK else (done.error_message or status))
