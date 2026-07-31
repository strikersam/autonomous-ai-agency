"""The routing layer's REST surface (``/api/llm/*``).

Two properties matter most here and are asserted repeatedly:

* **No endpoint ever returns key material.** The dashboard renders these
  payloads verbatim, so a leak here is a leak to every viewer.
* **Every read endpoint answers even when the router is off.** A disabled
  router must degrade the page, not break it, so ``/status`` returns a
  shape-compatible payload with ``enabled: false`` and the reason.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from packages.llm import budget as llm_budget
from packages.llm import cache as llm_cache
from packages.llm import config as llm_config
from packages.llm import health as llm_health
from packages.llm import keys as llm_keys
from packages.llm import metrics as llm_metrics
from packages.llm import registry as llm_registry
from packages.llm import router as llm_router
from packages.llm.gateway import build_llm_router

PROVIDERS_YAML = """
providers:
  alpha:
    kind: openai
    base_url: https://alpha.test/v1
    key_env: [ALPHA_KEY]
    tier: free
    priority: 10
"""

MODELS_YAML = """
models:
  alpha-model:
    provider: alpha
    context_window: 32768
    supports_tools: true
    priority: 10
"""


@pytest.fixture
def client(tmp_path, monkeypatch):
    (tmp_path / "providers.yaml").write_text(PROVIDERS_YAML, encoding="utf-8")
    (tmp_path / "models.yaml").write_text(MODELS_YAML, encoding="utf-8")
    monkeypatch.setenv("LLM_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("ALPHA_KEY", "super-secret-alpha-key")
    monkeypatch.setenv("LLM_ROUTER_ENABLED", "true")
    monkeypatch.delenv("LLM_GATEWAY_ENABLED", raising=False)
    for name in ("NVIDIA_API_KEY", "GROQ_API_KEY", "CEREBRAS_API_KEY",
                 "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY",
                 "ANTHROPIC_API_KEY", "OLLAMA_BASE"):
        monkeypatch.delenv(name, raising=False)

    for module in (llm_config, llm_registry, llm_health, llm_keys,
                   llm_cache, llm_budget, llm_metrics, llm_router):
        module.reset()

    app = FastAPI()
    app.include_router(build_llm_router())
    with TestClient(app) as test_client:
        yield test_client

    for module in (llm_config, llm_registry, llm_health, llm_keys,
                   llm_cache, llm_budget, llm_metrics, llm_router):
        module.reset()


# ── Observability ───────────────────────────────────────────────────────────

def test_status_reports_providers(client):
    body = client.get("/api/llm/status").json()
    assert body["enabled"] is True
    assert body["strategy"]
    assert [p["id"] for p in body["providers"]] == ["alpha"]
    assert "queue" in body and "cache" in body and "budget" in body


def test_providers_are_ordered_healthiest_first(client):
    tracker = llm_health.get_tracker()
    tracker.record_success("alpha", latency_ms=50)

    body = client.get("/api/llm/providers").json()
    assert body["enabled"] is True
    assert body["providers"][0]["id"] == "alpha"
    assert body["providers"][0]["available"] is True
    assert "adaptive" in body["strategies"]


def test_no_endpoint_leaks_key_material(client):
    llm_keys.get_ring().acquire("alpha", ["super-secret-alpha-key"],
                                env_names=["ALPHA_KEY"])
    for path in ("/api/llm/status", "/api/llm/providers", "/api/llm/config",
                 "/api/llm/health", "/api/llm/models"):
        assert "super-secret-alpha-key" not in client.get(path).text, f"{path} leaked a key"


def test_config_exposes_variable_names_not_values(client):
    body = client.get("/api/llm/config").json()
    alpha = next(p for p in body["providers"] if p["id"] == "alpha")
    assert alpha["key_env"] == ["ALPHA_KEY"]
    assert alpha["key_count"] == 1
    assert body["router_enabled"] is True
    assert body["gateway_enabled"] is False


def test_health_endpoint_reports_breaker_state(client):
    llm_health.get_tracker().record_failure("alpha", status=500, error="boom")
    body = client.get("/api/llm/health").json()
    entry = next(p for p in body["providers"] if p["provider"] == "alpha")
    assert entry["state"] in {"closed", "open", "half_open"}
    assert entry["last_error"] == "boom"


def test_models_endpoint_returns_capabilities(client):
    body = client.get("/api/llm/models").json()
    alpha = next(m for m in body["models"] if m["id"] == "alpha-model")
    assert alpha["supports_tools"] is True
    assert alpha["context_window"] == 32768


def test_prometheus_metrics_render(client):
    llm_metrics.get_metrics().record_request(
        provider="alpha", model="alpha-model", outcome="success", latency_sec=0.4
    )
    response = client.get("/api/llm/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text
    assert "# TYPE llm_requests_total counter" in body
    assert 'llm_requests_total{model="alpha-model"' in body
    assert "llm_router_uptime_seconds" in body


def test_metrics_json_mirrors_the_exposition(client):
    llm_metrics.get_metrics().record_failure(provider="alpha", status="429", scope="key")
    body = client.get("/api/llm/metrics.json").json()
    assert "llm_failures_total" in body["counters"]
    assert body["uptime_sec"] >= 0


def test_usage_and_cache_endpoints(client):
    assert "total" in client.get("/api/llm/usage").json()
    assert "layers" in client.get("/api/llm/cache").json()
    assert client.delete("/api/llm/cache").json()["cleared"]["response"] == 0


def test_strategy_can_be_switched_at_runtime(client):
    assert client.put("/api/llm/config/strategy",
                      json={"strategy": "cost_optimized"}).status_code == 200
    assert client.get("/api/llm/status").json()["strategy"] == "cost_optimized"


def test_unknown_strategy_is_rejected(client):
    response = client.put("/api/llm/config/strategy", json={"strategy": "nonsense"})
    assert response.status_code == 400
    assert "unknown strategy" in response.json()["detail"]


def test_provider_can_be_taken_out_of_rotation_and_restored(client):
    client.put("/api/llm/providers/alpha/enabled", json={"enabled": False})
    assert llm_health.get_tracker().is_available("alpha") is False

    client.put("/api/llm/providers/alpha/enabled", json={"enabled": True})
    assert llm_health.get_tracker().is_available("alpha") is True


def test_config_reload_rereads_disk(client):
    body = client.post("/api/llm/config/reload").json()
    assert body["reloaded"] is True
    assert body["providers"] >= 1


# ── Gateway mode ────────────────────────────────────────────────────────────

def test_gateway_is_off_by_default(client):
    """Exposing the platform's keys to other applications must be deliberate."""
    response = client.post("/api/llm/v1/chat/completions", json={
        "model": "alpha-model", "messages": [{"role": "user", "content": "hi"}],
    })
    assert response.status_code == 403
    assert "LLM_GATEWAY_ENABLED" in response.json()["detail"]
    assert client.get("/api/llm/v1/models").status_code == 403


def test_gateway_serves_openai_shape_when_enabled(client, monkeypatch):
    import httpx

    monkeypatch.setenv("LLM_GATEWAY_ENABLED", "true")

    def handler(_request):
        return httpx.Response(200, json={
            "model": "alpha-model",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "hello"},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 4, "completion_tokens": 2},
        })

    llm_router.get_router()._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    )

    response = client.post("/api/llm/v1/chat/completions", json={
        "model": "alpha-model",
        "messages": [{"role": "user", "content": "hi"}],
        "temperature": 0.9,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["content"] == "hello"
    assert body["usage"]["prompt_tokens"] == 4
    # The routing audit trail rides along without breaking OpenAI clients.
    assert body["x_router"]["provider"] == "alpha"


def test_gateway_rejects_an_empty_conversation(client, monkeypatch):
    monkeypatch.setenv("LLM_GATEWAY_ENABLED", "true")
    response = client.post("/api/llm/v1/chat/completions",
                           json={"model": "alpha-model", "messages": []})
    assert response.status_code == 400


def test_gateway_model_list_when_enabled(client, monkeypatch):
    monkeypatch.setenv("LLM_GATEWAY_ENABLED", "true")
    body = client.get("/api/llm/v1/models").json()
    assert body["object"] == "list"
    assert any(m["id"] == "alpha-model" for m in body["data"])


# ── Disabled router ─────────────────────────────────────────────────────────

def test_status_is_shape_compatible_when_the_router_is_off(client, monkeypatch):
    """A disabled router degrades the page, never breaks it."""
    monkeypatch.setenv("LLM_ROUTER_ENABLED", "false")
    body = client.get("/api/llm/status").json()

    assert body["enabled"] is False
    assert "LLM_ROUTER_ENABLED" in body["reason"]
    # Same keys the dashboard reads on the enabled path.
    for key in ("providers", "queue", "cache", "budget", "strategy", "strategies"):
        assert key in body
    assert body["providers"] == []


def test_read_endpoints_still_answer_when_the_router_is_off(client, monkeypatch):
    monkeypatch.setenv("LLM_ROUTER_ENABLED", "false")
    for path in ("/api/llm/providers", "/api/llm/health", "/api/llm/models",
                 "/api/llm/usage", "/api/llm/cache", "/api/llm/config",
                 "/api/llm/metrics", "/api/llm/metrics.json"):
        assert client.get(path).status_code == 200, f"{path} failed while disabled"
