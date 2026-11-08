"""Company page: systems shown without a pre-existing graph document, and
priorities editable (production 2026-11-08: 0 systems, priorities missing)."""
from __future__ import annotations

from types import SimpleNamespace

import backend.company_api as api
from models.company_graph import Company, CompanyUpdateRequest


class _Cursor:
    def __init__(self, docs):
        self.docs = docs

    def __aiter__(self):
        async def gen():
            for d in self.docs:
                yield dict(d)
        return gen()


class _Coll:
    def __init__(self, docs=()):
        self.docs, self.inserts = list(docs), 0

    def find(self, query):
        return _Cursor([d for d in self.docs if d.get("company_id") == query["company_id"]])

    async def find_one(self, query):
        return next((dict(d) for d in self.docs if d.get("company_id") == query["company_id"]), None)

    async def insert_one(self, doc):
        self.inserts += 1


class _DB:
    def __init__(self, **colls):
        self._colls = colls

    def __getattr__(self, name):
        return self._colls.setdefault(name, _Coll())


def _mongo_store(db, company):
    from services.company_graph_store import MongoDBStore

    store = MongoDBStore.__new__(MongoDBStore)
    store._db = db
    store._get_db = lambda: db

    async def get_company(cid):
        return company if cid == company.id else None
    store.get_company = get_company
    return store


async def test_graph_view_without_a_stored_graph_shows_saved_systems():
    """Production: systems saved, no company_graphs doc -> graph=None -> 0 systems."""
    company = Company(id="c1", name="Acme", domain="acme.com", owner_id="u1")
    db = _DB(detected_systems=_Coll([{"_id": "s1", "company_id": "c1", "system_type": "backend", "name": "FastAPI",
                                      "confidence": 0.9, "evidence": []}]),
             repos=_Coll([{"_id": "r1", "company_id": "c1", "url": "https://github.com/a/b", "provider": "github",
                           "name": "b", "full_name": "a/b"}]))
    store = _mongo_store(db, company)

    assert await store.get_company_graph("c1") is None  # default unchanged for writers
    view = await store.get_company_graph("c1", allow_missing=True)
    assert [s.name for s in view.detected_systems] == ["FastAPI"]
    assert len(view.repos) == 1
    assert db.company_graphs.inserts == 0  # a read writes nothing
    assert await store.get_company_graph("gone", allow_missing=True) is None


async def test_get_company_route_reads_the_view_without_writing(monkeypatch):
    company = Company(id="c1", name="Acme", domain="acme.com", owner_id="u1")
    calls = []

    async def access(cid, user):
        return company

    class _Service:
        async def get_company_graph(self, cid, **kw):
            calls.append(kw)
            return None

        async def get_or_create_company_graph(self, cid):
            raise AssertionError("GET must not create graph documents")

    monkeypatch.setattr(api, "get_company_access", access)
    monkeypatch.setattr(api, "get_company_graph_service", lambda: _Service())
    await api.get_company(company_id="c1", user={}, response=None)
    assert calls == [{"allow_missing": True}]


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
