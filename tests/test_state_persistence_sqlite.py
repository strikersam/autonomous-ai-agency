"""Durable state persistence on STORAGE_BACKEND=sqlite (real temp-file SQLiteStore)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from agent import tool_output_store as tos
from packages.ai import user_token_quota as q
from packages.config import settings
from packages.governance.approvals import GrantStore, SessionGrant
from packages.storage import state_persistence as sp
from packages.storage.sqlite import SQLiteStore
from packages.storage.sqlite_atomic import atomic_increment, purge_expired
from tests._fake_state_db import drain


@pytest.fixture
async def store(tmp_path, monkeypatch):
    s = SQLiteStore(str(tmp_path / "state.db"))
    sp.reset()
    monkeypatch.setattr("backend.server.get_db", lambda: s)
    monkeypatch.setattr(settings, "agency_state_persistence_enabled_raw", "true")
    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "1000")
    q.reset()
    yield s
    q.reset()
    await s.close()


def _issue(gs: GrantStore, **kw):
    args = dict(session_id="s1", scope="action", surface="shell", action="run",
                granted_by="admin", ttl_s=600, agent_id="a1", owner="o1")
    args.update(kw)
    return gs.grant(**args)


def _past() -> dict:
    return sp.expiry_fields(datetime.now(timezone.utc) - timedelta(seconds=1))


async def test_collections_registered(store):
    for name in ("user_token_usage", "governance_grants", "tool_output_offload"):
        assert sp.collection(name) is not None


async def test_quota_round_trip_on_sqlite(store):
    with q.user_scope("alice"):
        q.record_user_tokens(100)
        q.record_user_tokens(250)
    await drain()
    q.reset()  # a fresh worker/restart: only the DB knows
    assert await q.refresh_user_total("alice") == 350
    assert q.tokens_used_today("alice") == 350


async def test_atomic_increment_concurrent_exact_total(store):
    col = store.user_token_usage
    await asyncio.gather(*[
        atomic_increment(col, "d:u", {"tokens": 3}, set_on_insert={"user_id": "u"}) for _ in range(200)
    ])
    doc = await col.find_one({"_id": "d:u"})
    assert doc["tokens"] == 600 and doc["user_id"] == "u"


async def test_atomic_increment_exact_across_two_stores_same_file(store, tmp_path):
    other = SQLiteStore(str(tmp_path / "state.db"))
    try:
        await store._get_conn()  # schema init races between fresh connections are not under test
        await other._get_conn()
        await asyncio.gather(*[
            atomic_increment((store if i % 2 else other).user_token_usage, "d:u", {"tokens": 1})
            for i in range(100)
        ])
        assert (await store.user_token_usage.find_one({"_id": "d:u"}))["tokens"] == 100
    finally:
        await other.close()


async def test_grant_issued_by_one_store_honoured_by_other(store):
    a, b = GrantStore(), GrantStore()
    grant = _issue(a)
    await drain()
    found = await b.has_grant_async("s1", "shell", "run", "a1", "o1")
    assert found is not None and found.grant_id == grant.grant_id
    assert await b.has_grant_async("s1", "shell", "run", "a1", "other") is None


async def test_expired_grant_rejected_and_revoke_propagates(store):
    a, b = GrantStore(), GrantStore()
    grant = _issue(a)
    await drain()
    await store.governance_grants.update_one({"_id": grant.grant_id}, {"$set": _past()})
    assert await b.has_grant_async("s1", "shell", "run", "a1", "o1") is None
    g2 = _issue(a, action="other")
    await drain()
    assert await b.has_grant_async("s1", "shell", "other", "a1", "o1") is not None
    await a.revoke_grant_async(g2.grant_id)
    assert await GrantStore().has_grant_async("s1", "shell", "other", "a1", "o1") is None


async def test_legacy_string_expiry_handled_fail_closed(store):
    a = GrantStore()
    grant = _issue(a)
    await drain()
    row = await store.governance_grants.find_one({"_id": grant.grant_id})
    row.pop(sp.EXPIRES_TS)
    row["expires_at"] = "not-a-date"
    assert SessionGrant.from_doc(row) is None
    row["expires_at"] = (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat()
    assert SessionGrant.from_doc(row) is not None  # a valid legacy ISO string still parses
    row["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
    assert SessionGrant.from_doc(row) is None
    del row["expires_at"]
    assert SessionGrant.from_doc(row) is None


def test_parse_expiry_defensive():
    now = datetime.now(timezone.utc)
    assert sp.parse_expiry(now) == pytest.approx(now.timestamp())
    assert sp.parse_expiry(now.replace(tzinfo=None)) == pytest.approx(now.timestamp())
    assert sp.parse_expiry(now.isoformat()) == pytest.approx(now.timestamp())
    assert sp.parse_expiry("123.5") == 123.5 and sp.parse_expiry(7) == 7.0
    for bad in (None, True, "", "garbage", float("nan"), float("inf"), object(), [1]):
        assert sp.parse_expiry(bad) is None


async def test_offload_read_async_by_owner_with_redaction(store):
    secret = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"
    ref = tos.ToolOutputStore().offload(f"token={secret} and plenty of text", owner="o")
    await drain()
    fresh = tos.ToolOutputStore()  # empty memory: must come from SQLite
    res = await fresh.read_async(ref, owner="o")
    assert res["ok"] is True and secret not in res["content"]
    assert (await fresh.read_async(ref, owner="intruder"))["ok"] is False


async def test_offload_expired_row_unreadable(store):
    ref = tos.ToolOutputStore().offload("old text", owner="o")
    await drain()
    await store.tool_output_offload.update_one({"_id": ref}, {"$set": _past()})
    assert (await tos.ToolOutputStore().read_async(ref, owner="o"))["ok"] is False


async def test_purge_expired_removes_only_expired(store):
    col = store.tool_output_offload
    future = sp.expiry_fields(datetime.now(timezone.utc) + timedelta(hours=1))
    await col.insert_one({"_id": "old", "text": "x", **_past()})
    await col.insert_one({"_id": "new", "text": "y", **future})
    assert await purge_expired(col, sp.EXPIRES_TS, datetime.now(timezone.utc).timestamp()) == 1
    assert await col.find_one({"_id": "old"}) is None
    assert await col.find_one({"_id": "new"}) is not None


async def test_ensure_ttl_index_noop_on_sqlite_and_purge_throttled(store):
    col = store.governance_grants
    await col.insert_one({"_id": "old", **_past()})
    await sp.ensure_ttl_index("governance_grants", col, "expires_at")  # purges; no create_index
    assert await col.find_one({"_id": "old"}) is None
    await col.insert_one({"_id": "old2", **_past()})
    await sp.ensure_ttl_index("governance_grants", col, "expires_at")  # inside the throttle window
    assert await col.find_one({"_id": "old2"}) is not None
    assert not sp._indexed


def test_id_equality_is_pushed_to_the_primary_key():
    from packages.storage.sqlite import _push_down_where

    where, params = _push_down_where("tool_output_offload", {"_id": "ref1", "owner": "o1"})
    assert where == " WHERE id = ?" and params == ["ref1"]


async def test_find_by_id_does_not_decode_every_row(store, monkeypatch):
    import packages.storage.sqlite as sq

    col = store.tool_output_offload
    for i in range(50):
        await col.insert_one({"_id": f"r{i}", "owner": "o1", "text": "x" * 10_000})
    decoded = 0
    real_loads = sq.json.loads

    def counting_loads(s, *a, **k):
        nonlocal decoded
        decoded += 1
        return real_loads(s, *a, **k)

    monkeypatch.setattr(sq.json, "loads", counting_loads)
    doc = await col.find_one({"_id": "r7", "owner": "o1"})
    assert doc is not None and doc["_id"] == "r7"
    assert decoded == 1


async def test_atomic_increment_rejects_empty_inc(store):
    with pytest.raises(ValueError):
        await atomic_increment(store.user_token_usage, "d:u", {})
