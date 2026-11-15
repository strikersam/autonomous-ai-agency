"""The side effect ledger (packages/runs/operations.py): begin, commit, fence, reconcile, replay."""
from __future__ import annotations

import pytest

from packages.runs import operations as ops_mod
from packages.runs.models import OperationState, RunRecord
from packages.runs.operations import (
    DONE, NOT_DONE, NOT_STARTED, UNKNOWN, OperationLedger, register_reconciler,
)
from packages.runs.store import FencedOut, RunStore
from tests._runs_backends import BACKENDS, open_pair

FAKE_KEY = "sk-" + "Q7" * 12
NOW = 10_000.0


@pytest.fixture(autouse=True)
def _clean_registry(monkeypatch):
    monkeypatch.setattr(ops_mod, "_RECONCILERS", {})
    monkeypatch.setenv("RUNS_OP_SKEW_SEC", "30")


@pytest.fixture(params=BACKENDS)
async def ledger(request, tmp_path):
    async with open_pair(request.param, tmp_path) as (db, _):
        store = RunStore(db)
        run = await store.create(RunRecord(company_id="c1", lease_token=1))
        yield OperationLedger(store), store, run.run_id


async def _states(ledger: OperationLedger, run_id: str) -> list[str]:
    return [op.state.value for op in await ledger.list(run_id)]


async def test_begin_moves_to_executing_with_a_skewed_deadline_then_commits(ledger):
    led, _, run_id = ledger
    op = await led.begin(run_id, "git_push", {"branch": "agent/task-1"}, {"repo": "o/r"}, 1, 60,
                         lease_remaining_s=120, now=NOW)
    assert op.op_id == f"{run_id}:1" and op.seq == 1
    assert op.state is OperationState.EXECUTING and op.op_deadline == NOW + 60 + 30
    assert await led.commit(op, "sha:abc") is True
    assert await led.commit(op, "twice") is False
    assert await _states(led, run_id) == ["committed"]


async def test_begin_refuses_when_the_lease_cannot_outlast_the_operation(ledger):
    led, _, run_id = ledger
    with pytest.raises(FencedOut):
        await led.begin(run_id, "git_push", {}, {}, 1, 60, lease_remaining_s=60)
    assert await led.list(run_id) == []


async def test_a_stale_token_is_fenced_out_and_the_effect_never_starts(ledger):
    led, store, run_id = ledger
    assert await store.update(run_id, {"lease_token": 2}, token=1)
    with pytest.raises(FencedOut):
        await led.begin(run_id, "git_push", {}, {}, 1, 60, lease_remaining_s=120, now=NOW)
    assert await _states(led, run_id) == ["failed"]


async def test_seq_is_never_reused_across_attempts(ledger):
    led, store, run_id = ledger
    first = await led.begin(run_id, "send", {"to": "a"}, {}, 1, 10, lease_remaining_s=60, now=NOW)
    await store.update(run_id, {"lease_token": 2, "attempt": 2})
    second = await led.begin(run_id, "send", {"to": "a"}, {}, 2, 10, lease_remaining_s=60, now=NOW)
    assert (first.seq, second.seq) == (1, 2) and first.action_hash == second.action_hash


async def test_recovery_fails_pending_records_without_parking(ledger):
    led, _, run_id = ledger
    # A record left pending: the worker died between the insert and the move to executing.
    pending = await led.begin(run_id, "send", {}, {}, 1, 10, lease_remaining_s=60, now=NOW)
    await led._ops.compare_and_set(pending.op_id, {}, {"state": "pending"})
    result = await led.reconcile_run(run_id, now=NOW + 1)
    assert [o.outcome for o in result.outcomes] == [NOT_STARTED] and not result.must_park
    assert await _states(led, run_id) == ["failed"]


async def test_executing_before_its_deadline_is_unknown_and_parks(ledger):
    led, _, run_id = ledger
    register_reconciler("git_push", lambda op: DONE, repeat_safe=True)
    await led.begin(run_id, "git_push", {}, {}, 1, 60, lease_remaining_s=120, now=NOW)
    result = await led.reconcile_run(run_id, now=NOW + 60)  # inside the 30 s skew
    assert [o.outcome for o in result.outcomes] == [UNKNOWN] and result.must_park
    assert await _states(led, run_id) == ["executing"]


async def test_after_the_deadline_a_repeat_safe_reconciler_may_say_not_done(ledger):
    led, _, run_id = ledger
    register_reconciler("git_push", lambda op: NOT_DONE, repeat_safe=True)
    await led.begin(run_id, "git_push", {}, {}, 1, 60, lease_remaining_s=120, now=NOW)
    result = await led.reconcile_run(run_id, now=NOW + 91)
    assert [o.outcome for o in result.outcomes] == [NOT_DONE] and not result.must_park
    assert await _states(led, run_id) == ["failed"]


async def test_not_done_from_a_non_repeat_safe_reconciler_stays_unknown(ledger):
    led, _, run_id = ledger

    async def says_not_done(op):
        return NOT_DONE

    register_reconciler("send_email", says_not_done)
    await led.begin(run_id, "send_email", {}, {}, 1, 60, lease_remaining_s=120, now=NOW)
    result = await led.reconcile_run(run_id, now=NOW + 1000)
    assert [o.outcome for o in result.outcomes] == [UNKNOWN] and result.must_park
    assert await _states(led, run_id) == ["executing"]


async def test_done_commits_and_missing_or_broken_reconcilers_are_unknown(ledger):
    led, _, run_id = ledger
    register_reconciler("pr_create", lambda op: DONE)

    def broken(op):
        raise RuntimeError("github down")

    register_reconciler("comment", broken)
    for tool in ("pr_create", "comment", "no_reconciler"):
        await led.begin(run_id, tool, {}, {}, 1, 60, lease_remaining_s=120, now=NOW)
    result = await led.reconcile_run(run_id, now=NOW + 1000)
    assert {o.tool: o.outcome for o in result.outcomes} == {
        "pr_create": DONE, "comment": UNKNOWN, "no_reconciler": UNKNOWN,
    }
    assert await _states(led, run_id) == ["committed", "executing", "executing"]


async def test_replay_skips_the_kth_call_only_when_k_copies_committed(ledger):
    led, _, run_id = ledger
    args = {"to": "ops@example.com", "body": "hi"}
    for _ in range(2):
        op = await led.begin(run_id, "send", args, {}, 1, 10, lease_remaining_s=60, now=NOW)
        await led.commit(op)
    failed = await led.begin(run_id, "send", args, {}, 1, 10, lease_remaining_s=60, now=NOW)
    await led.fail(failed, "smtp refused")
    assert await led.should_skip_replay(run_id, "send", args, 1) is True
    assert await led.should_skip_replay(run_id, "send", args, 2) is True
    assert await led.should_skip_replay(run_id, "send", args, 3) is False
    assert await led.should_skip_replay(run_id, "send", {"to": "other"}, 1) is False


async def test_targets_and_errors_are_redacted(ledger):
    led, _, run_id = ledger
    op = await led.begin(run_id, "http", {}, {"url": f"https://x/?k={FAKE_KEY}", "h": FAKE_KEY},
                         1, 10, lease_remaining_s=60, now=NOW)
    await led.fail(op, f"401 for token {FAKE_KEY}")
    blob = repr([o.model_dump() for o in await led.list(run_id)])
    assert FAKE_KEY not in blob


def test_ledger_flag_follows_the_live_control(monkeypatch):
    assert ops_mod.ledger_enabled() is True
    monkeypatch.setenv("RUNS_LEDGER_ENABLED", "false")
    assert ops_mod.ledger_enabled() is False
