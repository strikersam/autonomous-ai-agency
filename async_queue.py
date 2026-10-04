import asyncio
from typing import Awaitable, Callable, Any, Tuple

class AsyncQueue:
    """
    A minimal asyncio-based task queue that executes tasks sequentially.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[
            Tuple[Callable[..., Awaitable[Any]], Tuple[Any, ...], dict]
        ] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None
        self._running = False

    async def _worker(self) -> None:
        while self._running:
            try:
                func, args, kwargs = await self._queue.get()
                try:
                    await func(*args, **kwargs)
                finally:
                    self._queue.task_done()
            except asyncio.CancelledError:
                break

    def start(self) -> None:
        """
        Start the worker loop. This method is idempotent.
        """
        if not self._running:
            self._running = True
            self._worker_task = asyncio.create_task(self._worker())

    async def stop(self) -> None:
        """
        Stop the worker loop and drain the queue.
        """
        if self._running:
            self._running = False
            if self._worker_task:
                self._worker_task.cancel()
                try:
                    await self._worker_task
                except asyncio.CancelledError:
                    pass
            # Drain remaining tasks
            while not self._queue.empty():
                self._queue.get_nowait()
                self._queue.task_done()

    def enqueue(
        self, func: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any
    ) -> None:
        """
        Enqueue an awaitable function to be executed by the queue.
        """
        self._queue.put_nowait((func, args, kwargs))

    async def join(self) -> None:
        """
        Wait until all tasks have been processed.
        """
        await self._queue.join()
