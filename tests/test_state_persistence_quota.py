"""Durable per-user token ledger (packages/ai/user_token_quota.py + state_persistence)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from packages.ai import user_token_quota as q
from packages.config import settings
from tests._fake_state_db import FakeDB, drain, install


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "1000")
    monkeypatch.setattr(settings, "agency_state_persistence_enabled_raw", "true")
    q.reset()
    yield
    q.reset()


def _usage(db: FakeDB):
    return db.user_token_usage


async def test_record_writes_atomic_inc_upsert_with_ttl(monkeypatch):
    db = install(monkeypatch)
    with q.user_scope("alice"):
        q.record_user_tokens(100)
        q.record_user_tokens(250)
    await drain()
    day = q._today()
    doc = _usage(db).docs[f"{day}:alice"]
    assert doc["tokens"] == 350 and doc["user_id"] == "alice" and doc["day"] == day
    start = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    assert doc["expires_at"] == start + timedelta(days=3)
    assert _usage(db).indexes == [("expires_at", {"expireAfterSeconds": 0, "background": True})]
    assert q.usage_snapshot() == {"alice": 350}


async def test_second_worker_sees_total_and_pre_run_check_refuses(monkeypatch):
    db = install(monkeypatch)
    with q.user_scope("bob"):
        q.record_user_tokens(1200)  # worker A pushes the user over the cap
    await drain()
    q.reset()  # worker B: empty cache, same DB
    assert q.user_quota_refusal("bob") is None  # sync cache alone cannot know
    assert await q.user_quota_refusal_async("bob") == q.REFUSAL_MESSAGE
    assert q.tokens_used_today("bob") == 1200
    assert await q.user_quota_refusal_async("carol") is None


async def test_cache_and_db_are_not_double_counted(monkeypatch):
    install(monkeypatch)
    with q.user_scope("dave"):
        q.record_user_tokens(600)
    await drain()
    await q.user_quota_refusal_async("dave")  # DB (600) already includes local (600)
    assert q.tokens_used_today("dave") == 600
    assert await q.user_quota_refusal_async("dave") is None


async def test_per_call_check_refreshes_from_db_in_background(monkeypatch):
    db = install(monkeypatch)
    _usage(db).docs[f"{q._today()}:erin"] = {"_id": f"{q._today()}:erin", "tokens": 5000}
    with q.user_scope("erin"):
        q.ensure_user_within_quota()  # cache empty -> allowed, schedules a refresh
        await drain()
        with pytest.raises(q.UserTokenQuotaExceeded):
            q.ensure_user_within_quota()


async def test_background_refresh_is_throttled(monkeypatch):
    db = install(monkeypatch)
    with q.user_scope("fay"):
        for _ in range(5):
            q.ensure_user_within_quota()
        await drain()
    assert _usage(db).calls.count("find_one") == 1


async def test_db_error_falls_back_to_cache_enforcement(monkeypatch):
    db = install(monkeypatch)
    _usage(db).fail = True
    with q.user_scope("gus"):
        q.record_user_tokens(1500)  # write fails in the background, silently
        await drain()
        with pytest.raises(q.UserTokenQuotaExceeded):
            q.ensure_user_within_quota()
    assert await q.user_quota_refusal_async("gus") == q.REFUSAL_MESSAGE  # read fails -> cache
    assert await q.user_quota_refusal_async("hal") is None


async def test_index_failure_does_not_break_writes(monkeypatch):
    db = install(monkeypatch)
    _usage(db).index_fail = True
    with q.user_scope("ivy"):
        q.record_user_tokens(10)
    await drain()
    assert _usage(db).docs[f"{q._today()}:ivy"]["tokens"] == 10


async def test_flag_off_makes_no_db_calls(monkeypatch):
    db = install(monkeypatch)
    monkeypatch.setattr(settings, "agency_state_persistence_enabled_raw", "false")
    with q.user_scope("jon"):
        q.record_user_tokens(2000)
        with pytest.raises(q.UserTokenQuotaExceeded):
            q.ensure_user_within_quota()
    await drain()
    assert await q.user_quota_refusal_async("jon") == q.REFUSAL_MESSAGE
    assert db._cols == {}  # not even a collection was touched


def test_record_without_running_loop_is_cache_only(monkeypatch):
    db = install(monkeypatch)
    with q.user_scope("kim"):
        q.record_user_tokens(40)
    assert q.usage_snapshot() == {"kim": 40}
    assert db._cols == {}


async def test_yesterdays_document_is_not_counted(monkeypatch):
    db = install(monkeypatch)
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    _usage(db).docs[f"{yesterday}:lee"] = {"_id": f"{yesterday}:lee", "tokens": 99999}
    assert await q.user_quota_refusal_async("lee") is None


async def test_exempt_and_unbound_users_are_never_persisted(monkeypatch):
    db = install(monkeypatch)
    with q.user_scope("scheduler"):
        q.record_user_tokens(500)
    q.record_user_tokens(500)
    await drain()
    assert db._cols == {}


async def test_orchestrator_pre_run_check_uses_db_total(monkeypatch):
    from services.workflow_orchestrator import ExecutionRequest, WorkflowOrchestrator

    db = install(monkeypatch)
    _usage(db).docs[f"{q._today()}:max"] = {"_id": f"{q._today()}:max", "tokens": 4000}
    orch = WorkflowOrchestrator()  # this worker's cache is empty; only the DB knows
    run = await orch.execute(ExecutionRequest(request="x", auto_approve=True, user_id="max"))
    assert run.status == "failed"
    assert run.error == f"UserTokenQuotaExceeded: {q.REFUSAL_MESSAGE}"


async def test_legacy_row_without_expires_at_ts_is_counted_and_incremented(monkeypatch):
    """Rows written before expires_at_ts existed must keep their total on Mongo."""
    db = install(monkeypatch)
    day = q._today()
    _usage(db).docs[f"{day}:erin"] = {
        "_id": f"{day}:erin", "user_id": "erin", "day": day, "tokens": 400,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=2),
    }
    assert await q.refresh_user_total("erin") == 400
    with q.user_scope("erin"):
        q.record_user_tokens(100)
    await drain()
    assert _usage(db).docs[f"{day}:erin"]["tokens"] == 500
