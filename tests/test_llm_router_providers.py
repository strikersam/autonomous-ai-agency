"""Provider adapters: payload translation, response parsing, streaming.

Tool calls and structured outputs must survive every adapter round-trip
unchanged. That is the compatibility promise in ADR-008 — the routing layer
may substitute providers freely, but it must never alter what the caller asked
for or reinterpret what the model returned.
"""
from __future__ import annotations

import json

import httpx
import pytest

from packages.llm.config import ProviderConfig
from packages.llm.providers import build_provider, resolve_kind
from packages.llm.providers.anthropic import AnthropicProvider
from packages.llm.providers.base import OpenAICompatible
from packages.llm.providers.gemini import GeminiProvider
from packages.llm.providers.ollama import OllamaProvider
from packages.llm.types import LLMRequest, TransientError

TOOLS = [{
    "type": "function",
    "function": {
        "name": "search",
        "description": "Search the web",
        "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
    },
}]

MESSAGES = [
    {"role": "system", "content": "You are terse."},
    {"role": "user", "content": "hello"},
]


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# ── Factory ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("kind,expected", [
    ("openai", OpenAICompatible),
    ("openai-compatible", OpenAICompatible),
    ("groq", OpenAICompatible),
    ("lmstudio", OpenAICompatible),
    ("vllm", OpenAICompatible),
    ("localai", OpenAICompatible),
    ("litellm", OpenAICompatible),
    ("azure", OpenAICompatible),
    ("together", OpenAICompatible),
    ("fireworks", OpenAICompatible),
    ("deepinfra", OpenAICompatible),
    ("mistral", OpenAICompatible),
    ("anthropic", AnthropicProvider),
    ("claude", AnthropicProvider),
    ("gemini", GeminiProvider),
    ("ollama", OllamaProvider),
])
def test_every_supported_kind_builds(kind, expected):
    provider = build_provider(ProviderConfig(id="x", kind=kind, base_url="http://x/v1"))
    assert isinstance(provider, expected)


def test_unknown_kind_degrades_to_openai_compatible():
    """A typo in YAML must break one provider, not platform startup."""
    provider = build_provider(ProviderConfig(id="x", kind="totally-made-up", base_url="http://x"))
    assert isinstance(provider, OpenAICompatible)


def test_resolve_kind_normalises_aliases():
    assert resolve_kind("LM-Studio") == "openai"
    assert resolve_kind("Claude") == "anthropic"


# ── OpenAI-compatible ───────────────────────────────────────────────────────

async def test_openai_passes_tools_and_response_format_through_untouched():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={
            "model": "m",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2},
        })

    provider = OpenAICompatible(ProviderConfig(id="demo", base_url="http://demo/v1"))
    request = LLMRequest(
        messages=MESSAGES, tools=TOOLS, tool_choice="auto",
        response_format={"type": "json_object"},
    )
    async with _client(handler) as client:
        response = await provider.chat(request, model="m", api_key="k", client=client)

    assert captured["tools"] == TOOLS
    assert captured["tool_choice"] == "auto"
    assert captured["response_format"] == {"type": "json_object"}
    assert response.text == "ok"
    assert response.usage.prompt_tokens == 3


async def test_openai_parses_tool_calls():
    def handler(_request):
        return httpx.Response(200, json={
            "model": "m",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant", "content": None,
                    "tool_calls": [{
                        "id": "call_1", "type": "function",
                        "function": {"name": "search", "arguments": '{"q":"cats"}'},
                    }],
                },
                "finish_reason": "tool_calls",
            }],
            "usage": {},
        })

    provider = OpenAICompatible(ProviderConfig(id="demo", base_url="http://demo/v1"))
    async with _client(handler) as client:
        response = await provider.chat(LLMRequest(messages=MESSAGES), model="m",
                                       api_key="k", client=client)

    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].name == "search"
    # Arguments must stay the exact JSON string the model emitted.
    assert response.tool_calls[0].arguments == '{"q":"cats"}'
    assert response.finish_reason == "tool_calls"


async def test_openai_auth_styles():
    provider = OpenAICompatible(ProviderConfig(id="d", base_url="http://d/v1"))
    assert provider.auth_headers("k")["Authorization"] == "Bearer k"

    azure = OpenAICompatible(ProviderConfig(id="a", base_url="http://a", auth_style="api-key"))
    assert azure.auth_headers("k")["api-key"] == "k"

    none = OpenAICompatible(ProviderConfig(id="n", base_url="http://n", auth_style="none"))
    assert "Authorization" not in none.auth_headers("k")


def test_azure_url_includes_deployment_and_api_version():
    provider = OpenAICompatible(ProviderConfig(
        id="azure", base_url="https://x.openai.azure.com",
        api_version="2024-10-21", deployment="gpt4o",
    ))
    url = provider._chat_url()
    assert "/openai/deployments/gpt4o/chat/completions" in url
    assert "api-version=2024-10-21" in url


def test_bare_host_base_url_gets_v1_inserted():
    """An operator-overridden base-url env var replaces the whole default,
    it does not extend it — so ``NVIDIA_BASE_URL=https://integrate.api.nvidia.com``
    (render.yaml, no ``/v1``) must still resolve to the real endpoint.
    Without this every model 404s identically, which classify_error()
    correctly reports as a permanent, provider-scoped error (a wrong URL,
    not a missing model) — see test_404_without_a_model_hint_is_permanent.
    """
    provider = OpenAICompatible(ProviderConfig(
        id="nvidia", base_url="https://integrate.api.nvidia.com",
    ))
    assert provider._chat_url() == "https://integrate.api.nvidia.com/v1/chat/completions"


def test_base_url_already_ending_in_v1_is_untouched():
    provider = OpenAICompatible(ProviderConfig(id="demo", base_url="http://demo/v1"))
    assert provider._chat_url() == "http://demo/v1/chat/completions"


def test_base_url_with_its_own_path_is_not_given_a_second_v1():
    """A base url that already carries a path (e.g. Azure-style, or a gateway
    mounted under a prefix) is trusted as-is — inserting /v1 would corrupt it."""
    provider = OpenAICompatible(ProviderConfig(
        id="deepinfra", base_url="https://api.deepinfra.com/v1/openai",
    ))
    assert provider._chat_url() == "https://api.deepinfra.com/v1/openai/chat/completions"


async def test_openai_error_carries_retry_after():
    def handler(_request):
        return httpx.Response(429, json={"error": "slow down"}, headers={"retry-after": "7"})

    provider = OpenAICompatible(ProviderConfig(id="demo", base_url="http://demo/v1"))
    async with _client(handler) as client:
        with pytest.raises(TransientError) as excinfo:
            await provider.chat(LLMRequest(messages=MESSAGES), model="m",
                                api_key="k", client=client)

    assert excinfo.value.status == 429
    assert excinfo.value.retry_after == 7.0
    assert excinfo.value.scope == "key"


async def test_openai_streaming_normalises_deltas():
    def handler(_request):
        body = (
            'data: {"model":"m","choices":[{"delta":{"content":"Hel"}}]}\n\n'
            'data: {"model":"m","choices":[{"delta":{"content":"lo"}}]}\n\n'
            'data: {"model":"m","choices":[{"delta":{},"finish_reason":"stop"}],'
            '"usage":{"prompt_tokens":1,"completion_tokens":2}}\n\n'
            'data: [DONE]\n\n'
        )
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    provider = OpenAICompatible(ProviderConfig(id="demo", base_url="http://demo/v1"))
    async with _client(handler) as client:
        chunks = [c async for c in provider.stream(
            LLMRequest(messages=MESSAGES, stream=True), model="m", api_key="k", client=client
        )]

    assert "".join(c.text for c in chunks) == "Hello"
    assert chunks[-1].finish_reason == "stop"
    assert chunks[-1].usage.completion_tokens == 2


async def test_openai_lists_models():
    def handler(_request):
        return httpx.Response(200, json={"data": [{"id": "a"}, {"id": "b"}]})

    provider = OpenAICompatible(ProviderConfig(id="demo", base_url="http://demo/v1"))
    async with _client(handler) as client:
        assert await provider.list_models(api_key="k", client=client) == ["a", "b"]


# ── Anthropic ───────────────────────────────────────────────────────────────

async def test_anthropic_lifts_system_and_converts_tools():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json={
            "model": "claude", "content": [{"type": "text", "text": "hi"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 5, "output_tokens": 3},
        })

    provider = AnthropicProvider(ProviderConfig(
        id="anthropic", kind="anthropic", base_url="https://api.anthropic.com",
    ))
    async with _client(handler) as client:
        response = await provider.chat(
            LLMRequest(messages=MESSAGES, tools=TOOLS), model="claude",
            api_key="sk-test", client=client,
        )

    # system is a caching content block by default (prompt_caching=True)
    assert isinstance(captured["system"], list)
    assert captured["system"][0]["text"] == "You are terse."
    assert captured["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert all(m["role"] != "system" for m in captured["messages"])
    # OpenAI-shaped tools are translated to Anthropic's input_schema form.
    assert captured["tools"][0]["name"] == "search"
    assert captured["tools"][0]["input_schema"]["type"] == "object"
    assert captured["headers"]["x-api-key"] == "sk-test"
    assert captured["headers"]["anthropic-version"]
    assert "prompt-caching-2024-07-31" in captured["headers"]["anthropic-beta"]
    assert response.text == "hi"
    assert response.usage.prompt_tokens == 5


async def test_anthropic_parses_tool_use_blocks():
    def handler(_request):
        return httpx.Response(200, json={
            "model": "claude",
            "content": [
                {"type": "text", "text": "let me look"},
                {"type": "tool_use", "id": "tu_1", "name": "search", "input": {"q": "cats"}},
            ],
            "stop_reason": "tool_use", "usage": {"input_tokens": 1, "output_tokens": 1},
        })

    provider = AnthropicProvider(ProviderConfig(id="anthropic", kind="anthropic",
                                                base_url="https://api.anthropic.com"))
    async with _client(handler) as client:
        response = await provider.chat(LLMRequest(messages=MESSAGES), model="claude",
                                       api_key="k", client=client)

    assert response.text == "let me look"
    assert response.tool_calls[0].name == "search"
    assert json.loads(response.tool_calls[0].arguments) == {"q": "cats"}


async def test_anthropic_streaming_events_normalise():
    def handler(_request):
        body = (
            'data: {"type":"content_block_delta","index":0,'
            '"delta":{"type":"text_delta","text":"Hel"}}\n\n'
            'data: {"type":"content_block_delta","index":0,'
            '"delta":{"type":"text_delta","text":"lo"}}\n\n'
            'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},'
            '"usage":{"output_tokens":4}}\n\n'
        )
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    provider = AnthropicProvider(ProviderConfig(id="anthropic", kind="anthropic",
                                                base_url="https://api.anthropic.com"))
    async with _client(handler) as client:
        chunks = [c async for c in provider.stream(
            LLMRequest(messages=MESSAGES, stream=True), model="claude",
            api_key="k", client=client,
        )]

    assert "".join(c.text for c in chunks) == "Hello"
    assert chunks[-1].finish_reason == "end_turn"


# ── Gemini ──────────────────────────────────────────────────────────────────

async def test_gemini_translates_roles_and_system_instruction():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        captured["headers"] = dict(request.headers)
        captured["url"] = str(request.url)
        return httpx.Response(200, json={
            "candidates": [{
                "content": {"parts": [{"text": "hey"}]}, "finishReason": "STOP",
            }],
            "usageMetadata": {"promptTokenCount": 4, "candidatesTokenCount": 2},
        })

    provider = GeminiProvider(ProviderConfig(
        id="google", kind="gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta",
    ))
    messages = [*MESSAGES, {"role": "assistant", "content": "prior"}]
    async with _client(handler) as client:
        response = await provider.chat(
            LLMRequest(messages=messages, response_format={"type": "json_object"}),
            model="gemini-2.5-flash", api_key="AIza-test", client=client,
        )

    assert captured["systemInstruction"]["parts"][0]["text"] == "You are terse."
    assert [c["role"] for c in captured["contents"]] == ["user", "model"]
    assert captured["generationConfig"]["responseMimeType"] == "application/json"
    # The key travels in a header, not a query string that proxies would log.
    assert captured["headers"]["x-goog-api-key"] == "AIza-test"
    assert "key=" not in captured["url"]
    assert response.text == "hey"
    assert response.usage.prompt_tokens == 4


async def test_gemini_parses_function_calls():
    def handler(_request):
        return httpx.Response(200, json={
            "candidates": [{
                "content": {"parts": [{"functionCall": {"name": "search", "args": {"q": "x"}}}]},
                "finishReason": "STOP",
            }],
            "usageMetadata": {},
        })

    provider = GeminiProvider(ProviderConfig(
        id="google", kind="gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta",
    ))
    async with _client(handler) as client:
        response = await provider.chat(LLMRequest(messages=MESSAGES, tools=TOOLS),
                                       model="g", api_key="k", client=client)

    assert response.tool_calls[0].name == "search"
    assert json.loads(response.tool_calls[0].arguments) == {"q": "x"}


# ── Ollama ──────────────────────────────────────────────────────────────────

async def test_ollama_uses_native_endpoint_and_reports_zero_cost():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "model": "qwen3-coder:30b",
            "message": {"role": "assistant", "content": "local reply"},
            "done": True, "done_reason": "stop",
            "prompt_eval_count": 12, "eval_count": 7,
        })

    provider = OllamaProvider(ProviderConfig(id="ollama", kind="ollama",
                                             base_url="http://localhost:11434"))
    async with _client(handler) as client:
        response = await provider.chat(
            LLMRequest(messages=MESSAGES, response_format={"type": "json_object"}),
            model="qwen3-coder:30b", api_key="", client=client,
        )

    assert captured["url"].endswith("/api/chat")
    assert captured["body"]["format"] == "json"
    assert response.text == "local reply"
    assert response.usage.prompt_tokens == 12
    assert response.cost_usd == 0.0


async def test_ollama_streams_ndjson():
    def handler(_request):
        body = (
            '{"model":"m","message":{"content":"Hel"},"done":false}\n'
            '{"model":"m","message":{"content":"lo"},"done":false}\n'
            '{"model":"m","message":{"content":""},"done":true,"done_reason":"stop",'
            '"prompt_eval_count":2,"eval_count":3}\n'
        )
        return httpx.Response(200, text=body)

    provider = OllamaProvider(ProviderConfig(id="ollama", kind="ollama",
                                             base_url="http://localhost:11434"))
    async with _client(handler) as client:
        chunks = [c async for c in provider.stream(
            LLMRequest(messages=MESSAGES, stream=True), model="m", api_key="", client=client
        )]

    assert "".join(c.text for c in chunks) == "Hello"
    assert chunks[-1].finish_reason == "stop"
    assert chunks[-1].usage.completion_tokens == 3


async def test_health_probe_never_raises():
    def handler(_request):
        raise httpx.ConnectError("nothing listening")

    provider = OllamaProvider(ProviderConfig(id="ollama", kind="ollama",
                                             base_url="http://localhost:11434"))
    async with _client(handler) as client:
        result = await provider.health(api_key="", client=client)

    assert result["healthy"] is False


# ── Anthropic prompt caching and extended thinking ───────────────────────────

def _anthropic_provider(**kwargs) -> AnthropicProvider:
    return AnthropicProvider(ProviderConfig(
        id="anthropic", kind="anthropic", base_url="https://api.anthropic.com", **kwargs
    ))


def test_anthropic_auth_headers_prompt_caching_on_by_default():
    p = _anthropic_provider()
    headers = p.auth_headers("key")
    assert "prompt-caching-2024-07-31" in headers.get("anthropic-beta", "")


def test_anthropic_auth_headers_prompt_caching_off():
    p = _anthropic_provider(prompt_caching=False)
    headers = p.auth_headers("key")
    assert "prompt-caching-2024-07-31" not in headers.get("anthropic-beta", "")


def test_anthropic_auth_headers_thinking_beta_absent_when_zero():
    p = _anthropic_provider(thinking_budget=0)
    headers = p.auth_headers("key")
    assert "interleaved-thinking" not in headers.get("anthropic-beta", "")


def test_anthropic_auth_headers_thinking_beta_present_when_positive():
    p = _anthropic_provider(thinking_budget=8000, prompt_caching=False)
    headers = p.auth_headers("key")
    assert "interleaved-thinking-2025-05-14" in headers.get("anthropic-beta", "")


def test_anthropic_auth_headers_both_betas_when_both_enabled():
    p = _anthropic_provider(thinking_budget=4000)
    beta = p.auth_headers("key").get("anthropic-beta", "")
    assert "prompt-caching-2024-07-31" in beta
    assert "interleaved-thinking-2025-05-14" in beta


def test_anthropic_system_plain_string_when_caching_off():
    p = _anthropic_provider(prompt_caching=False)
    req = LLMRequest(messages=[{"role": "system", "content": "Be brief."},
                                {"role": "user", "content": "hi"}])
    payload = p.build_payload(req, "claude-sonnet-4-6")
    assert payload["system"] == "Be brief."


def test_anthropic_system_cache_block_when_caching_on():
    p = _anthropic_provider(prompt_caching=True)
    req = LLMRequest(messages=[{"role": "system", "content": "Be brief."},
                                {"role": "user", "content": "hi"}])
    payload = p.build_payload(req, "claude-sonnet-4-6")
    system = payload["system"]
    assert isinstance(system, list)
    assert system[0]["type"] == "text"
    assert system[0]["text"] == "Be brief."
    assert system[0]["cache_control"] == {"type": "ephemeral"}


def test_anthropic_no_system_key_when_no_system_messages():
    p = _anthropic_provider()
    req = LLMRequest(messages=[{"role": "user", "content": "hi"}])
    payload = p.build_payload(req, "claude-sonnet-4-6")
    assert "system" not in payload


def test_anthropic_thinking_block_injected_when_budget_positive():
    # max_tokens must exceed the budget for a non-tool request — Anthropic
    # requires budget_tokens < max_tokens outside interleaved (tool) thinking.
    p = _anthropic_provider(thinking_budget=6000)
    req = LLMRequest(messages=[{"role": "user", "content": "think hard"}], max_tokens=8192)
    payload = p.build_payload(req, "claude-sonnet-4-6")
    assert payload["thinking"] == {"type": "enabled", "budget_tokens": 6000}
    assert payload["temperature"] == 1


def test_anthropic_thinking_overrides_request_temperature():
    p = _anthropic_provider(thinking_budget=2000)
    req = LLMRequest(messages=[{"role": "user", "content": "hi"}], temperature=0.7)
    payload = p.build_payload(req, "claude-sonnet-4-6")
    assert payload["temperature"] == 1


def test_anthropic_thinking_overrides_extra_temperature():
    """request.extra must not be able to defeat the enforced temperature=1."""
    p = _anthropic_provider(thinking_budget=2000)
    req = LLMRequest(messages=[{"role": "user", "content": "hi"}],
                      extra={"temperature": 0.2, "thinking": {"type": "disabled"}})
    payload = p.build_payload(req, "claude-sonnet-4-6")
    assert payload["temperature"] == 1
    assert payload["thinking"] == {"type": "enabled", "budget_tokens": 2000}


def test_anthropic_no_thinking_block_when_budget_zero():
    p = _anthropic_provider(thinking_budget=0)
    req = LLMRequest(messages=[{"role": "user", "content": "hi"}])
    payload = p.build_payload(req, "claude-sonnet-4-6")
    assert "thinking" not in payload


def test_anthropic_thinking_disabled_when_budget_below_minimum():
    """Anthropic rejects budget_tokens < 1024 outright — never send it."""
    p = _anthropic_provider(thinking_budget=500)
    req = LLMRequest(messages=[{"role": "user", "content": "hi"}])
    payload = p.build_payload(req, "claude-sonnet-4-6")
    assert "thinking" not in payload
    assert "temperature" not in payload or payload["temperature"] != 1, (
        "an invalid budget must not enforce the thinking-only temperature=1"
    )


def test_anthropic_thinking_disabled_when_budget_would_exceed_max_tokens():
    """Without tools, budget_tokens must stay below max_tokens or Anthropic 400s."""
    p = _anthropic_provider(thinking_budget=6000)
    req = LLMRequest(messages=[{"role": "user", "content": "hi"}], max_tokens=4096)
    payload = p.build_payload(req, "claude-sonnet-4-6")
    assert "thinking" not in payload


def test_anthropic_thinking_allowed_to_exceed_max_tokens_with_tools():
    """Interleaved (tool) thinking lets the budget span the whole turn."""
    p = _anthropic_provider(thinking_budget=6000)
    req = LLMRequest(
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=4096,
        tools=[{"type": "function", "function": {"name": "t", "description": "t",
                                                   "parameters": {"type": "object", "properties": {}}}}],
    )
    payload = p.build_payload(req, "claude-sonnet-4-6")
    assert payload["thinking"] == {"type": "enabled", "budget_tokens": 6000}


def test_anthropic_configured_beta_header_is_preserved_alongside_features():
    """A pre-configured anthropic-beta must not be overwritten by feature flags."""
    p = _anthropic_provider(extra_headers={"anthropic-beta": "some-other-beta-2026-01-01"})
    beta = p.auth_headers("key").get("anthropic-beta", "")
    assert "some-other-beta-2026-01-01" in beta
    assert "prompt-caching-2024-07-31" in beta


# ── Adaptive-thinking model guard-rails (2026-08) ─────────────────────────────

def test_anthropic_sonnet5_no_temperature_in_payload():
    """claude-sonnet-5 rejects non-default temperature with HTTP 400."""
    p = _anthropic_provider()
    req = LLMRequest(messages=[{"role": "user", "content": "hi"}], temperature=0.3)
    payload = p.build_payload(req, "claude-sonnet-5")
    assert "temperature" not in payload


def test_anthropic_fable5_no_temperature_in_payload():
    """claude-fable-5 (adaptive thinking always-on) must not receive temperature."""
    p = _anthropic_provider()
    req = LLMRequest(messages=[{"role": "user", "content": "hi"}])
    payload = p.build_payload(req, "claude-fable-5")
    assert "temperature" not in payload


def test_anthropic_sonnet5_strips_temperature_from_extra():
    """temperature in request.extra must also be removed for no-temperature models."""
    p = _anthropic_provider()
    req = LLMRequest(messages=[{"role": "user", "content": "hi"}],
                     extra={"temperature": 0.9, "top_p": 0.95, "top_k": 40})
    payload = p.build_payload(req, "claude-sonnet-5")
    assert "temperature" not in payload
    assert "top_p" not in payload
    assert "top_k" not in payload


def test_anthropic_legacy_model_still_gets_temperature():
    """claude-sonnet-4-6 and older models must still receive the temperature field."""
    p = _anthropic_provider()
    req = LLMRequest(messages=[{"role": "user", "content": "hi"}], temperature=0.7)
    for model in ("claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5-20251001"):
        payload = p.build_payload(req, model)
        assert payload.get("temperature") == 0.7, f"{model} should carry temperature"


def test_anthropic_opus_family_no_temperature():
    """The whole adaptive-thinking Opus family (5 / 4.8 / 4.7) rejects temperature.

    Opus 5 is the anthropic planner preset — the production 400 was temperature
    sent to it. Opus was previously (incorrectly) absent from the no-temperature
    set even though it 400s the same way Sonnet 5 / Fable 5 do.
    """
    p = _anthropic_provider()
    req = LLMRequest(messages=[{"role": "user", "content": "hi"}], temperature=0.3)
    for model in ("claude-opus-5", "claude-opus-4-8", "claude-opus-4-7"):
        payload = p.build_payload(req, model)
        assert "temperature" not in payload, f"{model} must not carry temperature"


def test_anthropic_sonnet5_no_extended_thinking():
    """claude-sonnet-5 must not receive thinking.type='enabled'."""
    p = _anthropic_provider(thinking_budget=6000)
    req = LLMRequest(messages=[{"role": "user", "content": "think hard"}], max_tokens=8192)
    payload = p.build_payload(req, "claude-sonnet-5")
    assert "thinking" not in payload


def test_anthropic_opus5_no_extended_thinking():
    """claude-opus-5 uses adaptive thinking and must not receive budget thinking."""
    p = _anthropic_provider(thinking_budget=6000)
    req = LLMRequest(messages=[{"role": "user", "content": "think hard"}], max_tokens=8192)
    payload = p.build_payload(req, "claude-opus-5")
    assert "thinking" not in payload


def test_anthropic_opus46_still_gets_extended_thinking():
    """claude-opus-4-6 still supports legacy extended thinking."""
    p = _anthropic_provider(thinking_budget=6000)
    req = LLMRequest(messages=[{"role": "user", "content": "think hard"}], max_tokens=8192)
    payload = p.build_payload(req, "claude-opus-4-6")
    assert payload.get("thinking") == {"type": "enabled", "budget_tokens": 6000}
    assert payload.get("temperature") == 1


def test_anthropic_effort_via_request_field():
    """output_config.effort is set from request.effort."""
    p = _anthropic_provider()
    req = LLMRequest(messages=[{"role": "user", "content": "hi"}], effort="medium")
    payload = p.build_payload(req, "claude-opus-5")
    assert payload.get("output_config") == {"effort": "medium"}


def test_anthropic_effort_via_provider_default():
    """output_config.effort falls back to ProviderConfig.default_effort."""
    p = _anthropic_provider(default_effort="low")
    req = LLMRequest(messages=[{"role": "user", "content": "hi"}])
    payload = p.build_payload(req, "claude-sonnet-5")
    assert payload.get("output_config") == {"effort": "low"}


def test_anthropic_request_effort_overrides_provider_default():
    """Per-request effort takes priority over provider default."""
    p = _anthropic_provider(default_effort="low")
    req = LLMRequest(messages=[{"role": "user", "content": "hi"}], effort="xhigh")
    payload = p.build_payload(req, "claude-opus-5")
    assert payload.get("output_config") == {"effort": "xhigh"}


def test_anthropic_invalid_effort_not_sent():
    """An unknown effort level must not be forwarded to the API."""
    p = _anthropic_provider(default_effort="ultra")
    req = LLMRequest(messages=[{"role": "user", "content": "hi"}], effort="turbo")
    payload = p.build_payload(req, "claude-opus-5")
    assert "output_config" not in payload


def test_anthropic_no_output_config_when_no_effort():
    """output_config is absent when neither request nor provider sets effort."""
    p = _anthropic_provider()
    req = LLMRequest(messages=[{"role": "user", "content": "hi"}])
    payload = p.build_payload(req, "claude-opus-5")
    assert "output_config" not in payload


# ── C1: Structured Output / JSON Mode (Anthropic) ────────────────────────────

def test_anthropic_json_object_injects_system_instruction():
    """json_object mode must append a JSON instruction to the system prompt."""
    p = _anthropic_provider(prompt_caching=False)
    req = LLMRequest(
        messages=[
            {"role": "system", "content": "Be helpful."},
            {"role": "user", "content": "reply"},
        ],
        response_format={"type": "json_object"},
    )
    payload = p.build_payload(req, "claude-sonnet-4-6")
    system = payload["system"]
    assert isinstance(system, str)
    assert "Be helpful." in system
    assert "JSON" in system


def test_anthropic_json_object_without_existing_system_creates_system():
    """json_object mode works even when no system message is provided."""
    p = _anthropic_provider(prompt_caching=False)
    req = LLMRequest(
        messages=[{"role": "user", "content": "hi"}],
        response_format={"type": "json_object"},
    )
    payload = p.build_payload(req, "claude-sonnet-4-6")
    assert "system" in payload
    assert "JSON" in payload["system"]


def test_anthropic_json_schema_injects_schema_instruction():
    """json_schema mode must embed the schema in the system prompt."""
    p = _anthropic_provider(prompt_caching=False)
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
    }
    req = LLMRequest(
        messages=[{"role": "user", "content": "hi"}],
        response_format={"type": "json_schema", "json_schema": {"name": "person", "schema": schema}},
    )
    payload = p.build_payload(req, "claude-sonnet-4-6")
    system = payload["system"]
    assert "person" in system
    assert '"name"' in system  # schema serialised inline
    assert "JSON" in system


def test_anthropic_response_format_not_in_payload_body():
    """Anthropic's API rejects response_format — it must never appear in the body."""
    p = _anthropic_provider(prompt_caching=False)
    req = LLMRequest(
        messages=[{"role": "user", "content": "hi"}],
        response_format={"type": "json_object"},
    )
    payload = p.build_payload(req, "claude-sonnet-4-6")
    assert "response_format" not in payload


def test_anthropic_unknown_format_type_no_injection():
    """An unknown format type (e.g. 'xml') must not add any system instruction."""
    p = _anthropic_provider(prompt_caching=False)
    req = LLMRequest(
        messages=[{"role": "user", "content": "hi"}],
        response_format={"type": "xml"},
    )
    payload = p.build_payload(req, "claude-sonnet-4-6")
    assert "system" not in payload


def test_anthropic_no_response_format_no_system_injection():
    """Without response_format, system prompt must not change."""
    p = _anthropic_provider(prompt_caching=False)
    req = LLMRequest(
        messages=[
            {"role": "system", "content": "Be terse."},
            {"role": "user", "content": "hi"},
        ],
    )
    payload = p.build_payload(req, "claude-sonnet-4-6")
    assert payload["system"] == "Be terse."


def test_anthropic_json_instruction_static_method_json_object():
    """_json_instruction returns a non-empty string for json_object."""
    from packages.llm.providers.anthropic import AnthropicProvider
    result = AnthropicProvider._json_instruction({"type": "json_object"})
    assert result is not None
    assert "JSON" in result


def test_anthropic_json_instruction_static_method_json_schema_with_name():
    """_json_instruction embeds the schema name."""
    from packages.llm.providers.anthropic import AnthropicProvider
    result = AnthropicProvider._json_instruction({
        "type": "json_schema",
        "json_schema": {
            "name": "order_result",
            "schema": {"type": "object", "properties": {"id": {"type": "integer"}}},
        },
    })
    assert result is not None
    assert "order_result" in result
    assert "JSON" in result


def test_anthropic_json_instruction_static_method_unknown_type():
    """_json_instruction returns None for unknown types."""
    from packages.llm.providers.anthropic import AnthropicProvider
    assert AnthropicProvider._json_instruction({"type": "text"}) is None
    assert AnthropicProvider._json_instruction({}) is None


def test_anthropic_json_mode_with_prompt_caching_produces_list_system():
    """When prompt caching is on, the system field becomes a cache-control list."""
    p = _anthropic_provider(prompt_caching=True)
    req = LLMRequest(
        messages=[
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "hi"},
        ],
        response_format={"type": "json_object"},
    )
    payload = p.build_payload(req, "claude-sonnet-4-6")
    system = payload["system"]
    assert isinstance(system, list)
    # The combined text should contain both the original system content and
    # the JSON instruction.
    combined = system[0]["text"]
    assert "Be concise." in combined
    assert "JSON" in combined
