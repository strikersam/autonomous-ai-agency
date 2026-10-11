"""Review-fix regressions for the durable state layer (ids, revoke races, timeouts, caps)."""
from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timedelta, timezone

import pytest

from agent import tool_output_store as tos
from packages.ai import user_token_quota as q
from packages.config import settings
from packages.governance import approvals
from packages.governance.approvals import GrantStore, SessionGrant
from packages.storage import state_persistence as sp
from tests._fake_state_db import drain, install


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "2000")
    monkeypatch.setattr(settings, "agency_state_persistence_enabled_raw", "true")
    q.reset()
    tos.reset_store()
    yield
    q.reset()
    tos.reset_store()


def _issue(store: GrantStore, **kw):
    args = dict(session_id="s1", scope="action", surface="shell", action="run",
                granted_by="admin", ttl_s=600, agent_id="a1", owner="o1")
    args.update(kw)
    return store.grant(**args)


# ── B1: ids do not collide across workers ────────────────────────────────────


async def test_two_workers_issuing_in_the_same_second_get_distinct_ids(monkeypatch):
    db = install(monkeypatch)
    monkeypatch.setattr("time.time", lambda: 1_800_000_000.0)
    a, b = GrantStore(), GrantStore()  # both start their counters at 0
    ga, gb = _issue(a, session_id="sa"), _issue(b, session_id="sb")
    await drain()
    assert ga.grant_id != gb.grant_id
    assert set(db.governance_grants.docs) == {ga.grant_id, gb.grant_id}


# ── B2: revoke before / during the async write never resurrects ──────────────


async def test_revoke_before_write_lands_is_not_resurrected(monkeypatch):
    db = install(monkeypatch)
    a, b = GrantStore(), GrantStore()
    grant = _issue(a)
    assert await a.revoke_grant_async(grant.grant_id) is not None  # write not run yet
    await drain()
    assert grant.grant_id not in db.governance_grants.docs
    assert await b.has_grant_async("s1", "shell", "run", "a1", "o1") is None


async def test_revoke_while_write_is_in_flight_deletes_the_row(monkeypatch):
    db = install(monkeypatch)
    col = db.governance_grants
    started, release = asyncio.Event(), asyncio.Event()
    real = col.replace_one

    async def slow_replace(query, doc, upsert=False):
        started.set()
        await release.wait()
        await real(query, doc, upsert)

    monkeypatch.setattr(col, "replace_one", slow_replace)
    a, b = GrantStore(), GrantStore()
    grant = _issue(a)
    await started.wait()
    a.revoke(grant.grant_id)  # sync revoke while the write is mid-flight
    release.set()
    await drain()
    assert grant.grant_id not in col.docs
    assert await b.has_grant_async("s1", "shell", "run", "a1", "o1") is None


async def test_revoked_id_memory_is_bounded(monkeypatch):
    install(monkeypatch)
    monkeypatch.setattr(approvals, "_MAX_REVOKED", 3)
    store = GrantStore()
    for i in range(10):
        await store.revoke_grant_async(f"gnt_{i}")
    assert len(store._revoked) == 3


# ── Sync revoke deletes a grant this worker only saw remotely ────────────────


async def test_sync_revoke_of_unseen_grant_still_deletes_the_db_row(monkeypatch):
    db = install(monkeypatch)
    a, b = GrantStore(), GrantStore()
    grant = _issue(a)
    await drain()
    assert b.revoke(grant.grant_id) is False  # never held here
    await drain()
    assert grant.grant_id not in db.governance_grants.docs


# ── S1: a failed index is retried later ──────────────────────────────────────


async def test_index_creation_is_retried_after_a_failure(monkeypatch):
    db = install(monkeypatch)
    col = db.governance_grants
    col.index_fail = True
    await sp.ensure_ttl_index("governance_grants", col, "expires_at")
    assert col.indexes == [] and not sp._indexed
    col.index_fail = False
    await sp.ensure_ttl_index("governance_grants", col, "expires_at")  # inside the backoff
    assert col.indexes == []
    sp._index_retry_at.clear()
    await sp.ensure_ttl_index("governance_grants", col, "expires_at")
    await sp.ensure_ttl_index("governance_grants", col, "expires_at")  # now done once only
    assert len(col.indexes) == 1


# ── S2: slow DB reads fail closed ────────────────────────────────────────────


async def test_slow_grant_lookup_times_out_to_no_grant(monkeypatch):
    db = install(monkeypatch)
    a, b = GrantStore(), GrantStore()
    _issue(a)
    await drain()
    monkeypatch.setattr(approvals, "_DB_TIMEOUT_S", 0.05)

    async def slow_to_list(*args, **kw):
        await asyncio.sleep(1)

    class _SlowCursor:
        to_list = staticmethod(slow_to_list)

    monkeypatch.setattr(db.governance_grants, "find", lambda *a_, **k: _SlowCursor())
    assert await b.has_grant_async("s1", "shell", "run", "a1", "o1") is None


async def test_slow_offload_read_times_out_to_unknown_ref(monkeypatch):
    db = install(monkeypatch)
    ref = tos.ToolOutputStore().offload("abc", owner="r")
    await drain()
    monkeypatch.setattr(tos, "_DB_TIMEOUT_S", 0.05)

    async def slow(*a, **k):
        await asyncio.sleep(1)

    monkeypatch.setattr(db.tool_output_offload, "find_one", slow)
    assert (await tos.ToolOutputStore().read_async(ref, owner="r"))["ok"] is False


# ── S3: per-call check adds growth since the last refresh ────────────────────


async def test_growth_since_refresh_is_added_to_the_db_total(monkeypatch):
    db = install(monkeypatch)
    with q.user_scope("zed"):
        q.record_user_tokens(500)
    await drain()
    db.user_token_usage.docs[f"{q._today()}:zed"]["tokens"] = 1800  # others spent 1300
    assert await q.user_quota_refusal_async("zed") is None  # 1800 < 2000
    with q.user_scope("zed"):
        q.record_user_tokens(400)  # local 900; DB-side total is really 2200 now
        assert q.user_quota_refusal("zed") == q.REFUSAL_MESSAGE  # 1800 + 400
    assert q.tokens_used_today("zed") == 2200


# ── S5 / N2 ──────────────────────────────────────────────────────────────────


async def test_ownerless_offload_is_not_persisted(monkeypatch):
    db = install(monkeypatch)
    tos.ToolOutputStore().offload("no owner")
    await drain()
    assert db._cols == {}


# ── S6 / S9: bounded and server-loop-only fire-and-forget ────────────────────


async def test_pending_writes_are_capped(monkeypatch):
    install(monkeypatch)
    monkeypatch.setattr(sp, "_MAX_PENDING", 2)

    async def noop():
        await asyncio.sleep(0)

    assert [sp.fire_and_forget(noop()) for _ in range(3)] == [True, True, False]
    await drain()


def test_writes_from_a_background_thread_loop_are_dropped(monkeypatch):
    db = install(monkeypatch)
    seen: list[bool] = []

    async def go():
        with q.user_scope("thr"):
            q.record_user_tokens(100)
        await asyncio.sleep(0.01)
        seen.append(True)

    t = threading.Thread(target=lambda: asyncio.run(go()))
    t.start()
    t.join()
    assert seen == [True] and db._cols == {}
    assert q.usage_snapshot() == {"thr": 100}  # the cache still counts it


def test_warn_limited_logs_once_per_window(caplog):
    sp.reset()
    with caplog.at_level("DEBUG", logger="qwen-proxy"):
        for _ in range(5):
            sp.warn_limited("k", "db down %s", 1)
    assert len([r for r in caplog.records if r.levelname == "WARNING"]) == 1


# ── S8: admins see grants held by other workers ──────────────────────────────


async def test_list_grants_async_merges_db_rows(monkeypatch):
    install(monkeypatch)
    a, b = GrantStore(), GrantStore()
    ga = _issue(a, session_id="sa")
    gb = _issue(b, session_id="sb")
    await drain()
    assert [g["grant_id"] for g in b.list_grants()] == [gb.grant_id]
    listed = {g["grant_id"] for g in await b.list_grants_async()}
    assert listed == {ga.grant_id, gb.grant_id}


# ── N1: persisted rows are re-validated ──────────────────────────────────────


def _doc(**over):
    base = {"_id": "g", "session_id": "s", "scope": "action", "surface": "shell", "action": "run",
            "granted_by": "me", "ttl_s": 600, "agent_id": "a", "owner": "o",
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=300)}
    base.update(over)
    return base


def test_from_doc_revalidates_issue_time_rules():
    assert SessionGrant.from_doc(_doc()) is not None
    for bad in ({"scope": "once"}, {"scope": "everything"}, {"surface": "credential"},
                {"session_id": "anonymous"}, {"session_id": ""}, {"granted_by": ""},
                {"agent_id": "agent:unknown", "owner": "system"}):
        assert SessionGrant.from_doc(_doc(**bad)) is None, bad


def test_from_doc_caps_remaining_ttl_at_the_rows_own_ttl():
    grant = SessionGrant.from_doc(_doc(ttl_s=60, expires_at=datetime.now(timezone.utc) + timedelta(days=30)))
    assert grant is not None and grant.ttl_s <= 60
