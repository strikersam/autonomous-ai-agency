from __future__ import annotations

import asyncio
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

import backend.doctor_network as dn


def _provider(pid: str, priority: int, ptype: str = "openai-compatible"):
    return SimpleNamespace(provider_id=pid, type=ptype, priority=priority)


class _FakeRouter:
    def __init__(self, providers, reachable: dict[str, object]):
        self.providers = providers
        self._reachable = reachable

    async def health_check(self, provider):
        outcome = self._reachable[provider.provider_id]
        if isinstance(outcome, Exception):
            raise outcome
        if outcome == "hang":
            await asyncio.sleep(60)
        return outcome


async def _auth(request: Request) -> dict:
    if request.headers.get("Authorization") != "Bearer ok":
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"id": "u1"}


def _client(router) -> TestClient:
    app = FastAPI()
    app.include_router(dn.build_doctor_network_router(_auth, lambda: router))
    return TestClient(app)


def test_reports_each_provider_in_priority_order():
    router = _FakeRouter(
        [_provider("groq", 4), _provider("nvidia", 1), _provider("cerebras", 3)],
        {"nvidia": True, "cerebras": False, "groq": RuntimeError("boom")},
    )
    resp = _client(router).get("/api/doctor/network", headers={"Authorization": "Bearer ok"})
    assert resp.status_code == 200
    body = resp.json()
    assert [p["provider_id"] for p in body["providers"]] == ["nvidia", "cerebras", "groq"]
    assert [p["reachable"] for p in body["providers"]] == [True, False, False]
    assert body["reachable"] == 1 and body["total"] == 3 and body["ready"] is True


def test_not_ready_when_no_provider_is_reachable():
    router = _FakeRouter([_provider("nvidia", 1)], {"nvidia": False})
    body = _client(router).get(
        "/api/doctor/network", headers={"Authorization": "Bearer ok"}
    ).json()
    assert body["ready"] is False and body["reachable"] == 0


def test_empty_chain_is_not_ready():
    body = _client(_FakeRouter([], {})).get(
        "/api/doctor/network", headers={"Authorization": "Bearer ok"}
    ).json()
    assert body == {**body, "ready": False, "reachable": 0, "total": 0, "providers": []}


def test_a_hung_probe_times_out_as_unreachable(monkeypatch):
    monkeypatch.setattr(dn, "_PROBE_TIMEOUT_S", 0.05)
    router = _FakeRouter(
        [_provider("nvidia", 1), _provider("ollama", 5, "ollama")],
        {"nvidia": "hang", "ollama": True},
    )
    body = _client(router).get(
        "/api/doctor/network", headers={"Authorization": "Bearer ok"}
    ).json()
    assert [p["reachable"] for p in body["providers"]] == [False, True]


def test_requires_authentication():
    router = _FakeRouter([_provider("nvidia", 1)], {"nvidia": True})
    assert _client(router).get("/api/doctor/network").status_code == 401


def test_router_failure_returns_generic_500():
    def broken():
        raise RuntimeError("secret detail")

    app = FastAPI()
    app.include_router(dn.build_doctor_network_router(_auth, broken))
    resp = TestClient(app).get("/api/doctor/network", headers={"Authorization": "Bearer ok"})
    assert resp.status_code == 500
    assert "secret" not in resp.text


def test_backend_registers_the_route_behind_auth():
    from backend.server import app

    # Included routers are not flattened into app.routes, so prove the wiring by
    # behaviour: an unknown /api path is 404, this one demands auth.
    client = TestClient(app)
    assert client.get("/api/doctor/no-such-check").status_code == 404
    assert client.get("/api/doctor/network").status_code == 401
