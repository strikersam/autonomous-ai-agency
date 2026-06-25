"""Background dispatcher for task execution."""

from __future__ import annotations

import asyncio
import logging
import os
import time

from tasks.models import TaskStatus
from tasks.service import TaskExecutionCoordinator
from tasks.store import TaskStore, get_task_store

log = logging.getLogger("qwen-proxy")

# How often (in polls) to emit a "queue depth" diagnostic log line.
_QUEUE_DEPTH_LOG_EVERY = 12  # ~1 min at 5 s poll interval

# How often (in polls) to run the stranded-task reconciler.
# Default: every 60 polls ≈ 5 minutes at 5 s poll interval.
_RECONCILE_EVERY = int(os.environ.get("TASK_RECONCILE_EVERY_POLLS", "60"))

# How often (in polls) to run the blocked-task auto-retry.
# Default: every 30 polls ≈ 2.5 minutes at 5 s poll interval.
_AUTO_RETRY_BLOCKED_EVERY = int(os.environ.get("TASK_AUTO_RETRY_BLOCKED_EVERY_POLLS", "30"))    # A BLOCKED task must have been blocked for at least this many seconds
# before the dispatcher will auto-retry it.  Prevents hammering a task that
# was just blocked moments ago.
_BLOCKED_COOLDOWN_S = float(os.environ.get("TASK_BLOCKED_COOLDOWN_SEC", "300"))  # 5 min default

# Maximum number of times the dispatcher will auto-retry a BLOCKED task.
# Beyond this limit the task stays BLOCKED until a human intervenes.
_AUTO_RETRY_MAX = int(os.environ.get("TASK_AUTO_RETRY_MAX", "5"))

# A task is "stranded" if it has been IN_PROGRESS without completing for this
# many seconds.  Default is 2× the coordinator's default execution timeout (150 s).
_STALE_THRESHOLD_S = float(os.environ.get("TASK_STALE_THRESHOLD_SEC", "300"))


class TaskDispatcher:
    """Polls for queued task work and executes it through the coordinator.

    Crash recovery: on every ``_RECONCILE_EVERY``-th poll (and once on startup)
    the dispatcher calls ``store.reconcile_stranded_tasks()`` to re-queue any
    task that was left IN_PROGRESS by a previous server process that crashed or
    was hard-killed mid-execution.

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
        # Run reconciler immediately on startup to recover any tasks that were
        # left stranded by a previous server process.
        await self._reconcile()

        while not self._stop:
            try:
                await self._poll_and_execute()
            except Exception as exc:  # pragma: no cover - defensive loop logging
                log.error("TaskDispatcher error: %s", exc, exc_info=True)
            await asyncio.sleep(self.poll_interval_s)

    async def _reconcile(self) -> None:
        """Re-queue tasks stranded by a prior crash or hard-kill."""
        try:
            active = set(self.coordinator._active_task_ids)  # snapshot under lock
            recovered = await self.store.reconcile_stranded_tasks(
                active_task_ids=active,
                stale_threshold_s=_STALE_THRESHOLD_S,
            )
            if recovered:
                log.info(
                    "TaskDispatcher reconciler: recovered %d stranded task(s)", recovered
                )
        except Exception as exc:  # pragma: no cover
            log.error("TaskDispatcher reconciler error: %s", exc, exc_info=True)

    async def _poll_and_execute(self) -> None:
        self._poll_count += 1

        # Periodic reconciliation to catch tasks stranded by mid-flight crashes.
        if _RECONCILE_EVERY > 0 and self._poll_count % _RECONCILE_EVERY == 0:
            await self._reconcile()

        # Periodic auto-retry of BLOCKED tasks that have cooled down.
        if _AUTO_RETRY_BLOCKED_EVERY > 0 and self._poll_count % _AUTO_RETRY_BLOCKED_EVERY == 0:
            await self._auto_retry_blocked()

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

    async def _auto_retry_blocked(self) -> None:
        """Re-queue BLOCKED tasks that have cooled down and are ready for retry."""
        try:
            blocked_tasks = await self.store.list_blocked(limit=self.max_concurrency)
            if not blocked_tasks:
                return

            now = time.time()
            retried = 0
            for task in blocked_tasks:
                # Skip tasks that haven't cooled down yet
                if task.updated_at and (now - task.updated_at) < _BLOCKED_COOLDOWN_S:
                    continue
                # Respect the auto-retry limit to prevent infinite retry loops
                if task.auto_retry_count >= _AUTO_RETRY_MAX:
                    log.debug(
                        "TaskDispatcher: task %s hit auto-retry limit (%d), leaving blocked",
                        task.task_id, task.auto_retry_count,
                    )
                    continue
                # Use the TaskWorkflowService.retry() to safely transition the task
                # back to IN_PROGRESS.  After retry() transitions the status and sets
                # pending_agent_run=True, we reset it to False so the task is not
                # picked up again in the same poll cycle — it waits for the next
                # _poll_and_execute() loop iteration after the sleep interval.
                try:
                    self.coordinator.workflow.retry(task, actor="system:auto-retry")
                    # After retry(), the task is IN_PROGRESS with pending_agent_run=True.
                    # For the dispatcher to pick it up on the NEXT poll cycle (not the
                    # same cycle), put it back in TODO state so list_pending() sees it.
                    # This gives the runtime ~5s+ to recover between retry attempts.
                    task.status = TaskStatus.TODO
                    task.auto_retry_count += 1
                    task.add_log(
                        f"Auto-retry #{task.auto_retry_count} triggered by dispatcher",
                        level="info",
                        event_type="auto_retry",
                        actor="system:auto-retry",
                        task_status=TaskStatus.TODO,
                    )
                    await self.store.update(task)
                    retried += 1
                    log.info(
                        "TaskDispatcher auto-retry: re-queued blocked task %s "
                        "(attempt #%d, was blocked since %s)",
                        task.task_id,
                        task.auto_retry_count,
                        time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(task.updated_at or now)),
                    )
                except Exception as exc:
                    log.warning(
                        "TaskDispatcher auto-retry: failed to re-queue task %s: %s",
                        task.task_id, exc,
                    )

            if retried:
                log.info(
                    "TaskDispatcher auto-retry: re-queued %d blocked task(s)",
                    retried,
                )
        except Exception as exc:  # pragma: no cover
            log.error("TaskDispatcher auto-retry error: %s", exc, exc_info=True)

    def stop(self) -> None:
        self._stop = True
        log.info("TaskDispatcher stopped")
