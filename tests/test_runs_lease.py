"""The one run lease (packages/runs/lease.py): fencing tokens, expiry, renewal, heartbeat,
and the task claim that delegates to it (tasks/run_lease.py)."""
from __future__ import annotations

import asyncio

import pytest

from packages.runs.lease import LeaseHeartbeat, RunLease, remaining_s, run_lease_key
from tasks import run_lease as claims
from tasks.store import TaskStore
from tests._runs_backends import BACKENDS, SHARED_BACKENDS, open_pair


@pytest.fixture(autouse=True)
def _clean_local_claims(monkeypatch):
    monkeypatch.setattr(claims, "_local_claims", {})


@pytest.fixture(params=BACKENDS)
async def pair(request, tmp_path):
    async with open_pair(request.param, tmp_path) as (a, b):
        if a is None:
            shared = RunLease()
            yield shared, shared
        else:
            yield RunLease(a), RunLease(b)


async def test_one_holder_at_a_time_and_tokens_only_grow(pair):
    web, worker = pair
    assert await web.acquire("t1", "web", 60, now=1000) == 1
    assert await worker.acquire("t1", "worker", 60, now=1001) is None
    assert await web.release("t1", "worker") is False  # not the holder
    assert await web.release("t1", "web", 1) is True
    assert await worker.acquire("t1", "worker", 60, now=1002) == 2
    doc = await web.current("t1")
    assert doc["holder"] == "worker" and doc["token"] == 2


async def test_expiry_lets_another_holder_in_with_a_higher_token(pair):
    web, worker = pair
    assert await web.acquire("t1", "crashed", 60, run_id="r1", now=1000) == 1
    assert await worker.acquire("t1", "worker", 60, run_id="r1", now=1061) == 2
    assert await web.renew("t1", "crashed", 1, 60, now=1062) is False
    assert await web.acquire("t1", "crashed", 60, now=1062) is None


async def test_renewal_keeps_a_long_run_alive(pair):
    web, worker = pair
    token = await web.acquire("t1", "web", 10, now=1000)
    for step in range(1, 10):  # 90 s of work in 8 s renewals
        assert await web.renew("t1", "web", token, 10, now=1000 + 8 * step) is True
    assert await worker.acquire("t1", "worker", 10, now=1075) is None
    assert remaining_s(await web.current("t1"), now=1075) > 0


async def test_the_same_holder_reacquires_with_a_new_token(pair):
    web, _ = pair
    assert await web.acquire("t1", "web", 60, now=1000) == 1
    assert await web.acquire("t1", "web", 60, now=1001) == 2
    assert await web.renew("t1", "web", 1, 60, now=1002) is False


@pytest.mark.parametrize("kind", SHARED_BACKENDS)
async def test_two_processes_racing_get_exactly_one_token(kind, tmp_path):
    async with open_pair(kind, tmp_path) as (a, b):
        leases = [RunLease(a), RunLease(b)]
        tokens = await asyncio.gather(*(
            leases[i % 2].acquire("t1", f"proc-{i}", 60) for i in range(10)
        ))
    assert [t for t in tokens if t is not None] == [1]


@pytest.mark.parametrize("kind", SHARED_BACKENDS)
async def test_a_lease_written_by_the_old_code_is_taken_over_after_expiry(kind, tmp_path):
    async with open_pair(kind, tmp_path) as (a, _):
        lease = RunLease(a)
        # Pre fencing documents had no token and were keyed the same way.
        await lease._table.insert_if_absent("t1", {"holder": "old", "expires_at": 1000.0})
        assert await lease.acquire("t1", "new", 60, now=999) is None
        assert await lease.acquire("t1", "new", 60, now=1001) == 1


def test_run_keys_do_not_collide_with_task_ids():
    assert run_lease_key("abc") == "run:abc"


async def test_heartbeat_renews_until_stopped():
    lease = RunLease()
    token = await lease.acquire("t1", "web", 0.2)
    beat = LeaseHeartbeat(lease, "t1", "web", token, ttl_s=0.2, renew_s=0.02)
    beat.start()
    await asyncio.sleep(0.5)
    assert not beat.lost.is_set()
    assert await lease.acquire("t1", "other", 0.2) is None
    await beat.stop()


async def test_heartbeat_reports_a_lost_lease():
    lease = RunLease()
    token = await lease.acquire("t1", "web", 60, now=0)
    assert await lease.acquire("t1", "thief", 60, now=100) == token + 1
    beat = LeaseHeartbeat(lease, "t1", "web", token, ttl_s=60, renew_s=0.01)
    beat.start()
    await asyncio.wait_for(beat.lost.wait(), timeout=2)
    await beat.stop()


async def test_heartbeat_never_raises_and_gives_up_after_a_ttl_of_errors():
    class _Down(RunLease):
        async def renew(self, *args, **kwargs):
            raise RuntimeError("db down")

    ticks = iter(range(1000))
    beat = LeaseHeartbeat(_Down(), "t1", "web", 1, ttl_s=3, renew_s=0.001,
                          clock=lambda: float(next(ticks)))
    beat.start()
    await asyncio.wait_for(beat.lost.wait(), timeout=2)
    await beat.stop()


async def test_heartbeat_reads_its_defaults_from_the_live_controls(monkeypatch):
    monkeypatch.setenv("RUNS_LEASE_TTL_SEC", "90")
    monkeypatch.setenv("RUNS_LEASE_RENEW_SEC", "20")
    beat = LeaseHeartbeat(RunLease(), "t1", "web", 1)
    assert (beat._ttl_s, beat._renew_s) == (90.0, 20.0)


# ── TaskStore and the task claim delegate to the one lease ───────────────────


@pytest.mark.parametrize("kind", SHARED_BACKENDS)
async def test_task_claim_uses_the_durable_lease_and_skips_shared_state(kind, tmp_path, monkeypatch):
    async def _no_shared_state(*args, **kwargs):
        raise AssertionError("shared_state must not be used with a durable lease")

    monkeypatch.setattr(claims, "_shared_claim", _no_shared_state)
    monkeypatch.setattr(claims, "_shared_release", _no_shared_state)
    async with open_pair(kind, tmp_path) as (a, b):
        web, worker = TaskStore(db=a), TaskStore(db=b)
        assert web.has_durable_run_lease and worker.has_durable_run_lease
        assert await claims.claim_task_run_token(web, "t1", run_id="r1") == 1
        # A sibling coroutine in this process is refused even with the same holder id.
        assert await claims.claim_task_run(web, "t1") is False
        await claims.release_task_run(web, "t1")
        monkeypatch.setattr(claims, "_RUN_LEASE_HOLDER", "worker-process")
        assert await claims.claim_task_run_token(worker, "t1") == 2
        assert await web.renew_run_lease("t1", "worker-process", 2, 60) is True


async def test_memory_task_store_keeps_the_process_lock():
    store = TaskStore()
    assert store.has_durable_run_lease is False
    assert await claims.claim_task_run_token(store, "t-mem") == 0
    assert await claims.claim_task_run(store, "t-mem") is False
    await claims.release_task_run(store, "t-mem")
    assert await claims.claim_task_run(store, "t-mem") is True
    await claims.release_task_run(store, "t-mem")
