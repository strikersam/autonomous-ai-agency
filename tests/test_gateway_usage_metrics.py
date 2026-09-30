"""Gateway usage metrics and GET /gateway/metrics."""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

import proxy
from packages.gateway import usage_metrics
from packages.llm.metrics import get_metrics
from tests.gateway_support import (  # noqa: F401
    chat_body,
    clear_dependency_overrides,
    gateway_env,
    json_response,
    make_client,
)


def test_metrics_endpoint_requires_an_api_key(gateway_env):
    gateway_env.setenv("GATEWAY_USAGE_METRICS_ENABLED", "true")
    proxy.app.dependency_overrides.clear()

    assert TestClient(proxy.app).get("/gateway/metrics").status_code == 401


def test_metrics_endpoint_rejects_an_invalid_key(gateway_env):
    proxy.app.dependency_overrides.clear()
    resp = TestClient(proxy.app).get("/gateway/metrics", headers={"Authorization": "Bearer definitely-not-a-key"})
    assert resp.status_code == 403


def test_endpoint_is_404_while_the_toggle_is_off(gateway_env):
    client, _u, _o = make_client(gateway_env)
    assert client.get("/gateway/metrics").status_code == 404


def test_request_is_recorded_with_tokens_latency_and_outcome(gateway_env):
    gateway_env.setenv("GATEWAY_USAGE_METRICS_ENABLED", "true")
    client, _u, _o = make_client(gateway_env)

    assert client.post("/v1/chat/completions", json=chat_body()).status_code == 200
    resp = client.get("/gateway/metrics")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    text = resp.text
    assert 'llm_requests_total{agent="kid_a",model="test-model",outcome="ok",provider="ollama"} 1' in text
    assert 'llm_tokens_total{direction="input",model="test-model",provider="ollama"} 7' in text
    assert 'llm_tokens_total{direction="output",model="test-model",provider="ollama"} 5' in text
    assert "llm_request_duration_seconds_count" in text


def test_nothing_is_recorded_while_off(gateway_env):
    client, _u, _o = make_client(gateway_env)
    client.post("/v1/chat/completions", json=chat_body())
    assert get_metrics().requests.values == {}


def test_upstream_error_status_is_an_error_outcome(gateway_env):
    gateway_env.setenv("GATEWAY_USAGE_METRICS_ENABLED", "true")
    client, _u, _o = make_client(gateway_env, lambda _r: json_response(400, {"error": "bad"}))

    client.post("/v1/chat/completions", json=chat_body())

    assert any('outcome="error"' in line for line in client.get("/gateway/metrics").text.splitlines())


def test_unreachable_upstream_is_recorded_as_an_error(gateway_env):
    gateway_env.setenv("GATEWAY_USAGE_METRICS_ENABLED", "true")

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client, _u, _o = make_client(gateway_env, refuse)
    assert client.post("/v1/chat/completions", json=chat_body()).status_code == 503
    assert 'outcome="error"' in client.get("/gateway/metrics").text


def test_cost_is_attributed_through_the_cost_tracker(gateway_env):
    from packages.ai import cost_tracker

    gateway_env.setenv("GATEWAY_USAGE_METRICS_ENABLED", "true")
    cost_tracker.clear_stats()
    usage_metrics.record_call(
        consumer="c", model="gpt-4o-mini", prompt_tokens=1_000_000, completion_tokens=0,
        latency_sec=0.1, outcome="ok",
    )
    stats = cost_tracker.get_stats()
    assert stats["models"]["gpt-4o-mini"]["prompt_tokens"] == 1_000_000
    expected = cost_tracker.cost_for_tokens("gpt-4o-mini", 1_000_000, 0)
    assert expected > 0
    assert f"llm_cost_usd_total{{model=\"gpt-4o-mini\",provider=\"ollama\"}} {expected!r}" in get_metrics().render()
    cost_tracker.clear_stats()


def test_consumer_label_cardinality_is_capped(gateway_env):
    gateway_env.setenv("GATEWAY_USAGE_METRICS_ENABLED", "true")
    for i in range(usage_metrics.MAX_CONSUMER_LABELS + 25):
        usage_metrics.record_call(
            consumer=f"consumer-{i}", model="m", prompt_tokens=1, completion_tokens=1,
            latency_sec=0.0, outcome="ok",
        )
    agents = {labels for labels in get_metrics().requests.values}
    distinct = {dict(labels)["agent"] for labels in agents}
    assert len(distinct) == usage_metrics.MAX_CONSUMER_LABELS + 1
    assert "other" in distinct
    assert usage_metrics.consumer_label("consumer-0") == "consumer-0", "an admitted consumer keeps its label"


def test_metrics_never_contain_the_raw_key(gateway_env):
    gateway_env.setenv("GATEWAY_USAGE_METRICS_ENABLED", "true")
    client, _u, _o = make_client(gateway_env, key_id=None, key="raw-key-value-999")
    headers = {"Authorization": "Bearer raw-key-value-999"}

    client.post("/v1/chat/completions", json=chat_body(), headers=headers)
    text = client.get("/gateway/metrics", headers=headers).text

    assert "raw-key-value-999" not in text
    assert 'agent="sha256:' in text


def test_provider_is_derived_from_the_model_prefix():
    assert usage_metrics.provider_for("nvidia/nemotron") == "nvidia"
    assert usage_metrics.provider_for("qwen3-coder:30b") == "ollama"
