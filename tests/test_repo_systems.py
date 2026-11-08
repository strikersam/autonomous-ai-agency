"""Systems from a repo's own files (production 2026-11-08: the agency's
FastAPI + React + MongoDB repo reported 0 systems because only GitHub topics
were read)."""
from __future__ import annotations

import base64
import json
from types import SimpleNamespace

from services.repo_systems import fetch_repo_systems, systems_from_manifests

REQS = "fastapi==0.115\nmotor>=3  # mongo\nredis\nopenai\n"
PKG = json.dumps({"dependencies": {"react": "18"}, "devDependencies": {"vite": "5"}})


def test_manifests_and_deploy_files_become_systems():
    found = {s.name: s.system_type for s in systems_from_manifests(
        ["render.yaml", "wrangler.jsonc", ".github", "README.md"],
        {"requirements.txt": REQS, "frontend/package.json": PKG})}
    assert found == {
        "Render": "custom", "Cloudflare Workers": "api_gateway", "GitHub Actions": "custom",
        "FastAPI": "backend", "MongoDB": "database", "Redis": "cache", "OpenAI API": "ai_ml",
        "React": "frontend", "Vite": "frontend",
    }


def test_unknown_or_broken_manifests_add_nothing():
    assert systems_from_manifests(["README.md"], {"package.json": "{not json"}) == []


class _Client:
    def __init__(self, files):
        self.files, self.calls = files, []

    async def get(self, url):
        self.calls.append(url)
        path = url.split("/contents", 1)[1].lstrip("/")
        if path == "":
            return SimpleNamespace(status_code=200, json=lambda: [{"name": n} for n in
                                                                   ("requirements.txt", "frontend", "render.yaml")])
        if path in self.files:
            body = {"encoding": "base64", "content": base64.b64encode(self.files[path].encode()).decode()}
            return SimpleNamespace(status_code=200, json=lambda: body)
        return SimpleNamespace(status_code=404, json=lambda: {})


async def test_fetch_reads_root_and_present_manifests_only():
    client = _Client({"requirements.txt": REQS, "frontend/package.json": PKG})
    names = {s.name for s in await fetch_repo_systems(client, "https://api.github.com/repos/o/r")}
    assert {"FastAPI", "React", "Render", "MongoDB"} <= names
    assert len(client.calls) <= 5  # bounded: root + manifests that exist
    assert not any(c.endswith("/pyproject.toml") or c.endswith("contents/package.json") for c in client.calls)


async def test_fetch_never_raises():
    class Boom:
        async def get(self, url):
            raise RuntimeError("network down")
    assert await fetch_repo_systems(Boom(), "https://api.github.com/repos/o/r") == []
