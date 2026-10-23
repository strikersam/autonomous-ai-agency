"""Code Mode phase 7: the agency API as a search/execute MCP server."""
from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from backend import code_mode_mcp_router as r
from packages.config import settings


def _target_app() -> FastAPI:
    """Stands in for backend.server.app: what agency.request reaches in-process."""
    app = FastAPI()

    @app.get("/api/tasks")
    async def tasks(request: Request, status: str = "") -> dict[str, Any]:
        return {"auth": request.headers.get("authorization"), "status": status, "items": [1, 2, 3]}

    @app.get("/api/tasks/{task_id}")
    async def task(task_id: str) -> dict[str, Any]:
        return {"id": task_id}

    @app.post("/api/tasks")
    async def create() -> dict[str, Any]:
        raise AssertionError("POST must never be reached")

    return app


@pytest.fixture()
def client(monkeypatch):
    target = _target_app()
    monkeypatch.setattr(r, "_load_app", lambda: target)
    monkeypatch.setattr(settings, "code_mode_mcp_server_raw", "true")
    who: dict[str, Any] = {"user": {"email": "a@example.com", "role": "user"}}

    async def fake_user():
        if who["user"] is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return who["user"]

    app = FastAPI()
    app.include_router(r.build_code_mode_mcp_router(fake_user))
    with TestClient(app) as c:
        yield c, who


def _rpc(c: TestClient, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    resp = c.post(r.MCP_PATH, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
                  headers={"Authorization": "Bearer caller-token"})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _call(c: TestClient, tool: str, code: str) -> dict[str, Any]:
    result = _rpc(c, "tools/call", {"name": tool, "arguments": {"code": code}})["result"]
    return {"isError": result["isError"], **json.loads(result["content"][0]["text"])}


def test_handshake_and_two_tools(client):
    c, _ = client
    assert _rpc(c, "initialize")["result"]["serverInfo"]["name"] == "agency-code-mode"
    tools = _rpc(c, "tools/list")["result"]["tools"]
    assert [t["name"] for t in tools] == ["search", "execute"]
    assert all(t["annotations"]["readOnlyHint"] for t in tools)
    assert "error" in _rpc(c, "nope")


def test_search_filters_the_spec_without_requests(client):
    c, _ = client
    out = _call(c, "search", "result = [op['method'] + ' ' + op['path'] for op in agency.spec() if 'task' in op['path']]")
    assert out["ok"] and sorted(out["result"]) == ["GET /api/tasks", "GET /api/tasks/{task_id}", "POST /api/tasks"]
    out = _call(c, "search", "agency.request('GET', '/api/tasks')")
    assert out["isError"] and "agency.spec()" in out["error"]


def test_execute_gets_with_the_callers_credentials(client):
    c, _ = client
    out = _call(c, "execute", "r = agency.request('GET', '/api/tasks', query={'status': 'open'})\nresult = [r['auth'], r['status'], len(r['items'])]")
    assert out["ok"], out
    assert out["result"] == ["Bearer caller-token", "open", 3]
    out = _call(c, "execute", "result = agency.request('GET', '/api/tasks/abc')['id']")
    assert out["result"] == "abc"


@pytest.mark.parametrize(
    ("code", "msg"),
    [
        ("agency.request('POST', '/api/tasks')", "only GET"),
        ("agency.request('GET', '/api/unknown')", "not a GET endpoint"),
        ("agency.request('GET', '/api/tasks/../admin')", "not a GET endpoint"),
        ("agency.request('GET', '/health')", "not a GET endpoint"),
        ("agency.request('GET', '/api/code-mode/mcp')", "not a GET endpoint"),
        ("import os", "not supported"),
    ],
)
def test_execute_refusals(client, code, msg):
    c, _ = client
    out = _call(c, "execute", code)
    assert out["isError"] and msg in out["error"]


def test_unknown_tool_and_auth_and_switch(client, monkeypatch):
    c, who = client
    assert "error" in _rpc(c, "tools/call", {"name": "shell", "arguments": {}})
    who["user"] = None
    assert c.post(r.MCP_PATH, json={"method": "tools/list"}).status_code == 401
    who["user"] = {"email": "a@example.com"}
    monkeypatch.setattr(settings, "code_mode_mcp_server_raw", "false")
    assert c.post(r.MCP_PATH, json={"method": "tools/list"}).status_code == 404


def test_large_results_are_truncated(client):
    c, _ = client
    result = _rpc(c, "tools/call", {"name": "search", "arguments": {"code": "result = 'x' * 100000"}})["result"]
    assert result["content"][0]["text"].endswith("--- TRUNCATED ---")


def test_mounted_and_authenticated_in_the_backend_app():
    from backend.server import app

    assert TestClient(app).post(r.MCP_PATH, json={"method": "tools/list"}).status_code == 401
    assert r.MCP_PATH not in {op["path"] for op in r.compact_spec(app.openapi())}


def test_aliased_huge_result_is_refused_not_serialised(client):
    c, _ = client
    out = _call(c, "search", "row = 'x' * 100000\nresult = [row] * 100")
    assert out["isError"] and "too large" in out["error"]
