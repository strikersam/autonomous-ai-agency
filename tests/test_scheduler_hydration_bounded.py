"""Regression test for the 2026-08-01 502/503 crash-loop.

``services/background.py``'s scheduler hydration
(``scheduler.attach_persistence_async()``) reads every persisted schedule and
re-registers each with APScheduler, so its cost scales with the row count.
Production accumulated a large backlog of one-shot ``agency:``/``fix:`` jobs
that never got the chance to fire (a crash-restart loop killed the process
before their next-minute cron trigger), and this was the one startup step
NOT covered by backend/server.py's lifespan() warm-up budget introduced in
#1171 — so a large/growing backlog delayed port-opening past Render's
health-check timeout, causing the very restart that grew the backlog
further. tests/test_schedule_backlog_drain.py covers the cleanup-side half
of this incident; this file covers the startup-path half.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Generator
from typing import NoReturn

import pytest

from services import background


@pytest.fixture(autouse=True)
def _isolate_warmup_overflow() -> Generator[None, None, None]:
    """``_warmup_overflow`` is process-global — keep tests from sharing it."""
    from services.warmup import _warmup_overflow
    _warmup_overflow.clear()
    yield
    for task in list(_warmup_overflow):
        task.cancel()
    _warmup_overflow.clear()


class _FakeStore:
    """Stand-in for ``agent.schedule_store.ScheduleStore``'s constructor.

    ``_hydrate_scheduler_bounded`` constructs a real ``ScheduleStore()``
    inside ``asyncio.to_thread``, and the fake schedulers below don't touch
    it — but the real constructor still runs. Its default backend is
    "mongo" (``agent/schedule_store.py``), so unpatched it blocks on a real
    connection attempt (~2s ``serverSelectionTimeoutMS``); its sqlite path
    is also a module-level constant frozen at import time, so an env-var
    override in a test does nothing and every test would share one on-disk
    file, racing on the same lock. Patching the class itself sidesteps both
    and keeps this test hermetic, per CLAUDE.md's testing constitution.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass


@pytest.fixture(autouse=True)
def _fake_schedule_store(monkeypatch) -> None:
    monkeypatch.setattr("agent.schedule_store.ScheduleStore", _FakeStore)


class _HangingScheduler:
    """A scheduler whose hydration never returns within the test's lifetime."""

    def __init__(self) -> None:
        self.released = asyncio.Event()
        self.completed = asyncio.Event()

    async def attach_persistence_async(self, _persistence: object) -> int:
        await self.released.wait()
        self.completed.set()
        return 999


class _FastScheduler:
    """A scheduler whose hydration finishes well inside the budget."""

    def __init__(self) -> None:
        self.calls = 0

    async def attach_persistence_async(self, _persistence: object) -> int:
        self.calls += 1
        return 3


class _BrokenScheduler:
    """A scheduler whose persistence attach always fails."""

    async def attach_persistence_async(self, _persistence: object) -> NoReturn:
        raise RuntimeError("store unreachable")


@pytest.mark.asyncio
async def test_a_hanging_hydration_does_not_block_startup(monkeypatch):
    """The exact production failure: hydration must not hold up the caller.

    Against the previous code (a bare ``await
    scheduler.attach_persistence_async(...)``) this test hangs forever instead
    of completing.
    """
    monkeypatch.setattr(background, "_SCHEDULER_HYDRATE_BUDGET_SEC", 0.05)
    scheduler = _HangingScheduler()

    await asyncio.wait_for(background._hydrate_scheduler_bounded(scheduler), timeout=2.0)

    # The deferred hydration must still be running in the background, not
    # cancelled or dropped — releasing it must let it actually finish.
    assert not scheduler.released.is_set()
    scheduler.released.set()
    await asyncio.wait_for(scheduler.completed.wait(), timeout=1.0)


@pytest.mark.asyncio
async def test_hydration_inside_the_budget_behaves_exactly_as_before(monkeypatch):
    """A fast hydration must not be deferred or warned about."""
    monkeypatch.setattr(background, "_SCHEDULER_HYDRATE_BUDGET_SEC", 5.0)
    scheduler = _FastScheduler()

    await background._hydrate_scheduler_bounded(scheduler)

    assert scheduler.calls == 1, "hydration must actually run inline, not be skipped"
    from services.warmup import _warmup_overflow
    assert _warmup_overflow == [], "a fast step must never be deferred"


@pytest.mark.asyncio
async def test_hydration_failure_is_logged_not_raised(monkeypatch, caplog):
    """A broken store must not crash the caller's startup sequence."""
    monkeypatch.setattr(background, "_SCHEDULER_HYDRATE_BUDGET_SEC", 5.0)

    with caplog.at_level(logging.WARNING):
        await background._hydrate_scheduler_bounded(_BrokenScheduler())

    assert any("store unreachable" in r.getMessage() for r in caplog.records), (
        "a failed hydration must be logged, not silently swallowed"
    )
