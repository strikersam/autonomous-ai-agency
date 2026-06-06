"""Tests for agents/portfolio_api.py — the v5 portfolio board API.

Loads the module with a stubbed ``agents`` package so the heavy
``agents/__init__`` import chain is bypassed. The intelligence build is
short-circuited with an injected portfolio so no network is touched.
"""

from __future__ import annotations

import importlib.util
import sys
import time
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


if "agents" not in sys.modules or not hasattr(sys.modules.get("agents"), "__path__"):
    pkg = types.ModuleType("agents")
    pkg.__path__ = [str(ROOT / "agents")]
    sys.modules["agents"] = pkg
_load("agents.agile_sprints", "agents/agile_sprints.py")
portfolio_mod = _load("agents.portfolio", "agents/portfolio.py")
_load("agents.portfolio_intelligence", "agents/portfolio_intelligence.py")
papi = _load("agents.portfolio_api", "agents/portfolio_api.py")

PortfolioManager = portfolio_mod.PortfolioManager
InitiativeStatus = portfolio_mod.InitiativeStatus


def _seeded_manager() -> "PortfolioManager":
    mgr = PortfolioManager()
    a = mgr.add_initiative("High value", business_value=13, time_criticality=8, risk_reduction=4, job_size=4)
    a.source, a.rationale, a.status = "bug", "open bug", InitiativeStatus.APPROVED
    b = mgr.add_initiative("Mid value", business_value=8, time_criticality=3, risk_reduction=2, job_size=8)
    b.source, b.rationale = "roadmap", "P1 backlog"
    c = mgr.add_initiative("Low value", business_value=3, time_criticality=2, risk_reduction=1, job_size=8)
    c.source, c.rationale = "research", "trend"
    return mgr


def _install_service():
    """Install a PortfolioService whose portfolio is fixed (no rebuild)."""
    svc = papi.PortfolioService()
    svc.portfolio = _seeded_manager()
    svc._sources = {"bug": 1, "roadmap": 1, "research": 1}
    svc._built_at = time.time()  # fresh → ensure_fresh won't rebuild/network
    papi._SERVICE = svc
    return svc


class TestBoardPayload:
    def test_board_shape_and_ranking(self):
        _install_service()
        board = papi.get_service().board()
        assert isinstance(board, papi.BoardOut)
        wsjfs = [i.wsjf for i in board.ranked]
        assert wsjfs == sorted(wsjfs, reverse=True)
        assert board.ranked[0].title == "High value"
        # provenance flows through
        assert board.ranked[0].source == "bug"
        assert board.sources == {"bug": 1, "roadmap": 1, "research": 1}
        for key in ("now", "next", "later", "unscheduled"):
            assert key in board.roadmap
        assert board.allocation.committed_job_size <= board.allocation.capacity


class TestRoutes:
    def _client(self):
        fastapi = pytest.importorskip("fastapi")
        pytest.importorskip("httpx")
        from fastapi.testclient import TestClient
        app = fastapi.FastAPI()
        app.include_router(papi.portfolio_router)
        _install_service()
        return TestClient(app)

    def test_get_board(self):
        c = self._client()
        r = c.get("/api/portfolio/board")
        assert r.status_code == 200
        body = r.json()
        assert body["ranked"][0]["title"] == "High value"
        assert body["ranked"][0]["source"] == "bug"
        assert body["sources"]["bug"] == 1

    def test_add_initiative_ranks_and_marks_manual(self):
        c = self._client()
        r = c.post("/api/portfolio/initiatives", json={
            "title": "Critical manual", "business_value": 20, "time_criticality": 20,
            "risk_reduction": 20, "job_size": 2,
        })
        assert r.status_code == 201
        assert r.json()["source"] == "manual"
        iid = r.json()["initiative_id"]
        board = c.get("/api/portfolio/board").json()
        assert board["ranked"][0]["initiative_id"] == iid  # WSJF 30 → top

        d = c.delete(f"/api/portfolio/initiatives/{iid}")
        assert d.status_code == 204
        board2 = c.get("/api/portfolio/board").json()
        assert all(i["initiative_id"] != iid for i in board2["ranked"])

    def test_refresh_rebuilds_from_intelligence(self, monkeypatch):
        c = self._client()
        # Make the rebuild deterministic + offline.
        rebuilt = _seeded_manager()
        monkeypatch.setattr(papi.get_service().intelligence, "build",
                            lambda **kw: rebuilt)
        papi.get_service().intelligence.last_build = {"bug": 1}
        r = c.post("/api/portfolio/refresh")
        assert r.status_code == 200
        assert r.json()["ranked"][0]["title"] == "High value"

    def test_add_validation_rejects_zero_job_size(self):
        c = self._client()
        r = c.post("/api/portfolio/initiatives", json={"title": "Bad", "job_size": 0})
        assert r.status_code == 422
