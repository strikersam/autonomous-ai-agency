"""
Minimal asyncio-based task queue.

Usage:

    import asyncio
    from async_queue import enqueue, start_worker, stop_worker

    async def my_task():
        print("Running")

    async def main():
        start_worker()          # start background worker
        enqueue(my_task())      # enqueue coroutine
        await asyncio.sleep(1)  # give time for task to run
        stop_worker()           # stop background worker

    asyncio.run(main())
"""

import asyncio
from typing import Awaitable, Callable, Any

# Internal queue holding coroutines to run
_queue: asyncio.Queue[Awaitable[Any]] = asyncio.Queue()

# Background worker task
_worker_task: asyncio.Task | None = None


async def _worker() -> None:
    """
    Background worker that continuously pulls coroutines from the queue
    and awaits them.
    """
    while True:
        coro = await _queue.get()
        try:
            await coro
        except Exception:
            # Swallow exceptions to keep the worker alive.
            # In a real application, consider logging the error.
            pass
        finally:
            _queue.task_done()


def start_worker() -> None:
    """
    Start the background worker if it is not already running.
    """
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_worker())


def stop_worker() -> None:
    """
    Stop the background worker gracefully.
    """
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        _worker_task = None


def enqueue(coro: Awaitable[Any]) -> None:
    """
    Enqueue a coroutine to be executed by the background worker.

    Parameters
    ----------
    coro : Awaitable[Any]
        The coroutine object to enqueue.

    Raises
    ------
    RuntimeError
        If the event loop is not running.
    """
    loop = asyncio.get_running_loop()
    if loop is None:
        raise RuntimeError("Event loop is not running")
    _queue.put_nowait(coro)
