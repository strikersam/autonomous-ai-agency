"""Regression tests for the authorization gaps found by the 2026-10 security audit.

Each test drives the real router with a dummy role injected into
``request.state.user`` (what JWTUserStateMiddleware does in production) and
asserts that a non-admin can no longer cross the boundary the audit crossed.
"""

from __future__ import annotations

import json
import time

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

ADMIN = {"_id": "admin-1", "email": "admin@example.test", "role": "admin"}
ALICE = {"_id": "alice-1", "email": "alice@example.test", "role": "user"}
MALLORY = {"_id": "mallory-1", "email": "mallory@example.test", "role": "user"}


def _app_with(router) -> TestClient:
    app = FastAPI()

    @app.middleware("http")
    async def _inject_user(request: Request, call_next):
        raw = request.headers.get("x-test-user")
        if raw:
            request.state.user = json.loads(raw)
        return await call_next(request)

    app.include_router(router)
    return TestClient(app)


def _as(user: dict) -> dict:
    return {"x-test-user": json.dumps(user)}


# ── runtimes: lifecycle routes are admin-only ────────────────────────────────

@pytest.mark.parametrize(
    "path",
    ["/runtimes/stop-all", "/runtimes/start-all", "/runtimes/hermes/stop", "/runtimes/hermes/start"],
)
def test_runtime_lifecycle_requires_admin(monkeypatch, path):
    import runtimes.api as rapi

    calls: list[str] = []
    for name in ("stop_all_runtimes", "start_all_runtimes", "stop_runtime", "start_runtime"):
        if hasattr(rapi, name):
            monkeypatch.setattr(rapi, name, lambda *a, _n=name, **k: calls.append(_n) or {"ok": True})
    client = _app_with(rapi.runtime_router)

    assert client.post(path, headers=_as(MALLORY)).status_code == 403
    assert calls == []


def test_wake_all_company_runtimes_requires_admin():
    import runtimes.api as rapi

    client = _app_with(rapi.runtime_router)
    assert client.post("/runtimes/wake-company-runtimes", headers=_as(MALLORY)).status_code == 403


# ── schedules: mutation is admin-only, approval gate is honoured ─────────────

@pytest.fixture()
def scheduler(monkeypatch):
    from packages.scheduler import scheduler as sched_mod

    fired: list = []
    sched = sched_mod.AgentScheduler(on_fire=fired.append)
    sched.fired = fired  # type: ignore[attr-defined]
    monkeypatch.setattr("schedules.api.get_scheduler", lambda: sched)
    return sched


def test_non_admin_cannot_create_trigger_or_delete_schedules(scheduler):
    import schedules.api as sapi

    victim = scheduler.create(name="victim", cron="0 4 * * *", instruction="victim work")
    client = _app_with(sapi.schedules_router)
    body = {"name": "x", "cron": "0 4 * * *", "instruction": "attacker", "approval_gate": True}

    assert client.post("/api/schedules/", json=body, headers=_as(MALLORY)).status_code == 403
    assert client.post(f"/api/schedules/{victim.job_id}/run", headers=_as(MALLORY)).status_code == 403
    assert client.patch(
        f"/api/schedules/{victim.job_id}", json={"status": "paused"}, headers=_as(MALLORY)
    ).status_code == 403
    assert client.delete(f"/api/schedules/{victim.job_id}", headers=_as(MALLORY)).status_code == 403
    assert scheduler.get(victim.job_id) is not None
    assert scheduler.fired == []


@pytest.mark.asyncio
async def test_scheduler_fire_respects_approval_gate(monkeypatch):
    import backend.server as server
    import services.workflow_orchestrator as wo

    seen: list = []

    class _Orch:
        async def execute(self, req):
            seen.append(req)

            class _Run:
                run_id = "r1"

            return _Run()

    monkeypatch.setattr(wo, "get_workflow_orchestrator", lambda: _Orch())

    class _Job:
        job_id = "j1"
        instruction = "gated work"
        requires_approval = True

    await server._scheduler_on_fire(_Job())
    assert seen and seen[0].auto_approve is False


# ── tasks: purge and the v4 list are owner-scoped for non-admins ─────────────

@pytest.fixture()
def task_store(monkeypatch):
    import tasks.store as store_mod

    store = store_mod.TaskStore()
    monkeypatch.setattr(store_mod, "_global_store", store)
    return store


async def _seed(store, owner: str, title: str, status: str):
    from tasks.models import Task

    task = Task(owner_id=owner, title=title)
    task.status = status
    old = time.time() - 10 * 86400
    task.created_at = old
    task.updated_at = old
    await store.create(task)
    return task


@pytest.mark.asyncio
async def test_non_admin_purge_cannot_delete_other_owners_tasks(task_store):
    import tasks.api as tapi

    victim_done = await _seed(task_store, ALICE["_id"], "alice done", "done")
    victim_todo = await _seed(task_store, ALICE["_id"], "alice todo", "todo")
    client = _app_with(tapi.task_router)

    r = client.post("/api/tasks/purge?days=1&statuses=done,todo", headers=_as(MALLORY))
    assert r.status_code == 200
    assert r.json()["deleted"] == 0
    assert await task_store.get(victim_done.task_id) is not None
    assert await task_store.get(victim_todo.task_id) is not None


@pytest.mark.asyncio
async def test_admin_purge_never_deletes_live_statuses(task_store):
    import tasks.api as tapi

    live = await _seed(task_store, ALICE["_id"], "alice todo", "todo")
    client = _app_with(tapi.task_router)

    r = client.post("/api/tasks/purge?days=1&statuses=todo,done", headers=_as(ADMIN))
    assert r.status_code == 200
    assert await task_store.get(live.task_id) is not None


@pytest.mark.asyncio
async def test_v4_tasks_hides_other_owners_tasks(task_store):
    import backend.v4_api as v4

    v4._TASKS_CACHE.clear()
    await _seed(task_store, ALICE["_id"], "alice-secret-title", "todo")
    client = _app_with(v4.v4_router)

    titles = [t["title"] for t in client.get("/v4/tasks?limit=1000", headers=_as(MALLORY)).json()["tasks"]]
    assert "alice-secret-title" not in titles
    admin_titles = [t["title"] for t in client.get("/v4/tasks", headers=_as(ADMIN)).json()["tasks"]]
    assert "alice-secret-title" in admin_titles


# ── secrets: DB-backed listing applies the same policy as get_metadata ──────

def test_secret_listing_does_not_leak_workspace_or_global_metadata(monkeypatch, tmp_path):
    import secrets_store as ss
    from packages.storage.sqlite import SQLiteStore

    monkeypatch.setattr(ss, "_store", None)
    ss.get_secrets_store(db=SQLiteStore(db_path=str(tmp_path / "secrets.db")))
    power = {"_id": "power-1", "email": "power@example.test", "role": "power_user"}
    client = _app_with(ss.secrets_router)

    def _create(user, name, scope):
        body = {"name": name, "value": f"{name.upper()}-VALUE-0001", "scope": scope}
        assert client.post("/api/secrets/", json=body, headers=_as(user)).status_code == 201

    _create(ADMIN, "dummy-global", "global")
    _create(power, "dummy-workspace", "workspace")
    _create(MALLORY, "mallory-own", "user")

    mallory_names = {s["name"] for s in client.get("/api/secrets/", headers=_as(MALLORY)).json()["secrets"]}
    assert mallory_names == {"mallory-own"}
    power_names = {s["name"] for s in client.get("/api/secrets/", headers=_as(power)).json()["secrets"]}
    assert "dummy-global" not in power_names
    assert "dummy-workspace" in power_names


# ── proxy: agent sessions and snapshots are bound to the creating key ───────

def test_proxy_sessions_are_private_to_their_key(monkeypatch, tmp_path):
    import proxy
    from agent.memory import SessionMemory

    monkeypatch.setattr(proxy, "SESSION_MEMORY", SessionMemory(tmp_path / "memory"))

    def _auth_from_header(request: Request) -> proxy.AuthContext:
        who = request.headers.get("x-test-key", "alice")
        return proxy.AuthContext(
            key=f"k-{who}", email=f"{who}@example.test", department="eng", key_id=f"kid-{who}", source="store"
        )

    proxy.app.dependency_overrides[proxy.verify_api_key] = _auth_from_header
    try:
        client = TestClient(proxy.app)
        sid = client.post("/agent/sessions", json={"title": "alice private"}).json()["session_id"]
        assert client.post(f"/agent/memory/{sid}/snapshot").status_code == 200

        bob = {"x-test-key": "bob"}
        assert sid not in [s["session_id"] for s in client.get("/agent/sessions", headers=bob).json()["sessions"]]
        assert client.get(f"/agent/sessions/{sid}", headers=bob).status_code == 404
        assert client.post(f"/agent/memory/{sid}/snapshot", headers=bob).status_code == 404
        assert client.get(f"/agent/memory/{sid}", headers=bob).status_code == 404
        assert client.delete(f"/agent/memory/{sid}", headers=bob).json()["deleted"] is False
        assert client.get(f"/agent/memory/{sid}").status_code == 200
    finally:
        proxy.app.dependency_overrides.pop(proxy.verify_api_key, None)
