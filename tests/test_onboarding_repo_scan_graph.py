"""Onboarding repo scan writes what the Company page counts: one repo row and
the detected systems (production 2026-11-08 showed 0 repos / 0 systems)."""
from __future__ import annotations

from types import SimpleNamespace

import services.onboarding as ob

URL = "https://github.com/acme/app"


class _Store:
    def __init__(self):
        self.repos, self.systems, self.updated = [], [], []

    async def list_repos(self, cid):
        return list(self.repos)

    async def list_detected_systems(self, company_id, system_type=None):
        return [s for s in self.systems if system_type in (None, s.system_type)]

    async def create_detected_system(self, system, cid):
        self.systems.append(system)

    async def update_repo(self, repo):
        self.updated.append(repo)


class _Graph:
    def __init__(self, store):
        self.store, self.added = store, 0

    async def add_repo(self, company_id, url, provider):
        self.added += 1
        repo = SimpleNamespace(url=url, model_copy=lambda update: SimpleNamespace(url=url, **update))
        self.store.repos.append(repo)
        return repo


def _scan(systems):
    class _Scanner:
        def __init__(self, *a, **k):
            pass

        async def scan_repo(self, url):
            return SimpleNamespace(status="success", inferred_stack=None, detected_systems=systems,
                                   errors=[])
    return _Scanner


async def test_scan_saves_detected_systems_once_and_reuses_the_repo_row(monkeypatch):
    systems = [SimpleNamespace(name="FastAPI", system_type="backend"),
               SimpleNamespace(name="React", system_type="frontend")]
    monkeypatch.setattr(ob, "RepoScanner", _scan(systems))
    svc = object.__new__(ob.OnboardingService)
    svc.store = _Store()
    svc.graph_service = _Graph(svc.store)
    svc._detect_provider = lambda url: "github"

    await svc._scan_repo("c1", URL)
    await svc._scan_repo("c1", URL)  # rescan: same repo, no duplicates

    assert svc.graph_service.added == 1
    assert sorted(s.name for s in svc.store.systems) == ["FastAPI", "React"]
