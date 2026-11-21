"""Regression tests for two phase 4 verifier defects: in-process cancel settling, budget reservation."""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from packages.runs import budget
from packages.runs.composer import Composer
from packages.runs.composition import (ChildJob, ChildOutcome, CompositionSpec, Step,
                                       child_run_id, child_task_id)
from packages.runs.models import RunRecord, RunState
from packages.runs.store import RunStore
from packages.runs.tree import descendants
from tasks.models import Task, TaskStatus
from tasks.store import TaskStore


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for key in ("AGENCY_KILL_SWITCH", "RUNS_MAX_CHILDREN", "RUNS_MAX_DEPTH", "RUNS_MAX_PARALLEL"):
        monkeypatch.delenv(key, raising=False)


def t(key: str, **kw: Any) -> Step:
    return Step(key=key, title=key, **kw)


async def _mk_task(ts: TaskStore, task_id: str) -> None:
    await ts.create(Task(task_id=task_id, owner_id="o", title=task_id, status=TaskStatus.IN_PROGRESS))


async def test_cancel_settles_in_process_grandchild_and_keeps_succeeded_sibling():
    ts, store = TaskStore(), RunStore()

    async def leaf_exec(job: ChildJob) -> ChildOutcome:
        await asyncio.sleep(5)
        return ChildOutcome(success=True)

    async def outer(job: ChildJob) -> ChildOutcome:
        if job.step.key == "quick":
            return ChildOutcome(success=True, output="q")
        await _mk_task(ts, child_task_id(job.run_id, "leaf"))
        sub = Composer(store, leaf_exec, task_store=ts, cancel_poll_s=0.01)
        res = await sub.run(job.run_id, CompositionSpec(steps=[t("leaf")]))
        return ChildOutcome(success=res.state == "succeeded")

    spec = CompositionSpec(steps=[t("mid"), t("quick")], mode="parallel")
    composer = Composer(store, outer, task_store=ts, cancel_poll_s=0.01)
    root = await composer.start(spec)
    for key in ("mid", "quick"):
        await _mk_task(ts, child_task_id(root.run_id, key))

    async def stopper() -> None:
        mid = child_run_id(root.run_id, "mid")
        leaf = child_run_id(mid, "leaf")
        for _ in range(500):
            run = await store.get(leaf)
            if run is not None and run.state is RunState.RUNNING:
                break
            await asyncio.sleep(0.01)
        await store.update(root.run_id, {"cancel_requested": True})

    stop = asyncio.create_task(stopper())
    await asyncio.wait_for(composer.run(root.run_id, spec), 10)
    await stop
    runs = {r.phase.split(":", 1)[1]: r for r in await descendants(store, root.run_id)}
    assert runs["quick"].state is RunState.SUCCEEDED
    assert runs["leaf"].state is RunState.CANCELLED
    assert (await ts.get(runs["leaf"].task_id)).status is TaskStatus.WONT_DO
    assert (await ts.get(runs["quick"].task_id)).status is TaskStatus.IN_PROGRESS  # untouched


class _Cost:
    def __init__(self, cost: float, delay: float = 0.05) -> None:
        self.cost, self.delay, self.calls = cost, delay, []

    async def __call__(self, job: ChildJob) -> ChildOutcome:
        self.calls.append(job.step.key)
        await asyncio.sleep(self.delay)
        return ChildOutcome(success=True, output=job.step.key, cost_usd=self.cost)


async def _run_capped(steps: list[Step], ex: _Cost, cap: float = 1.0):
    store = RunStore()
    spec = CompositionSpec(steps=steps, mode="parallel", budget={"max_cost_usd": cap})
    composer = Composer(store, ex, cancel_poll_s=0.01)
    root = await composer.start(spec)
    res = await composer.run(root.run_id, spec)
    return store, root, res


async def test_parallel_children_cannot_overspend_the_cap(monkeypatch):
    monkeypatch.setenv("RUNS_MAX_PARALLEL", "8")
    ex = _Cost(0.3)
    store, root, res = await _run_capped([t(f"s{i}") for i in range(8)], ex)
    got = await store.get(root.run_id)
    assert got.spent_micro_usd <= 1_300_000
    assert len(ex.calls) < 8
    assert res.state == "failed" and "budget_exhausted" in (res.error or "")
    assert got.reserved_micro_usd == 0
    kinds = [e.kind for e in await store.list_events(root.run_id, limit=200)]
    assert "budget_exhausted" in kinds
    skipped = [r for r in await descendants(store, root.run_id) if r.state is RunState.CANCELLED]
    assert len(skipped) == 8 - len(ex.calls)


async def test_step_estimate_admits_only_what_fits(monkeypatch):
    monkeypatch.setenv("RUNS_MAX_PARALLEL", "8")
    ex = _Cost(0.3)
    steps = [t(f"s{i}", estimated_cost=0.3) for i in range(8)]
    store, root, _ = await _run_capped(steps, ex)
    got = await store.get(root.run_id)
    assert len(ex.calls) == 3 and got.spent_micro_usd == 900_000


async def test_concurrent_reservations_are_atomic():
    store = RunStore()
    root = await store.create(RunRecord(state=RunState.RUNNING, budget={"max_cost_usd": 1.0}))
    got = await asyncio.gather(*(budget.try_reserve(store, root.run_id, 300_000) for _ in range(8)))
    assert sum(1 for g in got if g is not None) <= 3
    assert (await store.get(root.run_id)).reserved_micro_usd <= 1_000_000
