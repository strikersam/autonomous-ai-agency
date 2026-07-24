"""The brain-failover chain must be reachable by the CEO, not just the agent loop.

Before this, the dispatch loop lived inline inside ``AgentRunner._chat_text``, so
only the agent loop could reach the env-configured provider chain. Everything
going through ``backend.server.call_llm`` — the CEO strategic assessment above
all — fell back only across the DB-configured ``providers`` records. When those
were rate-limited the CEO dropped straight to its rule-based path while a dozen
untried providers sat healthy.

These tests pin the extracted dispatcher's behaviour and the fact that both
callers now use it.
"""
from __future__ import annotations

import httpx
import pytest

from packages.ai.failover_client import (
    BrainFailoverExhausted,
    FailoverResult,
    _build_request,
    failover_chat_completion,
)


class _StubProvider:
    def __init__(self, pid, base_url, models, api_key="k", tier="free"):
        self.id = pid
        self.base_url = base_url
        self.models = models
        self.api_key = api_key
        self.tier = tier
        self.is_healthy = True


class _StubManager:
    """Minimal stand-in for BrainFailoverManager."""

    def __init__(self, providers):
        self._providers = list(providers)
        self.successes: list[str] = []
        self.failures: list[tuple[str, str]] = []

    def max_attempts(self):
        return max(len(self._providers), 1)

    def next_provider(self, *, exclude=None, requested_model=None):
        exclude = exclude or set()
        for p in self._providers:
            if p.id not in exclude and p.is_healthy:
                return p
        return None

    def get_providers(self):
        return self._providers

    def resolve_model(self, provider, requested_model):
        return provider.models[0]

    def record_success(self, provider_id, latency_ms=0.0):
        self.successes.append(provider_id)

    def record_failure(self, provider_id, reason, status=None):
        self.failures.append((provider_id, reason))


def _openai_body(text="hello", pt=3, ct=5):
    return {
        "choices": [{"message": {"role": "assistant", "content": text}}],
        "usage": {"prompt_tokens": pt, "completion_tokens": ct},
    }


@pytest.fixture
def patch_chain(monkeypatch):
    """Install a stub manager and a scripted sequence of HTTP responses."""

    def _apply(providers, responses):
        manager = _StubManager(providers)
        monkeypatch.setattr(
            "services.brain_failover.get_failover_manager", lambda: manager
        )
        calls: list[str] = []
        seq = list(responses)

        class _Client:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, json=None, headers=None):
                calls.append(url)
                nxt = seq.pop(0)
                if isinstance(nxt, Exception):
                    raise nxt
                return nxt

        monkeypatch.setattr(httpx, "AsyncClient", _Client)
        return manager, calls

    return _apply


@pytest.mark.asyncio
async def test_returns_first_success_with_usage(patch_chain) -> None:
    manager, calls = patch_chain(
        [_StubProvider("groq", "https://api.groq.com/openai/v1", ["llama-3.3-70b"])],
        [httpx.Response(200, json=_openai_body("ok", pt=11, ct=7))],
    )

    result = await failover_chat_completion(
        {"model": "llama-3.3-70b", "messages": [{"role": "user", "content": "hi"}]}
    )

    assert isinstance(result, FailoverResult)
    assert result.text == "ok"
    assert result.provider_id == "groq"
    assert (result.prompt_tokens, result.completion_tokens) == (11, 7)
    assert manager.successes == ["groq"]


@pytest.mark.asyncio
async def test_rate_limited_provider_fails_over_to_the_next(patch_chain) -> None:
    """A 429 must move to the next provider, not another model on the same one."""
    manager, calls = patch_chain(
        [
            _StubProvider("zai", "https://api.z.ai/api/paas/v4", ["glm-5.2", "glm-5.1"]),
            _StubProvider("groq", "https://api.groq.com/openai/v1", ["llama-3.3-70b"]),
        ],
        [
            httpx.Response(429, json={"error": "rate limited"}),
            httpx.Response(200, json=_openai_body("recovered")),
        ],
    )

    result = await failover_chat_completion(
        {"model": "glm-5.2", "messages": [{"role": "user", "content": "hi"}]}
    )

    assert result.text == "recovered"
    assert result.provider_id == "groq"
    # Exactly one call to zai — the second model on it must NOT be tried.
    assert len(calls) == 2
    assert ("zai", "rate_limited") in manager.failures


@pytest.mark.asyncio
async def test_410_tries_the_next_model_on_the_same_provider(patch_chain) -> None:
    """A dead model is per-model, so the sibling model is the right next try."""
    manager, calls = patch_chain(
        [_StubProvider("nvidia", "https://integrate.api.nvidia.com", ["dead", "alive"])],
        [
            httpx.Response(410, json={"error": "gone"}),
            httpx.Response(200, json=_openai_body("second model")),
        ],
    )

    result = await failover_chat_completion(
        {"model": "dead", "messages": [{"role": "user", "content": "hi"}]}
    )

    assert result.text == "second model"
    assert result.model == "alive"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_network_error_fails_over(patch_chain) -> None:
    manager, calls = patch_chain(
        [
            _StubProvider("ollama", "http://localhost:11434", ["qwen3-coder:30b"]),
            _StubProvider("groq", "https://api.groq.com/openai/v1", ["llama-3.3-70b"]),
        ],
        [
            httpx.ConnectError("All connection attempts failed"),
            httpx.Response(200, json=_openai_body("cloud")),
        ],
    )

    result = await failover_chat_completion(
        {"model": "qwen3-coder:30b", "messages": [{"role": "user", "content": "hi"}]}
    )

    assert result.text == "cloud"
    assert ("ollama", "network_error") in manager.failures


@pytest.mark.asyncio
async def test_exhaustion_raises_with_the_last_error(patch_chain) -> None:
    patch_chain(
        [_StubProvider("minimax", "https://api.minimax.chat/v1", ["mimo-v2-flash"])],
        [httpx.Response(401, json={"error": "bad key"})],
    )

    with pytest.raises(BrainFailoverExhausted) as excinfo:
        await failover_chat_completion(
            {"model": "mimo-v2-flash", "messages": [{"role": "user", "content": "hi"}]}
        )

    assert "minimax" in excinfo.value.last_error
    assert "401" in excinfo.value.last_error
    assert "minimax" in excinfo.value.tried


@pytest.mark.asyncio
async def test_anthropic_provider_uses_the_messages_api(patch_chain) -> None:
    """The Anthropic wire format must survive the extraction."""
    manager, calls = patch_chain(
        [
            _StubProvider(
                "anthropic", "https://api.anthropic.com", ["claude-sonnet-5"],
                tier="paid",
            )
        ],
        [
            httpx.Response(
                200,
                json={
                    "id": "msg_1",
                    "content": [{"type": "text", "text": "claude replied"}],
                    "usage": {"input_tokens": 4, "output_tokens": 2},
                },
            )
        ],
    )

    result = await failover_chat_completion(
        {"model": "claude-sonnet-5", "messages": [{"role": "user", "content": "hi"}]}
    )

    assert calls == ["https://api.anthropic.com/v1/messages"]
    assert result.text == "claude replied"
    assert (result.prompt_tokens, result.completion_tokens) == (4, 2)


class TestBuildRequest:
    def test_anthropic_native_gets_messages_route_and_x_api_key(self) -> None:
        url, headers, is_anthropic = _build_request(
            _StubProvider("anthropic", "https://api.anthropic.com", ["m"], api_key="sk")
        )

        assert is_anthropic is True
        assert url == "https://api.anthropic.com/v1/messages"
        assert headers["x-api-key"] == "sk"
        assert "Authorization" not in headers

    def test_openai_compatible_gateway_keeps_chat_completions(self) -> None:
        url, headers, is_anthropic = _build_request(
            _StubProvider("aerolink", "https://capi.aerolink.lat/v1", ["m"], api_key="sk")
        )

        assert is_anthropic is False
        assert url == "https://capi.aerolink.lat/v1/chat/completions"
        assert headers["Authorization"] == "Bearer sk"


def test_agent_loop_delegates_to_the_shared_client() -> None:
    """The loop must not carry its own copy of the dispatch loop."""
    import inspect

    from agent.loop import AgentRunner

    source = inspect.getsource(AgentRunner._chat_text)

    assert "failover_chat_completion" in source, (
        "AgentRunner._chat_text no longer delegates to the shared failover client"
    )
    # The inline loop's tell-tale locals must be gone, or the logic has been
    # duplicated back into the loop.
    assert "fm.next_provider(" not in source, (
        "the dispatch loop has been re-inlined into AgentRunner._chat_text; it "
        "belongs in packages/ai/failover_client.py so call_llm shares it"
    )


def test_call_llm_falls_through_to_the_shared_client() -> None:
    """call_llm must reach the env chain when DB providers are exhausted."""
    import inspect

    import backend.server

    source = inspect.getsource(backend.server.call_llm)

    assert "failover_chat_completion" in source, (
        "call_llm does not fall through to the brain-failover chain, so the CEO "
        "still degrades to rule-based while healthy providers sit untried"
    )
    assert "ProviderFallbackError" in source


@pytest.mark.asyncio
async def test_malformed_2xx_body_fails_over_instead_of_crashing(patch_chain) -> None:
    """A 2xx with an unusable body must be a failed attempt, never a crash.

    The dispatcher promises it either returns a complete result or raises
    BrainFailoverExhausted. Parsing outside the attempt guard broke that: an
    empty `choices` array raised IndexError straight out of the call.
    """
    manager, calls = patch_chain(
        [
            _StubProvider("zai", "https://api.z.ai/api/paas/v4", ["glm-5.2"]),
            _StubProvider("groq", "https://api.groq.com/openai/v1", ["llama-3.3-70b"]),
        ],
        [
            httpx.Response(200, json={"choices": []}),  # 2xx, unusable
            httpx.Response(200, json=_openai_body("recovered")),
        ],
    )

    result = await failover_chat_completion(
        {"model": "glm-5.2", "messages": [{"role": "user", "content": "hi"}]}
    )

    assert result.text == "recovered"
    assert result.provider_id == "groq"


@pytest.mark.asyncio
async def test_non_json_2xx_body_fails_over(patch_chain) -> None:
    patch_chain(
        [_StubProvider("zai", "https://api.z.ai/api/paas/v4", ["glm-5.2"])],
        [httpx.Response(200, text="<html>gateway</html>")],
    )

    with pytest.raises(BrainFailoverExhausted) as excinfo:
        await failover_chat_completion(
            {"model": "glm-5.2", "messages": [{"role": "user", "content": "hi"}]}
        )

    assert "malformed" in excinfo.value.last_error


@pytest.mark.asyncio
async def test_null_content_is_treated_as_malformed(patch_chain) -> None:
    patch_chain(
        [_StubProvider("zai", "https://api.z.ai/api/paas/v4", ["glm-5.2"])],
        [httpx.Response(200, json={"choices": [{"message": {"content": None}}]})],
    )

    with pytest.raises(BrainFailoverExhausted):
        await failover_chat_completion(
            {"model": "glm-5.2", "messages": [{"role": "user", "content": "hi"}]}
        )


def test_dispatcher_stays_within_the_function_length_limit() -> None:
    """ENGINEERING_STANDARDS caps functions at 50 lines."""
    import inspect

    source_lines, _ = inspect.getsourcelines(failover_chat_completion)

    assert len(source_lines) <= 50, (
        f"failover_chat_completion is {len(source_lines)} lines; the repo caps "
        f"functions at 50. Extract another helper."
    )
