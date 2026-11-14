"""Agency observations must not block the caller.

Production (2026-11-14): ``scheduler_tick`` (every 20 s) and the CEO cycle called
``emit_agency_observation``, which made two synchronous ``httpx`` POSTs to Langfuse on the
event loop. The watchdog caught 2.7-3.9 s stalls at ``langfuse_obs._emit_langfuse_http_sync``.
"""
from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

import pytest

import langfuse_obs

_BLOCK_S = 0.5
_MAX_GAP_S = 0.25


async def _max_gap_while(coro: Any) -> float:
    stamps: list[float] = [time.monotonic()]
    stop = asyncio.Event()

    async def ticker() -> None:
        while not stop.is_set():
            stamps.append(time.monotonic())
            await asyncio.sleep(0.01)

    task = asyncio.create_task(ticker())
    await asyncio.sleep(0.05)
    try:
        await coro
    finally:
        stop.set()
        await task
    stamps.append(time.monotonic())
    return max(b - a for a, b in zip(stamps, stamps[1:]))


async def _wait_for(predicate: Any, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, "timed out waiting"
        await asyncio.sleep(0.01)


@pytest.fixture(autouse=True)
def _enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(langfuse_obs, "_langfuse_enabled", lambda: True)
    monkeypatch.setattr(langfuse_obs, "_emit_pending", 0)


async def test_an_agency_observation_does_not_block_the_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[int, dict[str, Any]]] = []

    def slow_emit(**kwargs: Any) -> None:
        time.sleep(_BLOCK_S)  # deliberate: stands in for two slow Langfuse POSTs
        seen.append((threading.get_ident(), kwargs))

    monkeypatch.setattr(langfuse_obs, "_emit_langfuse_http", slow_emit)

    async def call() -> None:
        langfuse_obs.emit_agency_observation(operation="scheduler_tick", actor="scheduler")

    gap = await _max_gap_while(call())
    assert gap < _MAX_GAP_S, f"emit_agency_observation stalled the loop for {gap:.2f}s"
    await _wait_for(lambda: bool(seen))
    tid, kwargs = seen[0]
    assert tid != threading.get_ident()
    assert kwargs["task_name"] == "agency:scheduler_tick"
    assert kwargs["email"] == "scheduler@agency.internal"


async def test_a_failing_emit_is_swallowed_and_releases_its_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(**_kwargs: Any) -> None:
        raise RuntimeError("langfuse down")

    monkeypatch.setattr(langfuse_obs, "_emit_langfuse_http", boom)
    langfuse_obs.emit_agency_observation(operation="x")  # must not raise
    await _wait_for(lambda: langfuse_obs._emit_pending == 0)


async def test_a_saturated_queue_drops_instead_of_blocking_or_growing(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr(langfuse_obs, "_emit_langfuse_http", lambda **_k: calls.append(1))
    monkeypatch.setattr(langfuse_obs, "_emit_pending", langfuse_obs._EMIT_QUEUE_MAX)
    langfuse_obs.emit_agency_observation(operation="x")
    await asyncio.sleep(0.1)
    assert calls == [], "an observation was queued past the cap"
    assert langfuse_obs._emit_pending == langfuse_obs._EMIT_QUEUE_MAX


def test_a_disabled_langfuse_stays_a_no_op(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(langfuse_obs, "_langfuse_enabled", lambda: False)
    calls: list[int] = []
    monkeypatch.setattr(langfuse_obs, "_emit_langfuse_http", lambda **_k: calls.append(1))
    assert langfuse_obs.emit_agency_observation(operation="x") is None
    assert calls == []
