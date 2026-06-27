from __future__ import annotations

import json

import httpx
import pytest

from provider_router import (
    CommercialFallbackRequiredError,
    ProviderConfig,
    ProviderRouter,
    _normalize_nvidia_base_url,
    _openai_url,
    clear_cooldowns,
    extract_openai_text,
    is_commercial_provider,
)



# ── NVIDIA URL normalization tests (issue #363, item #8) ────────────────────

def test_normalize_nvidia_base_url_strips_trailing_v1():
    assert _normalize_nvidia_base_url("https://integrate.api.nvidia.com/v1") == "https://integrate.api.nvidia.com"


def test_normalize_nvidia_base_url_strips_trailing_v1_with_slash():
    assert _normalize_nvidia_base_url("https://integrate.api.nvidia.com/v1/") == "https://integrate.api.nvidia.com"


def test_normalize_nvidia_base_url_no_v1_unchanged():
    assert _normalize_nvidia_base_url("https://integrate.api.nvidia.com") == "https://integrate.api.nvidia.com"


def test_normalize_nvidia_base_url_strips_whitespace_and_v1():
    assert _normalize_nvidia_base_url("  https://integrate.api.nvidia.com/v1  ") == "https://integrate.api.nvidia.com"


def test_normalize_nvidia_base_url_empty_string():
    assert _normalize_nvidia_base_url("") == ""


def test_normalize_nvidia_base_url_none_fallback():
    assert _normalize_nvidia_base_url(None) == ""


def test_openai_url_with_v1_base_does_not_double():
    assert _openai_url("https://integrate.api.nvidia.com/v1", "/chat/completions") == "https://integrate.api.nvidia.com/v1/chat/completions"


def test_openai_url_without_v1_adds_v1():
    assert _openai_url("https://integrate.api.nvidia.com", "/chat/completions") == "https://integrate.api.nvidia.com/v1/chat/completions"


def test_openai_url_with_custom_path_does_not_add_v1():
    assert _openai_url("https://api.example.com/v1beta/openai", "/chat/completions") == "https://api.example.com/v1beta/openai/chat/completions"


def test_openai_url_models_endpoint_with_v1_base():
    assert _openai_url("https://integrate.api.nvidia.com/v1", "/models") == "https://integrate.api.nvidia.com/v1/models"


def test_openai_url_strips_trailing_slash():
    assert _openai_url("https://example.com/", "/chat/completions") == "https://example.com/v1/chat/completions"


@pytest.fixture(autouse=True)
async def reset_provider_cooldowns():
    """Clear module-level cooldown state before every test so tests don't bleed into each other."""
    await clear_cooldowns()
    yield
    await clear_cooldowns()


@pytest.mark.anyio
async def test_provider_router_falls_back_to_second_provider(monkeypatch):
    calls: list[str] = []

    async def fake_post_chat(self, provider, payload, timeout_sec):
        calls.append(provider.provider_id)
        if provider.provider_id == "ollama-local":
            return httpx.Response(503, json={"error": "down"})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "fallback-ok"}}]},
            headers={"content-type": "application/json"},
        )

    monkeypatch.setattr(ProviderRouter, "_post_chat", fake_post_chat)
    router = ProviderRouter(
        [
            ProviderConfig("ollama-local", "ollama", "http://localhost:11434", default_model="local", priority=0),
            ProviderConfig("openrouter", "openai-compatible", "https://openrouter.ai/api/v1", api_key="sk", default_model="cloud", priority=10),
        ]
    )

    result = await router.chat_completion({"model": "local", "messages": [{"role": "user", "content": "hi"}]}, max_retries=0)

    assert calls == ["ollama-local", "openrouter"]
    assert result.provider.provider_id == "openrouter"
    assert result.model == "cloud"
    assert extract_openai_text(result.response.json()) == "fallback-ok"


@pytest.mark.anyio
async def test_rate_limited_provider_fails_over_immediately_without_burning_retries(monkeypatch) -> None:
    """A 429 (e.g. 40 rpm hit) must NOT retry the same provider — it fails over to the
    next working provider at once and cools the rate-limited one."""
    from provider_router import is_provider_on_cooldown

    calls: list[str] = []

    async def fake_post_chat(self, provider, payload, timeout_sec):
        calls.append(provider.provider_id)
        if provider.provider_id == "fast-but-limited":
            return httpx.Response(429, json={"error": "rate limited"}, headers={"Retry-After": "17"})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "secondary-ok"}}]},
            headers={"content-type": "application/json"},
        )

    monkeypatch.setattr(ProviderRouter, "_post_chat", fake_post_chat)
    router = ProviderRouter(
        [
            ProviderConfig("fast-but-limited", "openai-compatible", "https://a/v1", api_key="k", default_model="a", priority=0),
            ProviderConfig("backup", "openai-compatible", "https://b/v1", api_key="k", default_model="b", priority=10),
        ]
    )

    # max_retries=2: the OLD behaviour would call fast-but-limited 3x before failover.
    result = await router.chat_completion(
        {"model": "a", "messages": [{"role": "user", "content": "hi"}]}, max_retries=2
    )

    # Rate-limited provider tried exactly once, then immediate failover.
    assert calls == ["fast-but-limited", "backup"]
    assert result.provider.provider_id == "backup"
    assert extract_openai_text(result.response.json()) == "secondary-ok"
    # And it was cooled down so subsequent requests skip it.
    assert await is_provider_on_cooldown("fast-but-limited") is True


# ── N1a: brain watchdog integration tests ────────────────────────────────────
# The provider router must fire-and-forget notify the brain watchdog on both
# success and failure-exhaustion paths so the watchdog's consecutive-failure
# counter is accurate. See services/brain_watchdog.py + docs/plans/next-pass-roadmap.md N1a.

@pytest.mark.anyio
async def test_provider_router_records_failure_on_failed_provider(monkeypatch):
    """When a provider call fails (and failover succeeds), the brain watchdog's
    record_failure MUST be called for the failed provider_id, and record_success
    for the one that succeeded."""
    import services.brain_watchdog as _bw  # top-level path used by tests

    # Reset the singleton so we get a clean watchdog state.
    _bw.reset_watchdog()
    real_wd = _bw.get_watchdog()
    failures: list[str] = []
    successes: list[str] = []

    def _stub_record_failure(provider):
        failures.append(provider)
        return None  # never trigger failover in this test
    def _stub_record_success(provider):
        successes.append(provider)

    monkeypatch.setattr(real_wd, "record_failure", _stub_record_failure)
    monkeypatch.setattr(real_wd, "record_success", _stub_record_success)
    # Ensure the lazy import in provider_router resolves to this same module
    # so monkeypatching is visible (it patches the instance, so identity is fine).
    monkeypatch.setattr(_bw, "get_watchdog", lambda: real_wd)

    async def fake_post_chat(self, provider, payload, timeout_sec):
        if provider.provider_id == "primary-down":
            return httpx.Response(503, json={"error": "down"})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}]},
            headers={"content-type": "application/json"},
        )

    monkeypatch.setattr(ProviderRouter, "_post_chat", fake_post_chat)
    router = ProviderRouter([
        ProviderConfig("primary-down", "openai-compatible", "https://a/v1", api_key="k", default_model="a", priority=0),
        ProviderConfig("backup-ok", "openai-compatible", "https://b/v1", api_key="k", default_model="b", priority=10),
    ])

    result = await router.chat_completion(
        {"model": "a", "messages": [{"role": "user", "content": "hi"}]},
        max_retries=0,
    )

    assert result.provider.provider_id == "backup-ok"
    # The failed provider had its failure recorded; the successful one had success recorded.
    assert failures == ["primary-down"]
    assert successes == ["backup-ok"]


@pytest.mark.anyio
async def test_provider_router_watchdog_notification_never_breaks_request(monkeypatch):
    """Even if the brain watchdog import itself fails, the request MUST still
    succeed — the watchdog hook is fire-and-forget."""
    # Force the lazy import inside _notify_watchdog to raise by sabotaging both
    # import paths. The request must still complete normally.
    import builtins
    real_import = builtins.__import__

    def _boom_import(name, *args, **kwargs):
        if name == "services.brain_watchdog" or name == "brain_watchdog":
            raise ImportError("simulated watchdog outage (test)")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _boom_import)

    async def fake_post_chat(self, provider, payload, timeout_sec):
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}]},
            headers={"content-type": "application/json"},
        )

    monkeypatch.setattr(ProviderRouter, "_post_chat", fake_post_chat)
    router = ProviderRouter([
        ProviderConfig("only", "openai-compatible", "https://a/v1", api_key="k", default_model="a", priority=0),
    ])

    result = await router.chat_completion(
        {"model": "a", "messages": [{"role": "user", "content": "hi"}]},
        max_retries=0,
    )
    assert result.provider.provider_id == "only"


def test_parse_retry_after_seconds_and_missing() -> None:
    assert ProviderRouter._parse_retry_after(httpx.Response(429, headers={"Retry-After": "20"})) == 20.0
    assert ProviderRouter._parse_retry_after(httpx.Response(429)) is None


@pytest.mark.anyio
async def test_provider_router_retries_model_fallback_on_404(monkeypatch):
    models: list[str] = []

    async def fake_post_chat(self, provider, payload, timeout_sec):
        models.append(payload["model"])
        if payload["model"] == "missing-model":
            return httpx.Response(404, json={"error": "missing"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "model-ok"}}]})

    monkeypatch.setattr(ProviderRouter, "_post_chat", fake_post_chat)
    router = ProviderRouter([ProviderConfig("ollama-local", "ollama", "http://localhost:11434", default_model="safe-model", priority=0)])

    result = await router.chat_completion(
        {"model": "missing-model", "messages": [{"role": "user", "content": "hi"}]},
        model_fallbacks=["safe-model"],
        max_retries=0,
    )

    assert models == ["missing-model", "safe-model"]
    assert result.model == "safe-model"


@pytest.mark.anyio
async def test_provider_router_passes_custom_provider_timeout(monkeypatch):
    captured: list[float] = []

    async def fake_post_chat(self, provider, payload, timeout_sec):
        captured.append(timeout_sec)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(ProviderRouter, "_post_chat", fake_post_chat)
    router = ProviderRouter(
        [ProviderConfig("ollama-local", "ollama", "http://localhost:11434", default_model="local", priority=0)]
    )

    await router.chat_completion(
        {"model": "local", "messages": [{"role": "user", "content": "hi"}]},
        max_retries=0,
        provider_timeout_sec=7.5,
    )

    assert captured == [7.5]


def test_provider_router_attempts_header_is_compact_json():
    header = ProviderRouter.attempts_header([])
    assert json.loads(header) == []


def test_provider_router_treats_emergent_anthropic_as_commercial():
    provider = ProviderConfig(
        provider_id="anthropic-universal",
        type="emergent-anthropic",
        base_url="emergent://anthropic",
        api_key="test-key",
        default_model="claude-sonnet-4-5-20250929",
    )

    assert is_commercial_provider(provider) is True


def test_provider_router_from_env_prioritizes_nvidia_nemotron_default(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nv-test-key")
    monkeypatch.delenv("NVIDIA_DEFAULT_MODEL", raising=False)

    router = ProviderRouter.from_env()

    assert router.providers[0].provider_id == "nvidia-nim"
    assert router.providers[0].default_model == "nvidia/llama-3.3-nemotron-super-49b-v1.5"


@pytest.mark.anyio
async def test_provider_router_respects_record_priority_for_configured_providers(monkeypatch):
    calls: list[str] = []

    async def fake_post_chat(self, provider, payload, timeout_sec):
        calls.append(provider.provider_id)
        if provider.provider_id == "deepseek":
            return httpx.Response(200, json={"choices": [{"message": {"content": "free-cloud-ok"}}]})
        return httpx.Response(503, json={"error": "down"})

    monkeypatch.setattr(ProviderRouter, "_post_chat", fake_post_chat)
    router = ProviderRouter.from_provider_records(
        [
            {"provider_id": "anthropic", "type": "anthropic", "base_url": "https://api.anthropic.com", "default_model": "claude-sonnet-4-5", "priority": 40},
            {"provider_id": "remote-win", "type": "openai-compatible", "base_url": "https://my-tunnel.ngrok-free.app/v1", "default_model": "remote-model", "priority": 20},
            {"provider_id": "deepseek", "type": "openai-compatible", "base_url": "https://api.deepseek.com", "default_model": "deepseek-chat", "priority": 10},
            {"provider_id": "ollama-local", "type": "ollama", "base_url": "http://localhost:11434", "default_model": "local-model", "priority": 30},
        ]
    )

    result = await router.chat_completion({"model": "local-model", "messages": [{"role": "user", "content": "hi"}]}, max_retries=0)

    assert calls == ["deepseek"]
    assert result.provider.provider_id == "deepseek"


@pytest.mark.anyio
async def test_provider_router_requires_approval_before_commercial_fallback(monkeypatch):
    async def fake_post_chat(self, provider, payload, timeout_sec):
        return httpx.Response(503, json={"error": "down"})

    monkeypatch.setattr(ProviderRouter, "_post_chat", fake_post_chat)
    router = ProviderRouter.from_provider_records(
        [
            {"provider_id": "ollama-local", "type": "ollama", "base_url": "http://localhost:11434", "default_model": "local-model"},
            {"provider_id": "anthropic", "type": "anthropic", "base_url": "https://api.anthropic.com", "default_model": "claude-sonnet-4-5"},
        ]
    )

    with pytest.raises(CommercialFallbackRequiredError) as exc:
        await router.chat_completion(
            {"model": "local-model", "messages": [{"role": "user", "content": "hi"}]},
            max_retries=0,
            allow_commercial_fallback=False,
        )

    assert exc.value.candidates == ["anthropic"]


def test_provider_router_infers_anthropic_type_from_base_url():
    router = ProviderRouter.from_provider_records(
        [
            {
                "provider_id": "anthropic-saved-as-openai",
                "type": "openai-compatible",
                "base_url": "https://api.anthropic.com",
                "api_key": "sk-ant-test",
                "default_model": "claude-sonnet-4-6",
            }
        ]
    )

    assert len(router.providers) == 1
    assert router.providers[0].type == "anthropic"


@pytest.mark.anyio
async def test_provider_router_can_use_emergent_provider(monkeypatch):
    async def fake_emergent(self, provider, payload, timeout_sec):
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok from emergent"}}]})

    monkeypatch.setattr(ProviderRouter, "_post_emergent_chat", fake_emergent)
    router = ProviderRouter([
        ProviderConfig(
            provider_id="anthropic-universal",
            type="emergent-anthropic",
            base_url="emergent://anthropic",
            api_key="test-key",
            default_model="claude-sonnet-4-5-20250929",
        )
    ])

    result = await router.chat_completion(
        {"model": "claude-sonnet-4-5-20250929", "messages": [{"role": "user", "content": "hi"}]},
        max_retries=0,
        allow_commercial_fallback=True,
    )

    assert extract_openai_text(result.response.json()) == "ok from emergent"