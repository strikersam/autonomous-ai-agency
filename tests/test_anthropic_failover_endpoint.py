"""Regression tests for the agent loop's multi-provider failover wire format.

Production symptom this guards against::

    Task task_... blocked after 5 failed dispatch attempts (No runtime available):
    Runtime 'internal_agent' execution error: planning: Client error
    '400 Bad Request' for url 'https://api.anthropic.com/v1/chat/completions'

``services/brain_failover`` offers ``anthropic`` as an ordinary failover
candidate whenever a paid brain is allowed, but the loop built every request as
OpenAI-compatible: ``POST {base}/v1/chat/completions`` with
``Authorization: Bearer``. Anthropic's native API serves neither that route nor
that auth scheme, so the call 400s for *every* model on the provider — burning
the whole dispatch budget on a deterministic failure.
"""
from __future__ import annotations

import pytest

from packages.ai.router import ProviderConfig, ProviderRouter, is_anthropic_base_url


class TestIsAnthropicBaseUrl:
    """Only Anthropic's own API is native; Claude gateways stay OpenAI-shaped."""

    @pytest.mark.parametrize(
        "base_url",
        [
            "https://api.anthropic.com",
            "https://api.anthropic.com/",
            "HTTPS://API.ANTHROPIC.COM",
            "https://anthropic.com",
        ],
    )
    def test_anthropic_hosts_are_native(self, base_url: str) -> None:
        assert is_anthropic_base_url(base_url) is True

    @pytest.mark.parametrize(
        "base_url",
        [
            # OpenAI-compatible Claude gateways — must NOT be rewritten to
            # /v1/messages, they genuinely serve /chat/completions.
            "https://capi.aerolink.lat/v1",
            "https://openrouter.ai/api/v1",
            # Look-alike host: endswith("anthropic.com") would wrongly match.
            "https://notanthropic.com",
            "https://evil-anthropic.com.attacker.test",
            "http://localhost:11434",
            "",
            None,
        ],
    )
    def test_non_anthropic_bases_are_not_native(self, base_url: str | None) -> None:
        assert is_anthropic_base_url(base_url) is False


class TestAnthropicRequestShape:
    """The pieces the failover loop assembles for an Anthropic-native provider."""

    def test_url_is_messages_not_chat_completions(self) -> None:
        cfg = ProviderConfig(
            provider_id="anthropic",
            type="anthropic",
            base_url="https://api.anthropic.com",
            api_key="sk-ant-test",
        )
        url = f"{cfg.normalized_base_url}/v1/messages"

        assert url == "https://api.anthropic.com/v1/messages"
        # The exact URL from the production traceback must never be rebuilt.
        assert url != "https://api.anthropic.com/v1/chat/completions"
        assert "chat/completions" not in url

    def test_auth_uses_x_api_key_not_bearer(self) -> None:
        cfg = ProviderConfig(
            provider_id="anthropic",
            type="anthropic",
            base_url="https://api.anthropic.com",
            api_key="sk-ant-test",
        )
        headers = cfg.auth_headers()

        assert headers["x-api-key"] == "sk-ant-test"
        assert "anthropic-version" in headers
        # Anthropic rejects Bearer auth outright.
        assert "Authorization" not in headers

    def test_payload_is_translated_to_messages_api(self) -> None:
        openai_payload = {
            "model": "claude-sonnet-5",
            "messages": [
                {"role": "system", "content": "You are a planner."},
                {"role": "user", "content": "Plan the task."},
            ],
            "max_tokens": 16384,
            "temperature": 0.3,
        }

        translated = ProviderRouter._anthropic_payload(openai_payload)

        # System prompts move out of `messages` into the top-level `system`
        # field — Anthropic rejects role="system" inside messages.
        assert all(m["role"] != "system" for m in translated["messages"])
        assert translated["messages"] == [
            {"role": "user", "content": "Plan the task."}
        ]
        assert "You are a planner." in str(translated["system"])
        assert translated["model"] == "claude-sonnet-5"
        assert translated["max_tokens"] == 16384

    def test_response_is_translated_back_to_openai_shape(self) -> None:
        import httpx

        anthropic_body = {
            "id": "msg_123",
            "content": [{"type": "text", "text": '{"steps": []}'}],
            "usage": {"input_tokens": 11, "output_tokens": 7},
        }
        resp = httpx.Response(200, json=anthropic_body)

        converted = ProviderRouter._anthropic_to_openai_response(
            resp, "claude-sonnet-5"
        )
        data = converted.json()

        # The failover loop's success path reads exactly these keys.
        assert data["choices"][0]["message"]["content"] == '{"steps": []}'
        assert data["usage"]["prompt_tokens"] == 11
        assert data["usage"]["completion_tokens"] == 7


class TestFailoverRegistryBaseUrls:
    """Registry base URLs must produce routes the provider actually serves."""

    def test_gemini_base_url_includes_openai_compat_path(self) -> None:
        from packages.ai.router import _openai_url
        from services.brain_failover import _PROVIDER_REGISTRY

        google = next(p for p in _PROVIDER_REGISTRY if p["id"] == "google")
        url = _openai_url(google["default_base_url"], "/chat/completions")

        # Gemini serves its OpenAI-compatible surface under /v1beta/openai.
        # The bare host yields /v1/chat/completions, which 404s.
        assert url == (
            "https://generativelanguage.googleapis.com"
            "/v1beta/openai/chat/completions"
        )

    def test_registry_base_urls_match_the_model_catalog(self) -> None:
        """brain_failover must not drift from the catalog's base URLs."""
        from packages.ai.brain_config import PROVIDER_DEFAULT_BASE_URL
        from services.brain_failover import _PROVIDER_REGISTRY

        mismatches = []
        for spec in _PROVIDER_REGISTRY:
            catalog_url = PROVIDER_DEFAULT_BASE_URL.get(spec["id"])
            if catalog_url is None:
                continue
            if catalog_url.rstrip("/") != spec["default_base_url"].rstrip("/"):
                mismatches.append(
                    f"{spec['id']}: failover={spec['default_base_url']!r} "
                    f"catalog={catalog_url!r}"
                )

        assert not mismatches, (
            "brain_failover base URLs disagree with "
            "packages.ai.brain_config.PROVIDER_DEFAULT_BASE_URL: "
            + "; ".join(mismatches)
        )
