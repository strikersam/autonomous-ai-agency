"""tests/test_runs_api.py — the /api/runs surface (reliability plan, phase 3)."""
from __future__ import annotations

import asyncio
import time

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from packages.runs import task_binding
from packages.runs.models import RunRecord, RunState
from packages.runs.store import RunStore, set_run_store
from tasks import store as task_store_mod
from tasks.models import TaskStatus
from tasks.store import TaskStore

ALICE = {"_id": "alice", "email": "alice@example.com", "role": "user"}
BOB = {"_id": "bob", "email": "bob@example.com", "role": "user"}
SECRET = "sk-" + "a1B2c3D4e5" * 4
JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefSIGNATURE123"


@pytest.fixture
def env(monkeypatch):
    from backend.server import app, get_current_user

    runs, tasks = RunStore(), TaskStore()
    set_run_store(runs)
    monkeypatch.setattr(task_store_mod, "_global_store", tasks)
    holder = {"user": ALICE}

    def _user():
        if holder["user"] is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return holder["user"]

    app.dependency_overrides[get_current_user] = _user
    c = TestClient(app, raise_server_exceptions=False)
    c.holder, c.runs, c.tasks = holder, runs, tasks
    yield c
    app.dependency_overrides.clear()
    set_run_store(None)


def _create(c, **body):
    body.setdefault("title", "t")
    return c.post("/api/runs", json=body)


def _seed(c, state, **kw):
    run = RunRecord(owner_id="alice", state=state, task_id=kw.pop("task_id", None), **kw)
    asyncio.run(c.runs.create(run))
    return run.run_id


def test_create_returns_queued_run_and_task(env):
    r = _create(env, title="Report", description="do it")
    assert r.status_code == 201
    j = r.json()
    assert j["state"] == "queued" and j["created"] is True and j["run_id"].startswith("run_")
    task = asyncio.run(env.tasks.get(j["task_id"]))
    assert task.current_run_id == j["run_id"] and task.pending_agent_run is True


def test_same_idempotency_key_same_run_no_second_task(env):
    h = {"Idempotency-Key": "k1"}
    a = env.post("/api/runs", json={"title": "t"}, headers=h)
    b = env.post("/api/runs", json={"title": "t"}, headers=h)
    assert (a.status_code, b.status_code) == (201, 200)
    assert a.json()["run_id"] == b.json()["run_id"] and b.json()["created"] is False
    assert len(asyncio.run(env.tasks.list_all())) == 1


def test_other_owner_gets_404_everywhere(env):
    rid = _create(env).json()["run_id"]
    env.holder["user"] = BOB
    assert env.get(f"/api/runs/{rid}").status_code == 404
    assert env.get(f"/api/runs/{rid}/events").status_code == 404
    assert env.get(f"/api/runs/{rid}/artifacts").status_code == 404
    assert env.post(f"/api/runs/{rid}/cancel").status_code == 404
    assert env.post(f"/api/runs/{rid}/retry").status_code == 404
    assert env.get("/api/runs").json()["runs"] == []
    assert _create(env, title="x", parent_run_id=rid).status_code == 404
    env.holder["user"] = {"_id": "root", "role": "admin"}
    assert env.get(f"/api/runs/{rid}").status_code == 200


def test_unauthenticated_is_401(env):
    env.holder["user"] = None
    for method, path in (("get", "/api/runs"), ("post", "/api/runs"), ("get", "/api/runs/capabilities")):
        assert getattr(env, method)(path).status_code == 401


def test_unauthenticated_without_override_is_401():
    from backend.server import app

    c = TestClient(app, raise_server_exceptions=False)
    assert c.get("/api/runs/capabilities").status_code == 401


def test_get_run_hides_lease_token(env):
    rid = _seed(env, RunState.RUNNING, lease_token=7)
    body = env.get(f"/api/runs/{rid}").json()
    assert "lease_token" not in body and body["state"] == "running"


def test_events_pagination(env):
    rid = _create(env).json()["run_id"]
    for i in range(4):
        asyncio.run(env.runs.append_event(rid, "step", {"i": i}))
    first = env.get(f"/api/runs/{rid}/events?limit=2").json()
    assert [e["seq"] for e in first["events"]] == [1, 2]
    rest = env.get(f"/api/runs/{rid}/events?after_seq={first['next_after_seq']}").json()
    seqs = [e["seq"] for e in rest["events"]]
    assert seqs == sorted(seqs) and seqs[0] == 3 and len(seqs) == 4


def test_list_filters_and_artifacts(env):
    rid = _create(env).json()["run_id"]
    assert [r["run_id"] for r in env.get("/api/runs?state=queued").json()["runs"]] == [rid]
    assert env.get("/api/runs?state=failed").json()["runs"] == []
    assert env.get("/api/runs?state=bogus").status_code == 422
    assert env.get(f"/api/runs/{rid}/artifacts").json() == {"run_id": rid, "artifacts": []}


def test_cancel_queued_then_409(env):
    j = _create(env).json()
    r = env.post(f"/api/runs/{j['run_id']}/cancel")
    assert r.status_code == 200 and r.json()["state"] == "cancelled" and r.json()["settled"]
    assert asyncio.run(env.tasks.get(j["task_id"])).status is TaskStatus.WONT_DO
    assert env.post(f"/api/runs/{j['run_id']}/cancel").status_code == 409


def test_cancel_running_sets_flag_only(env):
    rid = _seed(env, RunState.RUNNING)
    r = env.post(f"/api/runs/{rid}/cancel").json()
    assert r["state"] == "running" and r["cancel_requested"] and not r["settled"]
    assert asyncio.run(env.runs.get(rid)).cancel_requested is True


def test_retry_failed_creates_new_run(env):
    j = _create(env).json()
    asyncio.run(env.runs.transition(j["run_id"], RunState.FAILED, reason="boom"))
    r = env.post(f"/api/runs/{j['run_id']}/retry")
    assert r.status_code == 201 and r.json()["run_id"] != j["run_id"]
    new = asyncio.run(env.runs.get(r.json()["run_id"]))
    assert new.retry_of == j["run_id"] and new.attempt == 1 and new.state is RunState.QUEUED
    task = asyncio.run(env.tasks.get(j["task_id"]))
    assert task.current_run_id == new.run_id and task.pending_agent_run
    assert env.post(f"/api/runs/{j['run_id']}/retry").status_code == 409  # a newer run is active


def test_retry_running_is_409(env):
    j = _create(env).json()
    asyncio.run(env.runs.transition(j["run_id"], RunState.STARTING))
    asyncio.run(env.runs.transition(j["run_id"], RunState.RUNNING))
    assert env.post(f"/api/runs/{j['run_id']}/retry").status_code == 409


def test_capabilities_shape(env):
    j = env.get("/api/runs/capabilities")
    assert j.status_code == 200
    body = j.json()
    assert set(body) == {"backend", "durable_lease", "recovery", "recovery_enabled",
                         "ledger_enabled", "checkpoint_durable"}
    assert body["backend"] == "memory" and body["recovery"] == "none"
    assert body["durable_lease"] is False and isinstance(body["checkpoint_durable"], bool)


def test_secrets_in_request_never_reach_events(env):
    r = _create(env, title=f"use {SECRET}", description=f"token {SECRET} and {JWT}")
    rid = r.json()["run_id"]
    text = env.get(f"/api/runs/{rid}/events").text + env.get(f"/api/runs/{rid}").text
    assert SECRET not in text and JWT not in text and "api_created" in text


@pytest.mark.anyio
async def test_binding_tick_observes_cancel_request():
    store = RunStore()
    run = await store.create(RunRecord(state=RunState.RUNNING))

    class _B:
        recording = True
        cancel = asyncio.Event()
        run_id = run.run_id

    _B.store = store
    await task_binding._poll_cancel(_B)  # type: ignore[arg-type]
    assert not _B.cancel.is_set()
    await store.update(run.run_id, {"cancel_requested": True})
    await task_binding._poll_cancel(_B)  # type: ignore[arg-type]
    assert _B.cancel.is_set()


@pytest.mark.anyio
async def test_guard_raises_run_cancelled():
    class _HB:
        lost = asyncio.Event()

    class _B:
        task_id = "t"
        cancel = asyncio.Event()
        heartbeat = _HB()
        fenced = False

    _B.cancel.set()
    with pytest.raises(task_binding.RunCancelled):
        await task_binding.guard(_B, asyncio.sleep(30))  # type: ignore[arg-type]


def _gather_posts(env, n, path_fn, **kw):
    """Fire *n* concurrent requests at the app on one event loop (stores yield mid write)."""
    import httpx

    from backend.server import app

    real_create = env.runs.create

    calls = []

    async def slow_create(run):
        calls.append(run.run_id)
        # A yield point, as a networked store has; the first writer stalls longest so a
        # second request finds the key bound but the run missing and stores its own.
        await asyncio.sleep(0.2 if len(calls) == 1 else 0.01)
        return await real_create(run)

    env.runs.create = slow_create

    async def _go():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            return await asyncio.gather(*(c.post(path_fn(i), **kw) for i in range(n)))

    return asyncio.run(_go())


def test_concurrent_idempotent_creates_make_exactly_one_task(env):
    rs = _gather_posts(env, 6, lambda i: "/api/runs", json={"title": "t"},
                       headers={"Idempotency-Key": "race-1"})
    assert {r.status_code for r in rs} <= {200, 201}
    assert sum(r.status_code == 201 for r in rs) == 1
    assert len({r.json()["run_id"] for r in rs}) == 1
    run = asyncio.run(env.runs.get(rs[0].json()["run_id"]))
    assert run.task_id and asyncio.run(env.tasks.get(run.task_id)) is not None
    assert len(asyncio.run(env.tasks.list_all())) == 1


def test_a_run_won_by_another_request_never_gets_a_second_task(env):
    """A creator that stalled after binding the key: the recreated run is the winner's."""
    ghost = asyncio.run(env.runs.create(RunRecord(owner_id="alice", state=RunState.QUEUED)))
    asyncio.run(env.runs.idempotency.insert_if_absent(
        "owner:alice:k", env.runs._key_doc("owner:alice", "k", ghost.run_id, time.time(), 3600.0)))
    r = env.post("/api/runs", json={"title": "t"}, headers={"Idempotency-Key": "k"})
    assert r.status_code == 200 and r.json()["run_id"] == ghost.run_id
    assert asyncio.run(env.runs.get(ghost.run_id)).task_id is None
    assert asyncio.run(env.tasks.list_all()) == []


def test_concurrent_retries_create_exactly_one_new_run(env):
    j = _create(env).json()
    asyncio.run(env.runs.transition(j["run_id"], RunState.FAILED, reason="boom"))
    rs = _gather_posts(env, 5, lambda i: f"/api/runs/{j['run_id']}/retry")
    assert sorted(r.status_code for r in rs) == [201, 409, 409, 409, 409]
    new = [r.json()["run_id"] for r in rs if r.status_code == 201][0]
    task = asyncio.run(env.tasks.get(j["task_id"]))
    assert task.current_run_id == new
    kids = [r for r in asyncio.run(env.runs.list(task_id=j["task_id"])) if r.retry_of == j["run_id"]]
    assert [k.run_id for k in kids] == [new]


def test_a_failed_start_frees_the_idempotency_key(env, monkeypatch):
    """Task creation fails once: the same key must later start a fresh, working run."""
    from tasks.service import TaskWorkflowService

    real, calls = TaskWorkflowService.create_task, {"n": 0}

    async def flaky(self, task, actor):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("db down")
        return await real(self, task, actor=actor)

    monkeypatch.setattr(TaskWorkflowService, "create_task", flaky)
    first = env.post("/api/runs", json={"title": "t"}, headers={"Idempotency-Key": "k1"})
    assert first.status_code == 500
    again = env.post("/api/runs", json={"title": "t"}, headers={"Idempotency-Key": "k1"})
    assert again.status_code == 201
    assert again.json()["run_id"] != first.json().get("run_id")
    assert again.json()["task_id"]


def test_a_failed_retry_store_write_releases_the_claim(env, monkeypatch):
    j = _create(env).json()
    asyncio.run(env.runs.transition(j["run_id"], RunState.FAILED, reason="boom"))
    real = env.runs.create

    async def down(run):
        raise RuntimeError("db down")

    monkeypatch.setattr(env.runs, "create", down)
    assert env.post(f"/api/runs/{j['run_id']}/retry").status_code == 500
    assert asyncio.run(env.runs.get(j["run_id"])).retried_by is None
    monkeypatch.setattr(env.runs, "create", real)
    assert env.post(f"/api/runs/{j['run_id']}/retry").status_code == 201


def test_a_rejected_requeue_leaves_no_orphan_run(env, monkeypatch):
    from tasks.service import TaskRuleError, TaskWorkflowService

    j = _create(env).json()
    asyncio.run(env.runs.transition(j["run_id"], RunState.FAILED, reason="boom"))

    def reject(self, task, actor):
        raise TaskRuleError("no")

    monkeypatch.setattr(TaskWorkflowService, "retry", reject)
    assert env.post(f"/api/runs/{j['run_id']}/retry").status_code == 409
    kids = [r for r in asyncio.run(env.runs.list(task_id=j["task_id"])) if r.retry_of == j["run_id"]]
    assert kids == []
    assert asyncio.run(env.runs.get(j["run_id"])).retried_by is None
