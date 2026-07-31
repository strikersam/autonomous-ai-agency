"""Backwards compatibility of the routing layer (ADR-008 §8, Golden Rule).

The contract: ``failover_chat_completion`` keeps its exact signature, return
type, and raised exception whichever implementation serves it. Callers —
``agent/loop.py`` above all — must not be able to tell, and the operator must
be able to roll back with one environment variable rather than a revert.
"""
from __future__ import annotations

import httpx
import pytest

from packages.ai.failover_client import BrainFailoverExhausted, FailoverResult
from packages.llm import budget as llm_budget
from packages.llm import config as llm_config
from packages.llm import cache as llm_cache
from packages.llm import config as llm_config
from packages.llm import health as llm_health
from packages.llm import keys as llm_keys
from packages.llm import metrics as llm_metrics
from packages.llm import registry as llm_registry
from packages.llm import router as llm_router
from packages.llm.compat import (
    openai_body_from_response,
    request_from_openai_payload,
    should_use_router,
)
from packages.llm.types import Attempt, LLMResponse, ToolCall, Usage

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

ROUTING_YAML = """
routing:
  strategy: priority
  retry:
    max_attempts: 3
    base_delay_sec: 0.0
    max_delay_sec: 0.0
    jitter: 0.0
    budget_sec: 10.0
"""


@pytest.fixture
def routed(tmp_path, monkeypatch):
    (tmp_path / "providers.yaml").write_text(PROVIDERS_YAML, encoding="utf-8")
    (tmp_path / "models.yaml").write_text(MODELS_YAML, encoding="utf-8")
    (tmp_path / "routing.yaml").write_text(ROUTING_YAML, encoding="utf-8")
    monkeypatch.setenv("LLM_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("ALPHA_KEY", "alpha-key")
    monkeypatch.setenv("LLM_ROUTER_ENABLED", "true")
    for name in ("NVIDIA_API_KEY", "GROQ_API_KEY", "CEREBRAS_API_KEY",
                 "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY",
                 "ANTHROPIC_API_KEY", "OLLAMA_BASE"):
        monkeypatch.delenv(name, raising=False)

    for module in (llm_config, llm_registry, llm_health, llm_keys,
                   llm_cache, llm_budget, llm_metrics, llm_router):
        module.reset()

    def install(handler):
        instance = llm_router.get_router()
        instance._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        return instance

    yield install

    for module in (llm_config, llm_registry, llm_health, llm_keys,
                   llm_cache, llm_budget, llm_metrics, llm_router):
        module.reset()


# ── The feature flag ────────────────────────────────────────────────────────

def test_router_is_off_unless_explicitly_enabled(monkeypatch):
    monkeypatch.delenv("LLM_ROUTER_ENABLED", raising=False)
    assert should_use_router() is False

    monkeypatch.setenv("LLM_ROUTER_ENABLED", "false")
    assert should_use_router() is False

    monkeypatch.setenv("LLM_ROUTER_ENABLED", "true")
    assert should_use_router() is True


def test_flag_is_read_per_call_so_rollback_needs_no_restart(monkeypatch):
    monkeypatch.setenv("LLM_ROUTER_ENABLED", "true")
    assert should_use_router() is True
    monkeypatch.setenv("LLM_ROUTER_ENABLED", "false")
    assert should_use_router() is False


def test_legacy_path_runs_when_the_flag_is_off(monkeypatch):
    """With the flag off, the shim must not even import the new router."""
    from packages.ai import failover_client

    monkeypatch.delenv("LLM_ROUTER_ENABLED", raising=False)
    assert failover_client._router_enabled() is False


# ── Payload translation ─────────────────────────────────────────────────────

def test_openai_payload_translates_without_losing_fields():
    payload = {
        "model": "alpha-model",
        "messages": [{"role": "user", "content": "hi"}],
        "temperature": 0.7,
        "max_tokens": 512,
        "tools": [{"type": "function", "function": {"name": "f"}}],
        "tool_choice": "auto",
        "response_format": {"type": "json_object"},
        "seed": 42,                      # vendor-specific, must survive
    }
    request = request_from_openai_payload(payload, agent="planner", workflow="wf")

    assert request.model == "alpha-model"
    assert request.temperature == 0.7
    assert request.max_tokens == 512
    assert request.tools == payload["tools"]
    assert request.tool_choice == "auto"
    assert request.response_format == {"type": "json_object"}
    assert request.agent == "planner" and request.workflow == "wf"
    # Unknown keys ride along to the provider rather than being dropped.
    assert request.extra["seed"] == 42


def test_response_renders_as_an_openai_body():
    response = LLMResponse(
        text="hello", model="alpha-model", provider="alpha",
        usage=Usage(prompt_tokens=4, completion_tokens=2),
        tool_calls=[ToolCall(id="c1", name="search", arguments='{"q":"x"}')],
        finish_reason="tool_calls",
        attempts=[Attempt(provider="alpha", model="alpha-model", ok=True)],
    )
    body = openai_body_from_response(response)

    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["content"] == "hello"
    assert body["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "search"
    assert body["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"] == '{"q":"x"}'
    assert body["choices"][0]["finish_reason"] == "tool_calls"
    assert body["usage"]["total_tokens"] == 6
    assert body["x_router"]["provider"] == "alpha"


# ── The shim end to end ─────────────────────────────────────────────────────

async def test_shim_returns_a_real_failover_result(routed):
    from packages.ai.failover_client import failover_chat_completion

    routed(lambda _r: httpx.Response(200, json={
        "model": "alpha-model",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "routed"},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 7, "completion_tokens": 3},
    }))

    result = await failover_chat_completion({
        "model": "alpha-model",
        "messages": [{"role": "user", "content": "hi"}],
        "temperature": 0.9,
    })

    # The exact type and field names existing callers already read.
    assert isinstance(result, FailoverResult)
    assert result.text == "routed"
    assert result.model == "alpha-model"
    assert result.provider_id == "alpha"
    assert result.prompt_tokens == 7
    assert result.completion_tokens == 3
    assert result.attempts == ["alpha/alpha-model"]


async def test_shim_raises_the_legacy_exception_on_exhaustion(routed):
    from packages.ai.failover_client import failover_chat_completion

    routed(lambda _r: httpx.Response(503, json={"error": "down"}))

    with pytest.raises(BrainFailoverExhausted) as excinfo:
        await failover_chat_completion({
            "model": "alpha-model",
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0.9,
        })

    # agent/loop.py catches this type by name; it must not change.
    assert "alpha" in str(excinfo.value) or "alpha" in repr(excinfo.value)


async def test_shim_preserves_tool_calls_through_the_router(routed):
    """Tool calling is the compatibility case most likely to break silently."""
    from packages.ai.failover_client import failover_chat_completion

    captured = {}

    def handler(request):
        import json
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={
            "model": "alpha-model",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"},
                         "finish_reason": "stop"}],
            "usage": {},
        })

    routed(handler)
    tools = [{"type": "function", "function": {"name": "search", "parameters": {}}}]
    await failover_chat_completion({
        "model": "alpha-model",
        "messages": [{"role": "user", "content": "hi"}],
        "tools": tools,
        "temperature": 0.9,
    })

    assert captured["tools"] == tools


def test_legacy_registry_models_are_visible_to_the_new_registry(monkeypatch):
    """Migration must not make a model disappear from routing."""
    from packages.ai import registry as legacy

    monkeypatch.delenv("LLM_CONFIG_DIR", raising=False)
    llm_config.reset()
    llm_registry.reset()
    try:
        new_ids = {m.id for m in llm_registry.get_registry().all()}
        legacy_ids = {m.model_id for m in legacy.all_models()}
        missing = legacy_ids - new_ids
        assert not missing, f"models lost in migration: {sorted(missing)}"
    finally:
        # Leave no loaded singleton behind for the next test module.
        llm_registry.reset()
        llm_config.reset()
