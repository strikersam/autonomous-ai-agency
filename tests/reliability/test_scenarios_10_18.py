"""Reliability suite, brief section 13, scenarios 10 to 18 (idempotency, side effects, storage
faults, cancellation, approvals, verification, partial failure)."""
from __future__ import annotations

import asyncio
import time

import pytest

import agent.checkpoint as ckpt
from agent.checkpoint import Checkpoint, CheckpointStore
from packages.runs import checkpoints as mirror
from packages.runs import side_effects, task_binding
from packages.runs.approvals import ApprovalError, ApprovalState, RunApprovals
from packages.runs.composer import Composer
from packages.runs.composition import CompositionSpec, FailurePolicy
from packages.runs.lease import LeaseHeartbeat, RunLease
from packages.runs.models import RunRecord, RunState
from packages.runs.recovery import RecoveryService
from packages.runs.reference_workflows import BugFixture, BugToPrWorkflow
from packages.runs.store import RunStore, set_run_store
from packages.runs.tree import descendants
from tasks.verification import TaskVerification, has_passing_verdict
from tests._runs_task_fixtures import (FakeRuntime, coordinator, queued_task, reset_process_state,
                                       sqlite_pair, start_dead_worker)
from tests.reliability._helpers import ENV_KEYS, FakeExec, compose, step, wait_for

LATER = 1000  # past the lease TTL and every operation deadline


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    reset_process_state(monkeypatch)
    monkeypatch.setenv("RUNS_LEDGER_ENABLED", "true")
    monkeypatch.setenv("RUNS_RECOVERY_ENABLED", "true")
    monkeypatch.setenv("RUNS_RETRY_BACKOFF_BASE_SEC", "0")


def test_scenario_10_duplicate_request_with_the_same_idempotency_key_returns_one_run(api):
    headers = {"Idempotency-Key": "k-123"}
    first = api.post("/api/runs", json={"title": "t"}, headers=headers)
    again = api.post("/api/runs", json={"title": "t"}, headers=headers)
    assert first.status_code == 201 and again.status_code == 200
    assert again.json()["run_id"] == first.json()["run_id"] and again.json()["created"] is False
    assert len(asyncio.run(api.runs.list())) == 1  # one run, so one task


async def test_scenario_11_a_side_effect_committed_before_a_crash_is_not_repeated(tmp_path):
    opened: list[str] = []
    args = {"owner": "o", "repo": "r", "head": "agent/task-x", "base": "main"}

    async def open_pr() -> bool:
        async with side_effects.recorded_effect("open_pull_request", args, args, 30) as fx:
            if not fx.skipped:
                opened.append("pr")
                fx.result_ref = "https://example.invalid/pull/1"
            return fx.skipped

    async with sqlite_pair(tmp_path) as (worker, survivor):
        task = await queued_task(worker)
        job, finish, binding = await start_dead_worker(worker, task, before_death=lambda b: open_pr())
        assert opened == ["pr"]
        report = await RecoveryService(survivor).tick(now=time.time() + LATER)
        assert report.recovered == [binding.run_id]
        finish.set()
        await job
        replay: dict[str, bool] = {}

        async def second_attempt(spec):
            replay["skipped"] = await open_pr()
            return await FakeRuntime().execute(spec)

        await coordinator(survivor, FakeRuntime(second_attempt)).execute(task.task_id)
        assert replay["skipped"] is True and opened == ["pr"]  # the PR was opened exactly once


async def test_scenario_12_a_corrupt_checkpoint_falls_back_to_the_previous_good_one(tmp_path, monkeypatch):
    set_run_store(RunStore())
    mirror.reset()
    try:
        store = CheckpointStore(tmp_path / "ckpt")
        for i in (1, 2):
            store.save(Checkpoint(session_id="s1", step_index=i, goal=f"g{i}"))
        (store._base_dir / "s1" / "checkpoint_0002.json").write_text("{torn write")
        assert store.load_latest("s1").step_index == 1
        # a replaced container has no files at all: the durable mirror still has the session
        assert await mirror.save(Checkpoint(session_id="s2", step_index=4, goal="g").to_dict())
        fresh = CheckpointStore(tmp_path / "empty")
        assert fresh.load_latest("s2") is None
        assert (await mirror.load_latest("s2"))[0]["step_index"] == 4
    finally:
        set_run_store(None)
        mirror.reset()


async def test_scenario_13_a_database_interruption_fails_safe_and_the_run_recovers():
    # (a) the store drops while the composition runs: the run is not reported succeeded ...
    store = RunStore()
    spec = CompositionSpec(steps=[step("a"), step("b"), step("c")])
    ex = FakeExec()
    composer = Composer(store, ex, cancel_poll_s=0.01)
    root = await composer.start(spec)
    real, down = store.append_event, {"on": True}

    async def flaky(*a, **k):
        if down["on"] and ex.calls == ["a", "b"]:
            raise ConnectionError("database unavailable")
        return await real(*a, **k)

    store.append_event = flaky  # type: ignore[method-assign]
    with pytest.raises(ConnectionError):
        await composer.run(root.run_id, spec)
    assert (await store.get(root.run_id)).state is RunState.RUNNING
    # (b) ... and once it is back, running again finishes it without redoing step a
    down["on"] = False
    res = await composer.run(root.run_id, spec)
    assert res.state == "succeeded" and ex.calls.count("a") == 1 and ex.calls[-1] == "c"


async def test_scenario_13b_lease_and_checkpoint_writers_survive_a_dead_database(monkeypatch):
    class DeadLease(RunLease):
        async def renew(self, *a, **k):
            raise ConnectionError("database unavailable")

    hb = LeaseHeartbeat(DeadLease(), "run:k", "w", 1, ttl_s=0.2, renew_s=0.05)
    hb.start()
    await asyncio.wait_for(hb.lost.wait(), 3)  # gives up after a TTL of errors, never raises
    await hb.stop()
    set_run_store(RunStore())
    mirror.reset()
    try:
        class Dead:
            kind = "dead"

            async def insert_if_absent(self, *a, **k):
                raise ConnectionError("database unavailable")

        monkeypatch.setattr(mirror, "_checkpoints", lambda: Dead())
        assert await mirror.save({"session_id": "s", "step_index": 1}) is False  # best effort, no raise
    finally:
        set_run_store(None)
        mirror.reset()


async def test_scenario_14_cancellation_while_an_agent_is_running_stops_it():
    store = RunStore()
    spec = CompositionSpec(steps=[step("work"), step("never")])
    ex = FakeExec({"work": {"delay": 30}})
    composer = Composer(store, ex, cancel_poll_s=0.01)
    root = await composer.start(spec)
    job = asyncio.create_task(composer.run(root.run_id, spec))
    await wait_for(lambda: _started(ex))
    await store.update(root.run_id, {"cancel_requested": True})
    res = await asyncio.wait_for(job, 3)
    assert res.state == "cancelled" and "never" not in ex.calls
    assert [k.state for k in await descendants(store, root.run_id)] == [RunState.CANCELLED]


async def _started(ex: FakeExec) -> bool:
    return bool(ex.calls)


async def test_scenario_15_a_run_pauses_for_approval_and_resumes_after_a_human_decides(tmp_path):
    wf = BugToPrWorkflow(RunStore())
    composer = Composer(wf.executor.runs, wf.executor, cancel_poll_s=0.01)
    spec = wf.spec()
    root = await composer.start(spec)
    paused = await composer.run(root.run_id, spec)
    assert paused.state == "waiting_for_approval" and paused.waiting_on == "human_approval"
    assert (await wf.executor.runs.get(root.run_id)).state is RunState.WAITING_FOR_APPROVAL
    await composer.approve(root.run_id, "human_approval", actor="priya")
    resumed = await composer.run(root.run_id, spec)
    assert resumed.state == "succeeded" and wf.executor.calls.count("triage") == 1


async def test_scenario_15b_a_durable_approval_is_visible_to_another_process(tmp_path):
    from tests._runs_backends import open_pair

    async with open_pair("sqlite", tmp_path) as (a, b):
        first = RunStore(a)
        rid = (await first.create(RunRecord(owner_id="alice"))).run_id
        ap = RunApprovals(first)
        aid = await ap.request(rid, "h1", {"env": "prod"}, "ship it")
        await ap.decide(aid, True, "priya")
        assert await RunApprovals(RunStore(b)).check(rid, "h1", {"env": "prod"}) is True


async def test_scenario_16_an_expired_approval_denies(monkeypatch):
    import packages.runs.approvals as mod

    runs = RunStore()
    rid = (await runs.create(RunRecord(owner_id="alice"))).run_id
    ap = RunApprovals(runs)
    aid = await ap.request(rid, "h1", {"env": "prod"}, "ship", ttl_s=5)
    now = time.time()
    monkeypatch.setattr(mod.time, "time", lambda: now + 60)  # the wall clock passes the expiry
    assert (await ap.get(aid)).state is ApprovalState.EXPIRED
    with pytest.raises(ApprovalError):
        await ap.decide(aid, True, "priya")
    assert await ap.check(rid, "h1", {"env": "prod"}) is False


async def test_scenario_17_independent_verifier_rejection_blocks_the_draft_pr():
    wf = BugToPrWorkflow(RunStore(), BugFixture(tests_passed=3, tests_failed=2))
    composer = Composer(wf.executor.runs, wf.executor, cancel_poll_s=0.01)
    spec = wf.spec()
    root = await composer.start(spec)
    res = await composer.run(root.run_id, spec)
    assert res.state == "failed" and res.results["verify"].state == "failed"
    assert res.results["draft_pr"].state == "skipped" and res.waiting_on is None
    # a FAIL verdict is never a pass, and a missing verdict is not one either
    fail = TaskVerification(verdict="FAIL", verifier="verifier:x", defects_found=["2 tests failed"])
    assert fail.passed is False
    assert has_passing_verdict(type("T", (), {"verification": None})()) is False


async def test_scenario_18_a_failed_child_does_not_cost_its_successful_sibling():
    spec = CompositionSpec(mode="parallel", policy=FailurePolicy.CONTINUE,
                           steps=[step("good"), step("bad"), step("also_good")])
    _, store, _, root, res = await compose(spec, {"bad": {"ok": False}})
    assert res.state == "succeeded" and res.partial is True and res.failed == ["bad"]
    assert res.aggregate == ["out:good", "out:also_good"]
    by_key = {k.phase: k.state for k in await descendants(store, root.run_id)}
    assert by_key["step:good"] is RunState.SUCCEEDED and by_key["step:bad"] is RunState.FAILED
