"""Regression tests for the security-audit follow-up on the surfaces it never covered."""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

USER = {"_id": "u1", "email": "u1@example.test", "role": "user"}
ADMIN = {"_id": "a1", "email": "a1@example.test", "role": "admin"}


def _client(router) -> TestClient:
    app = FastAPI()

    @app.middleware("http")
    async def _inject(request: Request, call_next):
        request.state.user = json.loads(request.headers.get("x-test-user", "null"))
        return await call_next(request)

    app.include_router(router)
    return TestClient(app)


def _as(user: dict) -> dict:
    return {"x-test-user": json.dumps(user)}


def test_spec_approval_is_admin_only(monkeypatch):
    import services.spec_store as spec_store
    from backend.spec_router import build_spec_router

    decided: list = []

    async def _set(spec_id, status, decided_by=None):
        decided.append((spec_id, status))
        return {"spec_id": spec_id, "status": status}

    monkeypatch.setattr(spec_store, "set_spec_status", _set)

    async def _current_user(request: Request) -> dict:
        return request.state.user

    client = _client(build_spec_router(_current_user))
    assert client.post("/api/specs/s1/approve", headers=_as(USER)).status_code == 403
    assert client.post("/api/specs/s1/reject", headers=_as(USER)).status_code == 403
    assert decided == []
    assert client.post("/api/specs/s1/approve", headers=_as(ADMIN)).status_code == 200
    assert decided == [("s1", "approved")]


def test_sprint_changes_are_admin_only():
    from agents.agile_api import agile_router

    client = _client(agile_router)
    body = {"name": "s", "goal": "g"}
    assert client.post("/api/agile/sprints", json=body, headers=_as(USER)).status_code == 403
    assert client.post("/api/agile/sprints", json=body, headers=_as(ADMIN)).status_code == 201


@pytest.mark.asyncio
async def test_direct_chat_never_falls_back_to_the_host_github_token(monkeypatch):
    import direct_chat

    monkeypatch.setenv("GITHUB_TOKEN", "ghp_HOST")
    monkeypatch.setenv("GH_PAT", "ghp_HOST")
    monkeypatch.setenv("GH_TOKEN", "ghp_HOST")
    assert await direct_chat._get_github_token_for_user("nobody@example.test") is None


def test_every_service_running_hermes_adapters_gets_the_shared_key():
    """Regression: the worker lacked HERMES_API_KEY, so fail-closed Hermes refused its tasks."""
    from pathlib import Path

    import yaml

    services = yaml.safe_load((Path(__file__).resolve().parents[1] / "render.yaml").read_text())["services"]
    by_name = {s["name"]: s for s in services}
    for name in ("local-llm-server", "local-llm-server-worker"):
        keys = [e for e in by_name[name].get("envVars", []) if e.get("key") == "HERMES_API_KEY"]
        assert keys and keys[0].get("fromService", {}).get("name") == "agency-hermes", name
