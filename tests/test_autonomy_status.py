"""tests/test_autonomy_status.py — public /api/autonomy/status readiness probe.

The probe exists so a misconfigured live deploy (e.g. an unset NVIDIA_API_KEY,
which leaves every agent task with no brain) is *visible* instead of silently
manifesting as "nothing happens". These tests pin that contract.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    # Import failures must fail the suite loudly, not skip it.
    from backend.server import app
    return TestClient(app)


def test_status_is_public_and_well_shaped(client):
    """No auth required; response carries the readiness contract keys."""
    resp = client.get("/api/autonomy/status")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("brain", "loops", "loops_running", "missing_secrets", "status"):
        assert key in body, f"missing key: {key}"
    assert set(body["loops"]) == {
        "log_monitor", "self_healing", "improvement_loop", "trend_watcher",
    }
    assert body["status"] in {"no_brain", "idle", "partial", "autonomous"}


def test_loop_readiness_is_surfaced(client):
    """The probe carries the loop fleet readiness summary (loop-audit)."""
    body = client.get("/api/autonomy/status").json()
    assert "loop_readiness" in body
    lr = body["loop_readiness"]
    # Defensive contract: present and well-shaped, or None if registry missing.
    if lr is not None:
        assert 0 <= lr["score"] <= 100
        assert lr["grade"] in {"A", "B", "C", "D", "F"}
        assert lr["total_loops"] >= 1
        assert set(lr["dimensions"]) == {"maturity", "self_heal", "governance", "safety"}
        assert "drift_ok" in lr


def test_no_brain_when_nvidia_key_absent(client, monkeypatch):
    """Without an NVIDIA key the probe must report no_brain + name the secret."""
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVidiaApiKey", raising=False)
    body = client.get("/api/autonomy/status").json()
    assert body["brain"]["configured"] is False
    assert body["status"] == "no_brain"
    assert "NVIDIA_API_KEY" in body["missing_secrets"]


def test_brain_configured_when_nvidia_key_present(client, monkeypatch):
    """With an NVIDIA key the brain resolves and the secret is no longer flagged."""
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-TESTKEY")
    body = client.get("/api/autonomy/status").json()
    assert body["brain"]["configured"] is True
    assert body["brain"]["model"]  # resolves to the configured default
    assert body["brain"]["provider"] == "nvidia-nim"
    assert "NVIDIA_API_KEY" not in body["missing_secrets"]
    # Brain ready but loops aren't bootstrapped under TestClient → not "no_brain".
    assert body["status"] in {"idle", "partial", "autonomous"}
