"""tests/test_seo_api.py - SEO audit API surface tests (issue #533)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    # Import failures must fail the suite loudly, not skip it.
    from backend.server import app
    return TestClient(app)


class TestSeoApiSurface:
    def test_check_catalog_requires_auth(self, client):
        # Per repo guidelines, only /health, /version and /api/doctor/public
        # are unauthenticated - the catalog is gated like everything else.
        resp = client.get("/api/seo/checks")
        assert resp.status_code in (401, 403)

    def test_catalog_contents_complete(self):
        from services.seo_checks import list_checks

        checks = list_checks()
        assert len(checks) >= 80
        sample = checks[0]
        for field in ("code", "name", "issue_type", "priority", "pillar",
                      "description", "how_to_fix", "auto_fixable"):
            assert hasattr(sample, field)

    def test_catalog_includes_geo_and_aio(self):
        from services.seo_checks import list_checks

        pillars = {c.pillar for c in list_checks()}
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

    def test_export_pdf_requires_auth(self, client):
        resp = client.get(
            "/api/company/some_company/seo/audits/seoaudit_x/export",
            params={"fmt": "pdf"},
        )
        assert resp.status_code in (401, 403)

    def test_export_accepts_pdf_format(self):
        # The export endpoint's fmt Literal must include "pdf" so FastAPI
        # doesn't 422 on a valid request before the auth dependency runs.
        import inspect
        from backend import seo_api

        sig = inspect.signature(seo_api.export_seo_audit, eval_str=True)
        fmt_annotation = sig.parameters["fmt"].annotation
        assert "pdf" in fmt_annotation.__args__


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
