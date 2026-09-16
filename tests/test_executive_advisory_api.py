"""tests/test_executive_advisory_api.py — auth and behaviour for /api/executives/*.

Isolation pattern from ``test_ceo_router.py``: a minimal FastAPI app wrapping the
router with a fake auth dependency, and an injected advisory so no provider or
network is touched.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from agent.executive_advisory import (
    AdviceResult,
    ExecOpinion,
    ExecutiveAdvisory,
    Grounding,
    reset_executive_advisory,
)

_ADMIN = {"_id": "admin-user", "email": "admin@llmrelay.local", "role": "admin"}
_REGULAR = {"_id": "regular-user", "email": "user@llmrelay.local", "role": "user"}


def _make_app(user, *, unauthenticated: bool = False) -> FastAPI:
    from backend.executive_advisory_api import build_executive_advisory_router

    async def _fake_get_current_user():
        if unauthenticated:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return user

    app = FastAPI()
    app.include_router(build_executive_advisory_router(_fake_get_current_user))
    return app


@pytest.fixture
def stub_advisory(monkeypatch):
    """Install an advisory whose LLM is a canned reply — no network."""
    async def llm(messages):
        return "canned"

    adv = ExecutiveAdvisory(llm=llm)
    reset_executive_advisory()
    monkeypatch.setattr(
        "agent.executive_advisory.get_executive_advisory", lambda: adv
    )
    yield adv
    reset_executive_advisory()


# ── GET /api/executives ─────────────────────────────────────────────────────


def test_list_executives_requires_auth():
    client = TestClient(_make_app(_REGULAR, unauthenticated=True))
    assert client.get("/api/executives").status_code == 401


def test_list_executives_returns_personas():
    client = TestClient(_make_app(_REGULAR))
    resp = client.get("/api/executives")
    assert resp.status_code == 200
    roles = {e["role"] for e in resp.json()["executives"]}
    assert {"cso", "cfo", "coo", "cmo", "cpo", "gc"} == roles


# ── POST /api/executives/consult ────────────────────────────────────────────


def test_consult_rejects_non_admin(stub_advisory):
    client = TestClient(_make_app(_REGULAR))
    resp = client.post("/api/executives/consult", json={"question": "pricing?"})
    assert resp.status_code == 403


def test_consult_rejects_empty_question(stub_advisory):
    client = TestClient(_make_app(_ADMIN))
    resp = client.post("/api/executives/consult", json={"question": ""})
    assert resp.status_code == 422  # Pydantic min_length


def test_consult_returns_advice(stub_advisory):
    client = TestClient(_make_app(_ADMIN))
    resp = client.post(
        "/api/executives/consult",
        json={"question": "What pricing vs competitors?", "ground": False,
              "remember": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["question"] == "What pricing vs competitors?"
    # pricing → cfo, competitors → cso are consulted
    assert set(body["consulted"]) >= {"cfo", "cso"}
    assert "answer" in body and "grounding" in body


def test_consult_maps_advisory_failure_to_502(monkeypatch):
    async def _boom(*a, **k):
        raise RuntimeError("provider exploded")

    class _Broken:
        advise = _boom

    reset_executive_advisory()
    monkeypatch.setattr(
        "agent.executive_advisory.get_executive_advisory", lambda: _Broken()
    )
    client = TestClient(_make_app(_ADMIN))
    resp = client.post(
        "/api/executives/consult",
        json={"question": "x", "ground": False, "remember": False},
    )
    assert resp.status_code == 502
    assert resp.json()["detail"] == "Advisory failed"  # no internal leak
    reset_executive_advisory()


def test_consult_passes_company_context(monkeypatch):
    captured: dict = {}

    async def _advise(question, **kwargs):
        captured.update(kwargs)
        return AdviceResult(
            question=question, consulted=["cfo"],
            opinions=[ExecOpinion(role="cfo", title="CFO", text="ok")],
            answer="ok", grounding=Grounding(),
        )

    class _Adv:
        advise = staticmethod(_advise)

    async def _ctx(company_id):
        return {"name": "Acme", "domain": "acme.test"}

    reset_executive_advisory()
    monkeypatch.setattr(
        "agent.executive_advisory.get_executive_advisory", lambda: _Adv()
    )
    monkeypatch.setattr("agent.agency._company_advisory_context", _ctx)
    client = TestClient(_make_app(_ADMIN))
    resp = client.post(
        "/api/executives/consult",
        json={"question": "pricing?", "company_id": "c1", "ground": False,
              "remember": False},
    )
    assert resp.status_code == 200
    assert captured["company_context"] == {"name": "Acme", "domain": "acme.test"}
    reset_executive_advisory()
