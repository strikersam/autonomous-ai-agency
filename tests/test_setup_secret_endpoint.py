"""POST /api/setup/secret — the setup wizard's secret store (authenticated)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _client(*, authed: bool) -> TestClient:
    from fastapi import FastAPI, Request

    from setup.api import setup_router

    app = FastAPI()

    @app.middleware("http")
    async def inject_user(request: Request, call_next):
        if authed:
            request.state.user = {"email": "user@example.com", "_id": "user-1"}
        return await call_next(request)

    app.include_router(setup_router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def anon() -> TestClient:
    return _client(authed=True)


def test_unauthenticated_caller_is_rejected() -> None:
    """Regression: this endpoint used to accept secrets from anyone."""
    resp = _client(authed=False).post("/api/setup/secret", json={"name": "k", "value": "v"})
    assert resp.status_code == 401


@pytest.mark.parametrize("body", ["not json", "[1, 2]", "null"])
def test_malformed_body_is_a_400_not_a_500(anon: TestClient, body: str) -> None:
    resp = anon.post(
        "/api/setup/secret", content=body, headers={"content-type": "application/json"}
    )
    assert resp.status_code == 400, resp.text


def test_store_failure_does_not_echo_the_exception(anon: TestClient, monkeypatch) -> None:
    """Regression: the 500 detail used to be f"Failed to store secret: {e}"."""
    import setup.api as setup_api

    class _Boom:
        async def create(self, rec):
            raise RuntimeError("mongodb://user:hunter2@internal-host")

    monkeypatch.setattr(setup_api, "get_secrets_store", lambda: _Boom())
    resp = anon.post("/api/setup/secret", json={"name": "k", "value": "v"})
    assert resp.status_code == 500
    assert "hunter2" not in resp.text
    assert resp.json()["detail"] == "Failed to store secret"
