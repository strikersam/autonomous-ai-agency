"""tests/test_runtimes_health_endpoint.py — N2 acceptance: GET /runtimes/health
includes a `hermes` entry (and every other registered runtime) so the Doctor
screen can surface runtime online/offline + version.

Roadmap item N2 — surface Hermes (and all runtimes) status in the Doctor UI.
The backend already exposes GET /runtimes/health backed by the runtime
manager's health_summary(); this test pins the contract so a future refactor
can't silently drop Hermes from the response.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def hermes_only_manager(monkeypatch):
    """Build a RuntimeManager with only internal_agent + Hermes registered.

    Mirrors the render.yaml production config (RUNTIME_EXTERNAL_DISABLED=true,
    RUNTIME_HERMES_ENABLED=true) so the test reflects what real deployments
    see on /runtimes/health.
    """
    _OTHER_FLAGS = (
        "RUNTIME_GOOSE_ENABLED",
        "RUNTIME_AIDER_ENABLED",
        "RUNTIME_OPENCODE_ENABLED",
        "RUNTIME_CLAUDE_CODE_ENABLED",
        "RUNTIME_JCODE_ENABLED",
        "RUNTIME_DOCKER_ENABLED",
        "AGENT_MODE_DOCKER",
        "RUNTIME_OPENHANDS_ENABLED",
        "TASK_HARNESS_ENABLED",
    )
    monkeypatch.setenv("RUNTIME_EXTERNAL_DISABLED", "true")
    monkeypatch.setenv("RUNTIME_HERMES_ENABLED", "true")
    for flag in _OTHER_FLAGS:
        monkeypatch.delenv(flag, raising=False)

    import runtimes.manager as rm_mod
    return rm_mod._build_default_manager()


def test_runtimes_health_includes_hermes_entry(hermes_only_manager):
    """GET /runtimes/health must include a `hermes` entry when the adapter is
    registered — that's the contract the Doctor screen's RuntimeHealthPanel
    relies on to surface the Hermes online/offline badge (N2)."""
    # list_runtimes() is what GET /runtimes/ returns; health_summary() backs
    # GET /runtimes/health. Both must surface hermes so the UI can render it
    # whether it polls the list or the health endpoint.
    listed = hermes_only_manager.list_runtimes()
    listed_ids = {r["runtime_id"] for r in listed}
    assert "hermes" in listed_ids, (
        f"Hermes must be registered so it appears in GET /runtimes/ — got {sorted(listed_ids)}. "
        "Doctor screen's RuntimeHealthPanel reads GET /runtimes/health; without hermes in the "
        "registry, the operator can never see Hermes status from the UI (N2 acceptance)."
    )
    # The internal_agent floor is always registered.
    assert "internal_agent" in listed_ids


def test_runtimes_health_endpoint_returns_hermes_via_testclient(monkeypatch, hermes_only_manager):
    """End-to-end (router level): GET /runtimes/health returns JSON with a
    `health` list that includes a hermes entry. The adapter's health_check is
    mocked so the test doesn't depend on a running Hermes sidecar."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from runtimes.api import runtime_router
    from packages.auth.rbac import require_authenticated
    from runtimes.base import RuntimeHealth

    # Inject a cached health snapshot for hermes so health_summary() returns it
    # without making a real HTTP probe. This is the same shape
    # HermesAdapter.health_check() returns on a real /health hit.
    mgr = hermes_only_manager
    mgr._health._cache["hermes"] = RuntimeHealth(
        runtime_id="hermes",
        available=True,
        version="0.4.2",
        latency_ms=12.3,
        details={"status": "ok", "runtime": "hermes", "ours": True, "version": "0.4.2"},
    )
    mgr._health._cache["internal_agent"] = RuntimeHealth(
        runtime_id="internal_agent",
        available=True,
        version=None,
        latency_ms=2.1,
    )

    monkeypatch.setattr("runtimes.api.get_runtime_manager", lambda: mgr)

    app = FastAPI()
    app.include_router(runtime_router)
    app.dependency_overrides[require_authenticated] = lambda: {
        "email": "test@example.com", "role": "admin",
    }
    client = TestClient(app)

    response = client.get("/runtimes/health")
    assert response.status_code == 200
    body = response.json()
    assert "health" in body
    by_id = {h["runtime_id"]: h for h in body["health"]}
    assert "hermes" in by_id, (
        f"GET /runtimes/health must surface hermes — Doctor's RuntimeHealthPanel "
        f"reads this endpoint. Got: {sorted(by_id)}"
    )
    hermes_entry = by_id["hermes"]
    assert hermes_entry["available"] is True
    assert hermes_entry["version"] == "0.4.2"
