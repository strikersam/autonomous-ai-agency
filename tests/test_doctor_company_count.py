"""The public doctor must count companies where the agency actually keeps them.

Regression (production 2026-11-07): /api/doctor/public said "Connected (0
companies)" while CompanyAgency was activating 5. The doctor counted through
db.get_store() (DB_NAME default "llm_platform") but companies live in the
company graph store (DB_NAME default "agency_core").
"""
from __future__ import annotations

from fastapi.testclient import TestClient

import backend.server as server
import services.company_graph_store as cgs


class _Store:
    async def count_companies(self) -> int:
        return 5


def test_doctor_counts_companies_from_company_graph_store(monkeypatch) -> None:
    monkeypatch.setattr(cgs, "_graph_store", _Store())
    resp = TestClient(server.app, raise_server_exceptions=False).get("/api/doctor/public")
    assert resp.status_code == 200, resp.text
    storage = next(c for c in resp.json()["checks"] if c["id"] == "storage")
    assert storage["status"] == "pass"
    assert storage["detail"] == "Connected (5 companies)"
