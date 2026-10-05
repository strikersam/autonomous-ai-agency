"""Background dispatcher for task execution."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time

from tasks.models import Task, TaskStatus
from tasks.service import TaskExecutionCoordinator
from tasks.store import TaskStore, get_task_store

log = logging.getLogger("qwen-proxy")

# How often (in polls) to emit a "queue depth" diagnostic log line.
_QUEUE_DEPTH_LOG_EVERY = 12  # ~1 min at 5 s poll interval

# How often (in polls) to mine recent agent sessions for repeating failures
# (services/session_retro.py). 720 polls is about an hour at the 5 s poll.
_RETRO_EVERY = 720

# When nothing is queued or running, check for portfolio work this often (in
# polls, ~1 min) instead of waiting for the regular intake interval.
_IDLE_PORTFOLIO_EVERY = 12

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

# The cooldown doubles with each auto-retry, up to this ceiling. A fixed 5 min
# retried every blocked task into the same exhausted free-tier quota (production
# 2026-10-04: one task blocked 7 times in 7 hours, each block 5 more LLM runs).
_BLOCKED_COOLDOWN_MAX_S = 4 * 3600.0


def blocked_cooldown_s(auto_retry_count: int) -> float:
    """Seconds a BLOCKED task waits before its next auto-retry."""
    return min(_BLOCKED_COOLDOWN_S * (2 ** max(auto_retry_count, 0)), _BLOCKED_COOLDOWN_MAX_S)


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
        # Tasks this dispatcher is running right now, by task id.
        self._running: dict[str, asyncio.Task] = {}

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

    async def _ceo_triage(self) -> None:
        """Approve/reject parked tasks and queue fixes for open error alerts."""
        from tasks.autonomy_triage import triage_gated_tasks

        await triage_gated_tasks(self.store)
        # The alerts feed lives in backend.server; only read it where that app is
        # already loaded — importing it from the proxy process would boot it.
        if "backend.server" not in sys.modules:
            return
        try:
            from agent.sam_actions import fix_alerts

            await fix_alerts("system:ceo")
        except Exception as exc:  # pragma: no cover - defensive loop logging
            log.error("CEO alert intake error: %s", exc, exc_info=True)

    async def _poll_and_execute(self) -> None:
        self._poll_count += 1

        # Periodic reconciliation to catch tasks stranded by mid-flight crashes.
        if _RECONCILE_EVERY > 0 and self._poll_count % _RECONCILE_EVERY == 0:
            await self._reconcile()

        # Periodic auto-retry of BLOCKED tasks that have cooled down.
        if _AUTO_RETRY_BLOCKED_EVERY > 0 and self._poll_count % _AUTO_RETRY_BLOCKED_EVERY == 0:
            await self._auto_retry_blocked()

        from packages.config.autonomy_limits import kill_switch_engaged
        if kill_switch_engaged():
            # Tasks stay pending and resume on the first poll after the switch is off;
            # CEO triage below is autonomous action too, so it is skipped as well.
            if self._poll_count % _QUEUE_DEPTH_LOG_EVERY == 0:
                log.warning("TaskDispatcher: kill switch engaged — not picking up tasks")
            return

        # Periodic CEO triage: decide parked tasks and pick up open alerts.
        from packages.config import settings
        every = settings.agency_auto_triage_every_polls
        if settings.is_agency_auto_triage_enabled and every > 0 and self._poll_count % every == 0:
            await self._ceo_triage()
        await self._maybe_materialize_portfolio(settings.portfolio_auto_materialize_every_polls)
        if _RETRO_EVERY > 0 and self._poll_count % _RETRO_EVERY == 0:
            await self._run_retro()

        free = self.max_concurrency - len(self._running)
        if free <= 0:
            return
        # Over-fetch so tasks this dispatcher is already running don't hide
        # queued work behind them.
        candidates = await self.store.list_pending(limit=self.max_concurrency * 2)
        tasks = [t for t in candidates if t.task_id not in self._running][:free]

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

        # Start each task in its own slot and return: a free slot is refilled on
        # the next poll instead of idling until the slowest task in a batch ends.
        for task in tasks:
            self._running[task.task_id] = asyncio.create_task(self._run_slot(task))

    async def _run_slot(self, task: Task) -> None:
        try:
            await self._execute_as_agent(task)
        except Exception as exc:  # pragma: no cover - defensive loop logging
            log.error("TaskDispatcher: task %s crashed: %s", task.task_id, exc, exc_info=True)
        finally:
            self._running.pop(task.task_id, None)

    async def _maybe_materialize_portfolio(self, every: int) -> None:
        """Queue portfolio work on its cadence, and right away when agents are idle."""
        if every <= 0:
            return
        idle = not self._running and self._poll_count % _IDLE_PORTFOLIO_EVERY == 0
        if self._poll_count % every != 0 and not (idle and await self._queue_empty()):
            return
        from tasks.autonomy_triage import materialize_portfolio

        await materialize_portfolio()

    async def _run_retro(self) -> None:
        """Learn from recent sessions: file repeating failures as improvement issues."""
        try:
            from services.session_retro import run_retro_cycle

            result = await run_retro_cycle()
            if result.get("routed"):
                log.info("Session retro: routed %d recurring failure(s) to the improvement loop",
                         result["routed"])
        except Exception as exc:  # pragma: no cover - defensive loop logging
            log.error("Session retro error: %s", exc, exc_info=True)

    async def _queue_empty(self) -> bool:
        return not await self.store.list_pending(limit=1)

    async def drain(self) -> None:
        """Wait for every running slot to finish (tests and graceful shutdown)."""
        while self._running:
            await asyncio.gather(*list(self._running.values()), return_exceptions=True)

    async def _execute_as_agent(self, task: Task) -> None:
        """Run one task with its LLM spend attributed to the assigned agent."""
        from packages.ai.agent_budget import agent_scope

        with agent_scope(task.agent_id or "task-dispatcher"):
            await self._execute_task(task.task_id)

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
                # task.updated_at may be a float OR an ISO 8601 string (depending
                # on which code path wrote it); normalise via _ts_to_float so the
                # subtraction doesn't raise TypeError.
                from tasks.store import _ts_to_float
                updated_at_f = _ts_to_float(task.updated_at) if task.updated_at else 0.0
                if updated_at_f and (now - updated_at_f) < blocked_cooldown_s(task.auto_retry_count):
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
                    # reset_auto_retry=False: the dispatcher owns the auto-retry
                    # budget here, so retry() must NOT clear it — otherwise the
                    # count resets to 0 every cycle, never reaches _AUTO_RETRY_MAX,
                    # and a deterministically-timing-out task loops forever.
                    self.coordinator.workflow.retry(
                        task, actor="system:auto-retry", reset_auto_retry=False
                    )
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
                        time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(updated_at_f or now)),
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
