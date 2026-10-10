"""Durable sticky approval grants (packages/governance/approvals.py GrantStore)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from packages.config import settings
from packages.governance.approvals import GrantStore
from tests._fake_state_db import FakeDB, drain, install


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setattr(settings, "agency_state_persistence_enabled_raw", "true")


def _issue(store: GrantStore, **kw):
    args = dict(session_id="s1", scope="action", surface="shell", action="run",
                granted_by="admin", ttl_s=600, agent_id="a1", owner="o1",
                source_approval_id="apr_1")
    args.update(kw)
    return store.grant(**args)


def _col(db: FakeDB):
    return db.governance_grants


async def test_issue_persists_with_expiry_and_indexes(monkeypatch):
    db = install(monkeypatch)
    grant = _issue(GrantStore())
    await drain()
    doc = _col(db).docs[grant.grant_id]
    assert doc["session_id"] == "s1" and doc["agent_id"] == "a1" and doc["owner"] == "o1"
    remaining = (doc["expires_at"] - datetime.now(timezone.utc)).total_seconds()
    assert 590 < remaining <= 600
    assert ("expires_at", {"expireAfterSeconds": 0, "background": True}) in _col(db).indexes


async def test_grant_issued_by_another_worker_is_honoured(monkeypatch):
    db = install(monkeypatch)
    worker_a, worker_b = GrantStore(), GrantStore()
    grant = _issue(worker_a)
    await drain()
    assert worker_b.has_grant("s1", "shell", "run", "a1", "o1") is None  # sync = memory only
    found = await worker_b.has_grant_async("s1", "shell", "run", "a1", "o1")
    assert found is not None and found.grant_id == grant.grant_id
    assert 0 < found.to_dict()["seconds_remaining"] <= 600


async def test_remote_grant_respects_binding_scope_and_session(monkeypatch):
    install(monkeypatch)
    a, b = GrantStore(), GrantStore()
    _issue(a)
    await drain()
    assert await b.has_grant_async("s1", "shell", "run", "other-agent", "o1") is None
    assert await b.has_grant_async("s1", "shell", "run", "a1", "other-owner") is None
    assert await b.has_grant_async("s1", "shell", "run", None, None) is None
    assert await b.has_grant_async("s1", "shell", "other-action", "a1", "o1") is None
    assert await b.has_grant_async("s2", "shell", "run", "a1", "o1") is None
    assert await b.has_grant_async("anonymous", "shell", "run", "a1", "o1") is None
    assert await b.has_grant_async("s1", "credential", "run", "a1", "o1") is None


async def test_expired_db_grant_is_not_honoured(monkeypatch):
    db = install(monkeypatch)
    a, b = GrantStore(), GrantStore()
    grant = _issue(a)
    await drain()
    _col(db).docs[grant.grant_id]["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert await b.has_grant_async("s1", "shell", "run", "a1", "o1") is None


def test_from_doc_handles_naive_utc_and_rejects_expired():
    from packages.governance.approvals import SessionGrant

    base = {"_id": "g", "session_id": "s", "scope": "session", "surface": "x",
            "action": "y", "granted_by": "me"}
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # Motor returns naive UTC
    live = SessionGrant.from_doc({**base, "expires_at": now + timedelta(seconds=60)})
    assert live is not None and 0 < live.ttl_s <= 60 and not live.expired
    assert SessionGrant.from_doc({**base, "expires_at": now - timedelta(seconds=5)}) is None


async def test_revoke_removes_from_db_and_other_workers(monkeypatch):
    db = install(monkeypatch)
    a, b = GrantStore(), GrantStore()
    grant = _issue(a)
    await drain()
    assert await a.has_grant_async("s1", "shell", "run", "a1", "o1") is not None
    revoked = await b.revoke_grant_async(grant.grant_id)  # revoked on a different worker
    assert revoked is not None and revoked.grant_id == grant.grant_id
    assert grant.grant_id not in _col(db).docs
    # Worker A still has it in memory but the DB copy is gone: no longer honoured.
    assert await a.has_grant_async("s1", "shell", "run", "a1", "o1") is None
    assert a.has_grant("s1", "shell", "run", "a1", "o1") is None
    assert await b.revoke_grant_async(grant.grant_id) is None


async def test_sync_revoke_schedules_db_delete(monkeypatch):
    db = install(monkeypatch)
    store = GrantStore()
    grant = _issue(store)
    await drain()
    assert store.revoke(grant.grant_id) is True
    await drain()
    assert grant.grant_id not in _col(db).docs


async def test_db_error_on_lookup_fails_closed(monkeypatch):
    db = install(monkeypatch)
    a, b = GrantStore(), GrantStore()
    _issue(a)
    await drain()
    _col(db).fail = True
    assert await b.has_grant_async("s1", "shell", "run", "a1", "o1") is None
    # A persisted local grant whose DB check errors is also not honoured.
    assert await a.has_grant_async("s1", "shell", "run", "a1", "o1") is None


async def test_db_error_on_issue_keeps_grant_valid_on_issuing_worker(monkeypatch):
    db = install(monkeypatch)
    _col(db).fail = True
    store = GrantStore()
    grant = _issue(store)
    await drain()
    assert grant is not None and _col(db).docs == {}
    _col(db).fail = False
    assert await store.has_grant_async("s1", "shell", "run", "a1", "o1") is not None
    assert await GrantStore().has_grant_async("s1", "shell", "run", "a1", "o1") is None


async def test_malformed_db_row_is_no_grant(monkeypatch):
    db = install(monkeypatch)
    _col(db).docs["gnt_bad"] = {"_id": "gnt_bad", "session_id": "s1",
                                "expires_at": datetime.now(timezone.utc) + timedelta(hours=1)}
    assert await GrantStore().has_grant_async("s1", "shell", "run", "a1", "o1") is None


async def test_flag_off_makes_no_db_calls_and_is_memory_only(monkeypatch):
    db = install(monkeypatch)
    monkeypatch.setattr(settings, "agency_state_persistence_enabled_raw", "false")
    a, b = GrantStore(), GrantStore()
    grant = _issue(a)
    assert await a.has_grant_async("s1", "shell", "run", "a1", "o1") is not None
    assert await b.has_grant_async("s1", "shell", "run", "a1", "o1") is None
    assert await a.revoke_grant_async(grant.grant_id) is not None
    await drain()
    assert db._cols == {}


async def test_index_failure_does_not_break_persistence(monkeypatch):
    db = install(monkeypatch)
    _col(db).index_fail = True
    grant = _issue(GrantStore())
    await drain()
    assert grant.grant_id in _col(db).docs


def test_issue_without_running_loop_is_memory_only(monkeypatch):
    db = install(monkeypatch)
    store = GrantStore()
    assert _issue(store) is not None
    assert store.has_grant("s1", "shell", "run", "a1", "o1") is not None
    assert db._cols == {}


async def test_gate_find_grant_async_sees_other_workers_grant(monkeypatch):
    from packages.governance import approvals
    from packages.governance.enforcement import GovernanceGate

    install(monkeypatch)
    _issue(GrantStore())  # another worker
    await drain()
    monkeypatch.setattr(approvals, "_GRANTS", GrantStore())  # this worker
    identity = SimpleNamespace(session_id="s1", agent_id="a1", owner="o1")
    decision = SimpleNamespace(surface=SimpleNamespace(value="shell"), action="run")
    settings_ns = SimpleNamespace(governance_session_grants_enabled=True)
    assert GovernanceGate._find_grant(identity, decision, settings_ns) is None
    assert await GovernanceGate._find_grant_async(identity, decision, settings_ns) is not None
    off = SimpleNamespace(governance_session_grants_enabled=False)
    assert await GovernanceGate._find_grant_async(identity, decision, off) is None
