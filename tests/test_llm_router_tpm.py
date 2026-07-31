"""A per-minute token budget is an input ceiling, not just a sort key.

Reproduces the failure that blocked agent tasks in production:

    All 6 brain provider attempt(s) failed: nvidia HTTP 404; groq HTTP 400:
    model unavailable; groq HTTP 413: {"error":{"message":"Request too large
    for model `llama-3.3-70b-versatile` ... on tokens per minute (TPM): Limit
    12000, Requested 17599 ...

Groq serves that model behind a 131k context window and a 12,000 TPM account
budget. The router sized requests against the window alone, so a 17.6k-token
planning prompt looked like it fit, was sent, and was refused — and because the
prompt was never shrunk, the next free provider refused it too. Two bugs in one
error: the ceiling was not honoured, and the 413 announcing it was classified
as a permanent payload error rather than the per-minute rate limit it is.
"""
from __future__ import annotations

import asyncio
from dataclasses import replace

import httpx
import pytest

from packages.llm import budget as llm_budget
from packages.llm import cache as llm_cache
from packages.llm import config as llm_config
from packages.llm import health as llm_health
from packages.llm import keys as llm_keys
from packages.llm import metrics as llm_metrics
from packages.llm import registry as llm_registry
from packages.llm import router as llm_router
from packages.llm import strategies as llm_strategies
from packages.llm.context import total_tokens
from packages.llm.providers.base import classify_error
from packages.llm.router import LLMRouter
from packages.llm.types import LLMRequest, PermanentError, TransientError

# `metered` advertises a huge window behind a small per-minute budget — the
# Groq free-tier shape. `roomy` is unmetered and is where an oversized request
# should end up if nothing is shrunk.
PROVIDERS_YAML = """
providers:
  metered:
    kind: openai
    base_url: https://metered.test/v1
    key_env: [METERED_KEY]
    tier: free
    priority: 10
    max_concurrency: 4
    tokens_per_minute: 4000
  roomy:
    kind: openai
    base_url: https://roomy.test/v1
    key_env: [ROOMY_KEY]
    tier: free
    priority: 20
    max_concurrency: 4
"""

MODELS_YAML = """
models:
  metered-model:
    provider: metered
    context_window: 131072
    max_output_tokens: 1024
    priority: 10
  roomy-model:
    provider: roomy
    context_window: 131072
    max_output_tokens: 1024
    priority: 20
"""

ROUTING_YAML = """
routing:
  strategy: priority
  escalate_context: false
  retry:
    max_attempts: 4
    base_delay_sec: 0.0
    max_delay_sec: 0.0
    budget_sec: 10.0
"""

_MODULES = (llm_config, llm_registry, llm_health, llm_keys,
            llm_cache, llm_budget, llm_metrics, llm_router)


def _ok(model="metered-model"):
    return httpx.Response(200, json={
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 5},
    })


# The real Groq body, trimmed. Its shape is the whole point: a 413 status
# carrying a tokens-per-minute message.
GROQ_TPM_BODY = {
    "error": {
        "message": (
            "Request too large for model `llama-3.3-70b-versatile` in "
            "organization `org_test` service tier `on_demand` on tokens per "
            "minute (TPM): Limit 12000, Requested 17599, please reduce your "
            "message size and try again."
        ),
        "type": "tokens",
        "code": "rate_limit_exceeded",
    }
}


@pytest.fixture
def router_factory(tmp_path, monkeypatch):
    (tmp_path / "providers.yaml").write_text(PROVIDERS_YAML, encoding="utf-8")
    (tmp_path / "models.yaml").write_text(MODELS_YAML, encoding="utf-8")
    (tmp_path / "routing.yaml").write_text(ROUTING_YAML, encoding="utf-8")

    monkeypatch.setenv("LLM_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("LLM_ROUTER_ENABLED", "true")
    monkeypatch.setenv("METERED_KEY", "metered-key")
    monkeypatch.setenv("ROOMY_KEY", "roomy-key")
    for name in ("NVIDIA_API_KEY", "GROQ_API_KEY", "CEREBRAS_API_KEY",
                 "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY",
                 "ANTHROPIC_API_KEY", "OLLAMA_BASE"):
        monkeypatch.delenv(name, raising=False)

    for module in _MODULES:
        module.reset()
    llm_strategies.reset()

    built: list[LLMRouter] = []

    def build(handler):
        instance = LLMRouter()
        instance._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        built.append(instance)
        return instance

    yield build

    for module in _MODULES:
        module.reset()
    llm_strategies.reset()
    for instance in built:
        client = getattr(instance, "_client", None)
        if client is not None and not client.is_closed:
            asyncio.run(client.aclose())


def _big_request(approx_tokens: int, *, turns: int = 40) -> LLMRequest:
    """A conversation comfortably past the metered provider's per-minute budget.

    Spread over many turns on purpose: that is the shape an agent planning
    prompt actually has (system brief, then accumulated history), and it is the
    shape the lossless context manager can shrink. A single enormous message is
    irreducible by design — message text is never rewritten — so a test built
    on one would be asserting a policy the router deliberately does not have.
    """
    # total_tokens() approximates ~4 characters per token.
    chars_per_turn = (approx_tokens * 4) // turns
    messages = [{"role": "system", "content": "plan the task"}]
    for i in range(turns):
        messages.append({
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"step {i}: " + ("x" * chars_per_turn),
        })
    messages.append({"role": "user", "content": "now produce the plan"})
    return LLMRequest(messages=messages, max_tokens=256)


# ── The ceiling is honoured ──────────────────────────────────────────────────


def test_usable_window_clamps_to_the_per_minute_budget(router_factory):
    """A 131k window behind a 4k budget is a 4k ceiling."""
    router = router_factory(lambda _r: _ok())
    metered = next(c for c in router._candidates(_big_request(50))
                   if c.provider.id == "metered")
    roomy = next(c for c in router._candidates(_big_request(50))
                 if c.provider.id == "roomy")

    assert metered.model.context_window == 131072
    assert router._usable_window(metered) == 4000, (
        "the advertised window was used instead of the account's TPM budget"
    )
    assert router._usable_window(roomy) == 131072, (
        "an unmetered provider must keep its full window"
    )


async def test_an_oversized_prompt_prefers_the_unmetered_provider(router_factory):
    """Routing around the low ceiling beats compressing to fit it."""
    seen: list[str] = []

    def handler(request):
        seen.append(request.url.host)
        return _ok(model="roomy-model")

    router = router_factory(handler)
    response = await router.chat(_big_request(9000))

    assert response.provider == "roomy"
    assert "metered.test" not in seen, (
        "a request past the per-minute budget should not be sent there at all"
    )


async def test_an_oversized_prompt_is_shrunk_when_the_ceiling_is_all_there_is(
    router_factory,
):
    """Production's case: every reachable provider has a low ceiling.

    Nothing can be routed around, so the request has to be made sendable
    instead of being sent and refused — which is what left agent tasks with
    six failed attempts and no completion.
    """
    sent: list[list[dict]] = []

    def handler(request):
        import json
        sent.append(json.loads(request.content)["messages"])
        return _ok()

    request = replace(_big_request(9000), providers=["metered"])
    router = router_factory(handler)
    await router.chat(request)

    assert sent, "no request was sent"
    # Assert against the implementation's own ceiling rather than a magic
    # number, so the test cannot drift from the reserve policy it is pinning.
    ceiling = router._context.budget_for(4000, request.max_tokens)
    assert total_tokens(sent[0]) <= ceiling, (
        f"sent {total_tokens(sent[0])} tokens against a {ceiling}-token ceiling "
        "— the prompt was not fitted"
    )
    assert total_tokens(sent[0]) < total_tokens(request.messages), "nothing was dropped"
    # The task definition and the live question must both survive the shrink.
    assert sent[0][0]["role"] == "system"
    assert sent[0][-1]["content"] == "now produce the plan"


async def test_a_request_within_the_budget_is_left_alone(router_factory):
    """No compression tax on requests that already fit."""
    original = LLMRequest(messages=[{"role": "user", "content": "hello"}])
    seen: list[dict] = []

    def handler(request):
        import json
        seen.append(json.loads(request.content))
        return _ok()

    router = router_factory(handler)
    await router.chat(original)

    assert seen[0]["messages"] == [{"role": "user", "content": "hello"}]


# ── The 413 that announces it ────────────────────────────────────────────────


def test_a_tpm_413_is_classified_as_a_rate_limit_not_a_payload_error():
    """Groq reports its per-minute budget with a 413. It clears in a minute."""
    import json
    error = classify_error(413, json.dumps(GROQ_TPM_BODY), provider_id="groq")

    assert isinstance(error, TransientError), (
        "a per-minute budget is transient — it resets without anyone doing anything"
    )
    assert error.scope == "key", "same blame and recovery as a 429"


def test_a_genuine_413_stays_permanent():
    """Not every 413 is a rate limit — a real payload refusal must stay one."""
    error = classify_error(413, "request entity too large", provider_id="alpha")
    assert isinstance(error, PermanentError)


async def test_a_tpm_413_rotates_keys_before_leaving_the_provider(router_factory,
                                                                 monkeypatch):
    """Key scope means the sibling key gets a turn — that is the point of it."""
    import json
    monkeypatch.setenv("METERED_KEY", "key-one,key-two")
    for module in _MODULES:
        module.reset()
    llm_strategies.reset()

    keys_tried: list[str] = []

    def handler(request):
        if request.url.host == "metered.test":
            keys_tried.append(request.headers.get("authorization", ""))
            return httpx.Response(413, json=GROQ_TPM_BODY)
        return _ok(model="roomy-model")

    router = router_factory(handler)
    response = await router.chat(LLMRequest(
        messages=[{"role": "user", "content": "hi"}], max_tokens=64,
    ))

    assert response.provider == "roomy", "it must still reach a working provider"
    assert len(set(keys_tried)) == 2, (
        f"only {len(set(keys_tried))} key(s) tried — a key-scoped failure must rotate"
    )
