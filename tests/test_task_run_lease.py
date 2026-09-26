"""Atomic task checkout: one run per task across processes (tasks/store.py, tasks/service.py).

Regression for double work. ``/api/autonomy/tick`` executed the oldest pending
task directly, never taking the coordinator's claim, so the cron tick and the
dispatcher could run the same task at once. And the coordinator's claim was
the in-memory ``shared_state`` lock, which does not span the web process and
the worker when ``REDIS_URL`` is unset.
"""
from __future__ import annotations

import asyncio
import time

import pytest

from tasks import run_lease as service
from tasks.store import TaskStore


class _DuplicateKeyError(Exception):
    """Same class name pymongo uses; the store matches on the name."""


class _Result:
    def __init__(self, matched: int, modified: int) -> None:
        self.matched_count = matched
        self.modified_count = modified


class _FakeMongoLeases:
    """The three Mongo operations the lease uses, with Mongo's atomicity."""

    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}

    async def insert_one(self, doc):
        if doc["_id"] in self.docs:
            raise _DuplicateKeyError("E11000 duplicate key")
        self.docs[doc["_id"]] = dict(doc)

    async def update_one(self, query, update):
        doc = self.docs.get(query["_id"])
        if doc is None:
            return _Result(0, 0)
        ok = any(
            ("expires_at" in c and doc["expires_at"] < c["expires_at"]["$lt"])
            or ("holder" in c and doc["holder"] == c["holder"])
            for c in query["$or"]
        )
        if not ok:
            return _Result(0, 0)
        changed = any(doc.get(k) != v for k, v in update["$set"].items())
        doc.update(update["$set"])
        return _Result(1, 1 if changed else 0)

    async def delete_one(self, query):
        doc = self.docs.get(query["_id"])
        if doc and doc["holder"] == query["holder"]:
            del self.docs[query["_id"]]


class _FakeMongoDb:
    def __init__(self) -> None:
        self.leases = _FakeMongoLeases()

    def __getitem__(self, name):
        assert name == "task_run_leases"
        return self.leases


def _mongo_store() -> TaskStore:
    store = TaskStore.__new__(TaskStore)
    store._db = _FakeMongoDb()
    store._mode = "mongo"
    store._mem = {}
    return store


@pytest.fixture(params=["memory", "mongo"])
def store(request):
    return TaskStore() if request.param == "memory" else _mongo_store()


@pytest.mark.anyio
async def test_only_one_holder_gets_the_lease(store):
    assert await store.acquire_run_lease("t1", "web", 60) is True
    assert await store.acquire_run_lease("t1", "worker", 60) is False
    assert await store.acquire_run_lease("t2", "worker", 60) is True


@pytest.mark.anyio
async def test_release_frees_it_and_only_for_the_holder(store):
    await store.acquire_run_lease("t1", "web", 60)
    await store.release_run_lease("t1", "worker")  # not the holder: no effect
    assert await store.acquire_run_lease("t1", "worker", 60) is False
    await store.release_run_lease("t1", "web")
    assert await store.acquire_run_lease("t1", "worker", 60) is True


@pytest.mark.anyio
async def test_an_expired_lease_can_be_taken_over(store, monkeypatch):
    await store.acquire_run_lease("t1", "crashed-process", 60)
    real = time.time
    monkeypatch.setattr("tasks.store.time.time", lambda: real() + 120)
    assert await store.acquire_run_lease("t1", "worker", 60) is True


@pytest.mark.anyio
async def test_the_holder_can_renew(store):
    assert await store.acquire_run_lease("t1", "web", 60) is True
    assert await store.acquire_run_lease("t1", "web", 60) is True


@pytest.mark.anyio
async def test_concurrent_claims_on_one_task_admit_exactly_one():
    store = _mongo_store()
    results = await asyncio.gather(
        *(store.acquire_run_lease("t1", f"proc-{i}", 60) for i in range(10))
    )
    assert results.count(True) == 1


@pytest.mark.anyio
async def test_claim_task_run_fails_closed_and_releases_the_local_lock(monkeypatch):
    class _BrokenStore:
        async def acquire_run_lease(self, *args):
            raise RuntimeError("lease backend down")

        async def release_run_lease(self, *args):
            pass

    assert await service.claim_task_run(_BrokenStore(), "t1") is False
    # The in-process lock was released, so a healthy retry can proceed.
    healthy = TaskStore()
    assert await service.claim_task_run(healthy, "t1") is True
    await service.release_task_run(healthy, "t1")


@pytest.mark.anyio
async def test_a_second_process_cannot_claim_a_running_task(monkeypatch):
    store = _mongo_store()
    assert await service.claim_task_run(store, "t1") is True
    # Another process: a different holder id, and its own in-memory lock.
    monkeypatch.setattr(service, "_RUN_LEASE_HOLDER", "other-process")
    monkeypatch.setattr(service, "_shared_claim", _always_free)
    assert await service.claim_task_run(store, "t1") is False


async def _always_free(key, ttl):
    return True


def test_autonomy_tick_skips_a_task_the_dispatcher_holds(monkeypatch):
    from fastapi.testclient import TestClient

    import backend.server as server
    from tasks.models import Task

    task = Task(owner_id="system", title="held by dispatcher")

    class _Store:
        async def list_pending(self, limit=1):
            return [task]

        async def list_blocked(self, limit=10):
            return []

        async def update(self, t):
            raise AssertionError("the tick must not touch a task it did not claim")

    async def held(store, task_id):
        return False

    monkeypatch.setattr("tasks.store.get_task_store", lambda: _Store())
    monkeypatch.setattr(service, "claim_task_run", held)
    monkeypatch.setattr(server, "_anon_tick_last", {})
    monkeypatch.delenv("CRON_SECRET", raising=False)
    client = TestClient(server.app, raise_server_exceptions=False)
    monkeypatch.setenv("SELF_BOOTSTRAP_ENABLED", "true")
    body = client.get("/api/autonomy/tick").json()
    assert body["dispatch"].get("task_id") == task.task_id, body
    assert body["dispatch"]["task_id"] == task.task_id
    assert body["dispatch"]["skipped"] == "task already running elsewhere"
    assert body["dispatch"]["ran"] is False


@pytest.mark.anyio
async def test_stores_without_a_lease_fall_back_to_the_process_lock():
    from unittest.mock import MagicMock

    store = MagicMock()  # no acquire_run_lease on its class
    assert await service.claim_task_run(store, "t-mock") is True
    assert await service.claim_task_run(store, "t-mock") is False  # process lock held
    await service.release_task_run(store, "t-mock")
    assert await service.claim_task_run(store, "t-mock") is True
    await service.release_task_run(store, "t-mock")
