"""Phase 2 A: the task path writes durable runs (packages/runs/task_binding.py)."""
from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from packages.runs import task_binding
from packages.runs.models import RunState
from tasks.models import TaskStatus
from tasks.store import TaskStore
from tests._runs_task_fixtures import (FakeRuntime, coordinator, queued_task,
                                       reset_process_state, sqlite_pair)


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    reset_process_state(monkeypatch)
    monkeypatch.setenv("RUNS_LEDGER_ENABLED", "true")


async def _events(store: TaskStore, run_id: str) -> list[str]:
    run_store = task_binding.run_store_for(store)
    return [e.kind for e in await run_store.list_events(run_id)]


@pytest.mark.anyio
async def test_memory_store_keeps_todays_path_and_writes_no_run():
    store = TaskStore()
    task = await queued_task(store)
    updated = await coordinator(store, FakeRuntime()).execute(task.task_id)
    assert updated.status is TaskStatus.FAILED
    assert updated.current_run_id is None
    assert task_binding.active_bindings() == []


@pytest.mark.anyio
async def test_a_failed_execution_records_the_run_and_releases_the_lease(tmp_path):
    async with sqlite_pair(tmp_path) as (store, other):
        task = await queued_task(store)
        updated = await coordinator(store, FakeRuntime()).execute(task.task_id)
        assert updated.status is TaskStatus.FAILED
        run_id = updated.current_run_id
        assert run_id and (await store.get(task.task_id)).current_run_id == run_id
        run = await task_binding.run_store_for(other).get(run_id)
        assert run.state is RunState.FAILED and run.attempt == 1 and run.lease_token == 1
        kinds = await _events(store, run_id)
        assert kinds[:2] == ["created", "state_changed"] and "attempt_started" in kinds
        lease = await other._run_lease().current(task.task_id)
        assert lease["holder"] == ""  # released
        assert task_binding.active_bindings() == []


@pytest.mark.anyio
async def test_a_requeued_task_resumes_the_same_run_with_the_next_attempt(tmp_path):
    async with sqlite_pair(tmp_path) as (store, _):
        task = await queued_task(store)
        runtime = FakeRuntime(lambda spec: _raise(httpx.ConnectError("Connection refused")))
        first = await coordinator(store, runtime).execute(task.task_id)
        assert first.status is TaskStatus.TODO and first.pending_agent_run is True
        run = await task_binding.run_store_for(store).get(first.current_run_id)
        assert run.state is RunState.RETRYING
        second = await coordinator(store, FakeRuntime()).execute(task.task_id)
        assert second.current_run_id == first.current_run_id
        run = await task_binding.run_store_for(store).get(second.current_run_id)
        assert run.attempt == 2 and run.lease_token == 2 and run.state is RunState.FAILED


@pytest.mark.anyio
async def test_ledger_off_keeps_the_heartbeat_but_writes_no_run(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNS_LEDGER_ENABLED", "false")
    async with sqlite_pair(tmp_path) as (store, _):
        task = await queued_task(store)
        updated = await coordinator(store, FakeRuntime()).execute(task.task_id)
        assert updated.status is TaskStatus.FAILED
        assert updated.current_run_id is None
        assert await task_binding.run_store_for(store).list(task_id=task.task_id) == []


@pytest.mark.anyio
async def test_a_worker_that_loses_its_lease_stops_and_its_result_is_dropped(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNS_LEASE_TTL_SEC", "10")
    monkeypatch.setenv("RUNS_LEASE_RENEW_SEC", "1")
    async with sqlite_pair(tmp_path) as (store, other):
        task = await queued_task(store)

        async def stolen(spec):
            # Another process takes the lease over (as if it had expired) mid run.
            token = await other._run_lease().acquire(task.task_id, "other-process", 60,
                                                     now=time.time() + 1000)
            assert token == 2
            await asyncio.sleep(30)  # the guard must stop this stale work

        started = time.monotonic()
        updated = await coordinator(store, FakeRuntime(stolen)).execute(task.task_id)
        assert time.monotonic() - started < 10
        stored = await other.get(task.task_id)
        assert stored.status is TaskStatus.IN_PROGRESS  # the stale FAILED was not written
        assert updated.status is TaskStatus.FAILED  # only in the stale worker's memory
        assert "fenced_out" in await _events(store, updated.current_run_id)
        lease = await other._run_lease().current(task.task_id)
        assert lease["holder"] == "other-process" and lease["token"] == 2


def test_path_to_follows_the_run_lifecycle():
    assert task_binding.path_to("running", "succeeded") == ["verifying", "succeeded"]
    assert task_binding.path_to("created", "starting") == ["queued", "starting"]
    assert task_binding.path_to("waiting_for_approval", "starting") == [
        "recovering", "queued", "starting"]
    assert task_binding.path_to("starting", "retrying") == ["running", "retrying"]


async def _raise(exc: BaseException):
    raise exc


@pytest.mark.anyio
async def test_an_api_cancel_is_observed_with_the_ledger_off(tmp_path, monkeypatch):
    from packages.runs.models import RunRecord

    monkeypatch.setenv("RUNS_LEDGER_ENABLED", "false")
    monkeypatch.setenv("RUNS_LEASE_TTL_SEC", "10")
    monkeypatch.setenv("RUNS_LEASE_RENEW_SEC", "1")
    async with sqlite_pair(tmp_path) as (store, _):
        task = await queued_task(store)
        runs = task_binding.run_store_for(store)
        run = await runs.create(RunRecord(task_id=task.task_id, state=RunState.QUEUED,
                                          cancel_requested=True))
        task.current_run_id = run.run_id
        await store.update(task)

        async def long_work(spec):
            await asyncio.sleep(30)

        started = time.monotonic()
        updated = await coordinator(store, FakeRuntime(long_work)).execute(task.task_id)
        assert time.monotonic() - started < 10
        assert updated.status is TaskStatus.WONT_DO
