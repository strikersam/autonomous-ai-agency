"""Regression: two first connects on a brand new SQLite file must both succeed.

``SQLiteStore._get_conn`` switches the file to WAL and creates the schema on its
first connect. When two processes (here: two stores, each with its own
connection thread) do that at the same instant on a new file, the loser got
"database is locked" at once and the store failed to start. The fix retries the
first connect a bounded number of times with a short backoff.
"""
from __future__ import annotations

import asyncio
import multiprocessing as mp

import pytest

from packages.storage.sqlite import SQLiteStore


async def _open(path: str) -> None:
    store = SQLiteStore(path)
    try:
        await store._get_conn()
        await store.tasks.insert_one({"_id": f"t-{id(store)}", "status": "todo"})
    finally:
        await store.close()


@pytest.mark.anyio
async def test_concurrent_first_connects_in_one_process(tmp_path):
    for i in range(15):
        path = str(tmp_path / f"race-{i}.db")
        results = await asyncio.gather(*(_open(path) for _ in range(4)), return_exceptions=True)
        assert [r for r in results if isinstance(r, BaseException)] == [], (i, results)


def _child(path: str, barrier: object) -> None:
    barrier.wait()  # type: ignore[attr-defined]
    asyncio.run(_open(path))


def test_concurrent_first_connects_across_processes(tmp_path):
    ctx = mp.get_context("spawn")
    for i in range(4):
        path = str(tmp_path / f"proc-race-{i}.db")
        barrier = ctx.Barrier(3)
        procs = [ctx.Process(target=_child, args=(path, barrier)) for _ in range(3)]
        for p in procs:
            p.start()
        for p in procs:
            p.join(60)
        assert [p.exitcode for p in procs] == [0, 0, 0], i


@pytest.mark.anyio
async def test_a_locked_first_connect_is_retried(tmp_path, monkeypatch):
    """Deterministic: the first connect meets a lock once; the store still opens."""
    import sqlite3

    real = SQLiteStore._init_schema
    calls = {"n": 0}

    async def flaky(self):
        calls["n"] += 1
        if calls["n"] == 1:
            raise sqlite3.OperationalError("database is locked")
        await real(self)

    monkeypatch.setattr(SQLiteStore, "_init_schema", flaky)
    store = SQLiteStore(str(tmp_path / "locked.db"))
    try:
        await store._get_conn()
        await store.tasks.insert_one({"_id": "t1", "status": "todo"})
        assert (await store.tasks.find_one({"_id": "t1"}))["status"] == "todo"
    finally:
        await store.close()
    assert calls["n"] == 2


@pytest.mark.anyio
async def test_other_errors_are_not_retried(tmp_path, monkeypatch):
    import sqlite3

    async def broken(self):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(SQLiteStore, "_init_schema", broken)
    store = SQLiteStore(str(tmp_path / "broken.db"))
    with pytest.raises(sqlite3.OperationalError, match="disk I/O"):
        await store._get_conn()
