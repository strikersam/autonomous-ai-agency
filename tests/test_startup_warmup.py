"""Regression tests for the bounded startup warm-up and login bootstrap.

Uvicorn opens its listening socket only after the lifespan startup returns, so
anything awaited during warm-up runs with the port closed. A warm-up that
outlives the platform's health-check budget therefore reads as a dead app: the
deploy is restarted, the restart repeats the warm-up, and requests that land in
the gap fail with a browser-level "Network Error" instead of an HTTP status.

These tests pin the two guards that break that loop — the shared warm-up
deadline and the bounded bootstrap in the login handler — plus the concurrent
index creation that made the warm-up short enough to fit in the first place.
"""
from __future__ import annotations

import asyncio
import os
from collections.abc import Coroutine
from typing import Any, NoReturn

import pytest

from backend import server


@pytest.fixture(autouse=True)
def _isolate_warmup_overflow():
    """``_warmup_overflow`` is process-global — keep tests from sharing it."""
    server._warmup_overflow.clear()
    yield
    for task in list(server._warmup_overflow):
        task.cancel()
    server._warmup_overflow.clear()



class _StopLifespan(RuntimeError):
    """Sentinel: halt ``lifespan()`` once the startup ordering is observed."""


def _unexpected_wire() -> NoReturn:
    raise AssertionError("wiring ran even though a store was already registered")


# ── Shared warm-up deadline ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_warmup_step_defers_an_overrunning_step_instead_of_blocking():
    """A slow step must not hold the caller past the deadline."""
    finished = asyncio.Event()

    async def slow() -> str:
        await asyncio.sleep(0.3)
        finished.set()
        return "done"

    deadline = asyncio.get_running_loop().time() + 0.05
    result = await server._warmup_step(slow(), "slow step", deadline)

    assert result is None, "an overrunning step must not block on its result"
    assert not finished.is_set(), "the step should still have been in flight"

    # Deferred, not cancelled: the work still completes in the background.
    await asyncio.wait_for(finished.wait(), timeout=2.0)


@pytest.mark.asyncio
async def test_warmup_step_returns_the_value_when_it_finishes_in_budget():
    async def quick() -> str:
        return "value"

    deadline = asyncio.get_running_loop().time() + 5.0
    assert await server._warmup_step(quick(), "quick step", deadline) == "value"


@pytest.mark.asyncio
async def test_warmup_step_propagates_errors_raised_inside_the_budget():
    """Callers keep their own error handling — failures are not swallowed."""

    async def boom() -> None:
        raise RuntimeError("bootstrap exploded")

    deadline = asyncio.get_running_loop().time() + 5.0
    with pytest.raises(RuntimeError, match="bootstrap exploded"):
        await server._warmup_step(boom(), "failing step", deadline)


@pytest.mark.asyncio
async def test_warmup_budget_is_shared_across_steps_not_spent_per_step():
    """Three slow steps must cost one budget, not three."""

    async def slow() -> None:
        await asyncio.sleep(5.0)

    loop = asyncio.get_running_loop()
    deadline = loop.time() + 0.1
    started = loop.time()
    for i in range(3):
        await server._warmup_step(slow(), f"step {i}", deadline)
    elapsed = loop.time() - started

    assert elapsed < 1.0, f"warm-up spent {elapsed:.2f}s — budget is per step"


@pytest.mark.asyncio
async def test_deferred_step_failure_is_consumed_and_unregistered():
    """A deferred step that fails must not leak a reference or an exception."""

    async def slow_boom() -> None:
        await asyncio.sleep(0.05)
        raise RuntimeError("late failure")

    deadline = asyncio.get_running_loop().time()  # already spent
    await server._warmup_step(slow_boom(), "late failure", deadline)
    assert len(server._warmup_overflow) == 1

    await asyncio.sleep(0.2)
    assert server._warmup_overflow == [], "settled tasks must be unregistered"


# ── Deferral must not take the app down with it ──────────────────────────────


def test_feature_stores_are_wired_on_demand_not_eagerly(monkeypatch):
    """Wire only what is missing — never replace a store somebody registered.

    ``TaskStore(db=None)`` raises outside tests by design, so when a cold
    database pushed bootstrap past its warm-up budget, the deferral skipped
    the wiring inside ``ensure_bootstrap()`` and the next lifespan line
    (``start_background_services(task_store=...)``) crashed the process:
    uvicorn exited with STARTUP_FAILURE and the deploy failed.

    The first attempt at a fix wired the stores eagerly at the top of the
    lifespan. That traded one bug for another — it overwrote stores callers
    had already registered, including the ones tests inject before starting a
    client, so their data silently vanished into a fresh empty store. Repair
    is therefore conditional: ask for the store, and wire only if asking
    fails.
    """
    sentinel = object()
    monkeypatch.setattr(server, "get_task_store", lambda: sentinel)
    monkeypatch.setattr(server, "_wire_feature_stores", _unexpected_wire)

    assert server._task_store_for_background() is sentinel, (
        "an already-registered store must be handed back untouched"
    )


def test_a_missing_task_store_is_wired_rather_than_left_to_crash(monkeypatch):
    """The deferred-bootstrap path: nothing registered, so wire it now."""
    wired: list[str] = []
    built = object()
    attempts = {"n": 0}

    def _get_task_store():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("TaskStore cannot start without a persistent backend")
        return built

    monkeypatch.setattr(server, "get_task_store", _get_task_store)
    monkeypatch.setattr(server, "_wire_feature_stores", lambda: wired.append("wired"))

    assert server._task_store_for_background() is built
    assert wired == ["wired"], "a missing store must be wired, not re-raised"


def test_wire_feature_stores_registers_both_stores(monkeypatch):
    """Whatever triggers it, wiring must register the pair."""
    wired: list[str] = []
    monkeypatch.setattr(server, "set_agent_store", lambda store: wired.append("agent"))
    monkeypatch.setattr(server, "set_task_store", lambda store: wired.append("task"))

    server._wire_feature_stores()

    assert wired == ["agent", "task"]


def test_wiring_the_stores_performs_no_database_io(monkeypatch):
    """It has to be cheap, or it cannot live outside the warm-up budget."""
    calls = {"n": 0}

    class _LazyDb:
        def __getattr__(self, name: str) -> NoReturn:
            calls["n"] += 1
            raise AssertionError(f"store wiring touched the database ({name})")

    monkeypatch.setattr(server, "get_db", lambda: _LazyDb())
    monkeypatch.setattr(server, "set_agent_store", lambda store: None)
    monkeypatch.setattr(server, "set_task_store", lambda store: None)

    server._wire_feature_stores()
    assert calls["n"] == 0


# ── Bootstrap inside the login handler ───────────────────────────────────────


@pytest.mark.asyncio
async def test_login_bootstrap_is_bounded_and_never_raises(monkeypatch):
    """A hanging bootstrap must not hold /api/auth/login open."""
    monkeypatch.setattr(server, "_BOOTSTRAP_DONE", False)

    hung = asyncio.Event()

    async def never_finishes() -> None:
        hung.set()
        await asyncio.sleep(30)

    monkeypatch.setattr(server, "ensure_bootstrap", never_finishes)

    loop = asyncio.get_running_loop()
    started = loop.time()
    completed = await server._bootstrap_within_budget(budget=0.05)
    elapsed = loop.time() - started

    assert completed is False
    assert elapsed < 1.0, f"login waited {elapsed:.2f}s on bootstrap"
    assert hung.is_set()

    for task in list(server._warmup_overflow):
        task.cancel()
    server._warmup_overflow.clear()


@pytest.mark.asyncio
async def test_login_bootstrap_reports_failure_without_propagating(monkeypatch):
    """A failed bootstrap leaves the handler to its own DB error handling."""
    monkeypatch.setattr(server, "_BOOTSTRAP_DONE", False)

    async def broken() -> None:
        raise RuntimeError("no database")

    monkeypatch.setattr(server, "ensure_bootstrap", broken)
    assert await server._bootstrap_within_budget(budget=1.0) is False


@pytest.mark.asyncio
async def test_login_bootstrap_short_circuits_once_done(monkeypatch):
    """The warm path costs nothing — no task, no timer."""
    monkeypatch.setattr(server, "_BOOTSTRAP_DONE", True)

    called = False

    async def should_not_run() -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(server, "ensure_bootstrap", should_not_run)
    assert await server._bootstrap_within_budget() is True
    assert called is False


# ── Concurrent index creation ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bootstrap_indexes_are_created_concurrently(monkeypatch):
    """Fifteen serial round-trips to Atlas is the warm-up cost being removed."""
    in_flight = 0
    peak = 0

    class _FakeCollection:
        async def create_index(self, *_args, **_kwargs) -> None:
            nonlocal in_flight, peak
            in_flight += 1
            peak = max(peak, in_flight)
            await asyncio.sleep(0.01)
            in_flight -= 1

    class _FakeDb:
        def __getattr__(self, _name: str) -> _FakeCollection:
            return _FakeCollection()

    monkeypatch.setattr(server, "get_db", lambda: _FakeDb())
    await server._create_bootstrap_indexes()

    assert peak > 1, "indexes were still issued one round-trip at a time"
    assert peak == len(server._BOOTSTRAP_INDEXES)


def test_bootstrap_index_declaration_covers_the_known_collections():
    """Guard against an index silently dropping out of the data table."""
    collections = {name for name, _keys, _opts in server._BOOTSTRAP_INDEXES}
    assert {
        "users", "wiki_pages", "sources", "activity_log", "chat_sessions",
        "providers", "api_keys", "github_settings", "oauth_states",
        "agent_definitions", "tasks",
    } <= collections

    unique_on = {
        (name, keys) for name, keys, opts in server._BOOTSTRAP_INDEXES
        if opts.get("unique")
    }
    assert ("users", "email") in unique_on
    assert ("tasks", "task_id") in unique_on

    ttl = [opts for name, _k, opts in server._BOOTSTRAP_INDEXES if name == "oauth_states"]
    assert ttl and ttl[0]["expireAfterSeconds"] == 600


# ── Login behaviour is unchanged ─────────────────────────────────────────────


def test_login_still_rejects_bad_credentials(client):
    resp = client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "wrong"},
    )
    assert resp.status_code == 401


def test_login_still_succeeds_for_the_seeded_admin(client):
    resp = client.post(
        "/api/auth/login",
        json={
            "email": server.ADMIN_EMAIL,
            "password": os.environ.get("ADMIN_PASSWORD", ""),
        },
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]
