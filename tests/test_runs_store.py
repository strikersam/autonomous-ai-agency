"""RunStore (packages/runs/store.py) on memory, Mongo (real MongoStore over a fake) and SQLite."""
from __future__ import annotations

import pytest

from packages.lifecycle.machine import IllegalTransition
from packages.runs import store as store_mod
from packages.runs.models import RunRecord, RunState
from packages.runs.store import FencedOut, RunStore
from tests._runs_backends import BACKENDS, open_pair

# Built at runtime so no secret-shaped literal sits in the file; redact_secrets
# recognises the OpenAI style "sk-" prefix followed by 16+ characters.
FAKE_KEY = "sk-" + "Z9" * 12


@pytest.fixture(params=BACKENDS)
async def pair(request, tmp_path):
    async with open_pair(request.param, tmp_path) as (a, b):
        if a is None:
            shared = RunStore()
            yield shared, shared
        else:
            yield RunStore(a), RunStore(b)


async def test_create_is_insert_if_absent_and_get_round_trips(pair):
    s, other = pair
    run = RunRecord(company_id="c1", task_id="t1", owner_id="u1")
    stored = await s.create(run)
    assert stored.run_id == run.run_id
    again = await other.create(RunRecord(run_id=run.run_id, company_id="intruder"))
    assert again.company_id == "c1"
    fetched = await other.get(run.run_id)
    assert fetched is not None and fetched.state is RunState.CREATED
    assert isinstance(fetched.updated_at, float)
    assert await s.get("nope") is None


async def test_list_filters_by_company_state_parent_and_task(pair):
    s, _ = pair
    a = await s.create(RunRecord(company_id="c1", task_id="t1"))
    await s.create(RunRecord(company_id="c2", task_id="t2"))
    child = await s.create(RunRecord(company_id="c1", parent_run_id=a.run_id))
    await s.transition(a.run_id, RunState.QUEUED)
    assert {r.run_id for r in await s.list(company_id="c1")} == {a.run_id, child.run_id}
    assert [r.run_id for r in await s.list(company_id="c1", state=RunState.QUEUED)] == [a.run_id]
    assert [r.run_id for r in await s.list(parent_run_id=a.run_id)] == [child.run_id]
    assert [r.run_id for r in await s.list(task_id="t2")][0] != a.run_id


async def test_a_stale_token_cannot_update_the_run(pair):
    s, other = pair
    run = await s.create(RunRecord(company_id="c1", lease_token=1))
    # A recovering worker took the lease: token 2 is now current.
    assert await other.update(run.run_id, {"lease_token": 2}, token=1) is True
    assert await s.update(run.run_id, {"phase": "stale write"}, token=1) is False
    assert await other.update(run.run_id, {"phase": "fresh"}, token=2) is True
    assert (await s.get(run.run_id)).phase == "fresh"
    with pytest.raises(FencedOut):
        await s.transition(run.run_id, RunState.QUEUED, token=1)


async def test_transitions_follow_the_run_lifecycle_and_are_logged(pair):
    s, _ = pair
    run = await s.create(RunRecord(company_id="c1"))
    with pytest.raises(IllegalTransition):
        await s.transition(run.run_id, RunState.SUCCEEDED)
    for state in (RunState.QUEUED, RunState.STARTING, RunState.RUNNING, RunState.VERIFYING,
                  RunState.SUCCEEDED):
        moved = await s.transition(run.run_id, state, actor="worker")
        assert moved.state is state
    final = await s.get(run.run_id)
    assert final.is_terminal and final.started_at and final.completed_at
    kinds = [(e.kind, e.data.get("to")) for e in await s.list_events(run.run_id)]
    assert kinds[0] == ("created", None) and kinds[-1] == ("state_changed", "succeeded")
    with pytest.raises(KeyError):
        await s.transition("missing", RunState.QUEUED)


async def test_event_and_operation_seq_are_monotonic_across_attempts(pair):
    s, other = pair
    run = await s.create(RunRecord(company_id="c1"))
    first_attempt = [await s.next_op_seq(run.run_id) for _ in range(3)]
    await other.update(run.run_id, {"attempt": 2, "lease_token": 2})
    second_attempt = [await other.next_op_seq(run.run_id) for _ in range(2)]
    assert first_attempt + second_attempt == [1, 2, 3, 4, 5]
    seqs = [e.seq for e in await other.list_events(run.run_id)]
    assert seqs == sorted(set(seqs))
    assert [e.seq for e in await s.list_events(run.run_id, after_seq=1)] == seqs[1:]
    with pytest.raises(KeyError):
        await s.next_op_seq("missing")


async def test_idempotency_key_returns_one_run_per_company(pair):
    s, other = pair
    first, created = await s.get_or_create("c1", "k1", lambda: RunRecord(task_id="t"))
    again, created_again = await other.get_or_create("c1", "k1", lambda: RunRecord(task_id="t"))
    assert created is True and created_again is False
    assert again.run_id == first.run_id and again.idempotency_key == "k1"
    tenant2, created2 = await s.get_or_create("c2", "k1", lambda: RunRecord(task_id="t"))
    assert created2 is True and tenant2.run_id != first.run_id and tenant2.company_id == "c2"


async def test_an_expired_idempotency_key_binds_a_new_run(pair):
    s, _ = pair
    first, _ = await s.get_or_create("c1", "k1", RunRecord, ttl_s=-1)
    second, created = await s.get_or_create("c1", "k1", RunRecord)
    assert created is True and second.run_id != first.run_id


async def test_secrets_are_redacted_in_events_and_failure_reasons(pair):
    s, other = pair
    run = await s.create(RunRecord(company_id="c1", failure_reason=f"boom {FAKE_KEY}"))
    await s.append_event(run.run_id, "tool_call", {"args": {"auth": f"Bearer {FAKE_KEY}"},
                                                   "lines": [f"key={FAKE_KEY}"]})
    await other.update(run.run_id, {"failure_reason": f"again {FAKE_KEY}"})
    stored = await other.get(run.run_id)
    events = await other.list_events(run.run_id)
    blob = repr(stored.model_dump()) + repr([e.model_dump() for e in events])
    assert FAKE_KEY not in blob
    assert "again" in stored.failure_reason


async def test_mongo_indexes_are_created_once_with_uniqueness(tmp_path):
    async with open_pair("mongo", tmp_path) as (db, _):
        s = RunStore(db)
        await s.create(RunRecord(company_id="c1"))
        raw = db._get_db()
        unique = {name for name in ("run_events", "run_operations", "run_idempotency")
                  if any(kw.get("unique") for _, kw in raw[name].indexes)}
        assert unique == {"run_events", "run_operations", "run_idempotency"}
        assert any("expireAfterSeconds" in kw for _, kw in raw["run_idempotency"].indexes)


def test_get_run_store_is_memory_under_tests_and_resettable(monkeypatch):
    monkeypatch.setattr(store_mod, "_store", None)
    first = store_mod.get_run_store()
    assert first.backend == "memory" and store_mod.get_run_store() is first
    store_mod.set_run_store(None)
    assert store_mod.get_run_store() is not first
