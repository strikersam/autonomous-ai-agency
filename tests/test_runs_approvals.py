"""Durable run approvals and the release gate (plan phase 5, decision D2)."""
from __future__ import annotations

import asyncio

import pytest

from agent.action_hash import action_hash
from packages.config import control_overrides
from packages.runs.approvals import ApprovalError, ApprovalState, RunApprovals
from packages.runs.models import RunRecord
from packages.runs.side_effects import ReleaseNotApproved, require_release_approval
from packages.runs.store import RunStore
from tests._runs_backends import BACKENDS, SHARED_BACKENDS, open_pair

SECRET = "sk-" + "a1B2c3D4e5" * 4
HASH = action_hash("deploy", {"env": "prod", "sha": "abc"})
TARGET = {"env": "prod", "service": "api"}


@pytest.fixture(autouse=True)
def _controls():
    control_overrides.apply_overrides({})
    yield
    control_overrides.apply_overrides({})


async def _run(runs: RunStore) -> str:
    return (await runs.create(RunRecord(owner_id="alice"))).run_id


@pytest.mark.parametrize("kind", SHARED_BACKENDS)
def test_approval_survives_a_new_store_instance(kind, tmp_path):
    async def go():
        async with open_pair(kind, tmp_path) as (a, b):
            first = RunStore(a)
            rid = await _run(first)
            aid = await RunApprovals(first).request(rid, HASH, TARGET, "ship it")
            await RunApprovals(first).decide(aid, True, "priya@example.com")
            later = RunApprovals(RunStore(b))  # another process over the same database
            assert await later.check(rid, HASH, TARGET) is True
            rec = await later.get(aid)
            assert rec.state is ApprovalState.APPROVED and rec.resolver == "priya@example.com"
    asyncio.run(go())


@pytest.mark.parametrize("kind", BACKENDS)
def test_only_the_same_action_and_target_is_approved(kind, tmp_path):
    async def go():
        async with open_pair(kind, tmp_path) as (db, _):
            runs = RunStore(db)
            rid, other = await _run(runs), await _run(runs)
            ap = RunApprovals(runs)
            assert await ap.check(rid, HASH, TARGET) is False  # nothing requested
            aid = await ap.request(rid, HASH, TARGET, "r")
            assert await ap.check(rid, HASH, TARGET) is False  # pending is not approved
            await ap.decide(aid, True, "priya")
            assert await ap.check(rid, HASH, TARGET) is True
            assert await ap.check(rid, HASH, {"target": 1}) is False
            assert await ap.check(rid, HASH, {**TARGET, "env": "staging"}) is False
            assert await ap.check(rid, action_hash("deploy", {"env": "prod", "sha": "def"}), TARGET) is False
            assert await ap.check(other, HASH, TARGET) is False
            assert await ap.check(rid, HASH, dict(reversed(list(TARGET.items())))) is True
    asyncio.run(go())


def test_denied_and_expired_approvals_deny(monkeypatch):
    async def go():
        runs = RunStore()
        rid = await _run(runs)
        ap = RunApprovals(runs)
        denied = await ap.request(rid, HASH, TARGET, "r")
        await ap.decide(denied, False, "priya")
        assert await ap.check(rid, HASH, TARGET) is False
        with pytest.raises(ApprovalError):
            await ap.decide(denied, True, "priya")  # already decided

        import packages.runs.approvals as mod
        aid = await ap.request(rid, HASH, TARGET, "r", ttl_s=60)
        real = mod.time.time()
        monkeypatch.setattr(mod.time, "time", lambda: real + 120)
        with pytest.raises(ApprovalError):
            await ap.decide(aid, True, "priya")  # too late: expiry denies
        assert (await ap.get(aid)).state is ApprovalState.EXPIRED
        assert await ap.check(rid, HASH, TARGET) is False
    asyncio.run(go())


def test_an_approved_record_stops_authorising_after_its_expiry(monkeypatch):
    async def go():
        runs = RunStore()
        rid = await _run(runs)
        ap = RunApprovals(runs)
        aid = await ap.request(rid, HASH, TARGET, "r", ttl_s=60)
        await ap.decide(aid, True, "priya")
        assert await ap.check(rid, HASH, TARGET) is True
        import packages.runs.approvals as mod
        real = mod.time.time()
        monkeypatch.setattr(mod.time, "time", lambda: real + 61)
        assert await ap.check(rid, HASH, TARGET) is False
    asyncio.run(go())


def test_a_named_resolver_and_a_known_run_are_required():
    async def go():
        runs = RunStore()
        rid = await _run(runs)
        ap = RunApprovals(runs)
        aid = await ap.request(rid, HASH, TARGET, "r")
        for bad in ("", "   "):
            with pytest.raises(ApprovalError):
                await ap.decide(aid, True, bad)
        with pytest.raises(KeyError):
            await ap.decide("apr_missing", True, "priya")
        with pytest.raises(KeyError):
            await ap.request("run_missing", HASH, TARGET, "r")
        with pytest.raises(ApprovalError):
            await ap.request(rid, "", TARGET, "r")
    asyncio.run(go())


def test_secrets_in_reason_target_and_note_are_not_stored():
    async def go():
        runs = RunStore()
        rid = await _run(runs)
        ap = RunApprovals(runs)
        aid = await ap.request(rid, HASH, {"url": f"https://x/{SECRET}", "token": SECRET}, f"why {SECRET}")
        await ap.decide(aid, True, "priya", note=f"ok {SECRET}")
        stored = repr(runs.table("run_approvals").docs[aid])
        events = repr([e.model_dump() for e in await runs.list_events(rid)])
        assert SECRET not in stored and SECRET not in events
        # The match still works on the real target, which is never stored.
        assert await ap.check(rid, HASH, {"url": f"https://x/{SECRET}", "token": SECRET}) is True
    asyncio.run(go())


def test_release_is_blocked_without_approval_and_allowed_with_it():
    async def go():
        runs = RunStore()
        rid = await _run(runs)
        args = {"env": "prod", "sha": "abc"}
        with pytest.raises(ReleaseNotApproved):
            await require_release_approval(rid, "deploy", args, TARGET, store=runs)
        ap = RunApprovals(runs)
        aid = await ap.request(rid, action_hash("deploy", args), TARGET, "go")
        with pytest.raises(ReleaseNotApproved):  # still pending
            await require_release_approval(rid, "deploy", args, TARGET, store=runs)
        await ap.decide(aid, True, "priya")
        assert await require_release_approval(rid, "deploy", args, TARGET, store=runs) == action_hash("deploy", args)
        with pytest.raises(ReleaseNotApproved):  # changed arguments
            await require_release_approval(rid, "deploy", {**args, "sha": "evil"}, TARGET, store=runs)
        with pytest.raises(ReleaseNotApproved):  # changed target
            await require_release_approval(rid, "deploy", args, {**TARGET, "env": "other"}, store=runs)
    asyncio.run(go())


def test_the_off_switch_blocks_every_release():
    async def go():
        runs = RunStore()
        rid = await _run(runs)
        ap = RunApprovals(runs)
        await ap.decide(await ap.request(rid, HASH, TARGET, "r"), True, "priya")
        assert await ap.check(rid, HASH, TARGET) is True
        control_overrides.apply_overrides({"RUNS_DURABLE_APPROVALS": "false"})
        assert await ap.check(rid, HASH, TARGET) is False
    asyncio.run(go())


def test_a_deploy_inside_a_run_needs_a_durable_approval():
    """Scenario 24 on a real release path: Render trigger_deploy inside a bound run."""
    from types import SimpleNamespace

    from packages.runs.store import set_run_store
    from packages.runs.task_binding import current_run
    from tests.test_render_mcp import _client

    async def go():
        runs = RunStore()
        set_run_store(runs)
        rid = await _run(runs)
        client, inner = _client({"ok": True}, allow_writes=True)
        token = current_run.set(SimpleNamespace(run_id=rid, watch_run_id=None))
        try:
            with pytest.raises(ReleaseNotApproved):
                await client.trigger_deploy("srv-1")
            assert inner.calls == []
            args = {"serviceId": "srv-1", "clearCache": False}
            ap = RunApprovals(runs)
            aid = await ap.request(rid, action_hash("render.trigger_deploy", args),
                                   {"service_id": "srv-1"}, "ship")
            await ap.decide(aid, True, "priya")
            await client.trigger_deploy("srv-1")
            assert inner.calls[0][0] == "trigger_deploy"
            with pytest.raises(ReleaseNotApproved):  # another service is not covered
                await client.trigger_deploy("srv-2")
        finally:
            current_run.reset(token)
            set_run_store(None)
    asyncio.run(go())


def test_a_dash_or_underscore_prefixed_jwt_is_redacted():
    from packages.runs.redaction import redact_text

    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefSIGNATURE123"
    for text in (f"agent-{jwt}", f"x_{jwt}", f"plain {jwt}", f"abc{jwt}", f"1{jwt}"):
        assert jwt not in redact_text(text)


def test_a_decision_that_crosses_the_expiry_is_not_approved(monkeypatch):
    """The request expires between the read and the write of the decision."""
    async def go():
        import packages.runs.approvals as mod

        runs = RunStore()
        rid = await _run(runs)
        ap = RunApprovals(runs)
        aid = await ap.request(rid, HASH, TARGET, "r", ttl_s=60)
        real_get, base = ap.get, mod.time.time()

        async def get_then_expire(approval_id):
            rec = await real_get(approval_id)
            monkeypatch.setattr(mod.time, "time", lambda: base + 120)  # expires now
            return rec

        monkeypatch.setattr(ap, "get", get_then_expire)
        with pytest.raises(ApprovalError):
            await ap.decide(aid, True, "priya")
        monkeypatch.setattr(ap, "get", real_get)
        assert (await ap.get(aid)).state is not ApprovalState.APPROVED
        assert await ap.check(rid, HASH, TARGET) is False
    asyncio.run(go())


def test_an_approval_written_after_its_expiry_is_reported_expired():
    """A crash between the approve write and the expire write in decide leaves this record."""
    async def go():
        runs = RunStore()
        rid = await _run(runs)
        ap = RunApprovals(runs)
        aid = await ap.request(rid, HASH, TARGET, "r", ttl_s=60)
        rec = await ap.get(aid)
        await runs.table("run_approvals").compare_and_set(
            aid, {"state": "pending"},
            {"state": "approved", "resolver": "priya", "resolved_at": rec.expires_at + 1})
        assert (await ap.get(aid)).state is ApprovalState.EXPIRED
    asyncio.run(go())


def test_check_reads_the_clock_after_the_lookup(monkeypatch):
    async def go():
        import packages.runs.approvals as mod

        runs = RunStore()
        rid = await _run(runs)
        ap = RunApprovals(runs)
        aid = await ap.request(rid, HASH, TARGET, "r", ttl_s=60)
        await ap.decide(aid, True, "priya")
        base, table = mod.time.time(), runs.table("run_approvals")
        real_find = table.find

        async def slow_find(*a, **k):
            docs = await real_find(*a, **k)
            monkeypatch.setattr(mod.time, "time", lambda: base + 120)  # expired during the query
            return docs

        monkeypatch.setattr(table, "find", slow_find)
        monkeypatch.setattr(ap, "_table", table)
        assert await ap.check(rid, HASH, TARGET) is False
    asyncio.run(go())
