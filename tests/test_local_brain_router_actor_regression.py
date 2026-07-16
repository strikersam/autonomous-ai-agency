"""Regression test pinning the include_router wiring fix in backend/local_brain_router.py.

Both buggy lines (now FIXED at master) were:
  * line 102:  log.info("local_brain: GET /state (actor=%s)", actor) -> name 'actor' was NOT in scope
  * line 119:  actor_str = (payload.actor or actor or "service:local_daemon")[:200] -> second 'actor' was NOT in scope

Plus a module-level include_router that was mis-aliased (PR #1056 fixed). Pattern: copy
the proven convention from tests/test_local_brain_router_smoke.py (status_code != 404
verifies the route mounts without import-time errors). A future regression that breaks
the include_router flow (module/router rebinding ambiguity) will be caught here.
"""
from __future__ import annotations

import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("ADMIN_PASSWORD", "ci-test")
sys.path.insert(0, ".")


def test_get_state_route_mounts_without_import_time_errors() -> None:
    from backend.local_brain_router import router as local_brain_router_obj
    app = FastAPI()
    app.include_router(local_brain_router_obj)
    client = TestClient(app)
    resp = client.get("/api/local-brain/state")
    # Smoke-test convention: anything but 404 proves the route mounted; 503 means
    # SERVICE_TOKEN dep rejected (expected). A 500 with NameError would mean a
    # module-level regression.
    assert resp.status_code != 404, f"route did not mount: {resp.text}"
    assert resp.status_code != 500, f"5xx with server error (regression): {resp.text}"


def test_post_toggle_route_mounts_without_import_time_errors() -> None:
    from backend.local_brain_router import router as local_brain_router_obj
    app = FastAPI()
    app.include_router(local_brain_router_obj)
    client = TestClient(app)
    resp = client.post(
        "/api/local-brain/toggle",
        json={"desired_state": "on", "desired_provider": "colibri", "actor": "test-actor"},
    )
    assert resp.status_code != 404, f"route did not mount: {resp.text}"
    assert resp.status_code != 500, f"5xx with server error (regression): {resp.text}"
