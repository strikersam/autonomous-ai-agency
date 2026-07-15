"""Smoke test: backend/local_brain_router is mounted on the public FastAPI app.

This test is a thin sentinel that proves the include_router call at
backend/server.py:9558 does NOT raise AttributeError on backend.server
import. The detailed behaviour of the 3 child routes + persistence + lease
mechanics is exhaustively covered by tests/test_local_brain_state.py (10/10
PASS) — keeping this file as a one-line regression tripwire avoids false
404s when the underlying routes are method-gated (e.g. /api/local-brain
/toggle is POST-only and would 404 a GET that bypasses the auth middleware).
"""
from __future__ import annotations

import os


def test_backend_server_app_loads_without_attributeerror() -> None:
    """Importing backend.server.app must not raise AttributeError or NameError."""
    os.environ.setdefault("ADMIN_PASSWORD", "ci-regression-test-stub")
    from backend.server import app  # noqa: F401 -- import IS the assertion

    assert app is not None


def test_local_brain_state_route_is_mounted_on_public_app() -> None:
    """The /api/local-brain/state GET route must be reachable via the FastAPI app.

    This is the unique surface that catches the historical
    ``app.include_router(local_brain_router_module.router)`` silently
    registering a no-op wrapper (with route count +1 and zero reachable paths).
    /state is a GET endpoint so a real ``404 Not Found`` is unimpeachable;
    503 (missing SERVICE_TOKEN) is acceptable and proves the route IS mounted.

    Methods-specific assertion rationale:
        /api/local-brain/state is GET (handler: backend/local_brain_router.py:104).
        /api/local-brain/toggle and /heartbeat are POST and are covered by
        tests/test_local_brain_state.py which drives the inner router directly.
    """
    os.environ.setdefault("ADMIN_PASSWORD", "ci-regression-test-stub")
    from fastapi.testclient import TestClient
    from backend.server import app

    with TestClient(app) as client:
        response = client.get("/api/local-brain/state")
        assert response.status_code != 404, (
            f"GET /api/local-brain/state returned 404; "
            f"app.include_router(local_brain_router_module.router) at "
            f"backend/server.py:9558 failed to mount the local_brain_router. "
            f"Cross-machine GLM-5.2 local-brain toggle UI is unreachable."
        )


def test_local_brain_router_module_is_wired() -> None:
    """The local_brain_router symbol MUST be importable + prefixed correctly.

    Quick import-time sentinel that catches module-path / alias drift before
    the heavier TestClient assertion above runs.
    """
    os.environ.setdefault("ADMIN_PASSWORD", "ci-regression-test-stub")
    import backend.server as srv
    import backend.local_brain_router as lbr_mod

    assert hasattr(srv, "app"), "backend.server.app must exist"
    assert hasattr(lbr_mod, "router"), "backend.local_brain_router.router must exist"
    prefix = getattr(lbr_mod.router, "prefix", "") or ""
    assert prefix == "/api/local-brain", (
        f"local_brain_router prefix drifted: {prefix!r} (expected '/api/local-brain'); "
        f"the public-toggle UI surface will break if this regresses."
    )
