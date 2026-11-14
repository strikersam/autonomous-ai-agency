"""A synchronous schedule store must not block the event loop.

Production (2026-11-14): ``scheduler_tick`` -> ``force_cleanup`` -> ``ScheduleStore.load_all``
is a synchronous pymongo ``find`` over every schedule row. It froze the loop for 3-6 s
every 20 s, failing Render's 5 s health check and restarting the service.
"""
from __future__ import annotations

import asyncio
import threading
import time

import pytest

from packages.scheduler.scheduler import AgentScheduler, _store_call


class _SlowSyncStore:
    """A ScheduleStore stand-in whose reads block like a slow pymongo call."""

    def __init__(self) -> None:
        self.threads: list[int] = []
        self.docs: dict[str, dict] = {}

    def load_all(self) -> list[dict]:
        self.threads.append(threading.get_ident())
        time.sleep(0.3)
        return list(self.docs.values())

    def upsert(self, doc: dict) -> None:
        self.threads.append(threading.get_ident())
        self.docs[doc["job_id"]] = doc

    def remove(self, job_id: str) -> bool:
        self.threads.append(threading.get_ident())
        return self.docs.pop(job_id, None) is not None


class _AsyncStore:
    def __init__(self) -> None:
        self.docs: list[dict] = [{"job_id": "a", "tags": ["company:c1"]}]

    async def load_all(self) -> list[dict]:
        return list(self.docs)


async def _ticks_while(coro) -> int:
    """Count how often the loop gets to run while ``coro`` is in flight."""
    ticks = 0
    stop = asyncio.Event()

    async def ticker() -> None:
        nonlocal ticks
        while not stop.is_set():
            ticks += 1
            await asyncio.sleep(0.01)

    task = asyncio.create_task(ticker())
    try:
        await coro
    finally:
        stop.set()
        await task
    return ticks


@pytest.mark.asyncio
async def test_a_sync_store_read_runs_off_the_loop_thread() -> None:
    store = _SlowSyncStore()
    ticks = await _ticks_while(_store_call(store.load_all))
    assert ticks >= 10, "the loop must keep running during a 0.3 s blocking read"
    assert store.threads and store.threads[0] != threading.get_ident()


@pytest.mark.asyncio
async def test_an_async_store_is_awaited_not_threaded() -> None:
    assert await _store_call(_AsyncStore().load_all) == [{"job_id": "a", "tags": ["company:c1"]}]


@pytest.mark.asyncio
async def test_force_cleanup_does_not_block_the_loop() -> None:
    store = _SlowSyncStore()
    sched = AgentScheduler(persistence=store)
    try:
        ticks = await _ticks_while(sched.force_cleanup())
    finally:
        sched.shutdown()
    assert ticks >= 10
    assert all(t != threading.get_ident() for t in store.threads)


@pytest.mark.asyncio
async def test_tag_values_does_not_block_the_loop() -> None:
    store = _SlowSyncStore()
    store.docs["j"] = {"job_id": "j", "tags": ["company:abc"]}
    sched = AgentScheduler(persistence=store)
    try:
        holder: dict[str, set[str]] = {}

        async def run() -> None:
            holder["tags"] = await sched.tag_values("company:")

        ticks = await _ticks_while(run())
    finally:
        sched.shutdown()
    assert ticks >= 10
    assert holder["tags"] == {"company:abc"}


@pytest.mark.asyncio
async def test_persist_and_remove_still_reach_a_sync_store() -> None:
    store = _SlowSyncStore()
    sched = AgentScheduler(persistence=store)
    try:
        await _store_call(store.upsert, {"job_id": "x"})
        assert "x" in store.docs
        assert await _store_call(store.remove, "x") is True
        assert "x" not in store.docs
    finally:
        sched.shutdown()
