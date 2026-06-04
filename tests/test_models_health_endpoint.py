"""Tests for GET /v1/models/health endpoint and router.health.get_health_status()."""
from __future__ import annotations

import pytest

import proxy
from router import health as health_module


@pytest.fixture(autouse=True)
def _reset_health_cache(monkeypatch):
    """Isolate health cache state between tests."""
    health_module.invalidate_cache()
    yield
    health_module.invalidate_cache()


@pytest.fixture()
def api_client(monkeypatch):
    from fastapi.testclient import TestClient

    def fake_verify():
        return proxy.AuthContext(
            key="test-key",
            email="test@example.com",
            department="engineering",
            key_id="kid_test",
            source="store",
        )

    proxy.app.dependency_overrides[proxy.verify_api_key] = fake_verify
    client = TestClient(proxy.app, raise_server_exceptions=False)
    yield client
    proxy.app.dependency_overrides.clear()


# ── Unit tests for get_health_status() ───────────────────────────────────────

def test_get_health_status_returns_pending_before_first_check(monkeypatch):
    monkeypatch.setenv("ROUTER_HEALTH_CHECK_ENABLED", "false")
    from router.health import get_health_status
    status = get_health_status()
    assert "status" in status
    assert "models" in status
    assert isinstance(status["models"], list)
    assert "model_count" in status
    assert "ttl_seconds" in status
    assert "enabled" in status
    assert "ollama_base" in status


def test_get_health_status_disabled_has_empty_models(monkeypatch):
    monkeypatch.setenv("ROUTER_HEALTH_CHECK_ENABLED", "false")
    from router.health import get_health_status, invalidate_cache
    invalidate_cache()
    status = get_health_status()
    assert status["enabled"] is False
    assert status["models"] == []
    assert status["model_count"] == 0


def test_get_health_status_cache_age_none_before_first_probe(monkeypatch):
    monkeypatch.setenv("ROUTER_HEALTH_CHECK_ENABLED", "false")
    from router.health import get_health_status, invalidate_cache
    invalidate_cache()
    status = get_health_status()
    assert status["cache_age_seconds"] is None


def test_get_health_status_after_mock_probe(monkeypatch):
    """Simulate a successful Ollama probe by directly writing cache state."""
    import time
    monkeypatch.setenv("ROUTER_HEALTH_CHECK_ENABLED", "true")
    health_module._cache_models = {"qwen3-coder:30b", "deepseek-r1:32b"}
    health_module._cache_ts = time.monotonic()
    health_module._ever_fetched = True

    from router.health import get_health_status
    status = get_health_status()
    assert status["status"] == "ok"
    assert status["model_count"] == 2
    assert "qwen3-coder:30b" in status["models"]
    assert "deepseek-r1:32b" in status["models"]
    assert status["cache_age_seconds"] is not None
    assert status["cache_age_seconds"] >= 0


# ── HTTP endpoint tests ───────────────────────────────────────────────────────

def test_models_health_endpoint_returns_200(api_client, monkeypatch):
    monkeypatch.setenv("ROUTER_HEALTH_CHECK_ENABLED", "false")
    resp = api_client.get("/v1/models/health")
    assert resp.status_code == 200


def test_models_health_endpoint_requires_auth():
    from fastapi.testclient import TestClient
    client = TestClient(proxy.app, raise_server_exceptions=False)
    resp = client.get("/v1/models/health")
    assert resp.status_code in (401, 403)


def test_models_health_endpoint_response_shape(api_client, monkeypatch):
    monkeypatch.setenv("ROUTER_HEALTH_CHECK_ENABLED", "false")
    resp = api_client.get("/v1/models/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "models" in data
    assert "model_count" in data
    assert isinstance(data["models"], list)
    assert isinstance(data["model_count"], int)
    assert "ollama_base" in data
    assert "ttl_seconds" in data
