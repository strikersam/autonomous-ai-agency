"""Regression: POST /seo/audit must not hold the request open for the crawl.

A bot-protected site (nike.com behind Akamai) can take minutes to crawl. When
the endpoint awaited the whole crawl, the proxy in front of the API timed the
request out and the dashboard showed a network error. The endpoint now returns
a 'pending' stub and the crawl replaces it when done; the dashboard polls.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import backend.seo_api as seo_api
from models.seo_audit import SeoAuditReport, SeoAuditRequest
from services.seo_audit import get_report


class _SlowEngine:
    """Engine stub whose crawl only finishes when the test releases it."""

    release: asyncio.Event

    async def run(self, request, company_id=None, audit_id=None) -> SeoAuditReport:
        await self.release.wait()
        return SeoAuditReport(
            audit_id=audit_id, company_id=company_id,
            website_url=request.website_url, status="failed", error="blocked",
        )


class _HangingEngine:
    async def run(self, request, company_id=None, audit_id=None) -> SeoAuditReport:
        await asyncio.sleep(3600)
        raise AssertionError("unreachable")


def _patch_access(monkeypatch) -> None:
    async def fake_access(company_id, user):
        return SimpleNamespace(id=company_id)

    monkeypatch.setattr(seo_api, "get_company_access", fake_access)


def test_audit_returns_pending_before_crawl_finishes(monkeypatch) -> None:
    _patch_access(monkeypatch)
    monkeypatch.setattr(seo_api, "SeoAuditEngine", _SlowEngine)

    async def scenario() -> None:
        _SlowEngine.release = asyncio.Event()
        stub = await seo_api.run_seo_audit(
            company_id="co_bg", request=SeoAuditRequest(website_url="https://www.nike.com"),
            user={"id": "u"},
        )
        assert stub.status == "pending"
        assert get_report(stub.audit_id).status == "pending"

        _SlowEngine.release.set()
        await asyncio.gather(*list(seo_api._audit_tasks))
        final = get_report(stub.audit_id)
        assert final.status == "failed" and final.error == "blocked"

    asyncio.run(scenario())


def test_hung_crawl_is_recorded_as_failed(monkeypatch) -> None:
    _patch_access(monkeypatch)
    monkeypatch.setattr(seo_api, "SeoAuditEngine", _HangingEngine)
    monkeypatch.setattr(seo_api, "_SEO_AUDIT_MAX_SECONDS", 0.05)

    async def scenario() -> None:
        stub = await seo_api.run_seo_audit(
            company_id="co_bg", request=SeoAuditRequest(website_url="https://www.nike.com"),
            user={"id": "u"},
        )
        await asyncio.gather(*list(seo_api._audit_tasks))
        final = get_report(stub.audit_id)
        assert final.status == "failed"
        assert final.completed_at is not None
        assert "did not finish" in final.error

    asyncio.run(scenario())
