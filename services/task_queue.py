from __future__ import annotations

"""Async Task Queue with Priority and Backpressure (A4 roadmap item).

Implements an asyncio-based priority queue with configurable worker pools,
backpressure signals (HTTP 429 when full), queue status introspection,
and SSE-based task progress tracking.

Replaces the simple threading-based BackgroundAgent queue with a
full-featured async queue suitable for production workloads.
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Awaitable

log = logging.getLogger("qwen-proxy")


# ── Configuration ──────────────────────────────────────────────────────────────

_MAX_QUEUE_SIZE = int(os.environ.get("TASK_QUEUE_MAX_SIZE", "500"))
_DEFAULT_WORKERS = int(os.environ.get("TASK_QUEUE_WORKERS", "4"))
_POLL_INTERVAL_S = float(os.environ.get("TASK_QUEUE_POLL_INTERVAL", "0.1"))
_BACKPRESSURE_ENABLED = os.environ.get("TASK_QUEUE_BACKPRESSURE", "true").strip().lower() in ("true", "1", "yes")


class Priority(IntEnum):
    """Task priority levels. Lower number = higher priority (executed first)."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


@dataclass(order=True)
class PrioritizedTask:
    """Wrapper around a task payload with priority ordering."""
    priority: int
    task_id: str = field(compare=False)
    payload: dict[str, Any] = field(compare=False)
    enqueued_at: float = field(default_factory=time.monotonic, compare=False)
    progress: list[dict[str, Any]] = field(default_factory=list, compare=False)
    status: str = "pending"  # pending | running | done | failed | cancelled

    def record_progress(self, phase: str, message: str) -> None:
        self.progress.append({
            "timestamp": time.monotonic(),
            "phase": phase,
            "message": message,
        })


class PriorityTaskQueue:
    """Asyncio-based priority queue with backpressure and worker pool.

    Features:
    - Priority ordering (CRITICAL → BACKGROUND)
    - Backpressure: reject new tasks when queue is full (returns False)
    - Worker pool: configurable number of concurrent workers
    - Progress tracking: per-task progress events for SSE streaming
    - Status introspection: queue depth, worker count, task statuses

    Usage::

        queue = PriorityTaskQueue(max_size=500, num_workers=4)
        await queue.start()

        # Submit a task
        accepted = await queue.submit(
            task_id="task-123",
            payload={"instruction": "Run tests"},
            priority=Priority.NORMAL,
        )
        if not accepted:
            raise HTTPException(429, "Queue full — retry later")

        # Get queue status
        status = queue.status()
        # {"queue_depth": 12, "max_size": 500, "workers": 4, ...}
    """

    def __init__(
        self,
        *,
        max_size: int = _MAX_QUEUE_SIZE,
        num_workers: int = _DEFAULT_WORKERS,
        poll_interval: float = _POLL_INTERVAL_S,
        enable_backpressure: bool = _BACKPRESSURE_ENABLED,
    ) -> None:
        self._queue: asyncio.PriorityQueue[PrioritizedTask] = asyncio.PriorityQueue(maxsize=max_size)
        self.max_size = max_size
        self.num_workers = num_workers
        self.poll_interval = poll_interval
        self.enable_backpressure = enable_backpressure
        self._tasks: dict[str, PrioritizedTask] = {}
        self._workers: list[asyncio.Task[None]] = []
        self._running = False
        self._processed_count = 0
        self._rejected_count = 0
        self._handler: Callable[[PrioritizedTask], Awaitable[Any]] | None = None
        self._subscribers: dict[str, list[Callable[[PrioritizedTask], Awaitable[None]]]] = {}

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def start(
        self,
        handler: Callable[[PrioritizedTask], Awaitable[Any]] | None = None,
    ) -> None:
        """Start the worker pool."""
        if self._running:
            return
        self._running = True
        self._handler = handler
        for i in range(self.num_workers):
            worker = asyncio.create_task(self._worker_loop(i), name=f"taskq-worker-{i}")
            self._workers.append(worker)
        log.info("PriorityTaskQueue started: workers=%d max_size=%d", self.num_workers, self.max_size)

    async def stop(self) -> None:
        """Stop the worker pool gracefully."""
        self._running = False
        for worker in self._workers:
            worker.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        log.info("PriorityTaskQueue stopped (processed=%d rejected=%d)", self._processed_count, self._rejected_count)

    # ── Submission ───────────────────────────────────────────────────────────

    async def submit(
        self,
        *,
        task_id: str,
        payload: dict[str, Any],
        priority: Priority = Priority.NORMAL,
    ) -> bool:
        """Submit a task to the queue.

        Returns True if accepted, False if rejected due to queue being full.
        """
        task = PrioritizedTask(
            priority=int(priority),
            task_id=task_id,
            payload=payload,
        )
        self._tasks[task_id] = task

        try:
            self._queue.put_nowait(task)
            self._processed_count += 1
            await self._notify("task_queued", task_id, {"priority": priority.name})
            log.debug("Task queued: id=%s priority=%s", task_id, priority.name)
            return True
        except asyncio.QueueFull:
            if self.enable_backpressure:
                self._rejected_count += 1
                log.warning("Task rejected (queue full): id=%s depth=%d", task_id, self._queue.qsize())
                self._tasks.pop(task_id, None)
                return False
            # Without backpressure, block until space is available
            await self._queue.put(task)
            self._processed_count += 1
            await self._notify("task_queued", task_id, {"priority": priority.name})
            return True

    # ── Queries ──────────────────────────────────────────────────────────────

    def get_task(self, task_id: str) -> PrioritizedTask | None:
        return self._tasks.get(task_id)

    def list_tasks(self, status: str | None = None) -> list[dict[str, Any]]:
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return [
            {
                "task_id": t.task_id,
                "status": t.status,
                "priority": Priority(t.priority).name,
                "enqueued_at": t.enqueued_at,
                "progress": t.progress,
            }
            for t in sorted(tasks, key=lambda t: t.priority)
        ]

    def status(self) -> dict[str, Any]:
        """Return queue introspection data for status endpoints."""
        return {
            "queue_depth": self._queue.qsize(),
            "max_size": self.max_size,
            "workers": self.num_workers,
            "running": self._running,
            "processed": self._processed_count,
            "rejected": self._rejected_count,
            "backpressure": self.enable_backpressure,
            "tasks_by_status": {
                s: sum(1 for t in self._tasks.values() if t.status == s)
                for s in ("pending", "running", "done", "failed", "cancelled")
            },
        }

    # ── SSE progress streaming ───────────────────────────────────────────────

    async def subscribe(self, task_id: str) -> asyncio.Queue[dict[str, Any]]:
        """Subscribe to progress events for a specific task.

        Returns an asyncio.Queue that receives progress dicts.
        The caller should iterate over the queue until the task is complete.
        """
        event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        async def forward(task: PrioritizedTask) -> None:
            for event in task.progress:
                await event_queue.put(event)
            if task.status in ("done", "failed", "cancelled"):
                await event_queue.put({
                    "type": "complete",
                    "status": task.status,
                })

        # Send existing progress immediately
        task = self._tasks.get(task_id)
        if task:
            await forward(task)

        # Subscribe for future updates
        key = f"task:{task_id}"
        if key not in self._subscribers:
            self._subscribers[key] = []
        self._subscribers[key].append(forward)
        return event_queue

    async def unsubscribe(self, task_id: str) -> None:
        self._subscribers.pop(f"task:{task_id}", None)

    # ── Internal ─────────────────────────────────────────────────────────────

    async def _worker_loop(self, worker_id: int) -> None:
        while self._running:
            try:
                task = await asyncio.wait_for(self._queue.get(), timeout=self.poll_interval)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            if not self._running:
                self._queue.task_done()
                break

            task.status = "running"
            task.record_progress("running", f"Worker {worker_id} started")
            await self._notify("task_started", task.task_id, {"worker": worker_id})

            try:
                if self._handler:
                    result = await self._handler(task)
                else:
                    result = {"dispatched": True}
                task.status = "done"
                task.record_progress("done", "Task completed")
                await self._notify("task_done", task.task_id, {"result": result})
            except asyncio.CancelledError:
                task.status = "cancelled"
                task.record_progress("cancelled", "Worker cancelled")
                await self._notify("task_cancelled", task.task_id, {})
                self._queue.task_done()
                break
            except Exception as exc:
                task.status = "failed"
                task.record_progress("failed", str(exc)[:500])
                log.error("Task %s failed: %s", task.task_id, exc)
                await self._notify("task_failed", task.task_id, {"error": str(exc)[:500]})
            finally:
                self._queue.task_done()
                # Evict old completed/failed tasks to prevent memory leaks.
                # Keep only the most recent N tasks in the tracking dict.
                _MAX_TRACKED = int(os.environ.get("TASK_QUEUE_MAX_TRACKED", "1000"))
                if len(self._tasks) > _MAX_TRACKED:
                    stale = sorted(
                        [t for t in self._tasks.values() if t.status in ("done", "failed", "cancelled")],
                        key=lambda t: t.enqueued_at,
                    )
                    for t in stale[: len(stale) // 2]:
                        self._tasks.pop(t.task_id, None)

        log.debug("Worker %d stopped", worker_id)

    async def _notify(self, event: str, task_id: str, data: Any) -> None:
        key = f"task:{task_id}"
        for callback in self._subscribers.get(key, []):
            try:
                await callback(self._tasks.get(task_id))
            except Exception:
                pass


# ── Module-level singleton ─────────────────────────────────────────────────────

_task_queue: PriorityTaskQueue | None = None


def get_task_queue() -> PriorityTaskQueue:
    """Return the module-level PriorityTaskQueue singleton."""
    global _task_queue
    if _task_queue is None:
        _task_queue = PriorityTaskQueue()
    return _task_queue
