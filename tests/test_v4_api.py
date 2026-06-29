"""tests/test_v4_api.py — Tests for the v4 dashboard API endpoints."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def v4_client(client) -> TestClient:
    """Return the test client — reuses conftest client which has bootstrap."""
    return client


@pytest.fixture
def auth_headers(client) -> dict:
    """Get auth headers by logging in as admin via the admin API."""
    from backend.server import ADMIN_EMAIL, ADMIN_PASSWORD
    resp = client.post(
        "/admin/api/login",
        json={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    resp.raise_for_status()
    data = resp.json()
    return {"Authorization": f"Bearer {data['token']}"}


def test_v4_status_returns_200(v4_client: TestClient):
    """GET /v4/status returns 200 with improvement_loop and self_healing keys."""
    resp = v4_client.get("/v4/status")
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "improvement_loop" in data
    assert "self_healing" in data
    loop = data["improvement_loop"]
    assert "active_issues" in loop
    assert "scan_count" in loop
    assert isinstance(loop["active_issues"], list)


def test_v4_improvements_returns_200(v4_client: TestClient):
    """GET /v4/improvements returns 200 with active and resolved lists."""
    resp = v4_client.get("/v4/improvements")
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "active" in data
    assert "resolved" in data


def test_v4_tasks_returns_200(v4_client: TestClient):
    """GET /v4/tasks returns 200 with tasks array."""
    resp = v4_client.get("/v4/tasks")
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "tasks" in data
    assert isinstance(data["tasks"], list)


def test_v4_scheduler_jobs_returns_200(v4_client: TestClient):
    """GET /v4/scheduler/jobs returns 200 with jobs array."""
    resp = v4_client.get("/v4/scheduler/jobs")
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "jobs" in data
    assert isinstance(data["jobs"], list)


def test_v4_quick_notes_returns_200(v4_client: TestClient):
    """GET /v4/quick-notes returns 200 with notes array."""
    resp = v4_client.get("/v4/quick-notes")
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "notes" in data
    assert isinstance(data["notes"], list)


def test_v4_improvements_resolve_nonexistent(v4_client: TestClient):
    """POST /v4/improvements/nonexistent_id/resolve returns resolved=False."""
    resp = v4_client.post("/v4/improvements/fake_id_123/resolve")
    assert resp.status_code == 200
    data = resp.json()
    assert data["resolved"] is False


def test_v4_quick_notes_submit_invalid(v4_client: TestClient):
    """POST /v4/quick-notes with empty body returns 422."""
    resp = v4_client.post("/v4/quick-notes", json={})
    assert resp.status_code == 422


def test_v4_report_bug_invalid(v4_client: TestClient):
    """POST /v4/report-bug with empty body returns 422."""
    resp = v4_client.post("/v4/report-bug", json={})
    assert resp.status_code == 422
