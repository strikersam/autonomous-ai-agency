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
    """Without NVIDIA key AND without Ollama, the probe must report no_brain."""
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVidiaApiKey", raising=False)
    monkeypatch.setenv("OLLAMA_BASE", "")
    monkeypatch.setenv("OLLAMA_BASE_URL", "")
    body = client.get("/api/autonomy/status").json()
    assert body["brain"]["configured"] is False
    assert body["status"] == "no_brain"
    assert "NVIDIA_API_KEY" in body["missing_secrets"]


def test_brain_configured_with_ollama_fallback(client, monkeypatch):
    """When NVIDIA is absent but Ollama is configured, report brain as ollama."""
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVidiaApiKey", raising=False)
    monkeypatch.setenv("OLLAMA_BASE", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3-coder:30b")
    body = client.get("/api/autonomy/status").json()
    assert body["brain"]["configured"] is True
    assert body["brain"]["provider"] == "ollama"
    assert body["brain"]["model"] == "qwen3-coder:30b"
    assert "NVIDIA_API_KEY" not in body["missing_secrets"]
    assert body["status"] in {"idle", "partial", "autonomous"}


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


def test_self_bootstrap_never_awaited_inline(monkeypatch):
    """Regression: /api/autonomy/status must SCHEDULE self-bootstrap, never
    await it inline. Awaiting onboarding (scan + provisioning + 300s-timeout
    LLM calls) on the request held this public endpoint past Render's 120s
    proxy read timeout — on an ephemeral-SQLite deploy that broke the first
    post-boot call (and the user session behind it) after every restart.

    Drives the handler coroutine directly on one event loop (like the
    production loop) so the in-flight dedup guard is observable across calls.
    """
    import asyncio
    import time as _time

    import backend.server as srv
    import services.self_bootstrap as sb

    async def _slow_bootstrap(**kwargs):
        await asyncio.sleep(300)  # would blow any sane request budget
        return {"status": "created"}

    async def _no_company():
        return None

    monkeypatch.setattr(sb, "ensure_self_company", _slow_bootstrap)
    monkeypatch.setattr(sb, "_find_self_company", _no_company)
    monkeypatch.setattr(sb, "self_bootstrap_enabled", lambda: True)
    monkeypatch.setattr(srv, "_self_bootstrap_task", None)

    async def _scenario():
        t0 = _time.monotonic()
        body1 = await srv.autonomy_status()
        elapsed = _time.monotonic() - t0
        # Second call while the task is still pending must not stack another.
        body2 = await srv.autonomy_status()
        task = srv._self_bootstrap_task
        pending = task is not None and not task.done()
        if pending:
            task.cancel()
        srv._self_bootstrap_task = None
        return elapsed, body1, body2, pending

    elapsed, body1, body2, pending = asyncio.run(_scenario())

    assert elapsed < 30, f"endpoint blocked {elapsed:.1f}s — bootstrap ran inline"
    assert body1["self_bootstrap"]["last_result"] == "bootstrap_scheduled"
    assert body2["self_bootstrap"]["last_result"] == "bootstrapping"
    assert pending, "scheduled bootstrap task should still be in flight"
