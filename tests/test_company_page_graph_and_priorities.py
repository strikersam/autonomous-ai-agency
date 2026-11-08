"""Company page: systems shown without a pre-existing graph document, and
priorities editable (production 2026-11-08: 0 systems, priorities missing)."""
from __future__ import annotations

from types import SimpleNamespace

import backend.company_api as api
from models.company_graph import Company, CompanyUpdateRequest


async def test_get_company_creates_the_graph_when_missing(monkeypatch):
    company = Company(id="c1", name="Acme", domain="acme.com", owner_id="u1")
    calls = []

    async def access(cid, user):
        return company

    class _Service:
        async def get_company_graph(self, cid):  # the old path: None without a graph doc
            calls.append("get")
            return None

        async def get_or_create_company_graph(self, cid):
            calls.append("get_or_create")
            return None  # the response model accepts a graph or None

    monkeypatch.setattr(api, "get_company_access", access)
    monkeypatch.setattr(api, "get_company_graph_service", lambda: _Service())
    await api.get_company(company_id="c1", user={}, response=None)
    assert calls == ["get_or_create"]


async def test_patch_priorities_are_cleaned_and_saved(monkeypatch):
    company = Company(id="c1", name="Acme", domain="acme.com", owner_id="u1")
    saved = {}

    async def access(cid, user):
        return company

    class _Store:
        async def update_company(self, c):
            saved["company"] = c
            return c

    class _Service:
        async def get_company_graph(self, cid):
            return None

    monkeypatch.setattr(api, "get_company_access", access)
    monkeypatch.setattr(api, "get_company_graph_store", lambda: _Store())
    monkeypatch.setattr(api, "get_company_graph_service", lambda: _Service())
    req = CompanyUpdateRequest(priorities=["  Rank in AI answers ", "ship weekly", "Ship weekly", ""])
    await api.update_company(company_id="c1", request=req, user={})
    assert saved["company"].priorities == ["Rank in AI answers", "ship weekly"]


def test_update_request_without_priorities_leaves_them_alone():
    assert "priorities" not in CompanyUpdateRequest(name="X").model_dump(exclude_unset=True)
