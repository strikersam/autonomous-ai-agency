"""Adversarial edge cases for packages/ai/user_token_quota.py (QA pass).

Complements tests/test_user_token_quota.py. Tests that fail here are real
defects in the feature under test, not problems with the tests.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone

import httpx
import pytest

from packages.ai import user_token_quota as q
from packages.ai.router import ProviderConfig, ProviderRouter

_PAYLOAD = {"model": "a", "messages": [{"role": "user", "content": "hi"}]}


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("AGENT_USER_TOKENS_PER_DAY", raising=False)
    q.reset()
    yield
    q.reset()


# ── Cap boundary: exactly reached vs exceeded ────────────────────────────────


def test_one_below_cap_is_allowed(monkeypatch):
    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "100")
    with q.user_scope("u1"):
        q.record_user_tokens(99)
    assert q.user_quota_refusal("u1") is None


def test_exactly_at_cap_is_refused(monkeypatch):
    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "100")
    with q.user_scope("u1"):
        q.record_user_tokens(100)
        with pytest.raises(q.UserTokenQuotaExceeded):
            q.ensure_user_within_quota()


def test_single_call_overshoot_is_refused_afterwards(monkeypatch):
    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "100")
    with q.user_scope("u1"):
        q.record_user_tokens(10_000)  # one huge call overshoots
    assert q.user_quota_refusal("u1") == q.REFUSAL_MESSAGE
    assert q.tokens_used_today("u1") == 10_000


def test_zero_tokens_at_zero_usage_is_not_refused_with_positive_cap(monkeypatch):
    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "1")
    with q.user_scope("u1"):
        q.record_user_tokens(0)
    assert q.user_quota_refusal("u1") is None


# ── Garbage / negative token counts ──────────────────────────────────────────


def test_negative_count_cannot_refund_earlier_usage(monkeypatch):
    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "100")
    with q.user_scope("u1"):
        q.record_user_tokens(100)
        q.record_user_tokens(-1_000_000)
    assert q.tokens_used_today("u1") == 100
    assert q.user_quota_refusal("u1") == q.REFUSAL_MESSAGE


def test_float_count_is_truncated_not_rejected():
    with q.user_scope("u1"):
        q.record_user_tokens(2.9)  # type: ignore[arg-type]
    assert q.tokens_used_today("u1") == 2


def test_bool_count_is_int_coerced():
    with q.user_scope("u1"):
        q.record_user_tokens(True)  # type: ignore[arg-type]
    assert q.tokens_used_today("u1") == 1


def test_huge_count_does_not_overflow_compare(monkeypatch):
    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "100")
    with q.user_scope("u1"):
        q.record_user_tokens(10**30)
    assert q.user_quota_refusal("u1") == q.REFUSAL_MESSAGE


def test_string_count_never_raises_per_docstring():
    # Docstring contract: "Add one call's tokens ... Never raises."
    with q.user_scope("u1"):
        q.record_user_tokens("not-a-number")  # type: ignore[arg-type]


def test_nan_count_never_raises_per_docstring():
    with q.user_scope("u1"):
        q.record_user_tokens(float("nan"))  # type: ignore[arg-type]


def test_infinite_count_never_raises_per_docstring():
    with q.user_scope("u1"):
        q.record_user_tokens(float("inf"))  # type: ignore[arg-type]


# ── User id None / empty / whitespace ────────────────────────────────────────


@pytest.mark.parametrize("raw", [None, "", "   ", "\t\n"])
def test_blank_user_ids_are_unbound_and_uncounted(monkeypatch, raw):
    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "1")
    with q.user_scope(raw):
        assert q.current_user() is None
        q.record_user_tokens(500)
        q.ensure_user_within_quota()
    assert q.usage_snapshot() == {}
    assert q.user_quota_refusal(raw) is None


def test_padded_user_id_shares_bucket_with_trimmed_id(monkeypatch):
    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "10")
    with q.user_scope(" u1 "):
        q.record_user_tokens(10)
    assert q.tokens_used_today("u1") == 10
    assert q.user_quota_refusal("  u1") == q.REFUSAL_MESSAGE


def test_padded_scheduler_is_still_exempt(monkeypatch):
    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "1")
    with q.user_scope("  scheduler  "):
        assert q.current_user() is None
        q.record_user_tokens(999)
    assert q.user_quota_refusal(" scheduler ") is None
    assert q.usage_snapshot() == {}


def test_scheduler_is_exempt_case_sensitively_only_for_exact_name():
    # Only the exact pseudo-user is exempt; a person named "Scheduler" is counted.
    with q.user_scope("Scheduler"):
        assert q.current_user() == "Scheduler"


def test_nested_none_scope_unbinds_then_restores():
    with q.user_scope("outer"):
        with q.user_scope(None):
            assert q.current_user() is None
        assert q.current_user() == "outer"


# ── Concurrency ──────────────────────────────────────────────────────────────


def test_concurrent_records_from_threads_lose_no_updates():
    def worker():
        with q.user_scope("u1"):
            for _ in range(1000):
                q.record_user_tokens(1)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert q.usage_snapshot() == {"u1": 8000}


def test_concurrent_distinct_users_each_keep_their_own_total():
    def worker(uid: str):
        with q.user_scope(uid):
            for _ in range(500):
                q.record_user_tokens(2)

    threads = [threading.Thread(target=worker, args=(f"u{i}",)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert q.usage_snapshot() == {f"u{i}": 1000 for i in range(6)}


def test_plain_thread_does_not_inherit_user_scope():
    # Known limitation, characterised: a raw threading.Thread does not copy the
    # ContextVar, so work offloaded that way escapes attribution. asyncio tasks
    # and asyncio.to_thread do copy it.
    seen: list[str | None] = []
    with q.user_scope("u1"):
        t = threading.Thread(target=lambda: seen.append(q.current_user()))
        t.start()
        t.join()
    assert seen == [None]


# ── Bounded ledger overflow ──────────────────────────────────────────────────


def test_overflow_bucket_collects_new_users_past_the_bound(monkeypatch):
    monkeypatch.setattr(q, "_MAX_USERS_PER_DAY", 1)
    for uid in ("a", "b", "c"):
        with q.user_scope(uid):
            q.record_user_tokens(7)
    assert q.usage_snapshot() == {"a": 7, "other": 14}


def test_existing_user_still_counted_after_ledger_is_full(monkeypatch):
    monkeypatch.setattr(q, "_MAX_USERS_PER_DAY", 1)
    with q.user_scope("a"):
        q.record_user_tokens(1)
    with q.user_scope("b"):
        q.record_user_tokens(1)  # folded into "other"
    with q.user_scope("a"):
        q.record_user_tokens(5)  # already tracked, must not be folded
    assert q.usage_snapshot() == {"a": 6, "other": 1}


def test_overflowed_user_is_still_refused_when_over_cap(monkeypatch):
    """BUG (expected to fail): a user whose spend was folded into "other" is never
    refused, because the cap check reads only the user's own ledger key."""
    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "50")
    monkeypatch.setattr(q, "_MAX_USERS_PER_DAY", 1)
    with q.user_scope("a"):
        q.record_user_tokens(5)
    with q.user_scope("b"):
        q.record_user_tokens(100)  # b is over cap, but lands in "other"
    assert q.user_quota_refusal("b") == q.REFUSAL_MESSAGE


def test_bucket_named_other_collides_with_overflow(monkeypatch):
    """BUG (expected to fail): a real user whose id is literally "other" shares the
    overflow bucket, so their own cap is driven by strangers' spend."""
    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "10")
    monkeypatch.setattr(q, "_MAX_USERS_PER_DAY", 1)
    with q.user_scope("a"):
        q.record_user_tokens(1)
    with q.user_scope("stranger"):
        q.record_user_tokens(50)  # folded into "other"
    assert q.user_quota_refusal("other") is None


# ── UTC day rollover ─────────────────────────────────────────────────────────


class _FakeDT:
    current = datetime(2026, 10, 9, 23, 59, 59, tzinfo=timezone.utc)
    seen_tz: list = []

    @classmethod
    def now(cls, tz=None):
        cls.seen_tz.append(tz)
        return cls.current


def test_day_key_uses_utc_not_local_time(monkeypatch):
    _FakeDT.seen_tz = []
    monkeypatch.setattr(q, "datetime", _FakeDT)
    q._today()
    assert _FakeDT.seen_tz == [timezone.utc]


def test_ledger_resets_one_second_after_utc_midnight(monkeypatch):
    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "10")
    monkeypatch.setattr(q, "datetime", _FakeDT)
    _FakeDT.current = datetime(2026, 10, 9, 23, 59, 59, tzinfo=timezone.utc)
    with q.user_scope("u1"):
        q.record_user_tokens(50)
    assert q.user_quota_refusal("u1") == q.REFUSAL_MESSAGE

    _FakeDT.current = datetime(2026, 10, 10, 0, 0, 0, tzinfo=timezone.utc)
    assert q.user_quota_refusal("u1") is None
    assert q.usage_snapshot() == {}


def test_rollover_happens_on_read_without_any_write(monkeypatch):
    monkeypatch.setattr(q, "datetime", _FakeDT)
    _FakeDT.current = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)
    with q.user_scope("u1"):
        q.record_user_tokens(42)
    _FakeDT.current = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
    assert q.tokens_used_today("u1") == 0


def test_write_on_new_day_does_not_carry_yesterday(monkeypatch):
    monkeypatch.setattr(q, "datetime", _FakeDT)
    _FakeDT.current = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)
    with q.user_scope("u1"):
        q.record_user_tokens(42)
    _FakeDT.current = datetime(2026, 10, 10, 0, 0, 1, tzinfo=timezone.utc)
    with q.user_scope("u1"):
        q.record_user_tokens(3)
    assert q.usage_snapshot() == {"u1": 3}


# ── Router: refusal before the provider is touched ───────────────────────────


def _router(monkeypatch, calls: list[str], prompt: int = 0, completion: int = 0,
            total: int | None = None) -> ProviderRouter:
    async def fake_post_chat(self, provider, payload, timeout_sec):
        calls.append(provider.provider_id)
        usage = {"prompt_tokens": prompt, "completion_tokens": completion}
        if total is not None:
            usage["total_tokens"] = total
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}], "usage": usage},
            headers={"content-type": "application/json"},
        )

    monkeypatch.setattr(ProviderRouter, "_post_chat", fake_post_chat)
    return ProviderRouter([
        ProviderConfig("only", "openai-compatible", "https://a/v1", api_key="k",
                       default_model="a", priority=0),
    ])


@pytest.mark.anyio
async def test_over_cap_user_never_reaches_the_provider(monkeypatch):
    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "10")
    calls: list[str] = []
    router = _router(monkeypatch, calls, total=5)
    with q.user_scope("u1"):
        q.record_user_tokens(10)
        with pytest.raises(q.UserTokenQuotaExceeded):
            await router.chat_completion(dict(_PAYLOAD))
    assert calls == []


@pytest.mark.anyio
async def test_usage_without_total_is_summed_from_prompt_and_completion(monkeypatch):
    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "1000")
    calls: list[str] = []
    router = _router(monkeypatch, calls, prompt=30, completion=20)
    with q.user_scope("u1"):
        await router.chat_completion(dict(_PAYLOAD))
    assert q.usage_snapshot() == {"u1": 50}


@pytest.mark.anyio
async def test_missing_usage_block_records_zero_and_does_not_fail(monkeypatch):
    calls: list[str] = []

    async def no_usage(self, provider, payload, timeout_sec):
        calls.append(provider.provider_id)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}]},
            headers={"content-type": "application/json"},
        )

    monkeypatch.setattr(ProviderRouter, "_post_chat", no_usage)
    router = ProviderRouter([
        ProviderConfig("only", "openai-compatible", "https://a/v1", api_key="k",
                       default_model="a", priority=0),
    ])
    with q.user_scope("u1"):
        await router.chat_completion(dict(_PAYLOAD))
    assert len(calls) == 1
    assert q.tokens_used_today("u1") == 0


# ── Orchestrator: scheduler exemption and refusal shape ──────────────────────


@pytest.mark.anyio
async def test_orchestrator_runs_scheduler_even_with_cap_engaged(monkeypatch):
    from services.workflow_orchestrator import ExecutionRequest, Phase, WorkflowOrchestrator

    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "1")
    with q.user_scope("scheduler"):
        q.record_user_tokens(999)  # exempt: must not count
    orch = WorkflowOrchestrator()
    seen: dict[str, str | None] = {}

    async def classify(run, req):
        seen["user"] = q.current_user()

    orch._phase_handlers = {Phase.CLASSIFY: classify}
    run = await orch.execute(
        ExecutionRequest(request="x", auto_approve=True, user_id="scheduler")
    )
    assert run.status == "done", run.error
    assert seen == {"user": None}


@pytest.mark.anyio
async def test_orchestrator_refusal_leaves_no_user_bound(monkeypatch):
    from services.workflow_orchestrator import ExecutionRequest, WorkflowOrchestrator

    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "1")
    with q.user_scope("u1"):
        q.record_user_tokens(1)
    orch = WorkflowOrchestrator()
    run = await orch.execute(ExecutionRequest(request="x", auto_approve=True, user_id="u1"))
    assert run.status == "failed"
    assert q.current_user() is None
    assert run.user_id == "u1"


@pytest.mark.anyio
async def test_orchestrator_with_no_user_is_never_refused(monkeypatch):
    from services.workflow_orchestrator import ExecutionRequest, Phase, WorkflowOrchestrator

    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "1")
    orch = WorkflowOrchestrator()

    async def classify(run, req):
        return None

    orch._phase_handlers = {Phase.CLASSIFY: classify}
    run = await orch.execute(ExecutionRequest(request="x", auto_approve=True, user_id=None))
    assert run.status == "done", run.error


# ── Endpoint edge cases ──────────────────────────────────────────────────────


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


def test_admin_listing_with_cap_disabled_never_reports_exceeded(usage_client):
    client, who = usage_client
    who["user"] = {"email": "ops@example.com", "role": "admin"}
    with q.user_scope("u1"):
        q.record_user_tokens(10**9)
    body = client.get("/api/admin/usage/agent-tokens").json()
    assert body["daily_cap"] == 0
    assert body["users"][0]["remaining"] is None
    assert body["users"][0]["exceeded"] is False


def test_admin_listing_empty_when_nobody_used_anything(usage_client):
    client, who = usage_client
    who["user"] = {"email": "ops@example.com", "role": "admin"}
    body = client.get("/api/admin/usage/agent-tokens").json()
    assert body == {"daily_cap": 0, "users": []}


def test_own_usage_at_exact_cap_reports_exceeded_and_zero_remaining(usage_client, monkeypatch):
    client, _who = usage_client
    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "100")
    with q.user_scope("a@example.com"):
        q.record_user_tokens(100)
    body = client.get("/api/usage/agent-tokens").json()
    assert body["remaining"] == 0 and body["exceeded"] is True


def test_own_usage_does_not_leak_other_users(usage_client, monkeypatch):
    client, _who = usage_client
    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "100")
    with q.user_scope("victim@example.com"):
        q.record_user_tokens(99)
    body = client.get("/api/usage/agent-tokens").json()
    assert body["tokens_used"] == 0
    assert "victim" not in client.get("/api/usage/agent-tokens").text
