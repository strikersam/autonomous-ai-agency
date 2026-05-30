"""End-to-end test: onboarding across all domain types provisions specialists
(agents) with the right skills (capabilities) and context (tools + system_types).

This drives the REAL services end to end against a real SQLite store:
    OnboardingService -> SpecialistService -> CompanyGraphService -> SQLiteStore

Only the website *fetch* is stubbed (the test environment has no outbound
network / no Chromium); each domain type returns a representative
WebsiteScanResult of exactly the shape the real scanner produces. Everything
downstream — website persistence, system-type detection, family mapping,
capability/tool/context assignment, persistence and retrieval — is real code.

Regression coverage for a cluster of bugs that made onboarding silently
provision **zero** agents:
  * SQLiteStore.create_website / update_website referenced ``doc["company_id"]``
    (KeyError) and never persisted inferred_stack / detected_systems;
  * Company.onboarding_status Literal rejected the lifecycle states the service
    writes ("in_progress"/"paused"/"failed"/"cancelled");
  * _prepare_doc couldn't JSON-encode nested datetimes (detected_systems);
  * SpecialistProvisionRequest had no ``tools``/``config`` fields the service read;
  * the framework-derived "frontend"/"backend" pseudo-types were fed into the
    strict SystemType context field, raising ValidationError.
"""
from __future__ import annotations

import sys
from datetime import datetime

import pytest

pytest.importorskip("pydantic")
pytest.importorskip("aiosqlite")


def _models():
    from models.company_graph import (
        WebsiteScanResult, DetectedSystem, StackInference, Evidence,
    )
    return WebsiteScanResult, DetectedSystem, StackInference, Evidence


def _ds(system_type, name, conf=0.95):
    _, DetectedSystem, _, Evidence = _models()
    return DetectedSystem(
        system_type=system_type, name=name, confidence=conf,
        evidence=[Evidence(type="header", value=name, location="test", confidence=conf)],
    )


def _profiles():
    _, _, StackInference, _ = _models()
    # host -> (detected_systems, inferred_stack, expected specialist families)
    return {
        "shop.example-store.com": (
            [_ds("CMS", "Shopify"), _ds("payment_gateway", "Stripe")],
            StackInference(cms=["Shopify"], analytics=["Google Analytics"]),
            {"analytics", "data", "backend", "frontend", "docs", "security", "operations"},
        ),
        "crm.example-saas.com": (
            [_ds("CRM", "Salesforce"), _ds("analytics", "Google Analytics")],
            StackInference(frameworks=["React"]),
            {"analytics", "data", "backend", "frontend", "operations"},
        ),
        "blog.example-media.com": (
            [_ds("CMS", "WordPress"), _ds("analytics", "Matomo")],
            StackInference(cms=["WordPress"], languages=["PHP"]),
            {"analytics", "data", "backend", "frontend", "docs"},
        ),
        "app.example-app.com": (
            [_ds("database", "PostgreSQL")],
            StackInference(frameworks=["React", "Express"], databases=["PostgreSQL"]),
            {"backend", "data", "infra", "frontend"},
        ),
        "help.example-support.com": (
            [_ds("support", "Zendesk"), _ds("chat", "Intercom")],
            StackInference(),
            {"operations", "docs", "backend", "frontend"},
        ),
        "mkt.example-marketing.com": (
            [_ds("marketing_automation", "HubSpot")],
            StackInference(analytics=["HubSpot Analytics"]),
            {"analytics", "data", "backend", "operations"},
        ),
        "erp.example-corp.com": (
            [_ds("ERP", "SAP")],
            StackInference(),
            {"operations", "backend", "data"},
        ),
        "static.example-jamstack.com": (
            [],
            StackInference(frameworks=["Vue"], analytics=["Plausible"]),
            {"analytics", "data", "backend", "frontend"},
        ),
    }


@pytest.fixture
def wired(tmp_path, monkeypatch):
    """Real services sharing one temp-DB SQLite store, with the website fetch stubbed."""
    try:
        from services.company_graph_store import CompanyGraphStore
        from services.company_graph import CompanyGraphService
        from services.specialist import SpecialistService
        from services.onboarding import OnboardingService
        import services.scanner as scanner_mod
    except (ImportError, ModuleNotFoundError) as e:  # pragma: no cover
        pytest.skip(f"company graph services not importable: {e}")

    WebsiteScanResult, _, StackInference, _ = _models()
    profiles = _profiles()

    dispatch = CompanyGraphStore(backend="sqlite")
    dispatch._sqlite_store._db_path = str(tmp_path / "onboard.db")
    graph_service = CompanyGraphService(store=dispatch)
    specialist_service = SpecialistService(store=dispatch)
    onboarding = OnboardingService(
        store=dispatch, graph_service=graph_service,
        specialist_service=specialist_service,
    )

    async def fake_scan_website(self, website_url, scan_depth="standard",
                                include_sitemap=True, max_pages=20):
        host = website_url.split("://", 1)[-1].split("/", 1)[0]
        detected, stack, _ = profiles.get(host, ([], StackInference(), set()))
        return WebsiteScanResult(
            scan_id=f"scan_{host}", website_url=website_url, status="success",
            started_at=datetime.utcnow(), completed_at=datetime.utcnow(),
            detected_systems=detected, inferred_stack=stack, pages_scanned=1,
        )

    monkeypatch.setattr(scanner_mod.WebsiteScanner, "scan_website", fake_scan_website)
    return graph_service, specialist_service, onboarding


@pytest.mark.asyncio
@pytest.mark.parametrize("host", list(_profiles().keys()))
async def test_onboarding_provisions_specialists_with_right_skills_and_context(host, wired):
    graph_service, specialist_service, onboarding = wired
    expected_families = _profiles()[host][2]

    company = await graph_service.create_company(
        name=host.split(".")[1], domain=host, owner_id="u_e2e",
    )
    progress = await onboarding.start_onboarding(
        company_id=company.id, website_urls=[f"https://{host}"],
        auto_provision_specialists=True, create_workflows=True,
    )

    # Onboarding ran to completion with no errors.
    assert progress.status == "completed", progress.errors
    assert not progress.errors, progress.errors

    # The website (with its scan results) round-tripped through storage.
    websites = await graph_service.store.list_websites(company.id)
    assert len(websites) == 1, "website was not persisted / not linked to company"
    assert websites[0].scan_status == "success"

    # Specialists (agents) were spun up with exactly the expected families.
    specialists = await specialist_service.list_specialists(company_id=company.id)
    got_families = {s.family for s in specialists}
    assert got_families == expected_families, (
        f"{host}: expected {sorted(expected_families)}, got {sorted(got_families)}"
    )

    # Every provisioned agent carries real skills (capabilities) and tools.
    for s in specialists:
        assert s.is_provisioned and s.status == "available"
        assert s.capabilities, f"{s.family} has no skills"
        assert s.tools, f"{s.family} has no tools"
        # Context (system_types) must be valid SystemType values when present.
        from typing import get_args
        from models.company_graph import SystemType
        valid = set(get_args(SystemType))
        assert all(st in valid for st in s.system_types), s.system_types


@pytest.mark.asyncio
async def test_specialist_context_matches_detected_systems(wired):
    """A detected system's type must show up as context on at least one agent."""
    graph_service, specialist_service, onboarding = wired
    host = "shop.example-store.com"

    company = await graph_service.create_company(name="shop", domain=host, owner_id="u1")
    await onboarding.start_onboarding(
        company_id=company.id, website_urls=[f"https://{host}"],
    )

    specialists = await specialist_service.list_specialists(company_id=company.id)
    all_context = {st for s in specialists for st in s.system_types}
    # The CMS + payment_gateway detections must be reflected as agent context.
    assert "CMS" in all_context
    assert "payment_gateway" in all_context
    assert "analytics" in all_context
