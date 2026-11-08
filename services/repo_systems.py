"""Detect a repository's systems from its own files.

The GitHub scan used to infer systems from repo *topics* only (ecommerce, CMS,
analytics), so a FastAPI + React + MongoDB codebase with no topics reported
zero systems. A repo says what it runs on in its manifests and deploy files:
``requirements.txt`` / ``pyproject.toml``, ``package.json``, ``render.yaml``,
``wrangler.*``, ``Dockerfile``, ``.github/workflows``.

``systems_from_manifests`` is pure (the mapping); ``fetch_repo_systems`` reads
those files through the GitHub contents API with a bounded number of calls.
"""
from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any

from models.company_graph import DetectedSystem, Evidence

log = logging.getLogger("qwen-proxy")

# dependency name (lower-case) -> (system_type, display name)
_PYTHON_DEPS: dict[str, tuple[str, str]] = {
    "fastapi": ("backend", "FastAPI"), "django": ("backend", "Django"),
    "flask": ("backend", "Flask"), "starlette": ("backend", "Starlette"),
    "pymongo": ("database", "MongoDB"), "motor": ("database", "MongoDB"),
    "psycopg2": ("database", "PostgreSQL"), "psycopg2-binary": ("database", "PostgreSQL"),
    "asyncpg": ("database", "PostgreSQL"), "sqlalchemy": ("database", "SQL database"),
    "redis": ("cache", "Redis"), "celery": ("message_queue", "Celery"),
    "openai": ("ai_ml", "OpenAI API"), "anthropic": ("ai_ml", "Anthropic API"),
    "litellm": ("ai_ml", "LiteLLM"), "stripe": ("payment_gateway", "Stripe"),
    "sentry-sdk": ("analytics", "Sentry"), "elasticsearch": ("search", "Elasticsearch"),
}
_JS_DEPS: dict[str, tuple[str, str]] = {
    "react": ("frontend", "React"), "vue": ("frontend", "Vue.js"),
    "next": ("frontend", "Next.js"), "nuxt": ("frontend", "Nuxt"),
    "svelte": ("frontend", "Svelte"), "@angular/core": ("frontend", "Angular"),
    "vite": ("frontend", "Vite"), "express": ("backend", "Express"),
    "@nestjs/core": ("backend", "NestJS"), "mongodb": ("database", "MongoDB"),
    "mongoose": ("database", "MongoDB"), "pg": ("database", "PostgreSQL"),
    "redis": ("cache", "Redis"), "ioredis": ("cache", "Redis"),
    "stripe": ("payment_gateway", "Stripe"), "@stripe/stripe-js": ("payment_gateway", "Stripe"),
    "posthog-js": ("analytics", "PostHog"), "@sentry/react": ("analytics", "Sentry"),
    "algoliasearch": ("search", "Algolia"),
}
# file or directory at the repo root -> (system_type, display name)
_ROOT_FILES: dict[str, tuple[str, str]] = {
    "render.yaml": ("custom", "Render"), "wrangler.toml": ("api_gateway", "Cloudflare Workers"),
    "wrangler.jsonc": ("api_gateway", "Cloudflare Workers"),
    "wrangler.json": ("api_gateway", "Cloudflare Workers"),
    "netlify.toml": ("custom", "Netlify"), "vercel.json": ("custom", "Vercel"),
    "Dockerfile": ("custom", "Docker"), "docker-compose.yml": ("custom", "Docker Compose"),
    "fly.toml": ("custom", "Fly.io"), ".github": ("custom", "GitHub Actions"),
}
_MANIFESTS = ("requirements.txt", "pyproject.toml", "package.json", "frontend/package.json")
_REQ_NAME = re.compile(r"^\s*([A-Za-z0-9_.\-\[\]]+)")


def _python_deps(text: str) -> set[str]:
    names = set()
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip().strip('"\',')
        m = _REQ_NAME.match(line)
        if m:
            names.add(m.group(1).split("[", 1)[0].lower())
    return names


def _js_deps(text: str) -> set[str]:
    try:
        data = json.loads(text)
    except ValueError:
        return set()
    deps: set[str] = set()
    for key in ("dependencies", "devDependencies"):
        deps |= {k.lower() for k in (data.get(key) or {})}
    return deps


def _system(kind: str, name: str, source: str) -> DetectedSystem:
    return DetectedSystem(
        system_type=kind, name=name, confidence=0.85,
        evidence=[Evidence(type="repo_file", value=source, location="repository", confidence=0.85)],
    )


def systems_from_manifests(root_names: list[str], manifests: dict[str, str]) -> list[DetectedSystem]:
    """Systems a repo's root listing and manifest contents show it uses (one per name)."""
    found: dict[str, DetectedSystem] = {}
    for fname in root_names:
        if fname in _ROOT_FILES:
            kind, name = _ROOT_FILES[fname]
            found.setdefault(name, _system(kind, name, fname))
    for path, text in manifests.items():
        table = _JS_DEPS if path.endswith("package.json") else _PYTHON_DEPS
        deps = _js_deps(text) if path.endswith("package.json") else _python_deps(text)
        for dep in sorted(deps):
            if dep in table:
                kind, name = table[dep]
                found.setdefault(name, _system(kind, name, path))
    return list(found.values())


async def _get_text(client: Any, api_url: str, path: str) -> str | None:
    resp = await client.get(f"{api_url}/contents/{path}")
    if resp.status_code != 200:
        return None
    body = resp.json()
    if not isinstance(body, dict) or body.get("encoding") != "base64":
        return None
    return base64.b64decode(body.get("content") or "").decode("utf-8", "replace")


async def fetch_repo_systems(client: Any, api_url: str) -> list[DetectedSystem]:
    """Read the repo root and its manifests (at most 5 GitHub calls); never raises."""
    try:
        resp = await client.get(f"{api_url}/contents")
        if resp.status_code != 200 or not isinstance(resp.json(), list):
            return []
        root = [item.get("name", "") for item in resp.json()]
        manifests = {}
        for path in _MANIFESTS:
            if path.split("/", 1)[0] in root:
                text = await _get_text(client, api_url, path)
                if text:
                    manifests[path] = text
        return systems_from_manifests(root, manifests)
    except Exception as exc:  # noqa: BLE001 - systems are best-effort enrichment
        log.debug("repo systems: could not read %s: %s", api_url, exc)
        return []
