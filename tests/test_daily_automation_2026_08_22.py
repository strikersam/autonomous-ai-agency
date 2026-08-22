"""tests/test_daily_automation_2026_08_22.py — Daily automation tests (2026-08-22).

Covers three ecosystem improvements applied today:
  1. packages/llm/types.py — Usage gains cache_creation_tokens and thinking_tokens
     fields for accurate Anthropic cost attribution.
  2. packages/llm/providers/anthropic.py — Non-streaming _parse() captures
     cache_creation_input_tokens and thinking_tokens; streaming _parse_event()
     now handles message_start (input usage) and thinking_tokens in message_delta;
     AnthropicProvider.cost() overrides the base to apply the cache-creation 25%%
     surcharge and thinking-token output rate.
  3. packages/ai/cost_tracker.py — cost_for_tokens() and record_usage() accept
     cache_creation_tokens and thinking_tokens; get_stats() exposes them.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── 1. Usage dataclass ────────────────────────────────────────────────────────

class TestUsageNewFields:
    """Usage gains cache_creation_tokens and thinking_tokens."""

    def _make(self, **kwargs):
        from packages.llm.types import Usage
        return Usage(**kwargs)

    def test_cache_creation_tokens_defaults_to_zero(self) -> None:
        u = self._make()
        assert u.cache_creation_tokens == 0

    def test_thinking_tokens_defaults_to_zero(self) -> None:
        u = self._make()
        assert u.thinking_tokens == 0

    def test_cache_creation_tokens_set(self) -> None:
        u = self._make(prompt_tokens=100, cache_creation_tokens=40)
        assert u.cache_creation_tokens == 40

    def test_thinking_tokens_set(self) -> None:
        u = self._make(completion_tokens=50, thinking_tokens=200)
        assert u.thinking_tokens == 200

    def test_total_tokens_excludes_thinking_and_cache_creation(self) -> None:
        # total_tokens only counts prompt + completion; other fields are separate
        u = self._make(
            prompt_tokens=100,
            completion_tokens=50,
            thinking_tokens=300,
            cache_creation_tokens=40,
        )
        assert u.total_tokens == 150

    def test_as_dict_includes_new_fields(self) -> None:
        u = self._make(
            prompt_tokens=10,
            completion_tokens=5,
            cached_tokens=3,
            cache_creation_tokens=7,
            thinking_tokens=20,
        )
        d = u.as_dict()
        assert d["cache_creation_tokens"] == 7
        assert d["thinking_tokens"] == 20
        assert d["cached_tokens"] == 3
        assert d["prompt_tokens"] == 10
        assert d["completion_tokens"] == 5
        assert d["total_tokens"] == 15

    def test_as_dict_backwards_compat_no_new_args(self) -> None:
        """Callers that construct Usage with only the old fields still work."""
        from packages.llm.types import Usage
        u = Usage(prompt_tokens=50, completion_tokens=20, cached_tokens=5)
        d = u.as_dict()
        assert d["cache_creation_tokens"] == 0
        assert d["thinking_tokens"] == 0


# ── 2a. AnthropicProvider._parse() — non-streaming ────────────────────────────

def _make_anthropic_provider():
    """Build a minimal AnthropicProvider instance with a mocked config."""
    from packages.llm.providers.anthropic import AnthropicProvider
    cfg = MagicMock()
    cfg.id = "anthropic"
    cfg.thinking_budget = 0
    cfg.prompt_caching = False
    cfg.api_version = None
    cfg.extra_headers = {}
    cfg.timeout_sec = 30.0
    cfg.models = []
    cfg.base_url = "https://api.anthropic.com"
    cfg.default_effort = None
    p = AnthropicProvider.__new__(AnthropicProvider)
    p.config = cfg
    return p


class TestAnthropicParseNonStreaming:
    """_parse() captures cache_creation and thinking tokens from Anthropic API response."""

    def _provider(self):
        return _make_anthropic_provider()

    def _raw_response(self, **usage_overrides):
        usage = {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_input_tokens": 10,
            "cache_creation_input_tokens": 0,
            "thinking_tokens": 0,
        }
        usage.update(usage_overrides)
        return {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-5",
            "content": [{"type": "text", "text": "Hello."}],
            "stop_reason": "end_turn",
            "usage": usage,
        }

    def test_cache_creation_tokens_captured(self) -> None:
        p = self._provider()
        data = self._raw_response(cache_creation_input_tokens=30)
        resp = p._parse(data, model="claude-sonnet-5", latency_ms=100)
        assert resp.usage.cache_creation_tokens == 30

    def test_thinking_tokens_captured(self) -> None:
        p = self._provider()
        data = self._raw_response(thinking_tokens=500)
        resp = p._parse(data, model="claude-sonnet-5", latency_ms=100)
        assert resp.usage.thinking_tokens == 500

    def test_zero_values_when_absent(self) -> None:
        p = self._provider()
        data = self._raw_response()
        data["usage"].pop("cache_creation_input_tokens", None)
        data["usage"].pop("thinking_tokens", None)
        resp = p._parse(data, model="claude-sonnet-5", latency_ms=100)
        assert resp.usage.cache_creation_tokens == 0
        assert resp.usage.thinking_tokens == 0

    def test_cached_tokens_still_captured(self) -> None:
        p = self._provider()
        data = self._raw_response(cache_read_input_tokens=25)
        resp = p._parse(data, model="claude-sonnet-5", latency_ms=100)
        assert resp.usage.cached_tokens == 25

    def test_all_usage_fields_together(self) -> None:
        p = self._provider()
        data = self._raw_response(
            input_tokens=200,
            output_tokens=80,
            cache_read_input_tokens=20,
            cache_creation_input_tokens=40,
            thinking_tokens=150,
        )
        resp = p._parse(data, model="claude-sonnet-5", latency_ms=50)
        assert resp.usage.prompt_tokens == 200
        assert resp.usage.completion_tokens == 80
        assert resp.usage.cached_tokens == 20
        assert resp.usage.cache_creation_tokens == 40
        assert resp.usage.thinking_tokens == 150


# ── 2b. AnthropicProvider._parse_event() — streaming ─────────────────────────

class TestAnthropicStreamingUsage:
    """_parse_event handles message_start (input usage) and message_delta (output usage)."""

    def _provider(self):
        return _make_anthropic_provider()

    def test_message_start_returns_input_usage(self) -> None:
        p = self._provider()
        event = {
            "type": "message_start",
            "message": {
                "usage": {
                    "input_tokens": 150,
                    "cache_read_input_tokens": 30,
                    "cache_creation_input_tokens": 20,
                    "output_tokens": 1,
                }
            },
        }
        chunk = p._parse_event(event, model="claude-sonnet-5", tool_names={}, tool_ids={})
        assert chunk is not None
        assert chunk.usage is not None
        assert chunk.usage.prompt_tokens == 150

    def test_message_start_captures_cache_read_tokens(self) -> None:
        p = self._provider()
        event = {
            "type": "message_start",
            "message": {"usage": {"input_tokens": 100, "cache_read_input_tokens": 50}},
        }
        chunk = p._parse_event(event, model="claude-sonnet-5", tool_names={}, tool_ids={})
        assert chunk is not None
        assert chunk.usage.cached_tokens == 50

    def test_message_start_captures_cache_creation_tokens(self) -> None:
        p = self._provider()
        event = {
            "type": "message_start",
            "message": {"usage": {"input_tokens": 80, "cache_creation_input_tokens": 35}},
        }
        chunk = p._parse_event(event, model="claude-sonnet-5", tool_names={}, tool_ids={})
        assert chunk is not None
        assert chunk.usage.cache_creation_tokens == 35

    def test_message_start_zero_when_absent(self) -> None:
        p = self._provider()
        event = {
            "type": "message_start",
            "message": {"usage": {"input_tokens": 60}},
        }
        chunk = p._parse_event(event, model="claude-sonnet-5", tool_names={}, tool_ids={})
        assert chunk is not None
        assert chunk.usage.cached_tokens == 0
        assert chunk.usage.cache_creation_tokens == 0

    def test_message_delta_captures_thinking_tokens(self) -> None:
        p = self._provider()
        event = {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn"},
            "usage": {"output_tokens": 90, "thinking_tokens": 400},
        }
        chunk = p._parse_event(event, model="claude-sonnet-5", tool_names={}, tool_ids={})
        assert chunk is not None
        assert chunk.usage.completion_tokens == 90
        assert chunk.usage.thinking_tokens == 400

    def test_message_delta_thinking_tokens_zero_when_absent(self) -> None:
        p = self._provider()
        event = {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn"},
            "usage": {"output_tokens": 45},
        }
        chunk = p._parse_event(event, model="claude-sonnet-5", tool_names={}, tool_ids={})
        assert chunk is not None
        assert chunk.usage.thinking_tokens == 0

    def test_content_block_delta_still_works(self) -> None:
        p = self._provider()
        event = {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "Hello"},
        }
        chunk = p._parse_event(event, model="claude-sonnet-5", tool_names={}, tool_ids={})
        assert chunk is not None
        assert chunk.text == "Hello"


# ── 2c. AnthropicProvider.cost() ─────────────────────────────────────────────

class TestAnthropicCostOverride:
    """AnthropicProvider.cost() applies cache-creation 25% surcharge and thinking output rate."""

    def _provider(self):
        return _make_anthropic_provider()

    def _mock_registry(self, input_per_m: float, output_per_m: float):
        """Patch get_registry() to return a spec with known rates."""
        spec = MagicMock()
        spec.input_cost_per_1m = input_per_m
        spec.output_cost_per_1m = output_per_m
        registry = MagicMock()
        registry.get.return_value = spec
        return registry

    def _with_registry(self, input_per_m: float, output_per_m: float, model_exists: bool = True):
        """Context manager that patches get_registry at the call site."""
        spec = MagicMock()
        spec.input_cost_per_1m = input_per_m
        spec.output_cost_per_1m = output_per_m
        registry = MagicMock()
        registry.get.return_value = spec if model_exists else None
        return patch("packages.llm.registry.get_registry", return_value=registry)

    def test_base_cost_matches_standard_formula(self) -> None:
        from packages.llm.types import Usage
        p = self._provider()
        with self._with_registry(input_per_m=2.0, output_per_m=10.0):
            usage = Usage(prompt_tokens=1_000_000, completion_tokens=0)
            cost = p.cost("claude-sonnet-5", usage)
        assert abs(cost - 2.0) < 1e-9

    def test_cache_creation_adds_25pct_surcharge(self) -> None:
        from packages.llm.types import Usage
        p = self._provider()
        with self._with_registry(input_per_m=2.0, output_per_m=10.0):
            # 1M cache_creation_tokens at input=$2/M with 25% surcharge → premium=$0.50
            usage = Usage(prompt_tokens=0, completion_tokens=0, cache_creation_tokens=1_000_000)
            cost = p.cost("claude-sonnet-5", usage)
        # 1_000_000 * 2.0 * 0.25 / 1_000_000 = 0.5
        assert abs(cost - 0.5) < 1e-9

    def test_thinking_tokens_billed_at_output_rate(self) -> None:
        from packages.llm.types import Usage
        p = self._provider()
        with self._with_registry(input_per_m=2.0, output_per_m=10.0):
            # 1M thinking_tokens at output=$10/M
            usage = Usage(prompt_tokens=0, completion_tokens=0, thinking_tokens=1_000_000)
            cost = p.cost("claude-sonnet-5", usage)
        assert abs(cost - 10.0) < 1e-9

    def test_combined_cost_all_three_categories(self) -> None:
        from packages.llm.types import Usage
        p = self._provider()
        with self._with_registry(input_per_m=2.0, output_per_m=10.0):
            usage = Usage(
                prompt_tokens=500_000,           # $1.00
                completion_tokens=100_000,       # $1.00
                cache_creation_tokens=200_000,   # $0.10 surcharge (200k × $2/M × 0.25)
                thinking_tokens=50_000,          # $0.50
            )
            cost = p.cost("claude-sonnet-5", usage)
        # 1.00 + 1.00 + 0.10 + 0.50 = 2.60
        assert abs(cost - 2.60) < 1e-6

    def test_returns_zero_for_unknown_model(self) -> None:
        from packages.llm.types import Usage
        p = self._provider()
        with self._with_registry(input_per_m=2.0, output_per_m=10.0, model_exists=False):
            usage = Usage(prompt_tokens=1000, completion_tokens=500, thinking_tokens=200)
            cost = p.cost("unknown-model-xyz", usage)
        assert cost == 0.0


# ── 3. cost_tracker updates ───────────────────────────────────────────────────

class TestCostForTokensNewParams:
    """cost_for_tokens now accepts cache_creation_tokens and thinking_tokens."""

    def test_cache_creation_surcharge_on_anthropic_model(self) -> None:
        from packages.ai.cost_tracker import cost_for_tokens
        # claude-sonnet-5 is $3/M input (corrected: tracker has $3.0), $15/M output
        # 1M cache_creation → 1M × $3/M × 0.25 = $0.75
        cost_only_cache = cost_for_tokens(
            "claude-sonnet-5", 0, 0, cache_creation_tokens=1_000_000
        )
        cost_no_cache = cost_for_tokens("claude-sonnet-5", 0, 0)
        assert cost_only_cache > cost_no_cache
        # 1M cache_creation_tokens at $3/M × 0.25 = $0.75
        assert abs(cost_only_cache - 0.75) < 1e-9

    def test_thinking_tokens_billed_at_output_rate(self) -> None:
        from packages.ai.cost_tracker import cost_for_tokens
        # claude-sonnet-5: $15/M output; 1M thinking = $15
        cost = cost_for_tokens("claude-sonnet-5", 0, 0, thinking_tokens=1_000_000)
        assert abs(cost - 15.0) < 1e-9

    def test_zero_cache_creation_and_thinking_is_unchanged(self) -> None:
        from packages.ai.cost_tracker import cost_for_tokens
        old = cost_for_tokens("claude-sonnet-5", 100, 50)
        new = cost_for_tokens("claude-sonnet-5", 100, 50, cache_creation_tokens=0, thinking_tokens=0)
        assert abs(old - new) < 1e-12

    def test_free_tier_model_always_zero(self) -> None:
        from packages.ai.cost_tracker import cost_for_tokens
        cost = cost_for_tokens(
            "meta/llama-3.3-70b-instruct", 1000, 500,
            cache_creation_tokens=200, thinking_tokens=100,
        )
        assert cost == 0.0

    def test_combined_cost_calculation(self) -> None:
        from packages.ai.cost_tracker import cost_for_tokens
        # claude-opus-5: $15/M input, $75/M output
        # 1M input: $15, 500k output: $37.5, 200k cache_creation: 200k × $15 × 0.25 = $0.75
        # 100k thinking: 100k × $75 = $7.5
        cost = cost_for_tokens(
            "claude-opus-5",
            prompt_tokens=1_000_000,
            completion_tokens=500_000,
            cache_creation_tokens=200_000,
            thinking_tokens=100_000,
        )
        expected = 15.0 + 37.5 + 0.75 + 7.5
        assert abs(cost - expected) < 1e-6


class TestRecordUsageNewFields:
    """record_usage accepts and tracks cache_creation_tokens and thinking_tokens."""

    def _reset(self):
        from packages.ai.cost_tracker import clear_stats
        clear_stats()

    def test_record_usage_with_cache_creation_tokens(self) -> None:
        from packages.ai.cost_tracker import clear_stats, get_stats, record_usage
        clear_stats()
        record_usage(
            "claude-sonnet-5",
            provider_id="anthropic",
            prompt_tokens=100,
            completion_tokens=50,
            cache_creation_tokens=40,
        )
        stats = get_stats()
        assert stats["models"]["claude-sonnet-5"]["cache_creation_tokens"] == 40

    def test_record_usage_with_thinking_tokens(self) -> None:
        from packages.ai.cost_tracker import clear_stats, get_stats, record_usage
        clear_stats()
        record_usage(
            "claude-opus-5",
            provider_id="anthropic",
            prompt_tokens=200,
            completion_tokens=80,
            thinking_tokens=300,
        )
        stats = get_stats()
        assert stats["models"]["claude-opus-5"]["thinking_tokens"] == 300

    def test_record_usage_defaults_to_zero(self) -> None:
        from packages.ai.cost_tracker import clear_stats, get_stats, record_usage
        clear_stats()
        record_usage("claude-sonnet-5", prompt_tokens=50, completion_tokens=20)
        stats = get_stats()
        assert stats["models"]["claude-sonnet-5"]["cache_creation_tokens"] == 0
        assert stats["models"]["claude-sonnet-5"]["thinking_tokens"] == 0

    def test_cost_includes_cache_creation_surcharge(self) -> None:
        from packages.ai.cost_tracker import clear_stats, get_stats, record_usage
        clear_stats()
        # With 1M cache_creation_tokens, cost should be higher than without
        record_usage(
            "claude-sonnet-5",
            prompt_tokens=0,
            completion_tokens=0,
            cache_creation_tokens=1_000_000,
        )
        stats = get_stats()
        model_cost = stats["models"]["claude-sonnet-5"]["estimated_cost_usd"]
        # 1M × $3/M × 0.25 = $0.75
        assert abs(model_cost - 0.75) < 1e-9

    def test_cost_includes_thinking_tokens(self) -> None:
        from packages.ai.cost_tracker import clear_stats, get_stats, record_usage
        clear_stats()
        record_usage(
            "claude-sonnet-5",
            prompt_tokens=0,
            completion_tokens=0,
            thinking_tokens=1_000_000,
        )
        stats = get_stats()
        model_cost = stats["models"]["claude-sonnet-5"]["estimated_cost_usd"]
        # 1M × $15/M = $15.0
        assert abs(model_cost - 15.0) < 1e-9

    def test_get_stats_exposes_new_fields(self) -> None:
        from packages.ai.cost_tracker import clear_stats, get_stats, record_usage
        clear_stats()
        record_usage("claude-haiku-4-5", prompt_tokens=10, completion_tokens=5,
                     cache_creation_tokens=3, thinking_tokens=0)
        stats = get_stats()
        model_entry = stats["models"]["claude-haiku-4-5"]
        assert "cache_creation_tokens" in model_entry
        assert "thinking_tokens" in model_entry
        assert model_entry["cache_creation_tokens"] == 3

    def test_accumulation_across_calls(self) -> None:
        from packages.ai.cost_tracker import clear_stats, get_stats, record_usage
        clear_stats()
        record_usage("claude-opus-5", prompt_tokens=50, completion_tokens=20,
                     cache_creation_tokens=10, thinking_tokens=100)
        record_usage("claude-opus-5", prompt_tokens=30, completion_tokens=10,
                     cache_creation_tokens=5, thinking_tokens=50)
        stats = get_stats()
        m = stats["models"]["claude-opus-5"]
        assert m["cache_creation_tokens"] == 15
        assert m["thinking_tokens"] == 150


# ── 4. budget._mirror_to_cost_tracker integration ────────────────────────────

class TestBudgetMirrorsCacheCreationAndThinking:
    """budget._mirror_to_cost_tracker passes new Usage fields to cost_tracker."""

    def test_mirror_passes_cache_creation_tokens(self) -> None:
        from packages.llm.types import Usage
        from packages.ai.cost_tracker import clear_stats, get_stats

        clear_stats()

        # Import the BudgetLedger and call the private mirror directly.
        import packages.llm.budget as budget_mod
        from packages.llm import budget as budget_pkg

        # Find _mirror_to_cost_tracker (it's a method on BudgetLedger or similar)
        # If the function is a method, instantiate a minimal BudgetLedger.
        import importlib
        bmod = importlib.import_module("packages.llm.budget")

        # Locate the class that has _mirror_to_cost_tracker
        import inspect
        classes = [
            cls for _, cls in inspect.getmembers(bmod, inspect.isclass)
            if hasattr(cls, "_mirror_to_cost_tracker")
        ]
        assert classes, "No class with _mirror_to_cost_tracker found in packages.llm.budget"
        cls = classes[0]

        # Create a minimal instance (no __init__ side-effects needed for this method)
        instance = cls.__new__(cls)
        instance._config = MagicMock()
        instance._config.enforce = False
        import threading
        instance._lock = threading.Lock()

        usage = Usage(
            prompt_tokens=100,
            completion_tokens=50,
            cache_creation_tokens=25,
            thinking_tokens=75,
        )
        instance._mirror_to_cost_tracker(usage, "anthropic", "claude-sonnet-5")

        stats = get_stats()
        m = stats["models"].get("claude-sonnet-5")
        assert m is not None
        assert m["cache_creation_tokens"] == 25
        assert m["thinking_tokens"] == 75
