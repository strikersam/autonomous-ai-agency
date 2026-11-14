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
        time.sleep(_BLOCK_S)
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


_BLOCK_S = 0.5      # how long the fake store blocks
_MAX_GAP_S = 0.25   # the loop may stall for less than this; a blocked loop stalls for _BLOCK_S


async def _max_gap_while(coro) -> float:
    """Longest time the loop went without running a 10 ms ticker while ``coro`` ran.

    Counting ticks depends on runner speed; the longest gap does not: a read that
    blocks the loop shows a gap of at least ``_BLOCK_S``, an off-loop read only jitter.
    """
    stamps: list[float] = [time.monotonic()]
    stop = asyncio.Event()

    async def ticker() -> None:
        while not stop.is_set():
            stamps.append(time.monotonic())
            await asyncio.sleep(0.01)

    task = asyncio.create_task(ticker())
    await asyncio.sleep(0.05)  # let the ticker establish its rhythm
    try:
        await coro
    finally:
        stop.set()
        await task
    stamps.append(time.monotonic())
    return max(b - a for a, b in zip(stamps, stamps[1:]))


@pytest.mark.asyncio
async def test_a_sync_store_read_runs_off_the_loop_thread() -> None:
    store = _SlowSyncStore()
    gap = await _max_gap_while(_store_call(store.load_all))
    assert gap < _MAX_GAP_S, f"the loop stalled for {gap:.2f}s during a blocking read"
    assert store.threads and store.threads[0] != threading.get_ident()


@pytest.mark.asyncio
async def test_an_async_store_is_awaited_not_threaded() -> None:
    assert await _store_call(_AsyncStore().load_all) == [{"job_id": "a", "tags": ["company:c1"]}]


@pytest.mark.asyncio
async def test_force_cleanup_does_not_block_the_loop() -> None:
    store = _SlowSyncStore()
    sched = AgentScheduler(persistence=store)
    try:
        gap = await _max_gap_while(sched.force_cleanup())
    finally:
        sched.shutdown()
    assert gap < _MAX_GAP_S, f"the loop stalled for {gap:.2f}s"
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

        gap = await _max_gap_while(run())
    finally:
        sched.shutdown()
    assert gap < _MAX_GAP_S, f"the loop stalled for {gap:.2f}s"
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


@pytest.mark.asyncio
async def test_store_calls_keep_their_submission_order() -> None:
    """A slow upsert followed by a remove must not be overtaken by the remove."""

    class _Store:
        def __init__(self) -> None:
            self.docs: dict[str, dict] = {}

        def upsert(self, doc: dict) -> None:
            time.sleep(0.1)
            self.docs[doc["job_id"]] = doc

        def remove(self, job_id: str) -> bool:
            return self.docs.pop(job_id, None) is not None

    store = _Store()
    first = asyncio.create_task(_store_call(store.upsert, {"job_id": "j"}))
    await asyncio.sleep(0)  # the upsert is queued before the remove is
    second = asyncio.create_task(_store_call(store.remove, "j"))
    await asyncio.gather(first, second)
    assert store.docs == {}, "the remove ran before the upsert and the row came back"
