"""Pytest configuration for the backend test suite.

Mongo availability
------------------
The CI job provides a real mongo:7 service (see .github/workflows/ci.yml).
Tests that exercise the full database path simply run against it.

If you're running locally WITHOUT MongoDB, set::

    SKIP_DB_TESTS=1 pytest -x

and any test decorated with ``@pytest.mark.requires_db`` will be skipped.

The ``client`` fixture connects to the real database — it does not patch
``get_db()``.  Mocking at the ``get_db()`` level (for unit tests) is the
responsibility of individual tests, not the shared fixture.

Admin password
--------------
Set ``ADMIN_PASSWORD`` in Render environment variables (single source of truth).
For local development the conftest sets a session-stable default so tests pass
without manual env-var configuration.  Individual test files MUST NOT hardcode
a fallback — read ``os.environ["ADMIN_PASSWORD"]`` directly.
"""
from __future__ import annotations

import os
import secrets

# ── Single source of truth for admin password ────────────────────────────────
# MUST run before ANY import that touches backend.server (which reads
# ADMIN_PASSWORD at module level).  Set via Render env var; conftest provides
# a session-stable random fallback for local dev.

if not os.environ.get("ADMIN_PASSWORD"):
    os.environ["ADMIN_PASSWORD"] = "test-" + secrets.token_hex(20)

# ── Now safe to import backend modules that read ADMIN_PASSWORD ──────────────

import pytest
from fastapi.testclient import TestClient

from backend.server import app as backend_app


# ─── markers ──────────────────────────────────────────────────────────────────

def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "requires_db: mark test as requiring a live MongoDB connection",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if not os.environ.get("SKIP_DB_TESTS"):
        return  # CI always has Mongo — run everything
    skip_db = pytest.mark.skip(reason="SKIP_DB_TESTS=1 — no MongoDB available")
    for item in items:
        if "requires_db" in item.keywords:
            item.add_marker(skip_db)



# ─── Legacy workflow mode for tests (Phase 2 deprecation guard) ──────────
# By default, ALL tests run in legacy mode so AgentRunner.run(),
# Agency.run_cycle(), MultiAgentSwarm.run() etc. work without patching
# every test individually.  Tests that need orchestrator mode explicitly
# override via monkeypatch.setattr + importlib.reload.

import pytest  # noqa: E402 — re-import for fixture decorator clarity


@pytest.fixture(autouse=True)
def _set_legacy_workflow_mode(monkeypatch):
    """Default all tests to legacy workflow mode (Phase 2 compatibility).

    Only patches WORKFLOW_MODE so ``is_legacy_mode()`` returns True naturally.
    Tests that need orchestrator mode can override via
    ``monkeypatch.setattr("...WORKFLOW_MODE", "orchestrator")``.
    """
    monkeypatch.setattr(
        "services.workflow_orchestrator.WORKFLOW_MODE", "legacy"
    )


# ─── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def client() -> TestClient:
    """TestClient for backend.server — used by backend-specific tests.

    Uses the context-manager form so the ASGI lifespan (startup/shutdown) and
    the underlying anyio event loop stay alive for the entire test.  This is
    required for background asyncio tasks (e.g. agent jobs dispatched via
    asyncio.create_task) to survive beyond a single HTTP response — without it,
    the portal is torn down after each request and background tasks are
    cancelled immediately.

    The admin user and indexes are seeded by ensure_bootstrap before the first
    request.  Tests that need to simulate a DB outage must mock ``get_db()``
    *within* the test body, not in this fixture.
    """
    with TestClient(backend_app) as c:
        yield c


@pytest.fixture
def wiki_client() -> TestClient:
    """TestClient with ``raise_server_exceptions=False`` for integration tests.

    Tests using this fixture should guard against unconfigured auth
    environments by checking login status and calling ``pytest.skip()``
    if the backend is not set up.
    """
    return TestClient(backend_app, raise_server_exceptions=False)
