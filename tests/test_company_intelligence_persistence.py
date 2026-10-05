"""Regression: Intelligence screen competitors/keywords must survive a PATCH round-trip.

``Company`` is ``extra="forbid"`` and the SQLite store writes explicit columns, so
values sent via ``PATCH /api/company/{id}`` used to be silently dropped and the
screen reloaded empty.
"""
from __future__ import annotations

from models.company_graph import Company
from services.company_graph_store import CompanyGraphStore

COMPETITORS = [{"name": "Rival", "url": "https://rival.example", "track": ["pricing"]}]
KEYWORDS = [{"keyword": "linen shirts", "tracked": True, "category": "Fashion"}]


def test_company_model_declares_intelligence_fields():
    company = Company(name="Acme", domain="acme.com")
    updated = company.model_copy(
        update={"intelligence_competitors": COMPETITORS, "intelligence_keywords": KEYWORDS}
    )
    dumped = updated.model_dump()
    assert dumped["intelligence_competitors"] == COMPETITORS
    assert dumped["intelligence_keywords"] == KEYWORDS


async def test_sqlite_store_round_trips_intelligence_data(tmp_path):
    store = CompanyGraphStore(backend="sqlite")
    store._sqlite_store._db_path = str(tmp_path / "intel.db")

    company = await store.create_company(Company(name="Acme", domain="acme.com", owner_id="u1"))
    await store.update_company(
        company.model_copy(
            update={"intelligence_competitors": COMPETITORS, "intelligence_keywords": KEYWORDS}
        )
    )

    loaded = await store.get_company(company.id)
    assert loaded is not None
    assert loaded.intelligence_competitors == COMPETITORS
    assert loaded.intelligence_keywords == KEYWORDS
