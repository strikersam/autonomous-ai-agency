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


def test_feature_stores_are_wired_before_anything_can_be_deferred(monkeypatch):
    """The startup crash that failed Render deploys after the warm-up landed.

    ``TaskStore(db=None)`` raises outside tests by design. Wiring the stores
    inside the timed bootstrap meant that when a cold database pushed
    bootstrap past its budget, the deferral skipped the wiring — and the next
    lifespan line, ``start_background_services(task_store=get_task_store())``,
    constructed a store with no database. The lifespan raised, uvicorn exited
    with STARTUP_FAILURE, and the deploy failed. Intermittently, because it
    needed the database to be slow rather than broken.
    """
    wired: list[str] = []
    monkeypatch.setattr(server, "set_agent_store", lambda store: wired.append("agent"))
    monkeypatch.setattr(server, "set_task_store", lambda store: wired.append("task"))

    server._wire_feature_stores()

    assert wired == ["agent", "task"], (
        "both feature stores must be wired without touching the bootstrap"
    )


def test_wiring_the_stores_performs_no_database_io(monkeypatch):
    """It has to be cheap, or it cannot live outside the warm-up budget."""
    calls = {"n": 0}

    class _LazyDb:
        def __getattr__(self, name):
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
