"""tests/test_ceo_router.py — auth and behaviour for /api/ceo/*.

Follows the isolation pattern of ``test_admin_local_brain_router.py``: a
minimal FastAPI app wrapping the router with a fake auth dependency, and a
SQLite ledger pointed at ``tmp_path`` so the operator's real
``.data/agency.db`` is never touched.

The two POST routes start real agent work, which spends provider tokens, so
the admin gate on them is pinned here rather than left to review.
"""
from __future__ import annotations

import time

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from services.ceo_ledger import CEOLedger, GoalRecord, SubtaskRecord, reset_ceo_ledger
from services.ceo_supervisor import (
    CEOSupervisor,
    SupervisorConfig,
    reset_ceo_supervisor,
    set_ceo_supervisor,
)

_ADMIN = {"_id": "admin-user", "email": "admin@llmrelay.local", "role": "admin"}
_REGULAR = {"_id": "regular-user", "email": "user@llmrelay.local", "role": "user"}


@pytest.fixture
def ledger(monkeypatch, tmp_path):
    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    reset_ceo_ledger()
    store = CEOLedger(sqlite_path=str(tmp_path / "agency.db"))
    monkeypatch.setattr("services.ceo_ledger.get_ceo_ledger", lambda: store)
    yield store
    reset_ceo_ledger()


@pytest.fixture(autouse=True)
def _supervisor():
    set_ceo_supervisor(CEOSupervisor(config=SupervisorConfig(wake_runtimes=False)))
    yield
    reset_ceo_supervisor()


def _make_app(user, *, unauthenticated: bool = False) -> FastAPI:
    from backend.ceo_router import build_ceo_router

    async def _fake_get_current_user():
        if unauthenticated:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return user

    app = FastAPI()
    app.include_router(build_ceo_router(_fake_get_current_user))
    return app


def _seed(ledger, goal_id="g-1", **kw):
    goal = GoalRecord(goal_id=goal_id, goal="Ship the health endpoint", request="Ship it", **kw)
    goal.subtasks = [SubtaskRecord(subtask_id="s1", title="Recon", role="scout", status="running")]
    ledger.upsert(goal)
    return goal


# ── Auth ──────────────────────────────────────────────────────────────────────


def test_status_requires_authentication(ledger):
    client = TestClient(_make_app(None, unauthenticated=True))
    assert client.get("/api/ceo/status").status_code == 401


def test_sweep_is_admin_only(ledger):
    client = TestClient(_make_app(_REGULAR))
    assert client.post("/api/ceo/sweep").status_code == 403


def test_redrive_is_admin_only(ledger):
    _seed(ledger)
    client = TestClient(_make_app(_REGULAR))
    assert client.post("/api/ceo/goals/g-1/redrive").status_code == 403


def test_reading_goals_does_not_require_admin(ledger):
    _seed(ledger)
    client = TestClient(_make_app(_REGULAR))
    assert client.get("/api/ceo/goals").status_code == 200


# ── Reads ─────────────────────────────────────────────────────────────────────


def test_status_reports_supervisor_and_micromanager_config(ledger):
    client = TestClient(_make_app(_ADMIN))
    body = client.get("/api/ceo/status").json()
    assert body["ledger"]["mode"] == "sqlite"
    assert body["micromanager"]["tier_ladder"] == ["intern", "junior", "midlevel", "senior"]
    assert body["micromanager"]["max_attempts_per_subtask"] >= 1
    assert "interval_s" in body["supervisor"]["config"]


def test_list_goals_omits_heavy_subtask_history(ledger):
    _seed(ledger)
    client = TestClient(_make_app(_ADMIN))
    body = client.get("/api/ceo/goals").json()
    assert body["count"] == 1
    assert "subtasks" not in body["goals"][0]
    assert body["goals"][0]["progress"] == {"done": 0, "total": 1}


def test_list_goals_filters_by_state(ledger):
    _seed(ledger, "open-1")
    _seed(ledger, "closed-1", state="closed")
    client = TestClient(_make_app(_ADMIN))

    open_ids = [g["goal_id"] for g in client.get("/api/ceo/goals?state=open").json()["goals"]]
    assert open_ids == ["open-1"]

    closed_ids = [g["goal_id"] for g in client.get("/api/ceo/goals?state=closed").json()["goals"]]
    assert closed_ids == ["closed-1"]


def test_goal_detail_carries_the_subtask_history(ledger):
    _seed(ledger)
    client = TestClient(_make_app(_ADMIN))
    body = client.get("/api/ceo/goals/g-1").json()
    assert body["goal_id"] == "g-1"
    assert [s["subtask_id"] for s in body["subtasks"]] == ["s1"]


def test_unknown_goal_is_404(ledger):
    client = TestClient(_make_app(_ADMIN))
    assert client.get("/api/ceo/goals/nope").status_code == 404


# ── Writes ────────────────────────────────────────────────────────────────────


def test_admin_can_run_a_sweep_on_demand(ledger):
    goal = _seed(ledger, "done-1")
    goal.subtasks[0].status = "done"
    ledger.upsert(goal)

    client = TestClient(_make_app(_ADMIN))
    body = client.post("/api/ceo/sweep").json()
    assert body["closed"] == 1
    assert ledger.get("done-1").state == "closed"


def test_redrive_refuses_a_goal_that_spent_its_budget(ledger):
    """The manual route must not be a way around the intervention cap."""
    _seed(ledger, "spent-1", interventions=99, last_progress_at=time.time() - 9999)
    client = TestClient(_make_app(_ADMIN))
    resp = client.post("/api/ceo/goals/spent-1/redrive")
    assert resp.status_code == 409
    assert "intervention budget" in resp.json()["detail"]


def test_redrive_of_an_unknown_goal_is_404(ledger):
    client = TestClient(_make_app(_ADMIN))
    assert client.post("/api/ceo/goals/nope/redrive").status_code == 404
