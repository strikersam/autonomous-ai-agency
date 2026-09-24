"""Regression: routers that read request.state.user but never required it.

agents/api.py, runtimes/api.py, secrets_store.py, agents/portfolio_api.py,
agents/agile_api.py and backend/v4_api.py resolved an anonymous caller to
uid "unknown" instead of rejecting it, so an unauthenticated request could
create agents or secrets, stop every runtime, or delete portfolio initiatives.
backend/server.py now mounts them behind get_current_user (rule 10).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def anon() -> TestClient:
    from backend.server import app

    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/agents/"),
        ("POST", "/api/agents/"),
        ("DELETE", "/api/agents/some-agent"),
        ("POST", "/runtimes/stop-all"),
        ("POST", "/runtimes/start-all"),
        ("POST", "/runtimes/hermes/stop"),
        ("GET", "/api/secrets/"),
        ("POST", "/api/secrets/"),
        ("GET", "/api/portfolio/board"),
        ("DELETE", "/api/portfolio/initiatives/some-id"),
        ("POST", "/api/portfolio/seed"),
        ("GET", "/api/agile/sprints"),
        ("GET", "/v4/tasks"),
        ("POST", "/v4/report-bug"),
    ],
)
def test_anonymous_caller_is_rejected(anon: TestClient, method: str, path: str) -> None:
    resp = anon.request(method, path, json={"name": "x", "value": "y", "title": "t"})
    assert resp.status_code == 401, f"{method} {path} -> {resp.status_code}: {resp.text[:200]}"


@pytest.mark.asyncio
async def test_openclaw_read_file_rejects_sibling_prefix_dir(tmp_path, monkeypatch) -> None:
    """A bare startswith() let REPO_PATH=/x/app read /x/app-secrets/*."""
    from services import openclaw_gateway

    repo = tmp_path / "app"
    repo.mkdir()
    (repo / "ok.txt").write_text("fine")
    sibling = tmp_path / "app-secrets"
    sibling.mkdir()
    (sibling / "key.txt").write_text("do-not-leak")
    monkeypatch.setenv("REPO_PATH", str(repo))

    leaked = await openclaw_gateway._cmd_read_file({"path": "../app-secrets/key.txt"})
    assert leaked["type"] == "error"
    assert "do-not-leak" not in str(leaked)

    ok = await openclaw_gateway._cmd_read_file({"path": "ok.txt"})
    assert ok == {"type": "response", "content": "fine", "path": "ok.txt"}
