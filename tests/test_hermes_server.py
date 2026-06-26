"""tests/test_hermes_server.py — the agency's OWN Hermes runtime server.

services/hermes_server.py speaks the API runtimes/adapters/hermes.py calls
(GET /health, POST /tasks) and executes via InternalAgentAdapter. These tests
pin that contract without any real LLM call (execute is monkeypatched).
"""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from services.hermes_server import app
from runtimes.base import TaskResult


client = TestClient(app)


def test_health_reports_ours():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["runtime"] == "hermes"
    assert body["ours"] is True            # our own Hermes, not NousResearch
    assert "version" in body


def test_tasks_executes_via_internal_agent():
    async def fake_execute(self, spec):
        # Echo back so we can assert the spec was built from the request body.
        return TaskResult(
            runtime_id="internal_agent",
            task_id=spec.task_id,
            success=True,
            output=f"done: {spec.instruction}",
            artifacts=[{"path": "x.py"}],
        )

    with patch("runtimes.adapters.internal_agent.InternalAgentAdapter.execute", fake_execute):
        r = client.post("/tasks", json={"instruction": "add a docstring", "task_type": "code_review"})

    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["status"] == "done"
    assert "add a docstring" in body["output"]
    assert body["artifacts"] == [{"path": "x.py"}]
    assert body["task_id"]                  # a task_id was generated


def test_tasks_failure_is_reported_not_crashed():
    async def boom(self, spec):
        raise RuntimeError("brain unreachable")

    with patch("runtimes.adapters.internal_agent.InternalAgentAdapter.execute", boom):
        r = client.post("/tasks", json={"instruction": "do a thing"})

    assert r.status_code == 200            # never 500 — surfaced as a failed task
    body = r.json()
    assert body["success"] is False
    assert body["status"] == "failed"
    assert "brain unreachable" in body["output"]


def test_tasks_auth_gate_when_key_set(monkeypatch):
    monkeypatch.setenv("HERMES_API_KEY", "secret-key")
    # No/incorrect bearer → 401.
    r = client.post("/tasks", json={"instruction": "x"}, headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401
