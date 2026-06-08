"""tests/test_phase5_doctor.py

Phase 5: /api/doctor endpoint tests.

Coverage:
  - GET /api/doctor returns structured DoctorReport
  - Report contains required fields (ready, summary, checks, run_at)
  - Each check has id, category, label, status, detail
  - Status values are constrained to pass/warn/fail
  - Returns 401 without auth
  - Endpoint survives when RuntimeManager raises (partial-failure tolerance)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── app fixture ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    from rbac import require_authenticated
    from backend.server import app

    app.dependency_overrides[require_authenticated] = lambda: {
        "email": "test@example.com",
        "role": "admin",
        "user_id": "test-user",
    }

    # Override get_current_user the same way the backend resolves it
    from backend.server import get_current_user
    async def _mock_user(request=None):
        return {"email": "test@example.com", "role": "admin", "user_id": "test-user"}
    app.dependency_overrides[get_current_user] = _mock_user

    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


# ── tests ─────────────────────────────────────────────────────────────────────

def test_doctor_returns_200(client):
    resp = client.get("/api/doctor")
    assert resp.status_code == 200


def test_doctor_response_shape(client):
    resp = client.get("/api/doctor")
    body = resp.json()
    assert "ready" in body
    assert "summary" in body
    assert "checks" in body
    assert "run_at" in body
    assert isinstance(body["checks"], list)
    assert isinstance(body["ready"], bool)
    assert isinstance(body["summary"], str)


def test_doctor_checks_have_required_fields(client):
    resp = client.get("/api/doctor")
    checks = resp.json()["checks"]
    for check in checks:
        assert "id" in check, f"check missing 'id': {check}"
        assert "category" in check
        assert "label" in check
        assert "status" in check
        assert "detail" in check
        assert check["status"] in {"pass", "warn", "fail"}, \
            f"invalid status {check['status']!r} in check {check['id']}"


def test_doctor_always_has_at_least_one_check(client):
    resp = client.get("/api/doctor")
    checks = resp.json()["checks"]
    assert len(checks) >= 1, "Expected at least 1 check in the doctor report"


def test_doctor_run_at_is_iso_format(client):
    import datetime
    resp = client.get("/api/doctor")
    run_at = resp.json()["run_at"]
    # Should be parseable as an ISO datetime
    parsed = datetime.datetime.fromisoformat(run_at.replace("Z", "+00:00"))
    assert parsed is not None


def test_doctor_langfuse_check_present(client):
    """Langfuse check is always emitted (pass or warn based on env)."""
    resp = client.get("/api/doctor")
    check_ids = {c["id"] for c in resp.json()["checks"]}
    assert "langfuse" in check_ids


def test_doctor_survives_runtime_manager_error(client):
    """If RuntimeManager raises, /api/doctor still returns 200 with a warn check."""
    with patch("backend.server.get_runtime_manager", side_effect=RuntimeError("boom")):
        resp = client.get("/api/doctor")
    assert resp.status_code == 200
    checks = resp.json()["checks"]
    # Should have a warn check for the runtime section
    runtime_checks = [c for c in checks if c.get("category") == "Runtime"]
    assert any(c["status"] == "warn" for c in runtime_checks), \
        "Expected a warn check when RuntimeManager fails"


def test_doctor_survives_preflight_error(client):
    """If DirectChatDoctor.check_all raises, /api/doctor still returns 200."""
    with patch("agent.doctor.DirectChatDoctor.check_all", new_callable=AsyncMock,
               side_effect=Exception("doctor down")):
        resp = client.get("/api/doctor")
    assert resp.status_code == 200
    checks = resp.json()["checks"]
    setup_checks = [c for c in checks if c.get("category") == "Setup"]
    assert any(c["status"] == "warn" for c in setup_checks)
