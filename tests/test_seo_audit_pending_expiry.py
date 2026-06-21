"""Regression tests for the SEO perpetual-pending guard.

Background: when background-task-style kickoff was used, a 'pending' stub was
written, the background crawl ran, and the result replaced it. On a server
restart between those two writes, the in-memory registry lost the
completion-write, so the GET endpoint saw perpetual 'pending'. This guard
makes that situation self-heal: any pending stub whose started_at is older
than the threshold is auto-failed on next GET.
"""
from __future__ import annotations

import importlib
import os
from datetime import datetime, timedelta, timezone

from models.seo_audit import SeoAuditReport
import services.seo_audit as seo_audit_mod


def _reload_with_expiry(expiry_seconds: float):
    """Reload backend.seo_api with a fresh expiry threshold."""
    os.environ["SEO_AUDIT_PENDING_EXPIRY_SEC"] = str(expiry_seconds)
    import backend.seo_api
    return importlib.reload(backend.seo_api)


def _pending_started(seconds_ago: float) -> SeoAuditReport:
    saved = list(seo_audit_mod._reports.keys())
    audit_id = saved[0] if saved else "seoaudit_test_pending_old"
    if audit_id in seo_audit_mod._reports:
        del seo_audit_mod._reports[audit_id]
    started = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
    return SeoAuditReport(
        audit_id=audit_id,
        company_id="company_test",
        website_url="https://example.com",
        status="pending",
        started_at=started,
    )


def test_pending_stub_older_than_threshold_is_auto_failed() -> None:
    seo_api = _reload_with_expiry(expiry_seconds=1800)
    report = _pending_started(seconds_ago=1801)  # older than threshold
    seo_audit_mod.save_report(report)

    # Call the helper on the saved (registry-resident) report so the test
    # verifies the actual stored state changes after the helper runs.
    saved = seo_audit_mod.get_report(report.audit_id)
    assert saved is not None
    seo_api._expire_stale_pending_report(saved)

    later = seo_audit_mod.get_report(report.audit_id)
    assert later is not None
    assert later.status == "failed"
    assert later.completed_at is not None
    assert "1801s" in later.error or "lost" in later.error.lower()


def test_pending_stub_within_threshold_is_left_alone() -> None:
    seo_api = _reload_with_expiry(expiry_seconds=1800)
    report = _pending_started(seconds_ago=10)

    seo_api._expire_stale_pending_report(report)

    assert report.status == "pending", "fresh pending stub MUST NOT be auto-failed"
    assert report.completed_at is None


def test_non_pending_status_is_never_expired() -> None:
    seo_api = _reload_with_expiry(expiry_seconds=1800)
    kept = SeoAuditReport(
        audit_id="seoaudit_already_success",
        company_id="company_test",
        website_url="https://example.com",
        status="success",
        started_at=datetime.now(timezone.utc) - timedelta(seconds=60_000),
    )

    seo_api._expire_stale_pending_report(kept)

    assert kept.status == "success", "non-pending statuses MUST never be touched"
