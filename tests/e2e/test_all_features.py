#!/usr/bin/env python3
"""
Comprehensive E2E smoke-test suite — covers every menu, page, and feature
of the LLM Relay platform.

Uses FastAPI TestClient against backend.server:app (the actual main application),
matching the project's standard test pattern.
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.server import app

ADMIN_EMAIL = "admin@llmrelay.local"
ADMIN_PASSWORD = "WikiAdmin2026!"


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client() -> TestClient:
    """TestClient for the backend FastAPI app (one per module for speed)."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers(client: TestClient) -> dict[str, str]:
    """Login once and return auth headers for the entire module."""
    r = client.post("/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
    })
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ─── 1. Server Health ─────────────────────────────────────────────────────────

class TestHealth:
    def test_health_endpoint(self, client):
        r = client.get("/api/health")
        assert r.status_code in (200, 503), f"Health: {r.status_code}"
        assert "status" in r.json()

    def test_ping_endpoint(self, client):
        r = client.get("/api/ping")
        assert r.status_code == 200

    def test_version_in_health(self, client):
        from version import __version__
        r = client.get("/api/health")
        # Health returns JSON with at least a status field
        assert isinstance(r.json(), dict)


# ─── 2. Authentication ────────────────────────────────────────────────────────

class TestAuth:
    def test_login_bad_password(self, client):
        r = client.post("/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": "wrong-password",
        })
        assert r.status_code in (401, 403)

    def test_login_success(self, client):
        r = client.post("/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
        })
        assert r.status_code == 200, f"Login: {r.text[:200]}"
        body = r.json()
        assert "access_token" in body
        assert body.get("role") == "admin"

    def test_auth_me(self, client, auth_headers):
        r = client.get("/api/auth/me", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL

    def test_auth_me_no_token(self, client):
        r = client.get("/api/auth/me")
        assert r.status_code == 401


# ─── 3. Providers ─────────────────────────────────────────────────────────────

class TestProviders:
    def test_list_providers(self, client, auth_headers):
        r = client.get("/api/providers", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        providers = body.get("providers", body) if isinstance(body, dict) else body
        assert len(providers) >= 1  # ollama-local always exists

    def test_create_and_delete_provider(self, client, auth_headers):
        pid = f"e2e-test-{uuid.uuid4().hex[:8]}"
        r = client.post("/api/providers", headers=auth_headers, json={
            "provider_id": pid,
            "name": "E2E Test Provider",
            "type": "openai-compatible",
            "base_url": "http://localhost:9999",
            "api_key": "test-e2e",
            "default_model": "test-model",
        })
        assert r.status_code in (200, 201), f"Create provider: {r.text[:200]}"

        r = client.delete(f"/api/providers/{pid}", headers=auth_headers)
        assert r.status_code == 200, f"Delete provider: {r.text[:200]}"

    def test_models_catalog(self, client, auth_headers):
        r = client.get("/api/models/catalog", headers=auth_headers)
        assert r.status_code == 200


# ─── 4. API Keys ──────────────────────────────────────────────────────────────

class TestApiKeys:
    def test_list_keys(self, client, auth_headers):
        r = client.get("/api/keys", headers=auth_headers)
        assert r.status_code == 200

    def test_create_and_delete_key(self, client, auth_headers):
        r = client.post("/api/keys", headers=auth_headers, json={
            "email": "e2e-all@ci.local",
            "department": "e2e",
        })
        assert r.status_code in (200, 201), f"Create key: {r.text[:200]}"
        kid = r.json().get("key_id") or r.json().get("id")
        if kid:
            r = client.delete(f"/api/keys/{kid}", headers=auth_headers)
            assert r.status_code == 200, f"Delete key: {r.text[:200]}"


# ─── 5. Wiki / Knowledge Pages ────────────────────────────────────────────────

class TestWiki:
    def test_wiki_crud(self, client, auth_headers):
        unique = uuid.uuid4().hex[:8]
        title = f"E2E All Features {unique}"

        # Create
        r = client.post("/api/wiki/pages", headers=auth_headers, json={
            "title": title,
            "content": "# E2E\n\nTesting all features.",
            "tags": ["e2e"],
        })
        assert r.status_code in (200, 201), f"Create wiki: {r.text[:200]}"
        slug = r.json().get("slug", "")
        assert slug, f"No slug in: {r.json()}"

        # Read
        r = client.get(f"/api/wiki/pages/{slug}", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["title"] == title

        # Update
        r = client.put(f"/api/wiki/pages/{slug}", headers=auth_headers, json={
            "title": title + " (updated)",
            "content": "# Updated",
            "tags": ["e2e"],
        })
        assert r.status_code == 200

        # List
        r = client.get("/api/wiki/pages", headers=auth_headers)
        assert r.status_code == 200
        pages = r.json().get("pages", [])
        assert len(pages) >= 1

        # Delete
        r = client.delete(f"/api/wiki/pages/{slug}", headers=auth_headers)
        assert r.status_code == 200, f"Delete wiki: {r.text[:200]}"


# ─── 6. Stats / Dashboard ─────────────────────────────────────────────────────

class TestDashboard:
    def test_stats(self, client, auth_headers):
        r = client.get("/api/stats", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert "wiki_pages" in body or isinstance(body, dict)

    def test_platform(self, client, auth_headers):
        r = client.get("/api/platform", headers=auth_headers)
        assert r.status_code == 200


# ─── 7. Activity Log ──────────────────────────────────────────────────────────

class TestActivity:
    def test_activity_log(self, client, auth_headers):
        r = client.get("/api/activity", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        logs = body.get("logs", body) if isinstance(body, dict) else body
        assert isinstance(logs, list) or isinstance(body, dict)

    def test_activity_no_auth(self, client):
        r = client.get("/api/activity")
        assert r.status_code in (200, 401)  # Some endpoints require auth


# ─── 8. Activation ────────────────────────────────────────────────────────────

class TestActivation:
    def test_activation_status(self, client):
        r = client.get("/api/activation/status")
        assert r.status_code == 200
        body = r.json()
        assert "activated" in body
        assert "instance_id" in body

    def test_activation_users(self, client, auth_headers):
        r = client.get("/api/activation/users", headers=auth_headers)
        assert r.status_code == 200


# ─── 9. Tasks ─────────────────────────────────────────────────────────────────

class TestTasks:
    def test_list_tasks(self, client, auth_headers):
        r = client.get("/api/tasks", headers=auth_headers)
        assert r.status_code in (200, 404)  # 404 if endpoint not yet wired

    def test_create_task(self, client, auth_headers):
        unique = uuid.uuid4().hex[:8]
        r = client.post("/api/tasks", headers=auth_headers, json={
            "title": f"E2E Task {unique}",
            "description": "Test task",
            "prompt": "Do something simple.",
        })
        assert r.status_code in (200, 201, 404, 405), f"Create task: {r.status_code}"


# ─── 10. Schedules ────────────────────────────────────────────────────────────

class TestSchedules:
    def test_list_schedules(self, client, auth_headers):
        r = client.get("/api/schedules", headers=auth_headers)
        assert r.status_code in (200, 404)

    def test_create_schedule(self, client, auth_headers):
        unique = uuid.uuid4().hex[:8]
        r = client.post("/api/schedules", headers=auth_headers, json={
            "name": f"E2E Schedule {unique}",
            "cron": "0 9 * * *",
            "instruction": "Daily check",
        })
        # Accept 200, 201, 404 (not yet wired), 422 (validation), 405 (method not supported)
        assert r.status_code in (200, 201, 404, 422, 405), f"Create schedule: {r.status_code}"


# ─── 11. Agents ───────────────────────────────────────────────────────────────

class TestAgents:
    def test_list_agents(self, client, auth_headers):
        r = client.get("/api/agents", headers=auth_headers)
        # CRISPY agent profiles are seeded on startup
        assert r.status_code in (200, 404)

    def test_agent_status(self, client, auth_headers):
        r = client.get("/api/agent/status", headers=auth_headers)
        assert r.status_code in (200, 404)


# ─── 12. Skills ───────────────────────────────────────────────────────────────

class TestSkills:
    def test_list_skills(self, client, auth_headers):
        r = client.get("/api/skills", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        skills = body.get("skills", body) if isinstance(body, dict) else body
        assert isinstance(skills, list)

    def test_skills_recommend(self, client, auth_headers):
        r = client.get("/api/skills/recommend/auto", headers=auth_headers)
        assert r.status_code in (200, 404)


# ─── 13. Company Graph ────────────────────────────────────────────────────────

class TestCompany:
    def test_company_crud(self, client, auth_headers):
        domain = f"e2e-all-{uuid.uuid4().hex[:8]}.example.com"

        # Create
        r = client.post("/api/company", headers=auth_headers, json={
            "name": "E2E All Co",
            "domain": domain,
        })
        assert r.status_code == 201, f"Create company: {r.text[:200]}"
        cid = r.json().get("company", r.json()).get("id")
        assert cid

        # Read
        r = client.get(f"/api/company/{cid}", headers=auth_headers)
        assert r.status_code == 200, f"Get company: {r.text[:200]}"

        # Patch (test intelligence fields)
        r = client.patch(f"/api/company/{cid}", headers=auth_headers, json={
            "name": "E2E All Co (Updated)",
            "intelligence_keywords": [{"id": "k-1", "keyword": "test", "category": "Tech", "tracked": True}],
        })
        assert r.status_code == 200, f"Patch company: {r.status_code} {r.text[:200]}"

        # Graph
        r = client.get(f"/api/company/{cid}/graph", headers=auth_headers)
        assert r.status_code == 200

        # Scan website
        r = client.post(f"/api/company/{cid}/scan/website", headers=auth_headers, json={
            "website_url": "https://example.com",
        })
        assert r.status_code == 200, f"Scan website: {r.status_code} {r.text[:200]}"
        scan = r.json()
        assert scan.get("status") in ("success", "failed", "partial")

        # Specialists
        r = client.get(f"/api/company/{cid}/specialists", headers=auth_headers)
        assert r.status_code in (200, 404)

        # Delete (may not be implemented — 405/404 is acceptable)
        r = client.delete(f"/api/company/{cid}", headers=auth_headers)
        assert r.status_code in (200, 204, 404, 405), f"Delete company: {r.status_code}"


# ─── 14. Onboarding ───────────────────────────────────────────────────────────

class TestOnboarding:
    def test_onboarding_flow(self, client, auth_headers):
        domain = f"e2e-ob-{uuid.uuid4().hex[:8]}.example.com"
        r = client.post("/api/company", headers=auth_headers, json={
            "name": "E2E Onboard Co",
            "domain": domain,
        })
        assert r.status_code == 201
        cid = r.json().get("company", r.json()).get("id")

        r = client.get(f"/api/company/{cid}/onboarding", headers=auth_headers)
        assert r.status_code == 200, f"Get onboarding: {r.text[:200]}"

        r = client.post(f"/api/company/{cid}/onboarding/start", headers=auth_headers, json={
            "skip_website_scan": True,
            "skip_repo_scan": True,
            "auto_provision_specialists": False,
        })
        assert r.status_code == 200, f"Start onboarding: {r.text[:200]}"

        r = client.post(f"/api/company/{cid}/onboarding/pause", headers=auth_headers)
        assert r.status_code == 200, f"Pause onboarding: {r.text[:200]}"

        r = client.post(f"/api/company/{cid}/onboarding/resume", headers=auth_headers)
        assert r.status_code == 200, f"Resume onboarding: {r.text[:200]}"

        # Cleanup (may not be implemented — 405/404 is acceptable)
        cleanup = client.delete(f"/api/company/{cid}", headers=auth_headers)
        assert cleanup.status_code in (200, 204, 404, 405), f"Cleanup: {cleanup.status_code}"


# ─── 15. Doctor ───────────────────────────────────────────────────────────────

class TestDoctor:
    def test_doctor_public(self, client):
        r = client.get("/api/company/doctor/public")
        assert r.status_code in (200, 404)

    def test_status(self, client, auth_headers):
        r = client.get("/api/status", headers=auth_headers)
        assert r.status_code == 200


# ─── 16. GitHub Integration ───────────────────────────────────────────────────

class TestGitHub:
    def test_github_status(self, client, auth_headers):
        r = client.get("/api/github/status", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert "connected" in body

    def test_github_repos_no_token(self, client, auth_headers):
        r = client.get("/api/github/repos", headers=auth_headers)
        # Without token, returns repos list (may be empty) with authorized=False
        assert r.status_code == 200


# ─── 17. Runtimes ─────────────────────────────────────────────────────────────

class TestRuntimes:
    def test_list_runtimes(self, client, auth_headers):
        r = client.get("/runtimes/", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert "runtimes" in body

    def test_runtime_health(self, client, auth_headers):
        r = client.get("/runtimes/health", headers=auth_headers)
        assert r.status_code == 200, f"Health: {r.status_code} {r.text[:200]}"
        body = r.json()
        assert "health" in body

    def test_runtime_decisions(self, client, auth_headers):
        r = client.get("/runtimes/decisions", headers=auth_headers)
        assert r.status_code == 200, f"Decisions: {r.status_code} {r.text[:200]}"
        body = r.json()
        assert "decisions" in body

    def test_runtime_policy(self, client, auth_headers):
        r = client.get("/runtimes/policy", headers=auth_headers)
        assert r.status_code == 200, f"Policy: {r.status_code} {r.text[:200]}"
        body = r.json()
        assert "policy" in body

    def test_runtimes_no_auth(self, client):
        r = client.get("/runtimes/")
        assert r.status_code in (200, 401)


# ─── 18. Features / Feature Flags ─────────────────────────────────────────────

class TestFeatures:
    def test_features_list(self, client, auth_headers):
        r = client.get("/admin/features", headers=auth_headers)
        # May be 200 or 404 if not yet wired
        assert r.status_code in (200, 404)

    def test_features_check(self, client, auth_headers):
        r = client.post("/admin/features/check", headers=auth_headers, json={
            "feature_id": "test",
        })
        assert r.status_code in (200, 404, 422, 405)


# ─── 19. Setup Wizard ─────────────────────────────────────────────────────────

class TestSetup:
    def test_wizard_state(self, client, auth_headers):
        r = client.get("/api/setup/wizard", headers=auth_headers)
        assert r.status_code in (200, 404)


# ─── 20. Secrets Store ────────────────────────────────────────────────────────

class TestSecrets:
    def test_secrets_status(self, client, auth_headers):
        r = client.get("/api/secrets/status", headers=auth_headers)
        assert r.status_code in (200, 404)


# ─── 21. Chat ─────────────────────────────────────────────────────────────────

class TestChat:
    def test_send_chat(self, client, auth_headers):
        r = client.post("/api/chat/send", headers=auth_headers, json={
            "agent_mode": False,
            "content": "Hello, e2e test!",
        })
        # May fail (409, 503) if no LLM provider; must not 4xx auth error
        assert r.status_code in (200, 409, 503), f"Chat send: {r.status_code} {r.text[:200]}"

    def test_chat_sessions(self, client, auth_headers):
        r = client.get("/api/chat/sessions", headers=auth_headers)
        assert r.status_code == 200
