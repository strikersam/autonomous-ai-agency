"""Reliability suite, brief section 13, scenarios 19 to 24 (propagation, kill switch, budget,
tenancy, redaction, release gate)."""
from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

import pytest

from agent.action_hash import action_hash
from agent.autonomy_gate import AutonomyViolation, assert_agent_can_merge
from packages.runs import tracing
from packages.runs.approvals import RunApprovals
from packages.runs.artifacts import ArtifactStore
from packages.runs.composer import Composer
from packages.runs.composition import ChildJob, ChildOutcome, CompositionSpec, Step
from packages.runs.models import RunRecord, RunState
from packages.runs.reference_workflows import BugToPrWorkflow
from packages.runs.side_effects import ReleaseNotApproved, gate_release_if_bound
from packages.runs.store import RunStore, set_run_store
from packages.runs.task_binding import current_run
from packages.runs.tree import descendants
from tests.reliability._helpers import ENV_KEYS, SECRET, FakeExec, compose, step, wait_for


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


async def _running(ex: FakeExec, n: int) -> bool:
    return ex.running >= n


async def test_scenario_19_parent_cancellation_propagates_to_every_descendant(monkeypatch):
    monkeypatch.setenv("RUNS_MAX_PARALLEL", "4")
    store = RunStore()
    spec = CompositionSpec(mode="parallel", steps=[
        step("solo"), Step(key="grp", kind="group", mode="parallel", steps=[step("x"), step("y")])])
    ex = FakeExec({k: {"delay": 30} for k in ("solo", "x", "y")})
    composer = Composer(store, ex, cancel_poll_s=0.01)
    root = await composer.start(spec)
    job = asyncio.create_task(composer.run(root.run_id, spec))
    await wait_for(lambda: _running(ex, 3))
    await store.update(root.run_id, {"cancel_requested": True})
    res = await asyncio.wait_for(job, 3)
    kids = await descendants(store, root.run_id)
    assert res.state == "cancelled" and len(kids) == 3
    assert {k.state for k in kids} == {RunState.CANCELLED}


async def test_scenario_20_the_kill_switch_stops_active_execution(monkeypatch):
    store = RunStore()
    spec = CompositionSpec(steps=[step("work"), step("after")])
    ex = FakeExec({"work": {"delay": 30}})
    composer = Composer(store, ex, cancel_poll_s=0.01)
    root = await composer.start(spec)
    job = asyncio.create_task(composer.run(root.run_id, spec))
    await wait_for(lambda: _running(ex, 1))
    monkeypatch.setenv("AGENCY_KILL_SWITCH", "true")
    res = await asyncio.wait_for(job, 3)
    assert res.state == "cancelled" and "after" not in ex.calls
    assert (await store.get(root.run_id)).state is RunState.CANCELLED
    assert {k.state for k in await descendants(store, root.run_id)} == {RunState.CANCELLED}


async def test_scenario_21_budget_exhaustion_across_delegated_agents_stops_the_composition():
    spec = CompositionSpec(steps=[step("a"), step("b"), step("c")], budget={"max_cost_usd": 1.0})
    plan = {k: {"cost": 0.6} for k in "abc"}
    _, store, ex, root, res = await compose(spec, plan)
    assert res.state == "failed" and "budget_exhausted" in (res.error or "")
    assert ex.calls == ["a"]  # b is refused before it starts, c never runs
    parent = await store.get(root.run_id)
    assert parent.spent_micro_usd == 600_000  # never over the cap
    assert [e for e in await store.list_events(root.run_id) if e.kind == "budget_exhausted"]


def test_scenario_22_tenant_isolation_denies_cross_company_access(api):
    from tests.reliability.conftest import BOB

    rid = api.post("/api/runs", json={"title": "alice's"}, headers={"Idempotency-Key": "shared"}).json()["run_id"]
    api.holder["user"] = BOB
    for method, path in (("get", f"/api/runs/{rid}"), ("get", f"/api/runs/{rid}/events"),
                         ("get", f"/api/runs/{rid}/artifacts"), ("post", f"/api/runs/{rid}/cancel"),
                         ("post", f"/api/runs/{rid}/retry")):
        assert getattr(api, method)(path).status_code == 404, path
    assert api.get("/api/runs").json()["runs"] == []
    other = api.post("/api/runs", json={"title": "bob's"}, headers={"Idempotency-Key": "shared"}).json()
    assert other["run_id"] != rid and other["created"] is True  # keys are per caller
    assert asyncio.run(api.runs.get(rid)).state is RunState.QUEUED  # bob's cancel changed nothing


async def test_scenario_22b_children_inherit_the_company_and_stay_separate():
    store = RunStore()
    for company in ("acme", "globex"):
        spec = CompositionSpec(name=company, company_id=company, steps=[step("a")])
        await compose(spec, store=store)
    acme = await store.list(company_id="acme", limit=50)
    assert len(acme) == 2 and {r.company_id for r in acme} == {"acme"}  # root and child
    assert {r.company_id for r in await store.list(company_id="globex", limit=50)} == {"globex"}


async def test_scenario_23_secrets_never_reach_events_artifacts_traces_or_logs(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    store = RunStore()

    async def leaky(job: ChildJob) -> ChildOutcome:
        return ChildOutcome(success=False, error=f"auth failed with {SECRET}", output={"api_key": SECRET})

    _, _, _, root, _ = await compose(CompositionSpec(steps=[step("a")]), store=store, executor=leaky)
    await store.append_event(root.run_id, "note", {"msg": f"saw {SECRET}", "token": SECRET})
    await ArtifactStore(store).put(root.run_id, "log.txt", f"key={SECRET}", extra={"secret": SECRET})
    ap = RunApprovals(store)
    await ap.request(root.run_id, "h", {"url": f"https://x/{SECRET}"}, f"why {SECRET}")
    spans: list = []

    class Span:
        def __init__(self) -> None:
            self.attrs: dict = {}
            spans.append(self)

        def set_attribute(self, key, value):
            self.attrs[key] = value

        def end(self): ...

    import services.otel_tracing as otel
    monkeypatch.setattr(otel, "get_tracer", lambda name="x": SimpleNamespace(start_span=lambda n, **k: Span()))
    tracing.open_run_span(RunRecord(run_id="run_x", task_id=f"token={SECRET}"))
    stored = repr({name: store.table(name).docs for name in
                   ("runs", "run_events", "run_artifacts", "run_approvals")})
    run = await store.get(root.run_id)
    assert "saw" in stored and "log.txt" in stored  # the records exist, only the secret is gone
    for haystack in (stored, repr(spans[0].attrs), caplog.text, repr(run.model_dump())):
        assert SECRET not in haystack


async def test_scenario_24_release_or_deploy_is_blocked_without_a_durable_human_approval():
    wf = BugToPrWorkflow(RunStore())
    composer = Composer(wf.executor.runs, wf.executor, cancel_poll_s=0.01)
    spec = wf.spec()
    root = await composer.start(spec)
    res = await composer.run(root.run_id, spec)
    assert res.results["draft_pr"].output["guards"] == {"merge": "blocked", "deploy": "blocked"}
    with pytest.raises(AutonomyViolation):
        assert_agent_can_merge(agent_initiated=True)
    set_run_store(wf.executor.runs)
    token = current_run.set(SimpleNamespace(run_id=root.run_id, watch_run_id=None))
    try:
        args, target = {"serviceId": "srv-1"}, {"service_id": "srv-1"}
        with pytest.raises(ReleaseNotApproved):
            await gate_release_if_bound("render.trigger_deploy", args, target)
        ap = RunApprovals(wf.executor.runs)
        aid = await ap.request(root.run_id, action_hash("render.trigger_deploy", args), target, "ship")
        with pytest.raises(ReleaseNotApproved):  # requested is not approved
            await gate_release_if_bound("render.trigger_deploy", args, target)
        await ap.decide(aid, True, "priya")
        await gate_release_if_bound("render.trigger_deploy", args, target)  # a human said yes
        with pytest.raises(ReleaseNotApproved):  # for that action only
            await gate_release_if_bound("render.trigger_deploy", {"serviceId": "srv-2"}, target)
    finally:
        current_run.reset(token)
        set_run_store(None)
