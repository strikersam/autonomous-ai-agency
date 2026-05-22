"""Background dispatcher for task execution."""

from __future__ import annotations

import asyncio
import logging
import os
import time

from tasks.service import TaskExecutionCoordinator
from tasks.store import TaskStore, get_task_store

log = logging.getLogger("qwen-proxy")

# How often (in polls) to emit a "queue depth" diagnostic log line.
_QUEUE_DEPTH_LOG_EVERY = 12  # ~1 min at 5 s poll interval


class TaskDispatcher:
    """Polls for queued task work and executes it through the coordinator.

    Diagnostics emitted (all at INFO level, queryable via /api/activity):
      - queue depth every ~1 min
      - per-task: task_id, why it wasn't picked up (no-pickup reason)
      - time-to-pickup once a task starts executing
    """

    def __init__(
        self,
        *,
        workspace_root: str,
        poll_interval_s: float = 5.0,
        max_concurrency: int | None = None,
        store: TaskStore | None = None,
        coordinator: TaskExecutionCoordinator | None = None,
    ) -> None:
        self.workspace_root = workspace_root
        self.poll_interval_s = poll_interval_s
        self.max_concurrency = max(
            1,
            int(max_concurrency or 0)
            or int(os.environ.get("TASK_DISPATCH_CONCURRENCY", "5")),
        )
        self.store = store or get_task_store()
        self.coordinator = coordinator or TaskExecutionCoordinator(
            store=self.store, workspace_root=workspace_root
        )
        self._stop = False
        self._poll_count = 0
        # Track when each task was first seen as pending so we can report
        # time-to-pickup once it actually starts.
        self._first_seen: dict[str, float] = {}

    async def run_forever(self) -> None:
        log.info(
            "TaskDispatcher started (poll_interval=%.1fs, workspace=%s, concurrency=%d)",
            self.poll_interval_s,
            self.workspace_root,
            self.max_concurrency,
        )
        while not self._stop:
            try:
                await self._poll_and_execute()
            except Exception as exc:  # pragma: no cover - defensive loop logging
                log.error("TaskDispatcher error: %s", exc, exc_info=True)
            await asyncio.sleep(self.poll_interval_s)

    async def _poll_and_execute(self) -> None:
        self._poll_count += 1
        tasks = await self.store.list_pending(limit=self.max_concurrency)

        # Emit periodic queue-depth diagnostic
        if self._poll_count % _QUEUE_DEPTH_LOG_EVERY == 0:
            depth = len(tasks)
            if depth:
                log.info(
                    "TaskDispatcher queue depth=%d (poll #%d, concurrency=%d)",
                    depth, self._poll_count, self.max_concurrency,
                )
                # Warn about tasks that have been pending for a long time
                now = time.monotonic()
                for task in tasks:
                    first = self._first_seen.get(task.task_id)
                    if first and (now - first) > 120:
                        log.warning(
                            "TaskDispatcher: task %s has been pending for %.0fs "
                            "— possible no-pickup. Check runtime health at /runtimes/health.",
                            task.task_id, now - first,
                        )

        if not tasks:
            # Prune stale first-seen entries for tasks no longer in the queue
            self._first_seen.clear()
            return

        # Record first-seen time for new pending tasks
        now = time.monotonic()
        for task in tasks:
            self._first_seen.setdefault(task.task_id, now)

        await asyncio.gather(*(self._execute_task(task.task_id) for task in tasks))

    async def _execute_task(self, task_id: str) -> None:
        first_seen = self._first_seen.pop(task_id, None)
        if first_seen is not None:
            wait_ms = (time.monotonic() - first_seen) * 1000
            log.info(
                "TaskDispatcher: executing task %s (time-to-pickup=%.0fms)",
                task_id, wait_ms,
            )
        else:
            log.info("TaskDispatcher: executing task %s", task_id)
        await self.coordinator.execute(task_id)

    def stop(self) -> None:
        self._stop = True
        log.info("TaskDispatcher stopped")
