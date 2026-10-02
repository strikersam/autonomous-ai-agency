"""tests/test_siliconflow_provider.py — SiliconFlow is wired as a free provider.

It joins the gateway (config/llm), the legacy failover registry, the provider
tiering and the Render "Set key" mapping, and only its zero-cost models route.
"""
from __future__ import annotations

from packages.ai.router import provider_access_tier
from packages.integrations.render_env import provider_env_names


def test_gateway_loads_siliconflow_as_free_with_only_zero_cost_models(monkeypatch):
    from packages.llm import config as llm_config
    from packages.llm import registry as llm_registry

    monkeypatch.delenv("LLM_CONFIG_DIR", raising=False)
    monkeypatch.delenv("SILICONFLOW_BASE_URL", raising=False)
    llm_config.reset()
    llm_registry.reset()
    try:
        provider = llm_config.get_config().providers["siliconflow"]
        assert provider.tier == "free"
        assert provider.base_url == "https://api.siliconflow.com/v1"
        free = llm_registry.get_registry().candidates(provider_id="siliconflow", allow_paid=False)
        assert {m.id for m in free} == {"Qwen/Qwen3-8B", "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"}
    finally:
        llm_config.reset()
        llm_registry.reset()


def test_china_endpoint_override(monkeypatch):
    from packages.llm import config as llm_config

    monkeypatch.delenv("LLM_CONFIG_DIR", raising=False)
    monkeypatch.setenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    llm_config.reset()
    try:
        assert llm_config.get_config().providers["siliconflow"].base_url == "https://api.siliconflow.cn/v1"
    finally:
        llm_config.reset()


def test_legacy_tiering_and_render_key_mapping():
    for host in ("https://api.siliconflow.com/v1", "https://api.siliconflow.cn/v1"):
        record = {"provider_id": "custom", "type": "openai-compatible", "base_url": host}
        assert provider_access_tier(record) == "free_cloud"
    assert provider_access_tier({"provider_id": "siliconflow", "base_url": "x"}) == "free_cloud"
    assert provider_env_names("siliconflow") == ("SILICONFLOW_API_KEY", "SILICONFLOW_BASE_URL")


def test_openrouter_free_models_route_without_paid(monkeypatch):
    """OpenRouter was tier 'cheap', so the router skipped it whenever paid was off."""
    from packages.llm import config as llm_config
    from packages.llm import registry as llm_registry

    monkeypatch.delenv("LLM_CONFIG_DIR", raising=False)
    llm_config.reset()
    llm_registry.reset()
    try:
        assert not llm_config.get_config().providers["openrouter"].is_paid
        free = {m.id for m in llm_registry.get_registry().candidates(provider_id="openrouter", allow_paid=False)}
        assert "nvidia/nemotron-3-super-120b-a12b:free" in free
        assert "openrouter/free" in free
        tools = {m.id for m in llm_registry.get_registry().candidates(
            provider_id="openrouter", allow_paid=False, require_tools=True)}
        assert tools == {"nvidia/nemotron-3-super-120b-a12b:free"}
    finally:
        llm_config.reset()
        llm_registry.reset()
