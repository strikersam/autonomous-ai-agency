"""
conftest.py — pytest fixtures and configuration for the E2E test suite.

Registered markers:
  e2e   — end-to-end tests requiring live services (browser + server)

Shared fixtures:
  base_url      — the backend URL (default: http://localhost:8001)
  proxy_url     — the proxy URL (default: http://localhost:8000)
  mobile_page   — a Playwright page pre-configured at 390×844 (iPhone 14 size)
"""
from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "e2e: end-to-end tests requiring live services")


@pytest.fixture(scope="session")
def base_url() -> str:
    import os
    return os.environ.get("RELAY_BASE_URL", "http://localhost:8001").rstrip("/")


@pytest.fixture(scope="session")
def proxy_url() -> str:
    import os
    return os.environ.get("PROXY_BASE_URL", "http://localhost:8000").rstrip("/")


@pytest.fixture
def mobile_page(browser):  # noqa: ANN001 — Playwright Browser injected by pytest-playwright
    """A browser page pre-configured for mobile viewport (390×844 — iPhone 14)."""
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844},
        ignore_https_errors=True,
    )
    page = ctx.new_page()
    yield page
    ctx.close()
