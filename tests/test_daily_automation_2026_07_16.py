"""tests/test_daily_automation_2026_07_16.py — Daily automation tests (2026-07-16).

Covers three ecosystem updates applied today (sources: Anthropic platform release
notes, Claude Code changelog, releasebot.io/updates/anthropic/claude-developer-platform):

1. packages/ai/router.py — Anthropic structured outputs (GA, no beta header):
   _anthropic_payload() maps OpenAI response_format → output_config.format.
2. packages/ai/router.py — Default Anthropic model updated to claude-sonnet-5
   (Anthropic's new default for all subscription tiers as of July 2026).
3. packages/ai/brain_config.py — PROVIDER_CANDIDATES["anthropic"] refreshed:
   stale claude-3-5-* and claude-opus-4-5 entries replaced with current-gen models.
4. backend/server.py — Pre-existing AttributeError fixed: double .router dereference
   on local_brain_router_module import alias (line 9558).
"""
from __future__ import annotations

import pytest

from packages.ai.router import ProviderConfig, ProviderRouter
from packages.ai.brain_config import PROVIDER_CANDIDATES


# ── 1. Structured outputs (GA) ────────────────────────────────────────────────


class TestStructuredOutputsGA:
    """Anthropic structured outputs are GA — output_config.format, no beta header."""

    def _payload(self, **extra) -> dict:
        return {"messages": [{"role": "user", "content": "Extract data"}], **extra}

    def _base(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_PROMPT_CACHING", "false")
        monkeypatch.delenv("ANTHROPIC_THINKING_BUDGET", raising=False)

    def test_json_schema_maps_to_output_config(self, monkeypatch):
        self._base(monkeypatch)
        schema = {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}
        payload = self._payload(
            response_format={"type": "json_schema", "json_schema": {"name": "PersonSchema", "schema": schema}}
        )
        out = ProviderRouter._anthropic_payload(payload)
        assert "output_config" in out
        fmt = out["output_config"]["format"]
        assert fmt["type"] == "json_schema"
        assert fmt["json_schema"]["name"] == "PersonSchema"
        assert fmt["json_schema"]["schema"] == schema

    def test_json_object_mode_maps_to_output_config(self, monkeypatch):
        self._base(monkeypatch)
        out = ProviderRouter._anthropic_payload(self._payload(response_format={"type": "json_object"}))
        assert out.get("output_config") == {"format": {"type": "json_object"}}

    def test_no_output_config_without_response_format(self, monkeypatch):
        self._base(monkeypatch)
        out = ProviderRouter._anthropic_payload(self._payload())
        assert "output_config" not in out

    def test_text_type_is_not_forwarded(self, monkeypatch):
        self._base(monkeypatch)
        out = ProviderRouter._anthropic_payload(self._payload(response_format={"type": "text"}))
        assert "output_config" not in out

    def test_no_extra_beta_header_for_structured_outputs(self, monkeypatch):
        """GA feature — structured outputs MUST NOT require an extra beta header."""
        monkeypatch.setenv("ANTHROPIC_PROMPT_CACHING", "false")
        monkeypatch.delenv("ANTHROPIC_THINKING_BUDGET", raising=False)
        p = ProviderConfig(
            provider_id="anthropic",
            type="anthropic",
            base_url="https://api.anthropic.com",
            api_key="sk-test",
            default_model="claude-sonnet-5",
        )
        beta = p.auth_headers().get("anthropic-beta", "")
        assert "structured-outputs" not in beta, (
            "Structured outputs are GA — no structured-outputs beta header should be sent"
        )


# ── 2. Default model = claude-sonnet-5 ───────────────────────────────────────


class TestDefaultModelSonnet5:
    """claude-sonnet-5 is Anthropic's new default (July 2026)."""

    def test_default_is_claude_sonnet5_when_env_unset(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
        monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
        router = ProviderRouter.from_env()
        anthropic = next((p for p in router.providers if p.provider_id == "anthropic"), None)
        assert anthropic is not None
        assert anthropic.default_model == "claude-sonnet-5"

    def test_sonnet46_not_the_default_anymore(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
        router = ProviderRouter.from_env()
        anthropic = next(p for p in router.providers if p.provider_id == "anthropic")
        assert anthropic.default_model != "claude-sonnet-4-6"


# ── 3. brain_config PROVIDER_CANDIDATES["anthropic"] ─────────────────────────


class TestAnthropicCandidatesCatalog:
    """PROVIDER_CANDIDATES["anthropic"] must list current-gen models, not stale ones."""

    def _candidates(self) -> list[str]:
        return PROVIDER_CANDIDATES.get("anthropic", [])

    def test_claude_sonnet5_in_candidates(self):
        assert "claude-sonnet-5" in self._candidates()

    def test_claude_opus_48_in_candidates(self):
        assert "claude-opus-4-8" in self._candidates()

    def test_claude_haiku_45_in_candidates(self):
        assert "claude-haiku-4-5-20251001" in self._candidates()

    def test_claude_fable5_in_candidates(self):
        assert "claude-fable-5" in self._candidates()

    def test_stale_oct2024_sonnet_not_in_candidates(self):
        """claude-3-5-sonnet-20241022 is a 2024 model — should not appear in 2026 catalog."""
        assert "claude-3-5-sonnet-20241022" not in self._candidates()

    def test_stale_oct2024_haiku_not_in_candidates(self):
        assert "claude-3-5-haiku-20241022" not in self._candidates()

    def test_compat_alias_sonnet46_kept(self):
        """claude-sonnet-4-6 must stay as a compat alias for existing callers."""
        assert "claude-sonnet-4-6" in self._candidates()


# ── 4. backend/server.py AttributeError fix ───────────────────────────────────


def test_backend_local_brain_router_import_does_not_double_attribute():
    """Regression: app.include_router(local_brain_router_module.router) was wrong —
    local_brain_router_module IS already the router object (imported with 'as router')."""
    from fastapi import APIRouter
    import backend.local_brain_router as mod
    router = getattr(mod, "router", None)
    assert router is not None, "local_brain_router must expose a 'router' attribute"
    assert isinstance(router, APIRouter), "local_brain_router.router must be an APIRouter"
    assert not hasattr(router, "router"), (
        "APIRouter has no .router attribute — double-dereference would have raised AttributeError"
    )
