from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from backend.server import app as backend_app


@pytest.fixture
def client():
    """TestClient for backend.server — used by backend-specific tests."""
    return TestClient(backend_app)


@pytest.fixture
def wiki_client():
    """TestClient for backend.server — used by full-stack integration tests.

    Tests that use this fixture should guard against unconfigured auth
    environments by checking login status and calling pytest.skip() if
    the backend is not set up, matching the pattern in test_v4_reliability.py.
    """
    return TestClient(backend_app, raise_server_exceptions=False)
