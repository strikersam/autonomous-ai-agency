"""Regression tests for the v5 screen/backend contract fixes."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient


# ── provider policy surfaces ────────────────────────────────────────────────


def _fake_db(doc):
    db = MagicMock()
    db.providers.find_one = AsyncMock(return_value=doc)
    db.providers.update_one = AsyncMock()
    return db


def test_policy_returns_stored_surfaces(monkeypatch) -> None:
    import backend.server as srv

    monkeypatch.delenv("ALLOW_PAID_BRAIN", raising=False)
    monkeypatch.setattr(
        srv, "get_db", lambda: _fake_db({"allow_paid": False, "surfaces": {"chat": "nvidia"}})
    )
    policy = asyncio.run(srv._get_provider_policy())
    assert policy["surfaces"] == {"chat": "nvidia"}


def test_policy_update_without_surfaces_keeps_stored(monkeypatch) -> None:
    import backend.server as srv

    monkeypatch.delenv("ALLOW_PAID_BRAIN", raising=False)
    db = _fake_db({"allow_paid": False, "surfaces": {"chat": "nvidia"}})
    monkeypatch.setattr(srv, "get_db", lambda: db)
    result = asyncio.run(srv._set_provider_policy(srv.ProviderPolicyUpdate(allow_paid=True)))
    assert result["surfaces"] == {"chat": "nvidia"}
    saved = db.providers.update_one.await_args.args[1]["$set"]
    assert saved["surfaces"] == {"chat": "nvidia"}


# ── /api/providers shape for non-admins ─────────────────────────────────────


def test_providers_non_admin_gets_same_shape(non_admin_client) -> None:
    resp = non_admin_client.get("/api/providers")
    assert resp.status_code == 200
    assert resp.json() == {"providers": []}


# ── workflow route order + generic 409 ──────────────────────────────────────


def test_workflow_agents_route_not_shadowed_by_run_id() -> None:
    from workflow.api import workflow_router

    paths = [r.path for r in workflow_router.routes if "GET" in getattr(r, "methods", set())]
    assert paths.index("/workflow/agents") < paths.index("/workflow/{run_id}")


def test_workflow_409_detail_is_generic() -> None:
    from workflow.api import workflow_router
    from workflow.engine import WorkflowEngine

    engine = MagicMock(spec=WorkflowEngine)
    engine.get.return_value = MagicMock()
    engine.approve.side_effect = ValueError("internal /srv/path detail")
    app = FastAPI()

    @app.middleware("http")
    async def inject_user(request: Request, call_next):
        request.state.user = {"email": "boss@example.com"}
        return await call_next(request)

    app.include_router(workflow_router, prefix="/api")
    from workflow.api import _engine

    app.dependency_overrides[_engine] = lambda: engine
    resp = TestClient(app, raise_server_exceptions=False).post(
        "/api/workflow/run1/approve", json={"approved_by": "admin"}
    )
    assert resp.status_code == 409
    assert "internal" not in resp.text
    assert engine.approve.call_args.kwargs["approved_by"] == "boss@example.com"


# ── scheduler failure counter ───────────────────────────────────────────────


def test_scheduler_counts_failed_fire() -> None:
    from packages.scheduler.scheduler import ScheduledJob

    job = ScheduledJob(job_id="j", name="n", cron="* * * * *", instruction="x", created_at="t")
    assert job.as_dict()["failures"] == 0
    job.fail_count = 2
    d = job.as_dict()
    assert d["failures"] == 2 and d["fail_count"] == 2
    assert ScheduledJob.from_dict(d).fail_count == 2


def test_scheduler_fire_records_callback_exception() -> None:
    from packages.scheduler.scheduler import AgentScheduler

    sched = AgentScheduler()
    job = sched.create(name="boom", cron="* * * * *", instruction="x")

    def _raise(_job):
        raise RuntimeError("nope")

    sched.set_on_fire(_raise)
    sched._fire(job.job_id)
    assert job.fail_count == 1
    sched.shutdown()


def test_scheduler_fire_records_async_callback_failure() -> None:
    from packages.scheduler.scheduler import AgentScheduler

    sched = AgentScheduler()
    job = sched.create(name="boom-async", cron="* * * * *", instruction="x")

    async def _raise(_job):
        raise RuntimeError("nope")

    async def _run() -> None:
        sched.set_on_fire(_raise)
        sched._fire(job.job_id)
        await asyncio.sleep(0.05)

    asyncio.run(_run())
    assert job.fail_count == 1
    sched.shutdown()


# ── voice container sniffing ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "head,ext",
    [
        (b"\x1aE\xdf\xa3" + b"\0" * 8, ".webm"),
        (b"OggS" + b"\0" * 8, ".ogg"),
        (b"\0\0\0\x18ftypmp42", ".m4a"),
        (b"RIFF\0\0\0\0WAVE", ".wav"),
    ],
)
def test_voice_sniffs_browser_containers(head: bytes, ext: str) -> None:
    from agent.voice import _sniff_container

    assert _sniff_container(head)[0] == ext


def test_voice_raw_pcm_is_not_a_container() -> None:
    from agent.voice import _sniff_container

    assert _sniff_container(b"\x01\x02\x03\x04\x05\x06\x07\x08\x09") is None


# ── MCP PATCH validated body ────────────────────────────────────────────────


def test_mcp_patch_rejects_wrong_types(non_admin_client) -> None:
    resp = non_admin_client.patch(
        "/api/mcp/servers/0123456789abcdef01234567", json={"tools": "many"}
    )
    assert resp.status_code == 422
