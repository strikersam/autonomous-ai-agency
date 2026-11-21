"""Reliability suite, brief section 13, scenarios 1 to 9 (execution, timeout, failover, worker death).

Each test builds a minimal deterministic setup (fake executors, fake runtimes, scripted
provider transport) and uses the in memory or SQLite backend. No network, no real model.
"""
from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from packages.ai.failover_client import failover_chat_completion
from packages.runs import task_binding
from packages.runs.composition import ChildJob, ChildOutcome, CompositionSpec
from packages.runs.lease import RunLease
from packages.runs.models import RunState
from packages.runs.recovery import RecoveryService
from packages.runs.tree import descendants
from runtimes.base import RuntimeUnavailableError
from tasks.models import TaskStatus
from tasks.service import TaskExecutionCoordinator, TaskWorkflowService
from tests._runs_task_fixtures import (FakeRuntime, coordinator, ok_result, queued_task,
                                       reset_process_state, sqlite_pair, start_dead_worker)
from tests.reliability._helpers import (ENV_KEYS, StubProvider, compose, install_scripted_transport,
                                        ok_body, step)

LATER = 600 + 5  # past the default RUNS_LEASE_TTL_SEC


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    reset_process_state(monkeypatch)
    monkeypatch.setenv("RUNS_LEDGER_ENABLED", "true")
    monkeypatch.setenv("RUNS_RECOVERY_ENABLED", "true")
    monkeypatch.setenv("RUNS_RETRY_BACKOFF_BASE_SEC", "0")


async def test_scenario_01_normal_sequential_execution():
    spec = CompositionSpec(steps=[step("a"), step("b"), step("c")])
    _, store, ex, root, res = await compose(spec)
    assert ex.calls == ["a", "b", "c"] and ex.peak == 1
    assert res.state == "succeeded" and res.aggregate == ["out:a", "out:b", "out:c"]
    kids = await descendants(store, root.run_id)
    assert [k.state for k in kids] == [RunState.SUCCEEDED] * 3
    assert (await store.get(root.run_id)).state is RunState.SUCCEEDED


async def test_scenario_02_two_or_more_agents_execute_in_parallel(monkeypatch):
    monkeypatch.setenv("RUNS_MAX_PARALLEL", "3")
    spec = CompositionSpec(mode="parallel", steps=[step("a"), step("b"), step("c")])
    plan = {k: {"delay": 0.1} for k in "abc"}
    t0 = time.monotonic()
    _, _, ex, _, res = await compose(spec, plan)
    assert res.state == "succeeded" and ex.peak == 3
    assert time.monotonic() - t0 < 0.28  # three 0.1 s children overlapped


async def test_scenario_03_parent_workflow_aggregates_child_results_and_cost():
    spec = CompositionSpec(mode="parallel", steps=[step("a"), step("b")], budget={"max_tokens": 1000})
    plan = {"a": {"out": 1, "tokens": 10, "cost": 0.01}, "b": {"out": 2, "tokens": 20, "cost": 0.02}}
    _, store, _, root, res = await compose(spec, plan)
    assert res.aggregate == [1, 2] and res.state == "succeeded"
    parent = await store.get(root.run_id)
    assert parent.spent_tokens == 30 and parent.spent_micro_usd == 30_000  # charged to the root


async def test_scenario_04_agent_timeout_cancels_the_child_and_times_out_the_parent():
    spec = CompositionSpec(steps=[step("slow")], deadline_s=0.2)
    _, store, _, root, res = await compose(spec, {"slow": {"delay": 30}})
    assert res.state == "timed_out"
    assert (await store.get(root.run_id)).state is RunState.TIMED_OUT
    kid = (await descendants(store, root.run_id))[0]
    assert kid.state is RunState.CANCELLED


async def test_scenario_04b_a_task_execution_timeout_requeues_instead_of_failing(tmp_path):
    async def hang(spec):
        await asyncio.sleep(30)

    async with sqlite_pair(tmp_path) as (store, _):
        task = await queued_task(store)
        coord = TaskExecutionCoordinator(store=store, workflow=TaskWorkflowService(store=store),
                                         runtime_manager=FakeRuntime(hang), execution_timeout_s=0.1,
                                         workspace_root="/tmp/workspace")  # nosec B108 - fake runtime
        done = await coord.execute(task.task_id)
        assert done.status is TaskStatus.TODO and done.pending_agent_run is True
        assert "timed out" in (done.error_message or "")


async def test_scenario_05_runtime_unavailable_before_execution_requeues_then_blocks(tmp_path):
    async def unavailable(spec):
        raise RuntimeUnavailableError("no healthy runtime")

    async with sqlite_pair(tmp_path) as (store, _):
        task = await queued_task(store)
        runtime = FakeRuntime(unavailable)
        done = await coordinator(store, runtime).execute(task.task_id)
        assert done.status is TaskStatus.TODO and done.pending_agent_run is True  # retried later
        assert [e for e in done.execution_log if e.event_type == "runtime_unavailable"]
        lease = await store._run_lease().current(task.task_id)
        assert lease["holder"] == ""  # nothing is left claimed
        for _ in range(6):  # the dispatch retry limit is 5, then the task is parked
            done = await coordinator(store, runtime).execute(task.task_id)
        assert done.status is TaskStatus.BLOCKED


async def test_scenario_06_provider_failure_fails_over_and_the_run_still_succeeds(monkeypatch):
    providers = [StubProvider("nvidia", ["nim-1"]), StubProvider("tokenin", ["t-1"]),
                 StubProvider("cerebras", ["c-1"])]
    manager, calls = install_scripted_transport(monkeypatch, providers, [
        httpx.Response(429, json={"error": "rate limited"}),
        httpx.ConnectError("provider down"), ok_body("answer from cerebras")])
    used: dict[str, str] = {}

    async def llm_child(job: ChildJob) -> ChildOutcome:
        res = await failover_chat_completion({"model": "nim-1", "messages": [{"role": "user", "content": "hi"}]})
        used["provider"] = res.provider_id
        return ChildOutcome(success=True, output=res.text)

    _, _, _, _, res = await compose(CompositionSpec(steps=[step("llm")]), executor=llm_child)
    assert res.state == "succeeded" and res.aggregate == ["answer from cerebras"]
    assert used["provider"] == "cerebras" and len(calls) == 3
    assert ("nvidia", "rate_limited") in manager.failures and ("tokenin", "network_error") in manager.failures


async def test_scenario_07_worker_termination_leaves_a_running_run_with_a_held_lease(tmp_path):
    async with sqlite_pair(tmp_path) as (worker, _):
        task = await queued_task(worker)
        job, finish, binding = await start_dead_worker(worker, task)
        run = await task_binding.run_store_for(worker).get(binding.run_id)
        assert run.state is RunState.RUNNING and run.lease_token == binding.token
        assert (await worker._run_lease().current(task.task_id))["holder"] != ""  # dead, never released
        finish.set()
        await job


async def test_scenario_08_another_worker_recovers_the_abandoned_run_and_finishes_it(tmp_path):
    async with sqlite_pair(tmp_path) as (worker, survivor):
        task = await queued_task(worker)
        job, finish, binding = await start_dead_worker(worker, task)
        report = await RecoveryService(survivor, holder="survivor").tick(now=time.time() + LATER)
        assert report.recovered == [binding.run_id] and report.requeued == [binding.run_id]
        finish.set()
        await job  # the dead worker's late write is fenced out
        async def succeed(spec):
            return ok_result(spec.task_id)

        done = await coordinator(survivor, FakeRuntime(succeed)).execute(task.task_id)
        assert done.current_run_id == binding.run_id
        run = await task_binding.run_store_for(survivor).get(binding.run_id)
        assert run.attempt == 2 and run.state is RunState.SUCCEEDED


async def test_scenario_09_an_expired_lease_is_reacquired_with_a_higher_token(tmp_path):
    async with sqlite_pair(tmp_path) as (a, b):
        la, lb = RunLease(a._db), RunLease(b._db)
        t0 = time.time()
        first = await la.acquire("run:k", "worker-a", 10, now=t0)
        assert first == 1
        assert await lb.acquire("run:k", "worker-b", 10, now=t0 + 5) is None  # still held
        second = await lb.acquire("run:k", "worker-b", 10, now=t0 + 11)  # expired
        assert second == 2
        assert await la.renew("run:k", "worker-a", first, 10, now=t0 + 12) is False  # fenced
        assert await lb.renew("run:k", "worker-b", second, 10, now=t0 + 12) is True
