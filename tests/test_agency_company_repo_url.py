"""The CEO's per-company 'Improve' directive read ``company.repos[0].url``.

``Company.repos`` is a list of repository *IDs* (strings), so that raised
``'str' object has no attribute 'url'`` on every sixth cycle and aborted the whole
CEO cycle ("Agency tick error"). 2026-11-15.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from agent.agency import Agency, AgentRole, _company_repo_url


class _Store:
    def __init__(self, companies, repos=None, boom=False):
        self._companies, self._repos, self._boom = companies, repos or {}, boom

    async def list_companies(self, limit=100):
        return self._companies

    async def get_repo(self, repo_id):
        if self._boom:
            raise RuntimeError("db down")
        return self._repos.get(repo_id)


def _company(**kw):
    base = dict(id="c1", name="Acme", domain="acme.test", repos=[], repo_connection=None)
    base.update(kw)
    return SimpleNamespace(**base)


def test_repo_id_is_resolved_through_the_store() -> None:
    store = _Store([], {"r1": SimpleNamespace(url="https://github.com/acme/app")})
    assert asyncio.run(_company_repo_url(store, _company(repos=["r1"]))) == "https://github.com/acme/app"


def test_connected_repo_wins_without_a_lookup() -> None:
    conn = SimpleNamespace(owner="acme", repo="app")
    store = _Store([], boom=True)
    assert asyncio.run(_company_repo_url(store, _company(repos=["r1"], repo_connection=conn))) \
        == "https://github.com/acme/app"


def test_no_repo_or_a_failing_store_is_na_not_an_exception() -> None:
    assert asyncio.run(_company_repo_url(_Store([]), _company())) == "N/A"
    assert asyncio.run(_company_repo_url(_Store([], boom=True), _company(repos=["r1"]))) == "N/A"
    assert asyncio.run(_company_repo_url(_Store([]), _company(repos=["gone"]))) == "N/A"


def test_the_improve_directive_is_generated_for_a_company_with_repo_ids(monkeypatch) -> None:
    store = _Store(
        [_company(repos=["r1"])], {"r1": SimpleNamespace(url="https://github.com/acme/app")})
    monkeypatch.setattr("services.company_graph_store.get_company_graph_store", lambda: store)

    class _Svc:
        async def activate_company(self, *a, **k):
            return None

    monkeypatch.setattr("services.company_agency.get_company_agency_service", lambda: _Svc())
    agency = Agency.__new__(Agency)
    agency._cycle_count = 6
    directives = asyncio.run(agency._company_directives({}))
    improve = [d for d in directives if d.role == AgentRole.DEV]
    assert improve, "the sixth-cycle Improve directive must not be lost to an exception"
    assert "https://github.com/acme/app" in improve[0].instruction
