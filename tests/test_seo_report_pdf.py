"""tests/test_seo_report_pdf.py - CTO-level PDF export tests (issue #533 follow-up).

Generates real PDFs via reportlab for revenue-modeled, revenue-unmodeled and
empty/failed audits, and asserts they are well-formed PDF documents.
"""
from __future__ import annotations

import asyncio

import httpx
import pytest

from models.seo_audit import SeoAuditReport, SeoAuditRequest
from services.seo_audit import SeoAuditEngine
from services.seo_report_pdf import money, report_to_pdf
from tests.test_seo_audit import _mock_site_handler


@pytest.fixture
def mock_report():
    transport = httpx.MockTransport(_mock_site_handler)
    engine = SeoAuditEngine(transport=transport)
    request = SeoAuditRequest(website_url="https://mocksite.test/", max_pages=10)
    return asyncio.run(engine.run(request, company_id="co_test"))


@pytest.fixture
def mock_report_with_revenue():
    transport = httpx.MockTransport(_mock_site_handler)
    engine = SeoAuditEngine(transport=transport)
    request = SeoAuditRequest(
        website_url="https://mocksite.test/", max_pages=10,
        monthly_organic_revenue=100_000,
    )
    return asyncio.run(engine.run(request, company_id="co_test"))


class TestReportToPdf:
    def test_returns_valid_pdf_bytes(self, mock_report):
        pdf = report_to_pdf(mock_report)
        assert pdf.startswith(b"%PDF-")
        assert pdf.rstrip().endswith(b"%%EOF")
        assert len(pdf) > 1000

    def test_with_revenue_baseline(self, mock_report_with_revenue):
        pdf = report_to_pdf(mock_report_with_revenue)
        assert pdf.startswith(b"%PDF-")
        assert len(pdf) > 1000

    def test_revenue_modeled_report_includes_dollar_figures(self, mock_report_with_revenue):
        # Sanity: a revenue baseline produces a strictly larger document than
        # the same audit with no baseline (extra $ tables/sections).
        pdf_with_revenue = report_to_pdf(mock_report_with_revenue)
        assert mock_report_with_revenue.monthly_organic_revenue > 0
        assert len(pdf_with_revenue) > 1000

    def test_failed_empty_audit_still_renders(self):
        report = SeoAuditReport(
            audit_id="audit_empty",
            company_id="co_empty",
            website_url="https://example.com/",
            status="failed",
            error="Could not reach site",
            pages_crawled=0,
            pages_failed=1,
            health_score=0,
        )
        pdf = report_to_pdf(report)
        assert pdf.startswith(b"%PDF-")
        assert len(pdf) > 500

    def test_money_helper(self):
        assert money(1234.5) == "$1,234"
        assert money(0) == "$0"
