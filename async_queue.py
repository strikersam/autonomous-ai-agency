"""
A minimal asyncio-based task queue implementation.

This module provides a simple `AsyncQueue` class that can enqueue coroutine
objects and execute them sequentially. It is intentionally lightweight and
does not depend on any external libraries beyond the standard library.
"""

import asyncio
from typing import Awaitable, List, Any


class AsyncQueue:
    """
    A minimal asynchronous task queue.

    The queue stores coroutine objects and executes them in the order they
    were enqueued when :meth:`run` is called. Each coroutine is awaited
    sequentially. This implementation is suitable for simple use cases
    such as unit tests or small scripts where a full-featured task queue
    is unnecessary.
    """

    def __init__(self) -> None:
        """
        Create a new, empty queue.
        """
        self._tasks: List[Awaitable[Any]] = []

    def enqueue(self, coro: Awaitable[Any]) -> None:
        """
        Add a coroutine to the queue.

        Parameters
        ----------
        coro:
            An awaitable coroutine object to be executed later.
        """
        if not asyncio.iscoroutine(coro):
            raise TypeError("enqueue expects a coroutine object")
        self._tasks.append(coro)

    async def run(self) -> None:
        """
        Execute all enqueued coroutines sequentially.

        This method awaits each coroutine in the order they were added.
        After all tasks have completed, the internal task list is cleared.
        """
        while self._tasks:
            coro = self._tasks.pop(0)
            await coro

    async def __aenter__(self) -> "AsyncQueue":
        """
        Context manager entry; returns the queue instance.
        """
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """
        Context manager exit; runs any remaining tasks.
        """
        await self.run()
