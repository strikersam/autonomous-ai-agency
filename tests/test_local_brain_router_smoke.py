"""Regression test: backend/server.py must not double-wrap the local_brain_router APIRouter alias.

Background: backend/local_brain_router.py:53 already exports the APIRouter
instance as `router = APIRouter(prefix="/api/local-brain", tags=["local-brain"])`.
backend/server.py originally imported that as
    from backend.local_brain_router import router as local_brain_router_module
then called
    app.include_router(local_brain_router_module.router)
which raised AttributeError at conftest.py import time and broke every
pytest collection on master.

This test fails on master pre-fix (the AttributeError surfaces) and passes
post-fix. Catches re-regression of the same mistake if anyone copies the
double-wrap pattern to a new alias in the future.
"""
from __future__ import annotations

import os


def test_backend_server_app_loads_without_attributeerror() -> None:
    """Importing backend.server.app must not raise AttributeError or NameError."""
    # ADMIN_PASSWORD is required by backend.server at import time. Use the
    # conftest-provided stub when running under pytest; otherwise set a
    # throwaway value here so the import succeeds.
    os.environ.setdefault("ADMIN_PASSWORD", "ci-regression-test-stub")
    from backend.server import app  # noqa: F401 -- import IS the assertion

    assert app is not None


def test_local_brain_routes_are_registered() -> None:
    """The local_brain_router routes must be mounted on the FastAPI app.

    This is the public surface the operator-facing toggle UI relies on. If a
    future PR double-wraps the same alias again, this list will be empty and
    the test will catch the regression pre-merge.
    """
    os.environ.setdefault("ADMIN_PASSWORD", "ci-regression-test-stub")
    from backend.server import app

    paths = {getattr(r, "path", "") for r in app.routes if getattr(r, "path", "")}
    local_brain_paths = sorted(p for p in paths if p.startswith("/api/local-brain"))
    assert local_brain_paths, (
        "No /api/local-brain/* routes were registered on the FastAPI app. "
        "This is the public surface for the cross-machine GLM-5.2 toggle; "
        "if this list is empty, the local_brain_router include_router call "
        "is broken (e.g. the historical double-wrap AttributeError)."
    )
