"""Configuration loading for the LLM routing layer (ADR-008).

The critical property under test is that ``config/llm/*.yaml`` never contains
key material and never causes one: the loader must carry variable *names*
through to the key ring and resolve values only at call time.
"""
from __future__ import annotations

import textwrap

import pytest

from packages.llm import config as llm_config
from packages.llm import keys as llm_keys


@pytest.fixture(autouse=True)
def _clean_config():
    llm_config.reset()
    llm_keys.reset()
    yield
    llm_config.reset()
    llm_keys.reset()


def _write(tmp_path, name: str, body: str) -> None:
    (tmp_path / f"{name}.yaml").write_text(textwrap.dedent(body), encoding="utf-8")


def test_missing_config_dir_falls_back_to_env_defaults(tmp_path, monkeypatch):
    """No YAML at all must still yield a working provider set."""
    monkeypatch.setenv("NVIDIA_API_KEY", "nv-key")
    cfg = llm_config.load_config(tmp_path / "does-not-exist")

    assert "nvidia" in cfg.providers
    assert cfg.providers["nvidia"].key_env == ["NVIDIA_API_KEY"]
    assert cfg.routing.strategy == "adaptive"


def test_env_expansion_with_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("MY_BASE", "https://example.test/v1")
    monkeypatch.setenv("MY_KEY", "secret")
    _write(tmp_path, "providers", """
        providers:
          demo:
            kind: openai
            base_url: ${MY_BASE}
            key_env: [MY_KEY]
            tier: ${DEMO_TIER:-free}
    """)
    cfg = llm_config.load_config(tmp_path)

    assert cfg.providers["demo"].base_url == "https://example.test/v1"
    assert cfg.providers["demo"].tier == "free"


def test_string_false_from_env_is_a_real_false(tmp_path, monkeypatch):
    """``${X:-false}`` expands to the string "false", which is truthy.

    Without coercion an unconfigured provider would be *enabled* by a config
    file that plainly says it is off.
    """
    monkeypatch.delenv("DEMO_ENABLED", raising=False)
    _write(tmp_path, "providers", """
        providers:
          demo:
            kind: openai
            base_url: http://localhost:1234/v1
            requires_key: false
            enabled: ${DEMO_ENABLED:-false}
            max_concurrency: ${DEMO_CONC:-3}
    """)
    cfg = llm_config.load_config(tmp_path)

    assert cfg.providers["demo"].enabled is False
    assert cfg.providers["demo"].max_concurrency == 3
    # Env-derived providers (a keyless local Ollama) may still be present —
    # what matters is that the disabled entry stays out of rotation.
    assert "demo" not in {p.id for p in cfg.enabled_providers()}


def test_keys_yaml_contributes_names_never_values(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_KEY_A", "value-a")
    monkeypatch.setenv("DEMO_KEY_B", "value-b")
    _write(tmp_path, "providers", """
        providers:
          demo:
            kind: openai
            base_url: http://demo.test/v1
            key_env: [DEMO_KEY_A]
    """)
    _write(tmp_path, "keys", """
        keys:
          demo:
            env: [DEMO_KEY_B]
    """)
    cfg = llm_config.load_config(tmp_path)
    provider = cfg.providers["demo"]

    assert provider.key_env == ["DEMO_KEY_A", "DEMO_KEY_B"]
    # The config object holds names, not secrets.
    assert "value-a" not in repr(provider)
    assert "value-b" not in repr(provider)
    # Values appear only when explicitly resolved from the environment.
    assert llm_keys.resolve_keys(provider.key_env) == ["value-a", "value-b"]


def test_unknown_keys_are_ignored_not_fatal(tmp_path):
    _write(tmp_path, "providers", """
        providers:
          demo:
            kind: openai
            base_url: http://demo.test/v1
            requires_key: false
            this_key_does_not_exist: 42
    """)
    cfg = llm_config.load_config(tmp_path)
    assert cfg.providers["demo"].base_url == "http://demo.test/v1"


def test_malformed_yaml_degrades_to_defaults(tmp_path):
    (tmp_path / "routing.yaml").write_text("routing: [this is not a mapping", encoding="utf-8")
    cfg = llm_config.load_config(tmp_path)
    assert cfg.routing.strategy == "adaptive"


def test_agent_policies_load(tmp_path):
    _write(tmp_path, "routing", """
        routing:
          strategy: cost_optimized
          retry:
            max_attempts: 3
            jitter: 0.1
          agents:
            planner:
              strategy: model_capability
              min_context_window: 32768
              priority: HIGH
          budget:
            monthly_usd: 25.0
            enforce: true
    """)
    cfg = llm_config.load_config(tmp_path)

    assert cfg.routing.strategy == "cost_optimized"
    assert cfg.routing.retry.max_attempts == 3
    assert cfg.policy_for("planner").strategy == "model_capability"
    assert cfg.budget.monthly_usd == 25.0
    assert cfg.budget.enforce is True


def test_env_overrides_beat_yaml(tmp_path, monkeypatch):
    _write(tmp_path, "routing", "routing:\n  strategy: priority\n")
    monkeypatch.setenv("LLM_ROUTER_STRATEGY", "lowest_latency")
    monkeypatch.setenv("ALLOW_PAID_BRAIN", "true")

    cfg = llm_config.load_config(tmp_path)
    assert cfg.routing.strategy == "lowest_latency"
    assert cfg.routing.allow_paid is True


def test_router_disabled_by_default(monkeypatch):
    monkeypatch.delenv("LLM_ROUTER_ENABLED", raising=False)
    assert llm_config.router_enabled() is False
    monkeypatch.setenv("LLM_ROUTER_ENABLED", "true")
    assert llm_config.router_enabled() is True


def test_shipped_config_parses():
    """The committed config/llm/*.yaml must actually load."""
    cfg = llm_config.load_config()
    assert cfg.providers, "config/llm/providers.yaml produced no providers"
    assert cfg.models, "config/llm/models.yaml produced no models"
    assert cfg.routing.fallback_chain
    # Embedding-only models must be flagged so chat routing skips them.
    assert cfg.models["nomic-embed-text"].supports_chat is False
