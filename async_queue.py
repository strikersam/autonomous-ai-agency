"""
Minimal asyncio‑based task queue implementation.

This module provides a simple asynchronous queue that can be used to
schedule coroutine tasks and run them sequentially.  It exposes two
module‑level coroutine functions:

* ``enqueue(coro)`` – put a coroutine into the queue.
* ``run()`` – run all queued coroutines in the order they were added.

The implementation is intentionally lightweight and does not provide
advanced features such as worker pools or cancellation handling.  It
is suitable for small projects or as a teaching example.
"""

import asyncio
from typing import Awaitable, Any


class AsyncQueue:
    """
    A minimal asynchronous queue that stores coroutine objects and
    executes them sequentially when ``run`` is called.

    Attributes
    ----------
    _queue : asyncio.Queue[Awaitable[Any]]
        Internal queue holding coroutine objects.
    _running : bool
        Flag indicating whether the queue is currently being processed.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[Awaitable[Any]] = asyncio.Queue()
        self._running: bool = False

    async def enqueue(self, coro: Awaitable[Any]) -> None:
        """
        Add a coroutine to the queue.

        Parameters
        ----------
        coro : Awaitable[Any]
            The coroutine to enqueue.
        """
        await self._queue.put(coro)

    async def run(self) -> None:
        """
        Run all queued coroutines sequentially.

        This method processes tasks until the queue is empty.  It
        ignores exceptions raised by individual tasks to ensure that
        the queue continues to run.  If ``run`` is called while the
        queue is already running, the call returns immediately.
        """
        if self._running:
            return

        self._running = True
        try:
            while not self._queue.empty():
                coro = await self._queue.get()
                try:
                    await coro
                except Exception:
                    # Swallow exceptions to keep the queue running.
                    # In a real application you might want to log the error.
                    pass
        finally:
            self._running = False


# Singleton instance used by the module-level helper functions.
_queue = AsyncQueue()


async def enqueue(coro: Awaitable[Any]) -> None:
    """
    Enqueue a coroutine for later execution.

    Parameters
    ----------
    coro : Awaitable[Any]
        The coroutine to enqueue.
    """
    await _queue.enqueue(coro)


async def run() -> None:
    """
    Run all queued coroutines.

    This is a convenience wrapper around the singleton ``AsyncQueue``.
    """
    await _queue.run()


__all__ = ["AsyncQueue", "enqueue", "run"]
