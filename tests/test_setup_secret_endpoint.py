"""POST /api/setup/secret — the setup wizard's pre-auth secret store."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def anon() -> TestClient:
    from backend.server import app

    return TestClient(app, raise_server_exceptions=False)


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
