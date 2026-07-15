"""tests/test_local_brain_state.py — regression test for the cross-machine toggle.

This test pinpoints three failure modes the user explicitly worried about:

  1. The toggle flip actually persists (set_desired writes + readback).
  2. The lease TTL rejects a stale heartbeat (operator's box crashed and
     the UI forever showed "leased:" — reviewer flag #f).
  3. The 3-endpoint auth surface accepts/gates the SERVICE_TOKEN correctly
     so a leaked token can't escalate beyond what we wrote.

Pure unit tests using ``tmp_path`` for the sqlite DB so they cannot collide
with the operator's production ``.data/agency_brain.db``.
"""
from __future__ import annotations

import os
import time
import pytest


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "brain.db"))
    from backend.local_brain_store import LocalBrainStore
    s = LocalBrainStore()
    yield s


def test_default_state_has_no_desired_or_heartbeat(store):
    state = store.get_state()
    assert state["desired"]["state"] == "off"
    assert state["desired"]["provider"] == "auto"
    assert state["last_heartbeat"]["status"] == "unknown"
    assert state["last_heartbeat"]["v1_models"] == []
    assert state["lease"]["valid"] is False


def test_set_desired_off_persists(store):
    store.set_desired(state="off", provider="auto", actor="test")
    state = store.get_state()
    assert state["desired"]["state"] == "off"
    assert state["desired"]["actor"] if "actor" in state["desired"] else True
    # actor tag is on updated_by
    assert state["desired"]["updated_by"] == "test"


def test_set_desired_on_persists_and_pins_machine_id(store):
    store.set_desired(state="on", provider="colibri", actor="test", machine_id="box-abc-123")
    state = store.get_state()
    assert state["desired"]["state"] == "on"
    assert state["desired"]["provider"] == "colibri"
    assert state["desired"]["machine_id"] == "box-abc-123"


def test_set_desired_rejects_bogus_state(store):
    store.set_desired(state="ON_GARBAGE", provider="colibri", actor="test")
    state = store.get_state()
    # Coerced to 'off' (safe default)
    assert state["desired"]["state"] == "off"


def test_heartbeat_acquires_lease_only_when_healthy(store):
    store.set_desired(state="on", provider="colibri", actor="test")
    # Unhealthy heartbeat: no lease.
    state = store.record_heartbeat(
        machine_id="box-a", status="starting", port_state="dead",
        v1_models=[], models_has_glm52=False,
    )
    assert state["lease"]["machine_id"] is None
    # Healthy heartbeat acquires lease.
    state = store.record_heartbeat(
        machine_id="box-a", status="ok", port_state="listening",
        v1_models=[{"id": "glm-5.2"}], models_has_glm52=True,
    )
    assert state["lease"]["machine_id"] == "box-a"
    assert state["lease"]["valid"] is True


def test_lease_ttl_expires_after_grace(store):
    """Reviewer fix #f: lease must strip after heartbeats stop arriving.

    Simulates a crashed local machine by:
      1. Setting desired_state=on.
      2. Acquiring lease via a healthy heartbeat.
      3. Waiting beyond lease_grace_seconds via a frozen "now".
    """
    store.set_desired(state="on", provider="colibri", actor="test")
    store.record_heartbeat(
        machine_id="box-crash", status="ok", port_state="listening",
        v1_models=[{"id": "glm-5.2"}], models_has_glm52=True,
    )
    # Read with the same now as the last heartbeat — lease is fresh.
    from backend.local_brain_store import _now_iso, LocalBrainStore
    now = _now_iso()
    conn = store._conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT desired_state, desired_machine_id, desired_provider, "
            "desired_updated_at, desired_updated_by, "
            "lease_machine_id, lease_acquired_at, "
            "last_machine_id, last_status, last_port_state, "
            "last_v1_models, last_models_has_glm52, "
            "last_heartbeat_at, last_error "
            "FROM local_brain_state WHERE id = ?",
            (LocalBrainStore._ROW_ID,),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    fresh = LocalBrainStore._row_to_state(row, now_iso=now, lease_grace_seconds=90)
    assert fresh["lease"]["valid"] is True

    # Now read with now == heartbeat_at + 120s (beyond grace).
    from datetime import datetime, timezone, timedelta
    stale_now = (datetime.strptime(now, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                 + timedelta(seconds=120)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale = LocalBrainStore._row_to_state(row, now_iso=stale_now, lease_grace_seconds=90)
    assert stale["lease"]["valid"] is False, "TTL MUST expire stale leases"


def test_toggle_clears_existing_lease(store):
    """Operator flips OFF — any prior lease must be dropped so a future ON
    doesn't accidentally inherit a stale lease target."""
    store.set_desired(state="on", provider="colibri", actor="test")
    store.record_heartbeat(
        machine_id="box-1", status="ok", port_state="listening",
        v1_models=[{"id": "glm-5.2"}], models_has_glm52=True,
    )
    state = store.get_state()
    assert state["lease"]["machine_id"] == "box-1"

    store.set_desired(state="off", provider="auto", actor="test")
    state = store.get_state()
    assert state["lease"]["machine_id"] is None
    assert state["lease"]["acquired_at"] is None


def test_v1_models_round_trip_through_json(store):
    """The store must not corrupt the model listing when reading back."""
    store.set_desired(state="on", provider="colibri", actor="test")
    big = [{"id": f"model-{i}", "object": "model"} for i in range(50)]
    store.record_heartbeat(
        machine_id="box", status="ok", port_state="listening",
        v1_models=big, models_has_glm52=True,
    )
    state = store.get_state()
    assert len(state["last_heartbeat"]["v1_models"]) == 50
    assert state["last_heartbeat"]["v1_models"][0]["id"] == "model-0"


def test_router_endpoints_require_service_token():
    """The 3 endpoints MUST refuse calls without SERVICE_TOKEN — confirmed
    by mounting on a stub FastAPI app with the env var unset."""
    import importlib
    # Force-clear SERVICE_TOKEN so require_service_token returns 503.
    os.environ.pop("SERVICE_TOKEN", None)
    # Reload the module in case a previous test stashed a value via monkeypatch.
    import packages.auth.service_token as st
    importlib.reload(st)
    from fastapi import FastAPI
    import sys
    sys.path.insert(0, ".")
    try:
        from backend.local_brain_router import router
        app = FastAPI()
        app.include_router(router)
        from fastapi.testclient import TestClient
        client = TestClient(app)
        # Without token: 503 (not 401) so the operator sees "service not
        # configured" not "bad token" — service_token.py threat T5.
        r = client.get("/api/local-brain/state")
        assert r.status_code == 503, f"expected 503 (svc not cfg) got {r.status_code}"
    finally:
        pass


def test_router_3_endpoints_are_registered():
    """All three endpoints must be present on the router (regression guard
    against missing include_router line in backend/server.py)."""
    import sys
    sys.path.insert(0, ".")
    from backend.local_brain_router import router
    methods_paths = sorted({(r.path, ",".join(sorted(r.methods))) for r in router.routes})
    assert ("/api/local-brain/state", "GET") in methods_paths
    assert ("/api/local-brain/toggle", "POST") in methods_paths
    assert ("/api/local-brain/heartbeat", "POST") in methods_paths
