"""Phase 4: the run tree budget (packages/runs/budget.py), scenario 21, and the kill switch."""
from __future__ import annotations

import asyncio
import time

import pytest

from packages.runs import budget, task_binding
from packages.runs.budget import BudgetExhausted
from packages.runs.composer import Composer
from packages.runs.composition import ChildJob, ChildOutcome, CompositionSpec, Step
from packages.runs.models import RunRecord, RunState
from packages.runs.store import RunStore
from packages.runs.tree import descendants
from tasks.models import TaskStatus
from tests._runs_task_fixtures import (FakeRuntime, coordinator, queued_task,
                                       reset_process_state, sqlite_pair)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("AGENCY_KILL_SWITCH", raising=False)


async def _tree(store: RunStore, **budget_kw):
    root = await store.create(RunRecord(state=RunState.RUNNING, budget=budget_kw))
    kids = [await store.create(RunRecord(parent_run_id=root.run_id, root_run_id=root.run_id,
                                         depth=1, state=RunState.RUNNING)) for _ in range(3)]
    return root, kids


async def test_children_charge_the_root_and_remaining_shrinks():
    store = RunStore()
    root, kids = await _tree(store, max_cost_usd=1.0, max_tokens=1000, max_steps=10)
    left = await budget.charge(store, kids[0].run_id, cost_usd=0.25, tokens=100, steps=1)
    assert (left.cost_usd, left.tokens, left.steps) == (0.75, 900, 9)
    left = await budget.charge(store, kids[1].run_id, cost_usd=0.25, tokens=100, steps=1)
    assert (left.cost_usd, left.tokens, left.steps) == (0.5, 800, 8)
    got = await store.get(root.run_id)
    assert (got.spent_micro_usd, got.spent_tokens, got.spent_steps) == (500_000, 200, 2)
    assert (await store.get(kids[0].run_id)).spent_tokens == 0  # only the root holds spend
    assert (await budget.remaining(store, kids[2].run_id)).tokens == 800


async def test_no_limits_means_unlimited():
    store = RunStore()
    _, kids = await _tree(store)
    left = await budget.charge(store, kids[0].run_id, cost_usd=99, tokens=10**9)
    assert (left.cost_usd, left.tokens, left.steps) == (None, None, None)


async def test_exhaustion_raises_cancels_the_tree_and_keeps_raising():
    store = RunStore()
    root, kids = await _tree(store, max_cost_usd=1.0)
    await budget.charge(store, kids[0].run_id, cost_usd=0.6)
    with pytest.raises(BudgetExhausted) as err:
        await budget.charge(store, kids[1].run_id, cost_usd=0.6)
    assert err.value.limit == "max_cost_usd" and err.value.root_run_id == root.run_id
    assert (await store.get(root.run_id)).cancel_requested
    assert all(k.cancel_requested for k in await descendants(store, root.run_id))
    events = [e.kind for e in await store.list_events(root.run_id)]
    assert events.count("budget_exhausted") == 1
    with pytest.raises(BudgetExhausted):
        await budget.charge(store, kids[2].run_id, cost_usd=0.01)
    assert [e.kind for e in await store.list_events(root.run_id)].count("budget_exhausted") == 1


async def test_concurrent_charges_are_not_lost():
    store = RunStore()
    root, kids = await _tree(store, max_tokens=10_000)
    await asyncio.gather(*(budget.charge(store, kids[i % 3].run_id, tokens=10) for i in range(50)))
    assert (await store.get(root.run_id)).spent_tokens == 500


async def test_step_cap_and_token_cap():
    store = RunStore()
    _, kids = await _tree(store, max_steps=2, max_tokens=50)
    await budget.charge(store, kids[0].run_id, steps=2, tokens=50)  # at the limit is fine
    with pytest.raises(BudgetExhausted) as err:
        await budget.charge(store, kids[0].run_id, steps=1)
    assert err.value.limit == "max_steps"


async def test_budget_exhaustion_across_delegated_children_cancels_the_composition():
    """Scenario 21: children of one composition spend; the root budget stops the rest."""
    async def ex(job: ChildJob) -> ChildOutcome:
        if job.step.key.startswith("slow"):
            await asyncio.sleep(5)
        return ChildOutcome(success=True, output=job.step.key, cost_usd=0.4)

    store = RunStore()
    spec = CompositionSpec(steps=[Step(key="a"), Step(key="b"), Step(key="c"),
                                  Step(key="slow1"), Step(key="slow2")], mode="parallel",
                           budget={"max_cost_usd": 1.0})
    composer = Composer(store, ex, cancel_poll_s=0.01)
    root = await composer.start(spec)
    import os
    os.environ["RUNS_MAX_PARALLEL"] = "5"
    try:
        res = await asyncio.wait_for(composer.run(root.run_id, spec), 3)
    finally:
        os.environ.pop("RUNS_MAX_PARALLEL", None)
    assert res.state == "failed" and "budget_exhausted" in (res.error or "")
    got = await store.get(root.run_id)
    assert got.state is RunState.FAILED and got.spent_micro_usd <= 1_400_000  # cap + one child (reserved before start)
    kids = {r.phase: r.state for r in await descendants(store, root.run_id)}
    assert kids["step:slow1"] is RunState.CANCELLED and kids["step:slow2"] is RunState.CANCELLED
    assert [e for e in await store.list_events(root.run_id) if e.kind == "budget_exhausted"]


async def test_kill_switch_during_an_active_run_stops_it_within_one_heartbeat(tmp_path, monkeypatch):
    """Scenario 20 on the real task path: the heartbeat tick sees the switch."""
    reset_process_state(monkeypatch)
    monkeypatch.setenv("RUNS_LEDGER_ENABLED", "true")
    monkeypatch.setenv("RUNS_LEASE_TTL_SEC", "10")
    monkeypatch.setenv("RUNS_LEASE_RENEW_SEC", "1")
    async with sqlite_pair(tmp_path) as (store, _):
        task = await queued_task(store)
        started = asyncio.Event()

        async def long_work(spec):
            started.set()
            await asyncio.sleep(30)

        job = asyncio.create_task(coordinator(store, FakeRuntime(long_work)).execute(task.task_id))
        await asyncio.wait_for(started.wait(), 5)
        t0 = time.monotonic()
        monkeypatch.setenv("AGENCY_KILL_SWITCH", "true")
        updated = await asyncio.wait_for(job, 5)
        assert time.monotonic() - t0 < 3.5  # one renew interval (1 s) plus slack
        assert updated.status is TaskStatus.WONT_DO
        run = await task_binding.run_store_for(store).get(updated.current_run_id)
        assert run.state is RunState.CANCELLED
        kinds = [e.kind for e in await task_binding.run_store_for(store).list_events(run.run_id)]
        assert "kill_switch" in kinds


async def test_poll_cancel_ignores_the_switch_when_off():
    store = RunStore()
    run = await store.create(RunRecord(state=RunState.RUNNING))

    class _B:
        cancel = asyncio.Event()
        recording = True
        task_id = "t"
        run_id = run.run_id
        watch_store = watch_run_id = None

    _B.store = store
    await task_binding._poll_cancel(_B)  # type: ignore[arg-type]
    assert not _B.cancel.is_set()
