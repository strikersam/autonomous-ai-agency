"""Per-user daily agent token cap (packages/ai/user_token_quota.py).

Covers quota math, UTC day rollover, the disabled (0) no-op, the live control,
refusal before an orchestrator run, router attribution and endpoint auth.
"""
from __future__ import annotations

import os

import httpx
import pytest

from packages.ai import user_token_quota as q
from packages.ai.router import ProviderConfig, ProviderRouter
from packages.config import control_overrides
from packages.config.autonomy_limits import user_daily_token_cap
from packages.config.control_registry import get_control

_PAYLOAD = {"model": "a", "messages": [{"role": "user", "content": "hi"}]}


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("AGENT_USER_TOKENS_PER_DAY", raising=False)
    q.reset()
    yield
    q.reset()


# ── Config / control ──────────────────────────────────────────────────────────


def test_control_is_registered_live_and_off_by_default():
    spec = get_control("AGENT_USER_TOKENS_PER_DAY")
    assert spec is not None and spec.live and spec.default == "0"
    assert user_daily_token_cap() == 0


def test_bad_values_mean_disabled(monkeypatch):
    for raw in ("lots", "-5", "2.5", ""):
        monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", raw)
        assert user_daily_token_cap() == 0


def test_override_takes_effect_at_call_time():
    applied_before = dict(control_overrides._applied)
    env_before = os.environ.get("AGENT_USER_TOKENS_PER_DAY")
    try:
        control_overrides.apply_overrides({"AGENT_USER_TOKENS_PER_DAY": "750"})
        assert user_daily_token_cap() == 750
        control_overrides.apply_overrides({})
        assert user_daily_token_cap() == 0
    finally:
        control_overrides._applied.clear()
        control_overrides._applied.update(applied_before)
        if env_before is None:
            os.environ.pop("AGENT_USER_TOKENS_PER_DAY", None)
        else:
            os.environ["AGENT_USER_TOKENS_PER_DAY"] = env_before


# ── Quota math ────────────────────────────────────────────────────────────────


def test_disabled_cap_never_refuses_but_still_records():
    with q.user_scope("u1"):
        q.record_user_tokens(10_000_000)
        q.ensure_user_within_quota()
    assert q.user_quota_refusal("u1") is None
    assert q.usage_snapshot() == {"u1": 10_000_000}


def test_cap_refuses_at_the_limit_and_isolates_users(monkeypatch):
    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "100")
    with q.user_scope("u1"):
        q.record_user_tokens(99)
        q.ensure_user_within_quota()
        q.record_user_tokens(1)
        with pytest.raises(q.UserTokenQuotaExceeded) as err:
            q.ensure_user_within_quota()
    assert str(err.value) == q.REFUSAL_MESSAGE
    assert "99" not in str(err.value) and "u1" not in str(err.value)
    with q.user_scope("u2"):
        q.ensure_user_within_quota()
    assert q.user_quota_refusal("u1") == q.REFUSAL_MESSAGE
    assert q.user_quota_refusal("u2") is None


def test_unbound_and_scheduler_traffic_is_never_counted(monkeypatch):
    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "1")
    q.record_user_tokens(500)
    q.ensure_user_within_quota()
    with q.user_scope("scheduler"):
        assert q.current_user() is None
        q.record_user_tokens(500)
        q.ensure_user_within_quota()
    assert q.usage_snapshot() == {}
    assert q.user_quota_refusal(None) is None and q.user_quota_refusal("scheduler") is None


def test_negative_and_garbage_tokens_are_ignored():
    with q.user_scope("u1"):
        q.record_user_tokens(-50)
        q.record_user_tokens(None)  # type: ignore[arg-type]
    assert q.usage_snapshot() == {"u1": 0}


def test_ledger_rolls_over_at_utc_midnight(monkeypatch):
    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "10")
    monkeypatch.setattr(q, "_today", lambda: "2026-10-09")
    with q.user_scope("u1"):
        q.record_user_tokens(50)
    assert q.user_quota_refusal("u1")
    monkeypatch.setattr(q, "_today", lambda: "2026-10-10")
    assert q.user_quota_refusal("u1") is None
    assert q.usage_snapshot() == {}


def test_ledger_is_bounded(monkeypatch):
    monkeypatch.setattr(q, "_MAX_USERS_PER_DAY", 2)
    for uid in ("a", "b", "c", "d"):
        with q.user_scope(uid):
            q.record_user_tokens(5)
    assert q.usage_snapshot() == {"a": 5, "b": 5, "other": 10}


def test_scope_restores_previous_user():
    with q.user_scope("outer"):
        with q.user_scope("inner"):
            assert q.current_user() == "inner"
        assert q.current_user() == "outer"
    assert q.current_user() is None


# ── Router attribution ────────────────────────────────────────────────────────


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


@pytest.mark.anyio
async def test_router_records_tokens_and_stops_a_user_over_the_cap(monkeypatch):
    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "150")
    calls: list[str] = []
    router = _router(monkeypatch, calls, total_tokens=100)
    with q.user_scope("u1"):
        await router.chat_completion(dict(_PAYLOAD))
        await router.chat_completion(dict(_PAYLOAD))  # 200 >= 150 now
        with pytest.raises(q.UserTokenQuotaExceeded):
            await router.chat_completion(dict(_PAYLOAD))
    assert len(calls) == 2
    assert q.usage_snapshot() == {"u1": 200}
    await router.chat_completion(dict(_PAYLOAD))  # unbound traffic unaffected
    assert q.usage_snapshot() == {"u1": 200}


# ── Orchestrator: refusal before the run ──────────────────────────────────────


@pytest.mark.anyio
async def test_orchestrator_refuses_over_cap_user_before_any_phase(monkeypatch):
    from services.workflow_orchestrator import ExecutionRequest, WorkflowOrchestrator

    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "10")
    with q.user_scope("u1"):
        q.record_user_tokens(10)
    orch = WorkflowOrchestrator()
    ran: list[str] = []

    async def must_not_run(run, req):
        ran.append("phase")

    orch._phase_handlers = {phase: must_not_run for phase in orch._phase_handlers}
    run = await orch.execute(ExecutionRequest(request="x", auto_approve=True, user_id="u1"))
    assert run.status == "failed"
    assert run.error == f"UserTokenQuotaExceeded: {q.REFUSAL_MESSAGE}"
    assert ran == []


@pytest.mark.anyio
async def test_orchestrator_binds_the_user_for_the_run_and_other_users_run(monkeypatch):
    from services.workflow_orchestrator import ExecutionRequest, Phase, WorkflowOrchestrator

    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "10")
    with q.user_scope("u1"):
        q.record_user_tokens(10)
    orch = WorkflowOrchestrator()
    seen: dict[str, str | None] = {}

    async def classify(run, req):
        seen["user"] = q.current_user()

    orch._phase_handlers = {Phase.CLASSIFY: classify}
    run = await orch.execute(ExecutionRequest(request="x", auto_approve=True, user_id="u2"))
    assert run.status == "done", run.error
    assert seen == {"user": "u2"}
    assert q.current_user() is None


# ── Endpoints ─────────────────────────────────────────────────────────────────


@pytest.fixture
def usage_client():
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient

    from backend.usage_router import build_usage_router

    who: dict[str, dict | None] = {"user": {"email": "a@example.com", "role": "user"}}

    async def fake_user():
        if who["user"] is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return who["user"]

    app = FastAPI()
    app.include_router(build_usage_router(fake_user))
    with TestClient(app) as client:
        yield client, who


def test_own_usage_endpoint(usage_client, monkeypatch):
    client, _who = usage_client
    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "1000")
    with q.user_scope("a@example.com"):
        q.record_user_tokens(400)
    with q.user_scope("someone-else"):
        q.record_user_tokens(999)
    body = client.get("/api/usage/agent-tokens").json()
    assert body == {"user_id": "a@example.com", "tokens_used": 400, "daily_cap": 1000,
                    "remaining": 600, "exceeded": False}


def test_own_usage_with_cap_disabled_has_no_remaining(usage_client):
    client, _who = usage_client
    body = client.get("/api/usage/agent-tokens").json()
    assert body["tokens_used"] == 0 and body["remaining"] is None and body["exceeded"] is False


def test_endpoints_require_authentication(usage_client):
    client, who = usage_client
    who["user"] = None
    assert client.get("/api/usage/agent-tokens").status_code == 401
    assert client.get("/api/admin/usage/agent-tokens").status_code == 401


def test_admin_endpoint_is_admin_only_and_lists_everyone(usage_client, monkeypatch):
    client, who = usage_client
    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "100")
    for uid, n in (("u1", 30), ("u2", 120)):
        with q.user_scope(uid):
            q.record_user_tokens(n)
    assert client.get("/api/admin/usage/agent-tokens").status_code == 403
    who["user"] = {"email": "ops@example.com", "role": "admin"}
    body = client.get("/api/admin/usage/agent-tokens").json()
    assert body["daily_cap"] == 100
    assert [(u["user_id"], u["tokens_used"], u["exceeded"]) for u in body["users"]] == [
        ("u2", 120, True), ("u1", 30, False),
    ]



def test_endpoints_are_mounted_and_authenticated_in_the_backend_app():
    from fastapi.testclient import TestClient

    from backend.server import app

    client = TestClient(app)
    assert client.get("/api/usage/agent-tokens").status_code == 401
    assert client.get("/api/admin/usage/agent-tokens").status_code == 401


# ── Agent loop: AgentRunner._chat_text bypasses ProviderRouter ───────────────


def _runner(tmp_path):
    from agent.loop import AgentRunner

    return AgentRunner(ollama_base="http://localhost:11434", workspace_root=tmp_path)


def _stub_failover(monkeypatch, calls: list[int], prompt: int = 30, completion: int = 20):
    from packages.ai import failover_client

    async def fake(payload, timeout_sec=0.0):
        calls.append(1)
        return failover_client.FailoverResult(
            text="ok", model="m", provider_id="p",
            prompt_tokens=prompt, completion_tokens=completion,
        )

    monkeypatch.setattr(failover_client, "failover_chat_completion", fake)


@pytest.mark.anyio
async def test_agent_runner_chat_text_records_tokens_for_the_bound_user(tmp_path, monkeypatch):
    calls: list[int] = []
    _stub_failover(monkeypatch, calls)
    runner = _runner(tmp_path)
    with q.user_scope("u1"):
        assert await runner._chat_text("m", [{"role": "user", "content": "hi"}]) == "ok"
    assert calls == [1]
    assert q.usage_snapshot() == {"u1": 50}
    await runner._chat_text("m", [{"role": "user", "content": "hi"}])  # unbound: not counted
    assert q.usage_snapshot() == {"u1": 50}


@pytest.mark.anyio
async def test_agent_runner_refuses_over_cap_user_before_the_http_call(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "50")
    calls: list[int] = []
    _stub_failover(monkeypatch, calls)
    runner = _runner(tmp_path)
    with q.user_scope("u1"):
        await runner._chat_text("m", [{"role": "user", "content": "hi"}])  # reaches 50
        with pytest.raises(q.UserTokenQuotaExceeded):
            await runner._chat_text("m", [{"role": "user", "content": "hi"}])
    assert calls == [1]


def test_anthropic_usage_total_reads_sdk_usage_and_tolerates_absence():
    from types import SimpleNamespace

    resp = SimpleNamespace(usage=SimpleNamespace(input_tokens=7, output_tokens=5))
    assert q.anthropic_usage_total(resp) == 12
    assert q.anthropic_usage_total(SimpleNamespace()) == 0


# ── call_llm / orchestrator propagate the quota refusal ──────────────────────


@pytest.mark.anyio
async def test_call_llm_reraises_quota_and_agent_budget_errors(monkeypatch):
    import backend.server as server
    from packages.ai.agent_budget import AgentBudgetExceeded

    async def provider():
        return {"type": "openai-compatible", "provider_id": "p"}

    monkeypatch.setattr(server, "get_active_provider", provider)
    for exc in (q.UserTokenQuotaExceeded(q.REFUSAL_MESSAGE), AgentBudgetExceeded("spent")):
        async def boom(**_kw):
            raise exc

        monkeypatch.setattr(server, "_build_provider_router", boom)
        with pytest.raises(type(exc)):
            await server.call_llm([{"role": "user", "content": "x"}])


def test_quota_errors_are_not_retryable():
    from services.workflow_orchestrator import WorkflowOrchestrator

    assert WorkflowOrchestrator._is_retryable(q.UserTokenQuotaExceeded(q.REFUSAL_MESSAGE)) is False


@pytest.mark.anyio
async def test_orchestrator_does_not_retry_a_quota_error_and_reports_the_reason():
    from services.workflow_orchestrator import ExecutionRequest, Phase, WorkflowOrchestrator

    orch = WorkflowOrchestrator()
    attempts: list[int] = []

    async def plan(run, req):
        attempts.append(1)
        raise q.UserTokenQuotaExceeded(q.REFUSAL_MESSAGE)

    orch._phase_handlers = {Phase.PLAN: plan}
    run = await orch.execute(ExecutionRequest(request="x", auto_approve=True, user_id="u1"))
    assert run.status == "failed"
    assert attempts == [1]
    assert q.REFUSAL_MESSAGE in (run.error or "")
