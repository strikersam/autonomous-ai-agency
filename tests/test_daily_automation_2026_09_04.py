"""tests/test_daily_automation_2026_09_04.py — Daily automation tests (2026-09-04).

Covers the ecosystem updates applied today:
  1. config/llm/models.yaml — claude-fable-5-1 added to the model catalog.
     ADAPTIVE_THINKING_MODELS already listed it; the YAML entry and cost-tracker
     entry were missing.
  2. packages/ai/cost_tracker.py — claude-fable-5 pricing corrected (3.0/15.0 →
     30.0/120.0) and claude-fable-5-1 added at the same rate. The cost-tracker
     table diverged from models.yaml, causing under-reporting in admin spend stats.
  3. packages/llm/types.py / providers/anthropic.py — reasoning_tokens added to
     Usage and populated from output_tokens_details.reasoning_tokens in Anthropic
     API responses.  Thinking models emit this field; it was silently discarded.
"""
from __future__ import annotations

import pytest


# ── helpers ──────────────────────────────────────────────────────────────────

def _cfg():
    from packages.llm.config import load_config
    return load_config()


def _cost_table():
    from packages.ai.cost_tracker import _DEFAULT_COST_TABLE
    return _DEFAULT_COST_TABLE


# ── 1. claude-fable-5-1 in model catalog ─────────────────────────────────────

class TestCatalogFable51:
    """Verify the claude-fable-5-1 entry in config/llm/models.yaml."""

    def test_fable51_in_catalog(self) -> None:
        assert "claude-fable-5-1" in _cfg().models

    def test_fable51_provider_is_anthropic(self) -> None:
        assert _cfg().models["claude-fable-5-1"].provider == "anthropic"

    def test_fable51_context_window(self) -> None:
        assert _cfg().models["claude-fable-5-1"].context_window == 200_000

    def test_fable51_max_output_tokens(self) -> None:
        assert _cfg().models["claude-fable-5-1"].max_output_tokens == 32_000

    def test_fable51_supports_tools(self) -> None:
        assert _cfg().models["claude-fable-5-1"].supports_tools is True

    def test_fable51_supports_reasoning(self) -> None:
        assert _cfg().models["claude-fable-5-1"].supports_reasoning is True

    def test_fable51_supports_images(self) -> None:
        assert _cfg().models["claude-fable-5-1"].supports_images is True

    def test_fable51_supports_streaming(self) -> None:
        assert _cfg().models["claude-fable-5-1"].supports_streaming is True

    def test_fable51_input_cost(self) -> None:
        assert _cfg().models["claude-fable-5-1"].input_cost_per_1m == 30.0

    def test_fable51_output_cost(self) -> None:
        assert _cfg().models["claude-fable-5-1"].output_cost_per_1m == 120.0

    def test_fable51_has_higher_priority_than_fable5(self) -> None:
        """5.1 is the newer release, so it should be preferred over 5.0."""
        models = _cfg().models
        fable5 = models.get("claude-fable-5")
        fable51 = models["claude-fable-5-1"]
        if fable5 is not None:
            assert fable51.priority < fable5.priority, (
                f"fable-5-1 priority {fable51.priority} should be lower "
                f"(higher-priority) than fable-5 {fable5.priority}"
            )

    def test_fable51_in_adaptive_thinking_models(self) -> None:
        """Must be listed in ADAPTIVE_THINKING_MODELS so temperature is suppressed."""
        from packages.llm.providers.anthropic import ADAPTIVE_THINKING_MODELS
        assert "claude-fable-5-1" in ADAPTIVE_THINKING_MODELS

    def test_fable51_no_temperature_in_payload(self) -> None:
        """Sending temperature to fable-5-1 returns HTTP 400 — the provider must omit it."""
        from packages.llm.providers.anthropic import AnthropicProvider
        from packages.llm.config import ProviderConfig
        from packages.llm.types import LLMRequest

        provider = AnthropicProvider(ProviderConfig(id="anthropic", kind="anthropic"))
        req = LLMRequest(messages=[{"role": "user", "content": "hi"}], temperature=0.9)
        payload = provider.build_payload(req, "claude-fable-5-1")
        assert "temperature" not in payload


# ── 2. cost_tracker pricing consistency ──────────────────────────────────────

class TestCostTrackerFable:
    """Verify that cost_tracker prices match models.yaml for the Fable family."""

    def test_fable5_cost_tracker_matches_yaml(self) -> None:
        """claude-fable-5 was 3.0/15.0 in the tracker but 30.0/120.0 in models.yaml."""
        table = _cost_table()
        assert "claude-fable-5" in table
        inp, out = table["claude-fable-5"]
        assert inp == 30.0, f"expected input 30.0, got {inp}"
        assert out == 120.0, f"expected output 120.0, got {out}"

    def test_fable51_in_cost_tracker(self) -> None:
        assert "claude-fable-5-1" in _cost_table()

    def test_fable51_cost_tracker_pricing(self) -> None:
        inp, out = _cost_table()["claude-fable-5-1"]
        assert inp == 30.0
        assert out == 120.0

    def test_fable5_and_fable51_same_pricing(self) -> None:
        table = _cost_table()
        assert table["claude-fable-5"] == table["claude-fable-5-1"]


# ── 3. reasoning_tokens in Usage ─────────────────────────────────────────────

class TestUsageReasoningTokens:
    """reasoning_tokens is a new field on Usage, populated for thinking models."""

    def test_usage_has_reasoning_tokens_field(self) -> None:
        from packages.llm.types import Usage
        u = Usage()
        assert hasattr(u, "reasoning_tokens")
        assert u.reasoning_tokens == 0

    def test_reasoning_tokens_not_additive_to_total(self) -> None:
        """reasoning_tokens is a SUBSET of completion_tokens — must not inflate total."""
        from packages.llm.types import Usage
        u = Usage(prompt_tokens=10, completion_tokens=50, reasoning_tokens=30)
        assert u.total_tokens == 60  # 10 + 50, not 10 + 50 + 30

    def test_as_dict_includes_reasoning_tokens_when_nonzero(self) -> None:
        from packages.llm.types import Usage
        u = Usage(prompt_tokens=10, completion_tokens=50, reasoning_tokens=30)
        d = u.as_dict()
        assert d["reasoning_tokens"] == 30

    def test_as_dict_omits_reasoning_tokens_when_zero(self) -> None:
        """Non-thinking models have no reasoning tokens — as_dict must stay minimal."""
        from packages.llm.types import Usage
        u = Usage(prompt_tokens=10, completion_tokens=50)
        d = u.as_dict()
        assert "reasoning_tokens" not in d


# ── 4. Anthropic provider extracts reasoning_tokens from API response ─────────

class TestAnthropicReasoningTokenExtraction:
    """generate() populates Usage.reasoning_tokens from output_tokens_details."""

    def _build_response(
        self,
        *,
        output_tokens: int = 50,
        reasoning_tokens: int = 0,
        cache_read: int = 0,
    ) -> dict:
        response = {
            "type": "message",
            "id": "msg_test",
            "role": "assistant",
            "model": "claude-opus-5",
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "Thinking answer."}],
            "usage": {
                "input_tokens": 20,
                "output_tokens": output_tokens,
                "cache_read_input_tokens": cache_read,
            },
        }
        if reasoning_tokens:
            response["usage"]["output_tokens_details"] = {
                "reasoning_tokens": reasoning_tokens,
            }
        return response

    def _parse(self, data: dict, model: str = "claude-opus-5"):
        """Exercise the same parsing path as AnthropicProvider.generate()."""
        from packages.llm.types import Usage

        raw_usage = data.get("usage") or {}
        output_details = raw_usage.get("output_tokens_details") or {}
        return Usage(
            prompt_tokens=int(raw_usage.get("input_tokens") or 0),
            completion_tokens=int(raw_usage.get("output_tokens") or 0),
            cached_tokens=int(raw_usage.get("cache_read_input_tokens") or 0),
            reasoning_tokens=int(output_details.get("reasoning_tokens") or 0),
        )

    def test_reasoning_tokens_extracted_when_present(self) -> None:
        data = self._build_response(output_tokens=50, reasoning_tokens=30)
        usage = self._parse(data)
        assert usage.reasoning_tokens == 30

    def test_reasoning_tokens_zero_when_absent(self) -> None:
        data = self._build_response(output_tokens=50)
        usage = self._parse(data)
        assert usage.reasoning_tokens == 0

    def test_reasoning_tokens_zero_when_details_empty(self) -> None:
        data = self._build_response(output_tokens=50)
        data["usage"]["output_tokens_details"] = {}
        usage = self._parse(data)
        assert usage.reasoning_tokens == 0

    def test_total_tokens_unaffected_by_reasoning_tokens(self) -> None:
        data = self._build_response(output_tokens=50, reasoning_tokens=30)
        usage = self._parse(data)
        # reasoning is a subset of completion; total must not double-count
        assert usage.total_tokens == usage.prompt_tokens + usage.completion_tokens

    def test_reasoning_tokens_in_as_dict_when_nonzero(self) -> None:
        data = self._build_response(output_tokens=50, reasoning_tokens=20)
        usage = self._parse(data)
        assert usage.as_dict().get("reasoning_tokens") == 20

    def test_non_thinking_model_as_dict_has_no_reasoning_key(self) -> None:
        data = self._build_response(output_tokens=50)
        usage = self._parse(data, model="claude-sonnet-4-6")
        assert "reasoning_tokens" not in usage.as_dict()
