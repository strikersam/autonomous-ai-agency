"""tests/test_anthropic_prompt_cache_ttl.py — extended-TTL prompt caching on
the legacy proxy path.

Anthropic's prompt cache defaults to a 5-minute TTL (``cache_control.type =
"ephemeral"``). Since 2025-04 an operator can extend it to a 1-hour TTL by
adding ``ttl: "1h"`` to the same block and requesting the
``extended-cache-ttl-2025-04-11`` beta. For the agent loop — plan → execute →
verify — the same system prompt is re-sent many times per hour, so a 1-hour
TTL cuts the number of cache refreshes an operator pays for by ~12×.

The single knob is ``ANTHROPIC_CACHE_TTL`` (``5m`` default, or ``1h``). The
newer ``AnthropicProvider`` adapter already honours it via
``packages/llm/config.py`` and is covered by
``tests/test_anthropic_conversation_caching.py``. This module covers the *other*
Anthropic path — the legacy OpenAI→Anthropic translator in
``packages/ai/router.py`` used by ``proxy.py`` — which reads the same env var so
both paths share one setting. Opt-in: the default (``5m``) keeps existing
behaviour byte-identical.
"""
from __future__ import annotations


class TestLegacyRouterCacheTTL:
    """The OpenAI→Anthropic translator applies the configured TTL to system."""

    def _payload_with_system(self):
        return {
            "model": "claude-sonnet-5",
            "messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "hi"},
            ],
        }

    def test_default_ttl_is_ephemeral_without_ttl_field(self, monkeypatch):
        """No env override → the block stays ``{"type": "ephemeral"}`` — no
        ``ttl`` key. This is the byte-identical-to-prior-behaviour guarantee."""
        monkeypatch.delenv("ANTHROPIC_CACHE_TTL", raising=False)
        from packages.ai.router import ProviderRouter

        result = ProviderRouter._anthropic_payload(self._payload_with_system())
        assert isinstance(result["system"], list)
        cc = result["system"][0]["cache_control"]
        assert cc == {"type": "ephemeral"}, (
            f"Default cache_control must be exactly the 5m form; got {cc!r}"
        )

    def test_ttl_1h_adds_ttl_field(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_CACHE_TTL", "1h")
        from packages.ai.router import ProviderRouter

        result = ProviderRouter._anthropic_payload(self._payload_with_system())
        cc = result["system"][0]["cache_control"]
        assert cc == {"type": "ephemeral", "ttl": "1h"}

    def test_ttl_5m_explicit_is_still_ttlless(self, monkeypatch):
        """``5m`` is the API default. Sending ``ttl: "5m"`` is legal but
        redundant, and the extended-TTL beta is only needed for a non-default
        TTL. Keep the block clean when the value is 5m."""
        monkeypatch.setenv("ANTHROPIC_CACHE_TTL", "5m")
        from packages.ai.router import ProviderRouter

        result = ProviderRouter._anthropic_payload(self._payload_with_system())
        assert result["system"][0]["cache_control"] == {"type": "ephemeral"}

    def test_invalid_ttl_falls_back_to_default(self, monkeypatch):
        """Anthropic only accepts ``5m`` and ``1h`` today. An unknown value is
        an operator typo — silently use the default rather than sending it and
        breaking every request."""
        monkeypatch.setenv("ANTHROPIC_CACHE_TTL", "24h")
        from packages.ai.router import ProviderRouter

        result = ProviderRouter._anthropic_payload(self._payload_with_system())
        assert result["system"][0]["cache_control"] == {"type": "ephemeral"}

    def test_ttl_ignored_when_caching_disabled(self, monkeypatch):
        """``ANTHROPIC_PROMPT_CACHING=off`` disables the cache_control block
        entirely — the TTL knob must not resurrect it."""
        monkeypatch.setenv("ANTHROPIC_PROMPT_CACHING", "off")
        monkeypatch.setenv("ANTHROPIC_CACHE_TTL", "1h")
        from packages.ai.router import ProviderRouter

        result = ProviderRouter._anthropic_payload(self._payload_with_system())
        # With caching off, system is a bare string, not a list of blocks.
        assert isinstance(result["system"], str)


class TestLegacyRouterHeaders:
    """The legacy adapter sets ``anthropic-beta`` on the wire.  ``1h`` TTL
    requires the extended-cache-ttl beta; ``5m`` does not."""

    def _headers_for_ttl(self, monkeypatch, ttl: str | None):
        from packages.ai.router import ProviderConfig

        if ttl is None:
            monkeypatch.delenv("ANTHROPIC_CACHE_TTL", raising=False)
        else:
            monkeypatch.setenv("ANTHROPIC_CACHE_TTL", ttl)
        cfg = ProviderConfig(
            provider_id="anthropic",
            type="anthropic",
            base_url="https://api.anthropic.com",
            api_key="test",
        )
        return cfg.auth_headers()

    def test_default_omits_extended_cache_beta(self, monkeypatch):
        headers = self._headers_for_ttl(monkeypatch, None)
        beta = headers.get("anthropic-beta", "")
        assert "extended-cache-ttl-2025-04-11" not in beta
        assert "prompt-caching-2024-07-31" in beta

    def test_1h_ttl_adds_extended_cache_beta(self, monkeypatch):
        headers = self._headers_for_ttl(monkeypatch, "1h")
        beta = headers.get("anthropic-beta", "")
        assert "extended-cache-ttl-2025-04-11" in beta
        # And prompt-caching itself is still on — 1h TTL is an extension, not
        # a replacement.
        assert "prompt-caching-2024-07-31" in beta

    def test_5m_ttl_omits_extended_cache_beta(self, monkeypatch):
        headers = self._headers_for_ttl(monkeypatch, "5m")
        assert "extended-cache-ttl-2025-04-11" not in headers.get(
            "anthropic-beta", ""
        )

    def test_extended_beta_absent_when_caching_disabled(self, monkeypatch):
        """1h TTL must not add the extended beta if caching is turned off — the
        extended cache is meaningless without the base prompt cache."""
        monkeypatch.setenv("ANTHROPIC_PROMPT_CACHING", "off")
        headers = self._headers_for_ttl(monkeypatch, "1h")
        beta = headers.get("anthropic-beta", "")
        assert "extended-cache-ttl-2025-04-11" not in beta
        assert "prompt-caching-2024-07-31" not in beta
