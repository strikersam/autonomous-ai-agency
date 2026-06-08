"""Tests for /api/agile/* endpoints."""
from __future__ import annotations

import os

import pytest


@pytest.fixture()
def auth_headers(client):
    """Get auth headers for an admin user."""
    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    resp = client.post("/api/auth/login", json={"email": "admin@test.local", "password": admin_password})
    if resp.status_code == 200:
        token = resp.json().get("access_token") or resp.json().get("token")
        if token:
            return {"Authorization": f"Bearer {token}"}
    return {}


def test_list_sprints_empty(client):
    resp = client.get("/api/agile/sprints")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert isinstance(data["data"], list)


def test_create_sprint_requires_auth(client):
    resp = client.post("/api/agile/sprints", json={"name": "Sprint 1", "goal": "Ship it"})
    assert resp.status_code == 401


def test_create_and_list_sprint(client, auth_headers):
    if not auth_headers:
        pytest.skip("No auth token available in test environment")
    resp = client.post("/api/agile/sprints", json={"name": "Sprint 1", "goal": "Ship it"}, headers=auth_headers)
    assert resp.status_code == 201
    sprint = resp.json()["data"]
    assert sprint["name"] == "Sprint 1"
    assert sprint["goal"] == "Ship it"
    assert sprint["status"] == "planning"
    sprint_id = sprint["sprint_id"]

    list_resp = client.get("/api/agile/sprints")
    assert list_resp.status_code == 200
    ids = [s["sprint_id"] for s in list_resp.json()["data"]]
    assert sprint_id in ids


def test_start_sprint(client, auth_headers):
    if not auth_headers:
        pytest.skip("No auth token available in test environment")
    create = client.post("/api/agile/sprints", json={"name": "Sprint Start Test"}, headers=auth_headers)
    assert create.status_code == 201
    sprint_id = create.json()["data"]["sprint_id"]

    start = client.post(f"/api/agile/sprints/{sprint_id}/start", json={"duration_days": 7}, headers=auth_headers)
    assert start.status_code == 200
    assert start.json()["data"]["status"] == "active"


def test_complete_sprint(client, auth_headers):
    if not auth_headers:
        pytest.skip("No auth token available in test environment")
    create = client.post("/api/agile/sprints", json={"name": "Sprint Complete Test"}, headers=auth_headers)
    sprint_id = create.json()["data"]["sprint_id"]
    client.post(f"/api/agile/sprints/{sprint_id}/start", json={}, headers=auth_headers)

    complete = client.post(f"/api/agile/sprints/{sprint_id}/complete", headers=auth_headers)
    assert complete.status_code == 200
    assert complete.json()["data"]["sprint"]["status"] == "completed"


def test_velocity(client):
    resp = client.get("/api/agile/velocity")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "predicted_velocity" in data
    assert "sprint_count" in data
    assert "history" in data


def test_start_nonexistent_sprint(client, auth_headers):
    if not auth_headers:
        pytest.skip("No auth token available in test environment")
    resp = client.post("/api/agile/sprints/doesnotexist/start", json={}, headers=auth_headers)
    assert resp.status_code == 404


def test_sprint_metrics_fields(client, auth_headers):
    if not auth_headers:
        pytest.skip("No auth token available in test environment")
    create = client.post("/api/agile/sprints", json={"name": "Metrics Sprint"}, headers=auth_headers)
    sprint = create.json()["data"]
    metrics = sprint["metrics"]
    for field in ("total_points", "completed_points", "health", "days_remaining", "completion_percentage", "burndown_rate"):
        assert field in metrics, f"Missing metrics field: {field}"
