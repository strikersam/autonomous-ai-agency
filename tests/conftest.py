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
"""
from __future__ import annotations

import os

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


# ─── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def client() -> TestClient:
    """TestClient for backend.server — used by backend-specific tests.

    The app's lifespan runs (including ensure_bootstrap) so the admin user
    and indexes are present before the first request.  Tests that need to
    simulate a DB outage must mock ``get_db()`` *within* the test body, not
    in this fixture.
    """
    return TestClient(backend_app)


@pytest.fixture
def wiki_client() -> TestClient:
    """TestClient with ``raise_server_exceptions=False`` for integration tests.

    Tests using this fixture should guard against unconfigured auth
    environments by checking login status and calling ``pytest.skip()``
    if the backend is not set up.
    """
    return TestClient(backend_app, raise_server_exceptions=False)
