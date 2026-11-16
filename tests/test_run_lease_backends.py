"""Regression: the run lease must hold across processes on the production storage types.

``TaskStore._lease_collection()`` returned ``None`` for any db whose class lives in
``packages.storage`` (``MongoStore`` and ``SQLiteStore``), so production
(``TaskStore(db=MongoStore())``) fell back to a process local dict and two
processes could both hold the lease for one task. Each test builds two
``TaskStore`` instances over the same backing database, one per "process".
"""
from __future__ import annotations

import time

import pytest

from packages.storage.mongo import MongoStore
from packages.storage.sqlite import SQLiteStore
from tasks.store import TaskStore
from tests._fake_motor import FakeMotorDb


def _mongo_store(shared: FakeMotorDb) -> MongoStore:
    store = MongoStore()
    # A real MongoStore whose lazy Motor database is replaced by the hermetic fake.
    store._get_db = lambda: shared  # type: ignore[method-assign]
    return store


@pytest.fixture(params=["mongo", "sqlite"])
async def two_processes(request, tmp_path):
    if request.param == "mongo":
        shared = FakeMotorDb()
        yield TaskStore(db=_mongo_store(shared)), TaskStore(db=_mongo_store(shared))
        return
    path = str(tmp_path / "agency.db")
    a, b = SQLiteStore(path), SQLiteStore(path)
    await a._get_conn()  # first connects one at a time (see tests/_runs_backends.py)
    await b._get_conn()
    try:
        yield TaskStore(db=a), TaskStore(db=b)
    finally:
        await a.close()
        await b.close()


async def test_two_processes_cannot_both_hold_the_lease(two_processes):
    web, worker = two_processes
    assert await web.acquire_run_lease("t1", "web-pid", 60) is True
    assert await worker.acquire_run_lease("t1", "worker-pid", 60) is False


async def test_release_in_one_process_frees_it_for_the_other(two_processes):
    web, worker = two_processes
    assert await web.acquire_run_lease("t1", "web-pid", 60) is True
    await worker.release_run_lease("t1", "worker-pid")  # not the holder: no effect
    assert await worker.acquire_run_lease("t1", "worker-pid", 60) is False
    await web.release_run_lease("t1", "web-pid")
    assert await worker.acquire_run_lease("t1", "worker-pid", 60) is True


async def test_an_expired_lease_is_taken_over_by_the_other_process(two_processes, monkeypatch):
    web, worker = two_processes
    assert await web.acquire_run_lease("t1", "crashed-pid", 60) is True
    real = time.time
    monkeypatch.setattr("tasks.store.time.time", lambda: real() + 120)
    assert await worker.acquire_run_lease("t1", "worker-pid", 60) is True
    assert await web.acquire_run_lease("t1", "crashed-pid", 60) is False
