"""Tests for needs_clarification status and /api/tasks/{id}/clarify endpoint."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(backend_app):
    return TestClient(backend_app)


@pytest.fixture()
def auth_headers(client):
    resp = client.post("/api/auth/login", json={"email": "admin@test.local", "password": "testpass"})
    if resp.status_code == 200:
        token = resp.json().get("access_token") or resp.json().get("token")
        if token:
            return {"Authorization": f"Bearer {token}"}
    return {}


@pytest.fixture()
def task_id(client, auth_headers):
    if not auth_headers:
        pytest.skip("No auth token available")
    resp = client.post("/api/tasks/", json={"title": "Test clarification task"}, headers=auth_headers)
    assert resp.status_code == 201
    return resp.json()["task"]["task_id"]


def test_needs_clarification_in_enum():
    from tasks.models import TaskStatus
    assert TaskStatus.NEEDS_CLARIFICATION.value == "needs_clarification"


def test_clarify_endpoint(client, auth_headers, task_id):
    resp = client.patch(f"/api/tasks/{task_id}/clarify", json={"reason": "What format should the output be in?"}, headers=auth_headers)
    assert resp.status_code == 200
    task = resp.json()["task"]
    assert task["status"] == "needs_clarification"
    assert task["blocked_reason"] == "What format should the output be in?"


def test_clarify_logs_entry(client, auth_headers, task_id):
    client.patch(f"/api/tasks/{task_id}/clarify", json={"reason": "Need more info"}, headers=auth_headers)
    task = client.get(f"/api/tasks/{task_id}", headers=auth_headers).json()["task"]
    events = [e["event_type"] for e in task.get("execution_log", [])]
    assert "clarification_requested" in events


def test_clarify_requires_auth(client, task_id):
    resp = client.patch(f"/api/tasks/{task_id}/clarify", json={"reason": "some reason"})
    assert resp.status_code == 401


def test_clarify_requires_reason(client, auth_headers, task_id):
    resp = client.patch(f"/api/tasks/{task_id}/clarify", json={"reason": ""}, headers=auth_headers)
    assert resp.status_code == 422


def test_task_with_story_points(client, auth_headers):
    if not auth_headers:
        pytest.skip("No auth token available")
    resp = client.post("/api/tasks/", json={"title": "SP task", "story_points": 5}, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["task"]["story_points"] == 5


def test_task_with_sprint_id(client, auth_headers):
    if not auth_headers:
        pytest.skip("No auth token available")
    resp = client.post("/api/tasks/", json={"title": "Sprint task", "sprint_id": "sprint_abc123"}, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["task"]["sprint_id"] == "sprint_abc123"


def test_patch_story_points_and_sprint_id(client, auth_headers, task_id):
    resp = client.patch(f"/api/tasks/{task_id}", json={"story_points": 8, "sprint_id": "sprint_xyz"}, headers=auth_headers)
    assert resp.status_code == 200
    task = resp.json()["task"]
    assert task["story_points"] == 8
    assert task["sprint_id"] == "sprint_xyz"
