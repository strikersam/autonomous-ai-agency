"""services/orchestrator_queue.py — Async FIFO run queue with concurrency semaphore.

Issue #522: The approve endpoint must return 202 immediately and enqueue
the run instead of executing it inline (which causes timeouts).  A global
concurrency semaphore (default 2) ensures at most N runs execute at once;
the rest wait in a FIFO queue without starvation.

Usage::

    queue = get_orchestrator_queue()
    await queue.enqueue(run_id, fn, *args, **kwargs)
    # Calls fn(*args, **kwargs) when a slot opens, returns immediately.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger("qwen-proxy")

_MAX_CONCURRENT = int(os.environ.get("ORCHESTRATOR_MAX_CONCURRENT", "2"))
_ORCHESTRATOR_TIMEOUT_SEC = float(os.environ.get("ORCHESTRATOR_PHASE_TIMEOUT_SEC", "120"))


@dataclass
class _QueueEntry:
    run_id: str
    fn: Callable
    args: tuple
    kwargs: dict
    enqueued_at: float = field(default_factory=time.time)
    future: asyncio.Future = field(default_factory=lambda: asyncio.Future())


class OrchestratorQueue:
    """Async FIFO queue that limits concurrent orchestrator run executions.

    ``approve()`` enqueues a run and returns immediately (the API returns 202).
    A background worker drains the queue, respecting the concurrency limit.
    """

    def __init__(self, max_concurrent: int = _MAX_CONCURRENT) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._queue: deque[_QueueEntry] = deque()
        self._active: dict[str, asyncio.Task] = {}
        self._running = False
        self._drain_task: asyncio.Task | None = None
        log.info("OrchestratorQueue: max_concurrent=%d", max_concurrent)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._drain_task = asyncio.create_task(self._drain_loop())
        log.info("OrchestratorQueue: drain loop started")

    async def stop(self) -> None:
        self._running = False
        if self._drain_task:
            self._drain_task.cancel()
            try:
                await self._drain_task
            except asyncio.CancelledError:
                pass
        for task in self._active.values():
            task.cancel()
        log.info("OrchestratorQueue: stopped (active=%d queued=%d)", len(self._active), len(self._queue))

    async def enqueue(self, run_id: str, fn: Callable, *args: Any, **kwargs: Any) -> None:
        """Enqueue a run for async execution.  Returns immediately.

        ``fn(*args, **kwargs)`` will be called when a concurrency slot opens.
        The caller should NOT await this — use ``enqueue_and_wait`` if you need
        the result.
        """
        entry = _QueueEntry(run_id=run_id, fn=fn, args=args, kwargs=kwargs)
        self._queue.append(entry)
        log.info(
            "OrchestratorQueue: enqueued run_id=%s (queue depth=%d active=%d)",
            run_id, len(self._queue), len(self._active),
        )

    async def enqueue_and_wait(self, run_id: str, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """Enqueue a run and return a future that resolves when it completes."""
        entry = _QueueEntry(run_id=run_id, fn=fn, args=args, kwargs=kwargs)
        self._queue.append(entry)
        log.info(
            "OrchestratorQueue: enqueued run_id=%s (waiting; queue depth=%d active=%d)",
            run_id, len(self._queue), len(self._active),
        )
        return await entry.future

    @property
    def queue_depth(self) -> int:
        return len(self._queue)

    @property
    def active_count(self) -> int:
        return len(self._active)

    def status(self) -> dict[str, Any]:
        return {
            "max_concurrent": _MAX_CONCURRENT,
            "active": self.active_count,
            "queued": self.queue_depth,
            "active_run_ids": list(self._active),
            "queued_run_ids": [e.run_id for e in self._queue],
        }

    async def _drain_loop(self) -> None:
        while self._running:
            if not self._queue:
                await asyncio.sleep(0.1)
                continue

            await self._semaphore.acquire()
            try:
                entry = self._queue.popleft()
            except IndexError:
                self._semaphore.release()
                continue

            async def _execute(ent: _QueueEntry) -> None:
                started = time.time()
                try:
                    result = await asyncio.wait_for(
                        ent.fn(*ent.args, **ent.kwargs),
                        timeout=_ORCHESTRATOR_TIMEOUT_SEC * 11,  # generous overall timeout
                    )
                    if not ent.future.done():
                        ent.future.set_result(result)
                except asyncio.TimeoutError:
                    log.error("OrchestratorQueue: run_id=%s timed out after %.0fs", ent.run_id, time.time() - started)
                    if not ent.future.done():
                        ent.future.set_exception(TimeoutError(f"Run {ent.run_id} timed out"))
                except Exception as exc:
                    log.exception("OrchestratorQueue: run_id=%s failed", ent.run_id)
                    if not ent.future.done():
                        ent.future.set_exception(exc)
                finally:
                    self._active.pop(ent.run_id, None)
                    self._semaphore.release()
                    log.info(
                        "OrchestratorQueue: run_id=%s completed in %.1fs (remaining: active=%d queued=%d)",
                        ent.run_id, time.time() - started, self.active_count, self.queue_depth,
                    )

            task = asyncio.create_task(_execute(entry))
            self._active[entry.run_id] = task


# ── Singleton ─────────────────────────────────────────────────────────────────

_queue: OrchestratorQueue | None = None


def get_orchestrator_queue() -> OrchestratorQueue:
    global _queue
    if _queue is None:
        _queue = OrchestratorQueue()
    return _queue


async def start_orchestrator_queue() -> None:
    await get_orchestrator_queue().start()


async def stop_orchestrator_queue() -> None:
    if _queue is not None:
        await _queue.stop()
