"""tests/test_company_list_and_persist_contracts.py

Locks two contracts that automated review surfaced on PR #391:

1. ``CompanyGraphStore.list_companies`` returns a plain ``list[Company]`` —
   NOT a ``(companies, total)`` tuple. Call sites that unpack it as a tuple
   500 for any result count != 2, so this guards against re-introducing that.
2. Workflow activity is persisted onto the **frozen** ``Company`` model via
   ``model_copy`` (into ``integration_config``), not by mutating a nonexistent
   ``activity_log`` attribute (which silently failed).
"""
from __future__ import annotations

import pytest

from models.company_graph import Company


async def test_list_companies_returns_a_plain_list(tmp_path):
    from services.company_graph_store import CompanyGraphStore

    store = CompanyGraphStore(backend="sqlite")
    store._sqlite_store._db_path = str(tmp_path / "list.db")

    result = await store.list_companies(limit=10)
    assert isinstance(result, list), (
        "list_companies must return a list, not a (companies, total) tuple — "
        "tuple-unpacking call sites break for result counts != 2"
    )

    # Seed one company and confirm it still returns a list (not a tuple).
    await store.create_company(Company(name="Acme", domain="acme.com", owner_id="u1"))
    result = await store.list_companies(owner_id="u1", limit=10)
    assert isinstance(result, list)
    assert len(result) == 1 and result[0].name == "Acme"


def test_company_is_frozen_and_activity_goes_through_model_copy():
    company = Company(name="Acme", domain="acme.com", owner_id="u1")

    # Frozen: direct attribute assignment must fail (this is why the old
    # `company.activity_log = []` persist path silently did nothing).
    with pytest.raises(Exception):
        company.integration_config = {"x": 1}

    # The supported path: model_copy with declared fields.
    cfg = dict(company.integration_config or {})
    cfg["workflow_activity"] = [{"run_id": "wfo_1", "verdict": "APPROVED"}]
    updated = company.model_copy(update={"integration_config": cfg})
    assert updated.integration_config["workflow_activity"][0]["run_id"] == "wfo_1"
    # Original is unchanged (immutability preserved).
    assert "workflow_activity" not in (company.integration_config or {})
