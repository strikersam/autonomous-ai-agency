"""Phase 4: the composer (packages/runs/composer.py) with a deterministic fake executor."""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from packages.runs.composer import Composer
from packages.runs.composition import (ChildJob, ChildOutcome, CompositionSpec, FailurePolicy,
                                       Step, StepCondition, child_run_id)
from packages.runs.models import RunRecord, RunState
from packages.runs.store import RunStore
from packages.runs.tree import cancel_tree, descendants
from tasks.models import Task, TaskStatus
from tasks.store import TaskStore


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for key in ("AGENCY_KILL_SWITCH", "RUNS_MAX_CHILDREN", "RUNS_MAX_DEPTH", "RUNS_MAX_PARALLEL"):
        monkeypatch.delenv(key, raising=False)


class FakeExec:
    """Deterministic executor: per step key (delay s, success, output, cost, tokens)."""

    def __init__(self, plan: dict[str, dict[str, Any]] | None = None) -> None:
        self.plan, self.calls, self.running, self.peak = plan or {}, [], 0, 0

    async def __call__(self, job: ChildJob) -> ChildOutcome:
        cfg = self.plan.get(job.step.key, {})
        self.calls.append(job.step.key)
        self.running += 1
        self.peak = max(self.peak, self.running)
        try:
            await asyncio.sleep(cfg.get("delay", 0.0))
        finally:
            self.running -= 1
        return ChildOutcome(success=cfg.get("ok", True), output=cfg.get("out", f"out:{job.step.key}"),
                            error=None if cfg.get("ok", True) else "boom",
                            cost_usd=cfg.get("cost", 0.0), tokens=cfg.get("tokens", 0))


def t(key: str, **kw: Any) -> Step:
    return Step(key=key, title=key, **kw)


async def go(spec: CompositionSpec, plan=None, *, store=None, task_store=None, **kw):
    store = store or RunStore()
    ex = FakeExec(plan)
    composer = Composer(store, ex, task_store=task_store, cancel_poll_s=0.01, **kw)
    root = await composer.start(spec)
    return composer, store, ex, root, await composer.run(root.run_id, spec)


async def states(store: RunStore, root_id: str) -> dict[str, RunState]:
    return {r.phase.split(":", 1)[1]: r.state for r in await descendants(store, root_id)}


async def test_sequential_steps_run_in_order_with_child_runs():
    spec = CompositionSpec(steps=[t("a"), t("b"), t("c")])
    _, store, ex, root, res = await go(spec)
    assert res.state == "succeeded" and ex.calls == ["a", "b", "c"]
    assert res.aggregate == ["out:a", "out:b", "out:c"]
    kids = await descendants(store, root.run_id)
    assert len(kids) == 3 and all(k.parent_run_id == root.run_id for k in kids)
    assert all(k.root_run_id == root.run_id and k.depth == 1 for k in kids)
    assert (await store.get(root.run_id)).state is RunState.SUCCEEDED
    kinds = [e.kind for e in await store.list_events(root.run_id)]
    assert kinds.count("child_spawned") == 3 and "composition_finished" in kinds


async def test_later_steps_see_earlier_outputs():
    seen = {}

    async def ex(job: ChildJob) -> ChildOutcome:
        seen[job.step.key] = dict(job.prior)
        return ChildOutcome(success=True, output=job.step.key.upper())

    store = RunStore()
    composer = Composer(store, ex, cancel_poll_s=0.01)
    spec = CompositionSpec(steps=[t("a"), t("b")])
    root = await composer.start(spec)
    await composer.run(root.run_id, spec)
    assert seen["b"] == {"a": "A"}


async def test_parallel_fan_out_honours_the_concurrency_cap(monkeypatch):
    monkeypatch.setenv("RUNS_MAX_PARALLEL", "2")
    keys = [f"p{i}" for i in range(6)]
    spec = CompositionSpec(steps=[t(k) for k in keys], mode="parallel")
    _, _, ex, _, res = await go(spec, {k: {"delay": 0.03} for k in keys})
    assert res.state == "succeeded" and sorted(ex.calls) == keys
    assert ex.peak <= 2 and ex.peak == 2


async def test_join_aggregates_child_results_in_step_order():
    spec = CompositionSpec(steps=[t("x"), t("y"), t("z")], mode="parallel")
    _, _, _, _, res = await go(spec, {"x": {"delay": 0.05, "out": 1}, "y": {"out": 2},
                                      "z": {"delay": 0.02, "out": 3}})
    assert res.aggregate == [1, 2, 3]
    assert {k: r.output for k, r in res.results.items()} == {"x": 1, "y": 2, "z": 3}


async def test_nested_group_joins_into_one_step_output():
    spec = CompositionSpec(steps=[
        Step(key="fan", kind="group", mode="parallel", steps=[t("a"), t("b")]), t("after")])
    _, _, _, _, res = await go(spec, {"a": {"out": "A"}, "b": {"out": "B"}})
    assert res.results["fan"].output == ["A", "B"] and res.state == "succeeded"


async def test_continue_policy_keeps_the_sibling_and_the_parent_reflects_the_failure():
    spec = CompositionSpec(steps=[t("ok1"), t("bad"), t("ok2")], mode="parallel",
                           policy=FailurePolicy.CONTINUE)
    _, store, _, root, res = await go(spec, {"bad": {"ok": False}})
    assert res.state == "succeeded" and res.partial and res.failed == ["bad"]
    assert res.aggregate == ["out:ok1", "out:ok2"]
    assert res.results["bad"].error == "boom"
    st = await states(store, root.run_id)
    assert st == {"ok1": RunState.SUCCEEDED, "bad": RunState.FAILED, "ok2": RunState.SUCCEEDED}
    events = await store.list_events(root.run_id)
    assert [e for e in events if e.kind == "composition_finished"][0].data["failed"] == ["bad"]


async def test_require_all_runs_everything_but_fails_the_parent():
    spec = CompositionSpec(steps=[t("a"), t("bad"), t("c")], mode="parallel",
                           policy=FailurePolicy.REQUIRE_ALL)
    _, store, ex, root, res = await go(spec, {"bad": {"ok": False}})
    assert res.state == "failed" and sorted(ex.calls) == ["a", "bad", "c"]
    assert (await store.get(root.run_id)).state is RunState.FAILED


async def test_fail_fast_in_sequence_skips_the_rest():
    spec = CompositionSpec(steps=[t("a"), t("bad"), t("never")])
    _, store, ex, root, res = await go(spec, {"bad": {"ok": False}})
    assert res.state == "failed" and ex.calls == ["a", "bad"]
    assert res.skipped == ["never"] and (await store.get(root.run_id)).state is RunState.FAILED


async def test_fail_fast_in_parallel_cancels_running_siblings_and_their_tasks():
    task_store, store = TaskStore(), RunStore()
    spec = CompositionSpec(steps=[t("bad"), t("slow1"), t("slow2")], mode="parallel")
    composer = Composer(store, FakeExec({"bad": {"ok": False, "delay": 0.02},
                                         "slow1": {"delay": 5}, "slow2": {"delay": 5}}),
                        task_store=task_store, cancel_poll_s=0.01)
    root = await composer.start(spec)
    for key in ("slow1", "slow2"):
        await task_store.create(Task(task_id=_tid(key, root.run_id), owner_id="o", title=key,
                                     status=TaskStatus.IN_PROGRESS))
    res = await asyncio.wait_for(composer.run(root.run_id, spec), 3)
    assert res.state == "failed"
    st = await states(store, root.run_id)
    assert st["slow1"] is RunState.CANCELLED and st["slow2"] is RunState.CANCELLED
    for key in ("slow1", "slow2"):
        task = await task_store.get(_tid(key, root.run_id))
        assert task is not None and task.status is TaskStatus.WONT_DO


def _tid(key: str, parent: str) -> str:
    from packages.runs.composition import child_task_id
    return child_task_id(parent, key)


async def test_quorum_policy():
    spec = CompositionSpec(steps=[t("a"), t("b"), t("c")], mode="parallel",
                           policy=FailurePolicy.QUORUM, quorum=2)
    plan = {"c": {"ok": False}}
    assert (await go(spec, plan))[-1].state == "succeeded"
    plan = {"b": {"ok": False}, "c": {"ok": False}}
    assert (await go(spec, plan))[-1].state == "failed"
    with pytest.raises(ValueError):
        CompositionSpec(steps=[t("a")], policy=FailurePolicy.QUORUM)


async def test_conditional_steps_skip_on_a_false_condition():
    spec = CompositionSpec(steps=[
        t("a"), t("on_ok", when=StepCondition(step="a")),
        t("on_fail", when=StepCondition(step="a", outcome="failed")),
        t("pred", predicate=lambda r: r["a"].output == "nope")], policy=FailurePolicy.CONTINUE)
    _, store, ex, root, res = await go(spec)
    assert ex.calls == ["a", "on_ok"] and res.skipped == ["on_fail", "pred"]
    assert res.state == "succeeded"
    assert [e.data["step"] for e in await store.list_events(root.run_id)
            if e.kind == "step_skipped"] == ["on_fail", "pred"]


async def test_spec_validation_rejects_duplicate_keys_and_empty_groups():
    with pytest.raises(ValueError):
        CompositionSpec(steps=[t("a"), Step(key="g", kind="group", steps=[t("a")])])
    with pytest.raises(ValueError):
        Step(key="g", kind="group")
    with pytest.raises(ValueError):
        Step(key="bad key!")


async def test_approval_step_parks_the_parent_and_resumes_after_approval():
    spec = CompositionSpec(steps=[t("a"), Step(key="gate", kind="approval"), t("b")])
    composer, store, ex, root, res = await go(spec)
    assert res.state == "waiting_for_approval" and res.waiting_on == "gate"
    assert ex.calls == ["a"]
    parked = await store.get(root.run_id)
    assert parked.state is RunState.WAITING_FOR_APPROVAL and parked.waiting_reason == "approval:gate"
    await composer.approve(root.run_id, "gate")
    res = await composer.run(root.run_id, spec)
    assert res.state == "succeeded" and ex.calls == ["a", "b"]  # a not repeated


async def test_denied_approval_fails_the_composition_and_a_hook_can_decide():
    spec = CompositionSpec(steps=[Step(key="gate", kind="approval"), t("b")])
    composer, store, ex, root, _ = await go(spec)
    await composer.approve(root.run_id, "gate", approved=False)
    res = await composer.run(root.run_id, spec)
    assert res.state == "failed" and ex.calls == []

    async def hook(run, step):
        return True

    _, _, ex2, _, res2 = await go(spec, approval_hook=hook)
    assert res2.state == "succeeded" and ex2.calls == ["b"]


async def test_parent_cancel_reaches_every_descendant_and_their_tasks():
    task_store = TaskStore()
    store = RunStore()
    spec = CompositionSpec(steps=[t("a"), t("b"), t("c")], mode="parallel")
    composer = Composer(store, FakeExec({k: {"delay": 5} for k in "abc"}),
                        task_store=task_store, cancel_poll_s=0.01)
    root = await composer.start(spec)
    for key in "abc":
        await task_store.create(Task(task_id=_tid(key, root.run_id), owner_id="o", title=key,
                                     status=TaskStatus.IN_PROGRESS))
    job = asyncio.create_task(composer.run(root.run_id, spec))
    await _until(lambda: _count_running(store, root.run_id, 3))
    # a grandchild, e.g. spawned by a nested composition of child "a"
    a = await store.get(child_run_id(root.run_id, "a"))
    grand = await store.create(RunRecord(parent_run_id=a.run_id, root_run_id=root.run_id,
                                         depth=2, state=RunState.QUEUED))
    await store.update(root.run_id, {"cancel_requested": True})
    res = await asyncio.wait_for(job, 3)
    assert res.state == "cancelled"
    runs = await descendants(store, root.run_id)
    assert len(runs) == 4 and all(r.state is RunState.CANCELLED for r in runs)
    assert (await store.get(grand.run_id)).state is RunState.CANCELLED
    for key in "abc":
        assert (await task_store.get(_tid(key, root.run_id))).status is TaskStatus.WONT_DO
    assert (await store.get(root.run_id)).state is RunState.CANCELLED


async def _count_running(store, root_id, n) -> bool:
    kids = await descendants(store, root_id)
    return len([k for k in kids if k.state is RunState.RUNNING]) >= n


async def _until(pred, timeout: float = 3.0) -> None:
    end = asyncio.get_event_loop().time() + timeout
    while not await pred():
        assert asyncio.get_event_loop().time() < end, "condition not reached"
        await asyncio.sleep(0.01)


async def test_cancel_tree_settles_runs_without_a_worker_and_flags_running_ones():
    store = RunStore()
    root = await store.create(RunRecord(state=RunState.RUNNING))
    q = await store.create(RunRecord(parent_run_id=root.run_id, state=RunState.QUEUED))
    r = await store.create(RunRecord(parent_run_id=q.run_id, state=RunState.RUNNING))
    flagged = await cancel_tree(store, root.run_id, reason="t", actor="x")
    assert set(flagged) == {root.run_id, q.run_id, r.run_id}
    assert (await store.get(q.run_id)).state is RunState.CANCELLED
    got = await store.get(r.run_id)
    assert got.state is RunState.RUNNING and got.cancel_requested
    assert await cancel_tree(store, root.run_id, reason="t", actor="x") == []


async def test_kill_switch_stops_running_children_and_the_composition(monkeypatch):
    spec = CompositionSpec(steps=[t("a"), t("b")], mode="parallel")
    store = RunStore()
    composer = Composer(store, FakeExec({"a": {"delay": 5}, "b": {"delay": 5}}),
                        cancel_poll_s=0.01)
    root = await composer.start(spec)
    job = asyncio.create_task(composer.run(root.run_id, spec))
    await _until(lambda: _count_running(store, root.run_id, 2))
    monkeypatch.setenv("AGENCY_KILL_SWITCH", "true")
    res = await asyncio.wait_for(job, 2)
    assert res.state == "cancelled" and res.error == "kill_switch"
    assert all(r.state is RunState.CANCELLED for r in await descendants(store, root.run_id))


async def test_deadline_expiry_cancels_outstanding_children_and_times_out_the_parent():
    spec = CompositionSpec(steps=[t("a"), t("b")], mode="parallel", deadline_s=0.05)
    _, store, _, root, res = await go(spec, {"a": {"delay": 5}, "b": {"delay": 5}})
    assert res.state == "timed_out"
    assert (await store.get(root.run_id)).state is RunState.TIMED_OUT
    assert all(r.state is RunState.CANCELLED for r in await descendants(store, root.run_id))


async def test_child_cap_refuses_the_spawn_with_an_event(monkeypatch):
    monkeypatch.setenv("RUNS_MAX_CHILDREN", "2")
    spec = CompositionSpec(steps=[t("a"), t("b"), t("c")], policy=FailurePolicy.CONTINUE)
    _, store, ex, root, res = await go(spec)
    assert ex.calls == ["a", "b"] and res.failed == ["c"]
    assert "RUNS_MAX_CHILDREN" in res.results["c"].error and res.partial
    refused = [e for e in await store.list_events(root.run_id) if e.kind == "spawn_refused"]
    assert len(refused) == 1 and refused[0].data["step"] == "c"
    assert len(await descendants(store, root.run_id)) == 2


async def test_depth_cap_refuses_the_spawn(monkeypatch):
    monkeypatch.setenv("RUNS_MAX_DEPTH", "2")
    store = RunStore()
    root = await store.create(RunRecord(state=RunState.QUEUED))
    mid = await store.create(RunRecord(parent_run_id=root.run_id, root_run_id=root.run_id,
                                       depth=1, state=RunState.RUNNING))
    deep = await store.create(RunRecord(parent_run_id=mid.run_id, root_run_id=root.run_id,
                                        depth=2, state=RunState.RUNNING))
    spec = CompositionSpec(steps=[t("x")])
    ex = FakeExec()
    composer = Composer(store, ex, cancel_poll_s=0.01)
    ok = await composer.run(mid.run_id, spec)  # depth 1 -> child at depth 2: allowed
    assert ok.state == "succeeded"
    refused = await composer.run(deep.run_id, spec)  # child would be depth 3
    assert refused.state == "failed" and "RUNS_MAX_DEPTH" in refused.results["x"].error
    kinds = [e.kind for e in await store.list_events(deep.run_id)]
    assert "spawn_refused" in kinds and ex.calls == ["x"]


async def test_rerunning_a_composition_does_not_duplicate_finished_children():
    spec = CompositionSpec(steps=[t("a"), t("b")])
    composer, store, ex, root, first = await go(spec, {"a": {"out": {"k": 1}}})
    # simulate a crash after the work: the parent run is put back to running
    await store.update(root.run_id, {"state": RunState.RUNNING})
    again = await composer.run(root.run_id, spec)
    assert ex.calls == ["a", "b"]  # nothing executed twice
    assert again.state == "succeeded" and again.results["a"].output == {"k": 1}
    assert len(await descendants(store, root.run_id)) == 2


async def test_restart_resumes_only_the_unfinished_step():
    spec = CompositionSpec(steps=[t("a"), t("b")])
    store = RunStore()
    first = Composer(store, FakeExec({"b": {"ok": False}}), cancel_poll_s=0.01)
    root = await first.start(spec)
    await first.run(root.run_id, spec)
    # a is final; b failed and is final too: a failed child is not retried by a re-run
    await store.update(root.run_id, {"state": RunState.RUNNING})
    ex = FakeExec()
    res = await Composer(store, ex, cancel_poll_s=0.01).run(root.run_id, spec)
    assert ex.calls == [] and res.state == "failed" and res.failed == ["b"]


async def test_default_executor_runs_children_as_tasks_through_the_coordinator(monkeypatch):
    from packages.runs.composer_tasks import TaskChildExecutor
    from tasks.service import TaskExecutionCoordinator, TaskWorkflowService
    from tests._runs_task_fixtures import FakeRuntime

    import tasks.service as svc

    async def _true() -> bool:
        return True

    monkeypatch.setattr(svc, "_brain_is_configured", _true)
    task_store = TaskStore()
    runtime = FakeRuntime(lambda spec: _ok(spec.task_id))
    coord = TaskExecutionCoordinator(store=task_store, workflow=TaskWorkflowService(store=task_store),
                                     runtime_manager=runtime, workspace_root="/tmp/workspace")  # nosec B108
    store = RunStore()
    composer = Composer(store, TaskChildExecutor(task_store, coord), task_store=task_store,
                        cancel_poll_s=0.01)
    spec = CompositionSpec(steps=[t("only")], owner_id="o@x.com")
    root = await composer.start(spec)
    res = await composer.run(root.run_id, spec)
    assert runtime.calls == 1
    child = (await descendants(store, root.run_id))[0]
    task = await task_store.get(child.task_id)
    assert task is not None and task.current_run_id == child.run_id
    assert res.results["only"].state == "succeeded"


async def _ok(task_id: str):
    from tests._runs_task_fixtures import ok_result
    return ok_result(task_id)
