"""tests/test_brain_failover.py — Universal multi-provider brain failover tests.

Tests cover:
  * Provider registry building from env vars
  * Circuit breaker states (CLOSED → OPEN → HALF_OPEN → CLOSED)
  * 429/410/5xx failure handling + cooldown
  * next_provider() ordering (free first, then local, then paid)
  * Model alias mapping
  * Status snapshot for observability
  * Singleton reset
"""
from __future__ import annotations

import time
import pytest

from services.brain_failover import (
    BrainFailoverManager,
    ProviderHealth,
    get_failover_manager,
    reset_failover_manager,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Strip all provider API keys before each test."""
    for k in [
        "NVIDIA_API_KEY", "GROQ_API_KEY", "CEREBRAS_API_KEY", "ZHIPU_API_KEY",
        "DEEPSEEK_API_KEY", "TOGETHER_API_KEY", "DASHSCOPE_API_KEY",
        "MOONSHOT_API_KEY", "OPENROUTER_API_KEY", "MINIMAX_API_KEY",
        "GOOGLE_API_KEY", "ANTHROPIC_API_KEY", "ALLOW_PAID_BRAIN",
    ]:
        monkeypatch.delenv(k, raising=False)
    reset_failover_manager()
    yield
    reset_failover_manager()


def _make_manager():
    """Make a fresh manager (bypasses the singleton for isolation)."""
    return BrainFailoverManager()


# ── Registry building ────────────────────────────────────────────────────


def test_no_providers_when_no_keys(monkeypatch):
    """No API keys set → no providers in the registry."""
    mgr = _make_manager()
    providers = mgr.get_providers()
    # Only ollama (no key required) might be present
    ids = [p.id for p in providers]
    assert "ollama" in ids or len(ids) == 0


def test_nvidia_registered_when_key_set(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    mgr = _make_manager()
    providers = mgr.get_providers()
    ids = [p.id for p in providers]
    assert "nvidia" in ids


def test_multiple_providers_registered(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.setenv("ZHIPU_API_KEY", "zhipu-test")
    mgr = _make_manager()
    ids = [p.id for p in mgr.get_providers()]
    assert "nvidia" in ids
    assert "groq" in ids
    assert "zhipu" in ids


def test_paid_providers_skipped_by_default(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    mgr = _make_manager()
    ids = [p.id for p in mgr.get_providers()]
    assert "nvidia" in ids
    assert "anthropic" not in ids  # paid, not allowed by default


def test_paid_providers_included_when_allowed(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("ALLOW_PAID_BRAIN", "true")
    mgr = _make_manager()
    ids = [p.id for p in mgr.get_providers()]
    assert "anthropic" in ids


# ── next_provider ordering ───────────────────────────────────────────────


def test_next_provider_returns_free_first(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    mgr = _make_manager()
    p = mgr.next_provider()
    assert p is not None
    assert p.tier == "free"


def test_next_provider_excludes(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    mgr = _make_manager()
    p = mgr.next_provider(exclude={"nvidia"})
    assert p is not None
    assert p.id != "nvidia"


def test_next_provider_returns_none_when_all_excluded(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    mgr = _make_manager()
    p = mgr.next_provider(exclude={"nvidia", "ollama"})
    # Might return ollama if it's in the registry; exclude it too
    if p is not None:
        p = mgr.next_provider(exclude={"nvidia", "ollama", p.id})
    # Eventually returns None when all are excluded
    all_ids = {p.id for p in mgr.get_providers()}
    assert mgr.next_provider(exclude=all_ids) is None


def test_next_provider_prefers_model_match(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.setenv("ZHIPU_API_KEY", "zhipu-test")
    mgr = _make_manager()
    # Request z-ai/glm-5.2 — should prefer nvidia or zhipu
    p = mgr.next_provider(requested_model="z-ai/glm-5.2")
    assert p is not None
    assert p.id in ("nvidia", "zhipu")


# ── Circuit breaker ──────────────────────────────────────────────────────


def test_record_success_keeps_closed(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    mgr = _make_manager()
    mgr.record_success("nvidia", latency_ms=150.0)
    p = mgr.get_provider("nvidia")
    assert p.health == ProviderHealth.CLOSED
    assert p.failure_count == 0
    assert p.avg_latency_ms == 150.0


def test_record_429_opens_circuit(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    mgr = _make_manager()
    mgr.record_failure("nvidia", "rate_limited", 429)
    p = mgr.get_provider("nvidia")
    assert p.health == ProviderHealth.OPEN
    assert p.is_healthy is False
    assert p.cooldown_until > time.time()


def test_record_410_opens_circuit_long_cooldown(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    mgr = _make_manager()
    mgr.record_failure("nvidia", "gone", 410)
    p = mgr.get_provider("nvidia")
    assert p.health == ProviderHealth.OPEN
    # 410 = 10 minute cooldown
    assert p.cooldown_until > time.time() + 500


def test_record_5xx_opens_circuit_short_cooldown(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    mgr = _make_manager()
    mgr.record_failure("nvidia", "server_error", 503)
    p = mgr.get_provider("nvidia")
    assert p.health == ProviderHealth.OPEN
    # 5xx = 15s cooldown
    assert p.cooldown_until > time.time() + 10
    assert p.cooldown_until < time.time() + 30


def test_circuit_recovers_after_cooldown(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    mgr = _make_manager()
    # Manually set a short cooldown in the past
    mgr.record_failure("nvidia", "rate_limited", 429)
    p = mgr.get_provider("nvidia")
    p.cooldown_until = time.time() - 1  # expired
    assert p.is_healthy is True  # HALF_OPEN after cooldown
    # Record success → back to CLOSED
    mgr.record_success("nvidia")
    assert p.health == ProviderHealth.CLOSED


def test_429_exponential_backoff(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    mgr = _make_manager()
    # First failure
    mgr.record_failure("nvidia", "rate_limited", 429)
    p1 = mgr.get_provider("nvidia")
    first_cooldown = p1.cooldown_until

    # Second failure (after first cooldown expires)
    p1.health = ProviderHealth.CLOSED
    p1.failure_count = 1
    mgr.record_failure("nvidia", "rate_limited", 429)
    p2 = mgr.get_provider("nvidia")
    # Second cooldown should be longer (exponential)
    assert p2.cooldown_until > first_cooldown


def test_unhealthy_provider_skipped(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    mgr = _make_manager()
    # Mark nvidia as rate-limited
    mgr.record_failure("nvidia", "rate_limited", 429)
    # next_provider should skip nvidia
    p = mgr.next_provider()
    assert p is not None
    assert p.id != "nvidia"


# ── Model alias mapping ──────────────────────────────────────────────────


def test_resolve_model_exact_match(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    mgr = _make_manager()
    p = mgr.get_provider("nvidia")
    model = mgr.resolve_model(p, "meta/llama-3.3-70b-instruct")
    assert model == "meta/llama-3.3-70b-instruct"


def test_resolve_model_alias(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    mgr = _make_manager()
    nvidia = mgr.get_provider("nvidia")
    groq = mgr.get_provider("groq")
    # The same requested model maps differently per provider
    nvidia_model = mgr.resolve_model(nvidia, "meta/llama-3.3-70b-instruct")
    groq_model = mgr.resolve_model(groq, "meta/llama-3.3-70b-instruct")
    assert nvidia_model == "meta/llama-3.3-70b-instruct"
    assert groq_model == "llama-3.3-70b-versatile"


def test_resolve_model_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    mgr = _make_manager()
    p = mgr.get_provider("nvidia")
    model = mgr.resolve_model(p, "some-unknown-model-xyz")
    assert model == p.default_model


def test_resolve_model_fuzzy_match(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    mgr = _make_manager()
    p = mgr.get_provider("nvidia")
    # "llama-3.3-70b-instruct" should fuzzy-match "meta/llama-3.3-70b-instruct"
    model = mgr.resolve_model(p, "llama-3.3-70b-instruct")
    assert "llama-3.3-70b" in model.lower()


# ── Status snapshot ──────────────────────────────────────────────────────


def test_status_snapshot(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    mgr = _make_manager()
    snapshot = mgr.status_snapshot()
    assert "providers" in snapshot
    assert snapshot["total_providers"] >= 2
    assert snapshot["healthy_providers"] >= 2
    ids = [p["id"] for p in snapshot["providers"]]
    assert "nvidia" in ids
    assert "groq" in ids


def test_status_snapshot_no_api_keys(monkeypatch):
    """Status snapshot doesn't leak API keys."""
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-super-secret-key")
    mgr = _make_manager()
    snapshot = mgr.status_snapshot()
    for p in snapshot["providers"]:
        assert "api_key" not in p
        assert p["base_url"]  # base URL is fine to expose
    # Make sure the key isn't anywhere in the snapshot
    import json
    assert "nvapi-super-secret-key" not in json.dumps(snapshot)


# ── Singleton ────────────────────────────────────────────────────────────


def test_singleton(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    m1 = get_failover_manager()
    m2 = get_failover_manager()
    assert m1 is m2


def test_singleton_reset(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    m1 = get_failover_manager()
    reset_failover_manager()
    m2 = get_failover_manager()
    assert m1 is not m2


# ── max_attempts ─────────────────────────────────────────────────────────


def test_max_attempts(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    mgr = _make_manager()
    assert mgr.max_attempts() >= 2
