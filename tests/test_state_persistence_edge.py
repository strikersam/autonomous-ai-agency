"""Adversarial edge tests for the durable state layer (feat/persist-octop-state).

Covers the token ledger (packages/ai/user_token_quota.py), sticky grants
(packages/governance/approvals.py GrantStore) and the tool-output offload
(agent/tool_output_store.py), all backed by the in-memory FakeDB. "Two workers"
are simulated by swapping process-level caches around the shared FakeDB.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from agent import tool_output_store as tos
from packages.ai import user_token_quota as q
from packages.config import settings
from packages.governance.approvals import GrantStore
from packages.security.redact import redact_secrets
from tests._fake_state_db import FakeDB, _Cursor, drain, install

_STATE_COLLECTIONS = ("user_token_usage", "governance_grants", "tool_output_offload")


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setenv("AGENT_USER_TOKENS_PER_DAY", "1000")
    monkeypatch.setattr(settings, "agency_state_persistence_enabled_raw", "true")
    q.reset()
    tos.reset_store()
    yield
    q.reset()
    tos.reset_store()


def _snapshot() -> dict:
    with q._lock:
        return {
            "day": q._day,
            "ledger": dict(q._ledger),
            "remote": dict(q._remote),
            "refreshed": dict(q._refreshed),
            "at_refresh": dict(q._local_at_refresh),
        }


def _become(state: dict) -> None:
    """Make this process's quota cache look like the given worker's cache."""
    q.reset()
    with q._lock:
        q._day = state["day"]
        q._ledger.update(state["ledger"])
        q._remote.update(state["remote"])
        q._refreshed.update(state["refreshed"])
        q._local_at_refresh.update(state["at_refresh"])


def _issue(store: GrantStore, **kw) -> object:
    args = dict(session_id="s1", scope="action", surface="shell", action="run",
                granted_by="admin", ttl_s=600, agent_id="a1", owner="o1")
    args.update(kw)
    return store.grant(**args)


def _row(grant_id: str, *, session: str = "s1", scope: str = "action", surface: str = "shell",
         action: str = "run", agent: str = "a1", owner: str = "o1") -> dict:
    return {
        "_id": grant_id, "session_id": session, "scope": scope, "surface": surface,
        "action": action, "granted_by": "admin", "ttl_s": 600, "agent_id": agent,
        "owner": owner, "source_approval_id": "", "created_iso": "",
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
    }


# ── Two-worker token quota ───────────────────────────────────────────────────


async def test_two_workers_each_under_cap_combined_over_cap_is_refused_pre_run(monkeypatch):
    db = install(monkeypatch)
    with q.user_scope("pat"):
        q.record_user_tokens(600)  # worker A
    await drain()
    worker_a = _snapshot()
    q.reset()
    with q.user_scope("pat"):
        q.record_user_tokens(600)  # worker B, its own cache is also under the cap
    await drain()
    worker_b = _snapshot()
    assert db.user_token_usage.docs[f"{q._today()}:pat"]["tokens"] == 1200

    _become(worker_b)
    assert q.user_quota_refusal("pat") is None  # local view alone is under the cap
    assert await q.user_quota_refusal_async("pat") == q.REFUSAL_MESSAGE

    _become(worker_a)
    assert q.user_quota_refusal("pat") is None
    assert await q.user_quota_refusal_async("pat") == q.REFUSAL_MESSAGE


# ── DB total lagging behind the local cache ──────────────────────────────────


async def test_db_total_lagging_below_local_cache_still_uses_the_max(monkeypatch):
    db = install(monkeypatch)
    with q.user_scope("quin"):
        q.record_user_tokens(900)
    await drain()
    db.user_token_usage.docs[f"{q._today()}:quin"]["tokens"] = 500  # stale DB view

    assert await q.user_quota_refusal_async("quin") is None  # 900 < 1000, not refused
    assert q.tokens_used_today("quin") == 900  # max(local 900, remote 500), not 500

    with q.user_scope("quin"):
        q.record_user_tokens(100)  # local 1000; DB ends at 600 after the $inc
    await drain()
    assert db.user_token_usage.docs[f"{q._today()}:quin"]["tokens"] == 600
    assert await q.user_quota_refusal_async("quin") == q.REFUSAL_MESSAGE  # max(1000, 600)


# ── Sticky grants: revoke on one worker, honoured on another ─────────────────


async def test_revoke_on_worker_b_async_makes_worker_a_has_grant_async_false(monkeypatch):
    install(monkeypatch)
    a, b = GrantStore(), GrantStore()
    grant = _issue(a)
    await drain()
    assert await b.has_grant_async("s1", "shell", "run", "a1", "o1") is not None
    assert await b.revoke_grant_async(grant.grant_id) is not None
    await drain()
    assert await a.has_grant_async("s1", "shell", "run", "a1", "o1") is None


async def test_revoke_on_worker_b_sync_makes_worker_a_has_grant_async_false(monkeypatch):
    install(monkeypatch)
    a, b = GrantStore(), GrantStore()
    grant = _issue(a)
    await drain()
    assert await b.has_grant_async("s1", "shell", "run", "a1", "o1") is not None  # B holds it
    assert b.revoke(grant.grant_id) is True
    await drain()
    assert await a.has_grant_async("s1", "shell", "run", "a1", "o1") is None


async def test_grant_expired_in_db_but_live_in_worker_cache_is_no_grant(monkeypatch):
    db = install(monkeypatch)
    a = GrantStore()
    grant = _issue(a)
    await drain()
    db.governance_grants.docs[grant.grant_id]["expires_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    )
    assert a.has_grant("s1", "shell", "run", "a1", "o1") is not None  # cache still live
    assert await a.has_grant_async("s1", "shell", "run", "a1", "o1") is None
    assert a.has_grant("s1", "shell", "run", "a1", "o1") is None  # and evicted


async def test_db_rows_for_other_owner_agent_or_session_are_never_grants(monkeypatch):
    db = install(monkeypatch)
    rows = [
        _row("g_other_owner", owner="o2"),
        _row("g_other_agent", agent="a2"),
        _row("g_other_session", session="s9"),
        _row("g_other_scope", surface="shell", action="other-action"),
    ]
    # Bypass the query filter entirely: the in-code binding checks must still refuse.
    monkeypatch.setattr(db.governance_grants, "find",
                        lambda query, *a, **k: _Cursor([dict(r) for r in rows]))
    worker = GrantStore()
    assert await worker.has_grant_async("s1", "shell", "run", "a1", "o1") is None

    # Positive control: the same path does honour a row that really matches.
    rows.append(_row("g_match"))
    found = await worker.has_grant_async("s1", "shell", "run", "a1", "o1")
    assert found is not None and found.grant_id == "g_match"


# ── Offload: owner binding on the DB copy ────────────────────────────────────


async def test_offload_read_async_with_wrong_owner_is_not_found(monkeypatch):
    db = install(monkeypatch)
    ref = tos.ToolOutputStore().offload("private output " * 50, owner="run_a")
    await drain()
    worker_b = tos.ToolOutputStore()
    for wrong in ("run_b", None):
        res = await worker_b.read_async(ref, owner=wrong)
        assert res["ok"] is False
        assert res["error"].startswith("unknown or expired ref")
    assert (await worker_b.read_async(ref, owner="run_a"))["ok"] is True


async def test_offload_db_row_ignoring_owner_is_still_refused_in_code(monkeypatch):
    db = install(monkeypatch)
    ref = tos.ToolOutputStore().offload("private output " * 50, owner="run_a")
    await drain()
    col = db.tool_output_offload
    original = dict(col.docs[ref])

    async def find_one_ignoring_owner(query, *a, **k):
        return dict(original)

    monkeypatch.setattr(col, "find_one", find_one_ignoring_owner)
    worker_b = tos.ToolOutputStore()
    assert (await worker_b.read_async(ref, owner="run_b"))["ok"] is False
    assert (await worker_b.read_async(ref, owner="run_a"))["ok"] is True


# ── Secret redaction in the DB copy vs the in-memory copy ────────────────────

# Official AWS documentation example key, plus obviously fake vendor-shaped tokens.
_SECRET_SAMPLES = {
    "anthropic": "sk-ant-api03-AbCdEf0123456789XyZ_-abcdefgh",
    "github_ghp": "ghp_abcdefghijklmnopqrstuvwxyz0123456789",
    "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
}


@pytest.mark.parametrize("label", sorted(_SECRET_SAMPLES))
async def test_secret_is_redacted_in_db_copy_but_memory_copy_keeps_original(monkeypatch, label):
    secret = _SECRET_SAMPLES[label]
    db = install(monkeypatch)
    store = tos.ToolOutputStore()
    text = f"tool said: {secret} end"
    ref = store.offload(text, owner="run_a")
    await drain()
    stored = db.tool_output_offload.docs[ref]["text"]
    assert secret not in stored
    assert stored == redact_secrets(text)
    # Design: the same owner's in-memory copy is the unredacted original.
    assert store.read(ref, owner="run_a")["content"] == text


async def test_aws_secret_access_key_is_redacted_in_db_copy(monkeypatch):
    db = install(monkeypatch)
    secret_line = "aws_secret_access_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    ref = tos.ToolOutputStore().offload(f"env dump: {secret_line}", owner="run_a")
    await drain()
    assert "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" not in db.tool_output_offload.docs[ref]["text"]


# ── DB raising on every call: all three stores keep working in memory ────────


async def test_db_failing_on_every_call_leaves_all_three_stores_working(monkeypatch):
    db = install(monkeypatch)
    for name in _STATE_COLLECTIONS:
        col = getattr(db, name)
        col.fail = True
        col.index_fail = True

    with q.user_scope("uma"):
        q.record_user_tokens(300)
        q.ensure_user_within_quota()  # must not raise
    await drain()
    assert q.tokens_used_today("uma") == 300
    assert await q.user_quota_refusal_async("uma") is None
    with q.user_scope("uma"):
        q.record_user_tokens(800)
    assert await q.user_quota_refusal_async("uma") == q.REFUSAL_MESSAGE

    store = GrantStore()
    grant = _issue(store)
    await drain()
    assert grant is not None
    assert store.has_grant("s1", "shell", "run", "a1", "o1") is not None
    assert await store.has_grant_async("s1", "shell", "run", "a1", "o1") is not None
    assert await store.revoke_grant_async(grant.grant_id) is not None
    assert store.has_grant("s1", "shell", "run", "a1", "o1") is None

    offload = tos.ToolOutputStore()
    ref = offload.offload("line\n" * 2000, owner="run_a")
    await drain()
    assert ref is not None
    assert offload.read(ref, owner="run_a")["ok"] is True
    assert (await offload.read_async(ref, owner="run_a"))["ok"] is True
    assert (await offload.read_async("out_missing", owner="run_a"))["ok"] is False


# ── Flag toggled off mid-run: no further DB calls ────────────────────────────


def _calls(db: FakeDB) -> dict[str, list[str]]:
    return {name: list(getattr(db, name).calls) for name in _STATE_COLLECTIONS}


async def test_flag_toggled_off_mid_run_makes_no_further_db_calls(monkeypatch):
    db = install(monkeypatch)
    store = GrantStore()
    grant = _issue(store)
    with q.user_scope("vic"):
        q.record_user_tokens(100)
    ref = tos.ToolOutputStore().offload("abc" * 100, owner="run_a")
    await drain()
    assert _calls(db) != {name: [] for name in _STATE_COLLECTIONS}  # writes did happen
    before = _calls(db)

    monkeypatch.setattr(settings, "agency_state_persistence_enabled_raw", "false")
    with q.user_scope("vic"):
        q.record_user_tokens(200)
        q.ensure_user_within_quota()
    assert await q.user_quota_refusal_async("vic") is None  # 300 local tokens, cache only
    assert await store.has_grant_async("s1", "shell", "run", "a1", "o1") is not None
    assert await store.revoke_grant_async(grant.grant_id) is not None
    fresh = tos.ToolOutputStore()
    late_ref = fresh.offload("xyz" * 100, owner="run_a")
    assert late_ref is not None
    assert (await fresh.read_async(ref, owner="run_a"))["ok"] is False  # memory miss, no DB
    await drain()

    assert _calls(db) == before


# ── Huge entries never reach the DB ──────────────────────────────────────────


async def test_entry_over_two_million_chars_is_never_written_to_db(monkeypatch):
    db = install(monkeypatch)
    big = "a" * (tos.MAX_PERSIST_CHARS + 1)
    store = tos.ToolOutputStore()
    ref = store.offload(big, owner="run_a")
    await drain()
    assert ref is not None
    assert db._cols.get("tool_output_offload") is None  # collection never even touched
    assert store.read(ref, owner="run_a", limit=8000)["ok"] is True  # memory still serves it
    assert (await tos.ToolOutputStore().read_async(ref, owner="run_a"))["ok"] is False


async def test_entry_exactly_at_two_million_chars_is_written(monkeypatch):
    db = install(monkeypatch)
    ref = tos.ToolOutputStore().offload("b" * tos.MAX_PERSIST_CHARS, owner="run_a")
    await drain()
    assert len(db.tool_output_offload.docs[ref]["text"]) == tos.MAX_PERSIST_CHARS
