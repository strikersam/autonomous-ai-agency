"""tests/test_public_kpi.py — public read-only autonomy KPI endpoint.

The autonomy KPIs (agent/kpi.py) were only reachable behind the auth-gated
/api/diagnostics/kpi. /api/kpi/public exposes the same aggregate counters with
no auth so the public site / public Doctor view can show a live KPI strip
(truth-reconciliation brief #6). Only non-sensitive counts are exposed.
"""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_public_kpi_endpoint_needs_no_auth_and_reports_real_counters(client: TestClient) -> None:
    from agent.kpi import get_tracker, reset_tracker

    reset_tracker()
    tracker = get_tracker()
    tracker.record_plan()
    tracker.record_step_applied()
    tracker.record_pr_created()

    r = client.get("/api/kpi/public")  # no Authorization header
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["available"] is True
    assert body["window"] == "cumulative-since-process-start"
    # The genuine snapshot is surfaced and reflects what we just recorded.
    assert body["metrics"]["total_plans"] >= 1
    assert body["metrics"]["steps_applied"] >= 1
    assert body["summary"]["prs_opened"] >= 1
    # Not-yet-instrumented metrics are reported honestly as null, never faked.
    assert body["summary"]["regressions_after_auto_merge"] is None
    assert "run_at" in body

    reset_tracker()


def test_public_kpi_does_not_leak_identifiers(client: TestClient) -> None:
    """The public strip must expose only aggregate counts — no user/company/repo
    or task identifiers."""
    r = client.get("/api/kpi/public")
    assert r.status_code == 200
    flat = r.text.lower()
    for forbidden in ("owner_id", "email", "company_id", "task_id", "repo", "token"):
        assert forbidden not in flat, f"public KPI payload leaked '{forbidden}'"
