"""tests/test_seo_api.py - SEO audit API surface tests (issue #533)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    try:
        from backend.server import app
        return TestClient(app)
    except ImportError:
        pytest.skip("Backend server not available")


class TestSeoApiSurface:
    def test_check_catalog_is_public(self, client):
        resp = client.get("/api/seo/checks")
        assert resp.status_code == 200
        checks = resp.json()
        assert len(checks) >= 80
        sample = checks[0]
        for field in ("code", "name", "issue_type", "priority", "pillar",
                      "description", "how_to_fix", "auto_fixable"):
            assert field in sample

    def test_catalog_includes_geo_and_aio(self, client):
        checks = client.get("/api/seo/checks").json()
        pillars = {c["pillar"] for c in checks}
        assert {"technical", "content", "security", "social", "geo", "aio"} <= pillars

    def test_audit_requires_auth(self, client):
        resp = client.post(
            "/api/company/some_company/seo/audit",
            json={"website_url": "https://example.com"},
        )
        assert resp.status_code in (401, 403)

    def test_list_audits_requires_auth(self, client):
        resp = client.get("/api/company/some_company/seo/audits")
        assert resp.status_code in (401, 403)

    def test_delegate_requires_auth(self, client):
        resp = client.post(
            "/api/company/some_company/seo/audits/seoaudit_x/delegate", json={},
        )
        assert resp.status_code in (401, 403)

    def test_fix_requires_auth(self, client):
        resp = client.post(
            "/api/company/some_company/seo/fix",
            json={"repo_path": "workspace/foo"},
        )
        assert resp.status_code in (401, 403)


class TestSkillBinding:
    def test_seo_audit_skill_registered(self):
        from services.skill_bindings import get_skill_bindings

        bindings = get_skill_bindings()
        skill = bindings.get("seo-audit")
        assert skill is not None
        assert skill.is_enabled
        assert "site_audit" in skill.capabilities_added
        assert "seo" in skill.specialist_families

    def test_seo_specialist_gets_skill_bound(self):
        from services.skill_bindings import get_skill_bindings

        bindings = get_skill_bindings()
        assert "seo-audit" in bindings.bind_to_specialist("seo")

    def test_seo_family_capabilities_extended(self):
        from services.specialist import SpecialistService

        svc = SpecialistService.__new__(SpecialistService)
        caps = svc._get_default_capabilities("seo")
        for cap in ("site_audit", "issue_remediation", "geo_optimization",
                    "aio_optimization"):
            assert cap in caps
        assert "seo_audit_engine" in svc._get_default_tools("seo")
