"""Phase 2 E: RecoveryService takes over crashed task runs (packages/runs/recovery.py).

Two ``TaskStore``s on one SQLite file stand in for the dead worker and the
process that recovers its run. The lease expiry is simulated by ticking the
recovery at a monotonic "now" past the lease TTL.
"""
from __future__ import annotations

import time

import pytest

from packages.runs import task_binding
from packages.runs.models import RunRecord, RunState
from packages.runs.operations import OperationLedger
from packages.runs.recovery import RecoveryService, backoff_s
from tasks.models import Task, TaskStatus
from tests._runs_task_fixtures import (FakeRuntime, coordinator, queued_task,
                                       reset_process_state, sqlite_pair, start_dead_worker)

LATER = 600 + 5  # past the default RUNS_LEASE_TTL_SEC


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    reset_process_state(monkeypatch)
    monkeypatch.setenv("RUNS_LEDGER_ENABLED", "true")
    monkeypatch.setenv("RUNS_RECOVERY_ENABLED", "true")
    monkeypatch.setenv("RUNS_RETRY_BACKOFF_BASE_SEC", "0")
    monkeypatch.delenv("AGENCY_KILL_SWITCH", raising=False)
    monkeypatch.delenv("RUNS_MAX_ATTEMPTS", raising=False)


@pytest.mark.anyio
async def test_a_dead_worker_is_recovered_and_its_late_settle_is_fenced(tmp_path):
    async with sqlite_pair(tmp_path) as (worker, survivor):
        task = await queued_task(worker)
        job, finish, binding = await start_dead_worker(worker, task)
        run_id = binding.run_id

        report = await RecoveryService(survivor, holder="survivor").tick(now=time.time() + LATER)
        assert report.recovered == [run_id] and report.requeued == [run_id]
        run = await task_binding.run_store_for(survivor).get(run_id)
        assert run.state is RunState.QUEUED and run.attempt == 2 and run.lease_token == 2
        lease = await survivor._run_lease().current(task.task_id)
        assert lease["token"] == 2 and lease["holder"] == ""  # taken with a higher token, released
        requeued = await survivor.get(task.task_id)
        assert requeued.status is TaskStatus.TODO and requeued.pending_agent_run is True
        assert requeued.current_run_id == run_id

        # (b) the dead worker comes back: its final write is fenced out and dropped.
        finish.set()
        stale = await job
        assert stale.status is TaskStatus.FAILED  # in its own memory only
        stored = await survivor.get(task.task_id)
        assert stored.status is TaskStatus.TODO and stored.pending_agent_run is True
        kinds = [e.kind for e in await task_binding.run_store_for(survivor).list_events(run_id)]
        assert "fenced_out" in kinds

        # The next dispatch resumes the same run without counting the attempt twice.
        again = await coordinator(survivor, FakeRuntime()).execute(task.task_id)
        assert again.current_run_id == run_id
        run = await task_binding.run_store_for(survivor).get(run_id)
        assert run.attempt == 2 and run.lease_token == 3 and run.state is RunState.FAILED


@pytest.mark.anyio
async def test_an_uncertain_side_effect_parks_the_run_for_a_person(tmp_path):
    async def push_in_flight(binding):
        await OperationLedger(binding.store).begin(
            binding.run_id, "git_push", {"branch": "agent/task-x", "sha": "abc"},
            {"branch": "agent/task-x"}, binding.token, 300, lease_remaining_s=1000)

    async with sqlite_pair(tmp_path) as (worker, survivor):
        task = await queued_task(worker)
        job, finish, binding = await start_dead_worker(worker, task, before_death=push_in_flight)
        report = await RecoveryService(survivor).tick(now=time.time() + LATER)
        assert report.parked == [binding.run_id] and report.requeued == []
        run = await task_binding.run_store_for(survivor).get(binding.run_id)
        assert run.state is RunState.WAITING_FOR_APPROVAL
        assert run.waiting_reason == "uncertain_side_effect"
        parked = await survivor.get(task.task_id)
        assert parked.requires_approval is True and parked.execution_approved is False
        assert parked.pending_agent_run is False
        assert any(e.event_type == "run_parked" for e in parked.execution_log)
        finish.set()
        await job


@pytest.mark.anyio
async def test_exhausted_attempts_dead_letter_the_run_and_fail_the_task(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNS_MAX_ATTEMPTS", "1")
    async with sqlite_pair(tmp_path) as (worker, survivor):
        task = await queued_task(worker)
        job, finish, binding = await start_dead_worker(worker, task)
        report = await RecoveryService(survivor).tick(now=time.time() + LATER)
        assert report.dead_lettered == [binding.run_id]
        run = await task_binding.run_store_for(survivor).get(binding.run_id)
        assert run.state is RunState.DEAD_LETTER and "dead letter" in run.failure_reason
        failed = await survivor.get(task.task_id)
        assert failed.status is TaskStatus.FAILED and failed.pending_agent_run is False
        assert failed.auto_retry_count >= 5  # the FAILED reconciler pass leaves it alone
        assert await survivor.reconcile_stranded_tasks(stale_threshold_s=0) == 0
        finish.set()
        await job


@pytest.mark.anyio
async def test_the_kill_switch_stops_the_recovery_tick(tmp_path, monkeypatch):
    async with sqlite_pair(tmp_path) as (worker, survivor):
        task = await queued_task(worker)
        job, finish, binding = await start_dead_worker(worker, task)
        monkeypatch.setenv("AGENCY_KILL_SWITCH", "true")
        report = await RecoveryService(survivor).tick(now=time.time() + LATER)
        assert report.skipped == "kill_switch" and report.recovered == []
        run = await task_binding.run_store_for(survivor).get(binding.run_id)
        assert run.state is RunState.RUNNING
        finish.set()
        await job


@pytest.mark.anyio
async def test_recovery_off_or_memory_mode_does_nothing(tmp_path, monkeypatch):
    from tasks.store import TaskStore

    assert (await RecoveryService(TaskStore()).tick()).skipped == "no_durable_lease"
    monkeypatch.setenv("RUNS_RECOVERY_ENABLED", "false")
    assert (await RecoveryService(TaskStore()).tick()).skipped == "disabled"


@pytest.mark.anyio
async def test_a_live_lease_is_not_recovered(tmp_path):
    async with sqlite_pair(tmp_path) as (worker, survivor):
        task = await queued_task(worker)
        job, finish, binding = await start_dead_worker(worker, task)
        # Not yet expired: nothing to recover.
        report = await RecoveryService(survivor).tick(now=time.time() + 5)
        assert report.recovered == []
        finish.set()
        await job


@pytest.mark.anyio
async def test_stranded_reconciler_skips_a_task_whose_lease_is_live_elsewhere(tmp_path):
    async with sqlite_pair(tmp_path) as (web, worker):
        task = Task(owner_id="o@x.com", title="t", status=TaskStatus.IN_PROGRESS,
                    pending_agent_run=False)
        await web.create(task)
        assert await worker.acquire_run_lease(task.task_id, "worker-process", 600) is True
        assert await web.reconcile_stranded_tasks(stale_threshold_s=0) == 0
        await worker.release_run_lease(task.task_id, "worker-process")
        assert await web.reconcile_stranded_tasks(stale_threshold_s=0) == 1


@pytest.mark.anyio
@pytest.mark.parametrize("durable", [False, True])
async def test_parked_parents_are_skipped_by_the_reconciler_and_auto_retry(tmp_path, durable):
    from tasks.store import TaskStore

    async with sqlite_pair(tmp_path) as (a, _):
        store = a if durable else TaskStore()
        parked = Task(owner_id="o@x.com", title="parent", status=TaskStatus.IN_PROGRESS,
                      pending_agent_run=False, waiting_on_children=True)
        todo = Task(owner_id="o@x.com", title="parent2", status=TaskStatus.TODO,
                    pending_agent_run=False, waiting_on_children=True)
        blocked = Task(owner_id="o@x.com", title="parent3", status=TaskStatus.BLOCKED,
                       waiting_on_children=True)
        for t in (parked, todo, blocked):
            await store.create(t)
        assert await store.reconcile_stranded_tasks(stale_threshold_s=0) == 0
        assert await store.list_blocked() == []


@pytest.mark.anyio
async def test_a_parked_parent_wakes_when_every_child_is_terminal(tmp_path):
    async with sqlite_pair(tmp_path) as (store, _):
        parent_task = Task(owner_id="o@x.com", title="parent", status=TaskStatus.IN_PROGRESS,
                           pending_agent_run=False, waiting_on_children=True)
        await store.create(parent_task)
        runs = task_binding.run_store_for(store)
        parent = await runs.create(RunRecord(task_id=parent_task.task_id,
                                             state=RunState.WAITING_FOR_AGENT))
        child = await runs.create(RunRecord(parent_run_id=parent.run_id, state=RunState.RUNNING))
        service = RecoveryService(store)
        assert (await service.tick()).woken == []
        await runs.update(child.run_id, {"state": RunState.SUCCEEDED})
        report = await service.tick()
        assert report.woken == [parent.run_id] and report.requeued == [parent.run_id]
        woken = await store.get(parent_task.task_id)
        assert woken.waiting_on_children is False and woken.pending_agent_run is True
        assert (await runs.get(parent.run_id)).state is RunState.QUEUED


@pytest.mark.anyio
async def test_a_run_past_its_deadline_times_out(tmp_path):
    async with sqlite_pair(tmp_path) as (store, _):
        runs = task_binding.run_store_for(store)
        run = await runs.create(RunRecord(state=RunState.RUNNING, deadline_at=time.time() - 1))
        report = await RecoveryService(store).tick()
        assert report.timed_out == [run.run_id]
        stored = await runs.get(run.run_id)
        assert stored.state is RunState.TIMED_OUT and stored.cancel_requested is True


def test_backoff_doubles_with_jitter(monkeypatch):
    monkeypatch.setenv("RUNS_RETRY_BACKOFF_BASE_SEC", "10")
    assert backoff_s(2, rand=lambda: 0.0) == 10
    assert backoff_s(3, rand=lambda: 0.0) == 20
    assert backoff_s(3, rand=lambda: 1.0) == 25
    monkeypatch.setenv("RUNS_RETRY_BACKOFF_BASE_SEC", "0")
    assert backoff_s(5) == 0


@pytest.mark.anyio
async def test_backoff_delays_the_requeue_until_not_before(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNS_RETRY_BACKOFF_BASE_SEC", "10")
    async with sqlite_pair(tmp_path) as (worker, survivor):
        task = await queued_task(worker)
        job, finish, binding = await start_dead_worker(worker, task)
        now = time.time() + LATER
        service = RecoveryService(survivor)
        report = await service.tick(now=now)
        assert report.recovered == [binding.run_id] and report.requeued == []
        assert (await survivor.get(task.task_id)).pending_agent_run is False
        report = await service.tick(now=now + 30)
        assert report.requeued == [binding.run_id]
        assert (await survivor.get(task.task_id)).pending_agent_run is True
        finish.set()
        await job


@pytest.mark.anyio
async def test_the_dispatcher_runs_the_tick_at_its_cadence(monkeypatch):
    from tasks import dispatcher as dmod
    from tasks.store import TaskStore

    calls = []

    class _Recovery:
        async def tick(self):
            calls.append(1)
            from packages.runs.recovery import RecoveryReport
            return RecoveryReport()

    d = dmod.TaskDispatcher(workspace_root="/tmp/workspace", store=TaskStore())  # nosec B108
    d._recovery = _Recovery()
    await d._recovery_tick()
    await d._recovery_tick()  # within RUNS_RECOVERY_TICK_SEC: skipped
    assert calls == [1]
    monkeypatch.setenv("RUNS_RECOVERY_ENABLED", "false")
    d._recovered_at = float("-inf")
    await d._recovery_tick()
    assert calls == [1]
