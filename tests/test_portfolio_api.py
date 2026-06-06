"""Tests for agents/portfolio_api.py — the v5 portfolio board API.

Loads the module with a stubbed ``agents`` package so the heavy
``agents/__init__`` import chain (swarm → workflow → httpx) is bypassed, then
exercises the PortfolioService logic and the FastAPI routes via TestClient.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# Stub the `agents` package so `from agents.portfolio import ...` resolves
# without executing agents/__init__.py.
if "agents" not in sys.modules or not hasattr(sys.modules.get("agents"), "__path__"):
    pkg = types.ModuleType("agents")
    pkg.__path__ = [str(ROOT / "agents")]
    sys.modules["agents"] = pkg
_load("agents.agile_sprints", "agents/agile_sprints.py")
_load("agents.portfolio", "agents/portfolio.py")

papi = _load("agents.portfolio_api", "agents/portfolio_api.py")
PortfolioService = papi.PortfolioService
BoardOut = papi.BoardOut


class TestPortfolioService:
    def test_seed_populates(self):
        svc = PortfolioService()
        svc.seed()
        assert svc.portfolio.initiative_count >= 5
        assert svc.agile.sprint_count == 1

    def test_seed_idempotent(self):
        svc = PortfolioService()
        svc.seed()
        n = svc.portfolio.initiative_count
        svc.seed()  # no-op
        assert svc.portfolio.initiative_count == n

    def test_seed_force_resets(self):
        svc = PortfolioService()
        svc.seed()
        svc.portfolio.add_initiative("Extra", job_size=2)
        svc.seed(force=True)
        # back to the canonical seed count (no leftover "Extra")
        assert all(i.title != "Extra" for i in svc.portfolio.prioritized(include_done=True))

    def test_board_shape_and_ranking(self):
        svc = PortfolioService()
        svc.seed()
        board = svc.board()
        assert isinstance(board, BoardOut)
        # ranked descending by WSJF
        wsjfs = [i.wsjf for i in board.ranked]
        assert wsjfs == sorted(wsjfs, reverse=True)
        # roadmap horizons present
        for key in ("now", "next", "later", "unscheduled"):
            assert key in board.roadmap
        # capacity allocation never exceeds capacity
        assert board.allocation.committed_job_size <= board.allocation.capacity
        # seeded sprint shows real roll-up + scope creep
        assert board.sprints and board.sprints[0].total_points > 0
        assert board.sprints[0].scope_added == 3

    def test_board_now_within_capacity(self):
        svc = PortfolioService()
        svc.seed()
        board = svc.board(horizon_capacity=8)
        now_load = sum(i.job_size for i in board.roadmap["now"])
        assert now_load <= 8


class TestPortfolioRoutes:
    def _client(self):
        fastapi = pytest.importorskip("fastapi")
        pytest.importorskip("httpx")  # starlette TestClient transport
        from fastapi.testclient import TestClient
        app = fastapi.FastAPI()
        app.include_router(papi.portfolio_router)
        # fresh service per client
        papi._SERVICE = None
        return TestClient(app)

    def test_get_board(self):
        c = self._client()
        r = c.get("/api/portfolio/board")
        assert r.status_code == 200
        body = r.json()
        assert body["metrics"]["total_initiatives"] >= 5
        assert len(body["ranked"]) >= 5

    def test_add_and_remove_initiative(self):
        c = self._client()
        r = c.post("/api/portfolio/initiatives", json={
            "title": "New thing", "business_value": 9, "time_criticality": 9,
            "risk_reduction": 9, "job_size": 3,
        })
        assert r.status_code == 201
        iid = r.json()["initiative_id"]
        assert r.json()["wsjf"] == pytest.approx(9.0)

        # it should now top the ranking (WSJF 9.0)
        board = c.get("/api/portfolio/board").json()
        assert board["ranked"][0]["initiative_id"] == iid

        d = c.delete(f"/api/portfolio/initiatives/{iid}")
        assert d.status_code == 204
        board2 = c.get("/api/portfolio/board").json()
        assert all(i["initiative_id"] != iid for i in board2["ranked"])

    def test_reseed(self):
        c = self._client()
        r = c.post("/api/portfolio/seed")
        assert r.status_code == 200
        assert r.json()["metrics"]["total_initiatives"] >= 5

    def test_add_validation_rejects_zero_job_size(self):
        c = self._client()
        r = c.post("/api/portfolio/initiatives", json={"title": "Bad", "job_size": 0})
        assert r.status_code == 422
