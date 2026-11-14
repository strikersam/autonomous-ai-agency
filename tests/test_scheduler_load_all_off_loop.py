"""Scheduler reads of the durable store must not run on the event loop thread.

Production 2026-11-14: the loop watchdog logged ``schedule_store.load_all`` (a
synchronous pymongo ``find``) as the frame the loop was stuck in, from
``scheduler_tick`` -> ``force_cleanup`` roughly every minute, plus
``tag_values`` and ``attach_persistence_async``. Each stall delayed Render's
5-second health check until it failed and restarted the service.
"""
from __future__ import annotations

import asyncio
import threading


from packages.scheduler.scheduler import AgentScheduler as Scheduler


class _SyncStore:
    """Mimics ``ScheduleStore`` in mongo mode: a blocking, synchronous read."""

    def __init__(self) -> None:
        self.read_threads: list[int] = []

    def load_all(self):
        self.read_threads.append(threading.get_ident())
        return [{"job_id": "j1", "name": "n", "tags": ["company:x"]}]

    def remove(self, *_a, **_k):
        return None


class _AsyncStore(_SyncStore):
    async def load_all(self):  # type: ignore[override]
        return [{"job_id": "j2", "tags": ["company:y"]}]


def _scheduler(store) -> Scheduler:
    sched = Scheduler()
    sched._store = store
    return sched


async def test_tag_values_reads_store_off_the_loop_thread():
    store = _SyncStore()
    tags = await _scheduler(store).tag_values("company:")
    assert tags == {"company:x"}
    assert store.read_threads, "store was never read"
    assert threading.get_ident() not in store.read_threads, "load_all ran on the loop thread"


async def test_force_cleanup_reads_store_off_the_loop_thread():
    store = _SyncStore()
    await _scheduler(store).force_cleanup()
    assert store.read_threads
    assert threading.get_ident() not in store.read_threads


async def test_async_store_is_still_awaited_directly():
    tags = await _scheduler(_AsyncStore()).tag_values("company:")
    assert tags == {"company:y"}


async def test_loop_keeps_ticking_during_a_slow_store_read():
    class _Slow(_SyncStore):
        def load_all(self):
            import time
            time.sleep(0.3)
            return []

    ticks = 0

    async def ticker():
        nonlocal ticks
        while True:
            await asyncio.sleep(0.01)
            ticks += 1

    t = asyncio.create_task(ticker())
    await _scheduler(_Slow()).tag_values("company:")
    t.cancel()
    assert ticks >= 10, f"loop starved during the read (ticks={ticks})"
