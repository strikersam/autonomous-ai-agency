"""Kill switch and per-agent daily spend cap (packages/config/autonomy_limits.py,
packages/ai/agent_budget.py).

The operator's two hard stops on autonomous work. Every gate is checked here:
router, orchestrator, scheduler, commit step and both cron ticks. So is the
property that human proxy traffic, which has no bound agent, is never stopped.
"""
from __future__ import annotations

import httpx
import pytest

from packages.ai import agent_budget
from packages.ai.agent_budget import (
    AgentBudgetExceeded,
    agent_scope,
    current_agent,
    ensure_agent_can_spend,
    record_agent_spend,
    spend_snapshot,
)
from packages.ai.router import ProviderConfig, ProviderRouter
from packages.config.autonomy_limits import (
    KillSwitchEngaged,
    agent_daily_budget_usd,
    agent_daily_token_budget,
    kill_switch_engaged,
)

_PAYLOAD = {"model": "a", "messages": [{"role": "user", "content": "hi"}]}


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for key in ("AGENCY_KILL_SWITCH", "AGENT_DAILY_KTOKENS_CAP", "AGENT_DAILY_USD_CAP"):
        monkeypatch.delenv(key, raising=False)
    agent_budget.reset()
    yield
    agent_budget.reset()


def _router(monkeypatch, calls: list[str], total_tokens: int = 100) -> ProviderRouter:
    async def fake_post_chat(self, provider, payload, timeout_sec):
        calls.append(provider.provider_id)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": total_tokens, "completion_tokens": 0,
                          "total_tokens": total_tokens},
            },
            headers={"content-type": "application/json"},
        )

    monkeypatch.setattr(ProviderRouter, "_post_chat", fake_post_chat)
    return ProviderRouter([
        ProviderConfig("only", "openai-compatible", "https://a/v1", api_key="k",
                       default_model="a", priority=0),
    ])


# ── Config readers ────────────────────────────────────────────────────────────


def test_limits_default_to_off(monkeypatch):
    assert kill_switch_engaged() is False
    assert agent_daily_token_budget() == 0
    assert agent_daily_budget_usd() == 0


@pytest.mark.parametrize("raw", ["true", "1", "YES", " on "])
def test_kill_switch_accepts_truthy_forms(monkeypatch, raw):
    monkeypatch.setenv("AGENCY_KILL_SWITCH", raw)
    assert kill_switch_engaged() is True


def test_budget_values_parse_and_bad_values_mean_unlimited(monkeypatch):
    monkeypatch.setenv("AGENT_DAILY_KTOKENS_CAP", "2.5")
    monkeypatch.setenv("AGENT_DAILY_USD_CAP", "1.25")
    assert agent_daily_token_budget() == 2500
    assert agent_daily_budget_usd() == 1.25
    monkeypatch.setenv("AGENT_DAILY_KTOKENS_CAP", "lots")
    monkeypatch.setenv("AGENT_DAILY_USD_CAP", "-4")
    assert agent_daily_token_budget() == 0
    assert agent_daily_budget_usd() == 0


# ── Ledger ────────────────────────────────────────────────────────────────────


def test_unbound_traffic_is_never_capped_or_killed(monkeypatch):
    monkeypatch.setenv("AGENCY_KILL_SWITCH", "true")
    monkeypatch.setenv("AGENT_DAILY_KTOKENS_CAP", "0.001")
    assert current_agent() is None
    record_agent_spend(10_000, 5.0)
    ensure_agent_can_spend()  # human traffic: no raise
    assert spend_snapshot() == {}


def test_token_cap_stops_only_the_agent_that_spent_it(monkeypatch):
    monkeypatch.setenv("AGENT_DAILY_KTOKENS_CAP", "1")
    with agent_scope("seo-specialist"):
        record_agent_spend(1000, 0.0)
        with pytest.raises(AgentBudgetExceeded, match="seo-specialist"):
            ensure_agent_can_spend()
    with agent_scope("dev-specialist"):
        ensure_agent_can_spend()


def test_usd_cap_trips_on_paid_spend(monkeypatch):
    monkeypatch.setenv("AGENT_DAILY_USD_CAP", "1")
    with agent_scope("planner"):
        record_agent_spend(10, 0.6)
        ensure_agent_can_spend()
        record_agent_spend(10, 0.6)
        with pytest.raises(AgentBudgetExceeded, match=r"\$1\.2000 of \$1\.00"):
            ensure_agent_can_spend()


def test_ledger_rolls_over_at_utc_midnight(monkeypatch):
    monkeypatch.setenv("AGENT_DAILY_KTOKENS_CAP", "1")
    monkeypatch.setattr(agent_budget, "_today", lambda: "2026-09-26")
    with agent_scope("a"):
        record_agent_spend(5000, 0.0)
        with pytest.raises(AgentBudgetExceeded):
            ensure_agent_can_spend()
        monkeypatch.setattr(agent_budget, "_today", lambda: "2026-09-27")
        ensure_agent_can_spend()


def test_scope_restores_the_previous_agent():
    with agent_scope("outer"):
        with agent_scope("inner"):
            assert current_agent() == "inner"
        assert current_agent() == "outer"
    assert current_agent() is None


def test_ledger_is_bounded(monkeypatch):
    monkeypatch.setattr(agent_budget, "_MAX_AGENTS_PER_DAY", 3)
    for i in range(10):
        with agent_scope(f"agent-{i}"):
            record_agent_spend(1, 0.0)
    assert len(spend_snapshot()) <= 4  # 3 named + the overflow bucket


# ── Router ────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_router_records_spend_and_refuses_once_capped(monkeypatch):
    monkeypatch.setenv("AGENT_DAILY_KTOKENS_CAP", "0.15")  # 150 tokens
    calls: list[str] = []
    router = _router(monkeypatch, calls, total_tokens=100)
    with agent_scope("dev"):
        await router.chat_completion(dict(_PAYLOAD), max_retries=0)
        await router.chat_completion(dict(_PAYLOAD, temperature=0.5), max_retries=0)
        with pytest.raises(AgentBudgetExceeded):
            await router.chat_completion(dict(_PAYLOAD, temperature=0.6), max_retries=0)
    assert calls == ["only", "only"]
    assert spend_snapshot()["dev"]["tokens"] == 200


@pytest.mark.anyio
async def test_router_kill_switch_stops_agents_but_not_humans(monkeypatch):
    monkeypatch.setenv("AGENCY_KILL_SWITCH", "true")
    calls: list[str] = []
    router = _router(monkeypatch, calls)
    with agent_scope("dev"):
        with pytest.raises(KillSwitchEngaged):
            await router.chat_completion(dict(_PAYLOAD), max_retries=0)
    assert calls == []
    result = await router.chat_completion(dict(_PAYLOAD), max_retries=0)
    assert result.provider.provider_id == "only"


# ── Orchestrator ──────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_orchestrator_refuses_runs_when_killed(monkeypatch):
    from services.workflow_orchestrator import ExecutionRequest, WorkflowOrchestrator

    monkeypatch.setenv("AGENCY_KILL_SWITCH", "true")
    orch = WorkflowOrchestrator()
    ran: list[str] = []

    async def must_not_run(run, req):
        ran.append("phase")

    orch._phase_handlers = {phase: must_not_run for phase in orch._phase_handlers}
    run = await orch.execute(ExecutionRequest(request="do work", auto_approve=True))
    assert run.status == "failed"
    assert "KillSwitchEngaged" in (run.error or "")
    assert ran == []


@pytest.mark.anyio
async def test_orchestrator_binds_the_agent_for_the_run(monkeypatch):
    from services.workflow_orchestrator import (
        ExecutionRequest,
        Phase,
        SpecialistSelection,
        WorkflowOrchestrator,
    )

    orch = WorkflowOrchestrator()
    seen: dict[str, str | None] = {}

    async def classify(run, req):
        seen["classify"] = current_agent()

    async def select(run, req):
        run.specialist = SpecialistSelection(specialist_ids=["s1"], specialist_names=["seo"])

    async def persist(run, req):
        seen["persist"] = current_agent()

    orch._phase_handlers = {
        Phase.CLASSIFY: classify,
        Phase.SELECT_SPECIALIST: select,
        Phase.PERSIST: persist,
    }
    run = await orch.execute(ExecutionRequest(request="x", auto_approve=True))
    assert run.status == "done", run.error
    assert seen == {"classify": "orchestrator", "persist": "seo"}
    assert current_agent() is None


# ── Scheduler, commit step, cron ticks ────────────────────────────────────────


def test_scheduler_does_not_fire_or_consume_run_once_jobs_when_killed(monkeypatch):
    from packages.scheduler.scheduler import AgentScheduler

    fired: list[str] = []
    sched = AgentScheduler(on_fire=lambda job: fired.append(job.job_id))
    try:
        job = sched.create(name="once", cron="* * * * *", instruction="x", tags=["run-once"])
        monkeypatch.setenv("AGENCY_KILL_SWITCH", "true")
        sched._fire(job.job_id)
        assert fired == []
        assert sched.get(job.job_id) is not None  # survives the halt
        monkeypatch.delenv("AGENCY_KILL_SWITCH")
        sched._fire(job.job_id)
        assert fired == [job.job_id]
    finally:
        sched.shutdown()


def test_commit_step_is_skipped_when_killed(monkeypatch, tmp_path):
    from agent.loop import AgentRunner

    monkeypatch.setenv("AGENCY_KILL_SWITCH", "true")
    runner = AgentRunner.__new__(AgentRunner)  # the gate runs before any attribute use
    assert runner._commit_step("step", ["a.py"]) is None


def test_cron_ticks_do_nothing_when_killed(monkeypatch):
    from fastapi.testclient import TestClient

    import backend.server as server

    monkeypatch.setattr(server, "_anon_tick_last", {})
    monkeypatch.delenv("CRON_SECRET", raising=False)
    monkeypatch.setenv("AGENCY_KILL_SWITCH", "true")
    client = TestClient(server.app, raise_server_exceptions=False)
    sched = client.post("/api/scheduler/tick")
    assert sched.status_code == 200
    assert sched.json()["skipped"] == "kill switch engaged"
    assert sched.json()["fired"] == []
    auto = client.get("/api/autonomy/tick")
    assert auto.status_code == 200
    assert auto.json()["dispatch"] == {"skipped": "kill switch engaged"}


@pytest.mark.anyio
async def test_dispatcher_leaves_tasks_pending_when_killed(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    from tasks.dispatcher import TaskDispatcher

    dispatcher = TaskDispatcher.__new__(TaskDispatcher)
    dispatcher._poll_count = 0
    dispatcher.max_concurrency = 1
    dispatcher.store = MagicMock()
    dispatcher.store.list_pending = AsyncMock(return_value=[])
    monkeypatch.setenv("AGENCY_KILL_SWITCH", "true")
    await dispatcher._poll_and_execute()
    dispatcher.store.list_pending.assert_not_called()


@pytest.mark.anyio
async def test_dispatcher_attributes_spend_to_the_assigned_agent():
    from types import SimpleNamespace

    from tasks.dispatcher import TaskDispatcher

    dispatcher = TaskDispatcher.__new__(TaskDispatcher)
    seen: list[str | None] = []

    async def fake_execute(task_id):
        seen.append(current_agent())

    dispatcher._execute_task = fake_execute
    await dispatcher._execute_as_agent(SimpleNamespace(task_id="t1", agent_id="seo"))
    await dispatcher._execute_as_agent(SimpleNamespace(task_id="t2", agent_id=None))
    assert seen == ["seo", "task-dispatcher"]


@pytest.mark.anyio
async def test_ceo_cycle_runs_as_the_ceo_agent():
    from agent.agency import Agency

    agency = Agency.__new__(Agency)
    seen: list[str | None] = []

    async def fake_cycle():
        seen.append(current_agent())

    agency.run_cycle = fake_cycle
    await agency._run_cycle_as_ceo()
    assert seen == ["ceo"]


@pytest.mark.anyio
async def test_orchestrator_keeps_an_agent_bound_by_its_caller():
    from services.workflow_orchestrator import ExecutionRequest, Phase, WorkflowOrchestrator

    orch = WorkflowOrchestrator()
    seen: list[str | None] = []

    async def classify(run, req):
        seen.append(current_agent())

    orch._phase_handlers = {Phase.CLASSIFY: classify}
    with agent_scope("seo"):
        await orch.execute(ExecutionRequest(request="x", auto_approve=True))
    assert seen == ["seo"]
