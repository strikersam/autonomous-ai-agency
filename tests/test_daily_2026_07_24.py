"""Daily automation tests — 2026-07-24.

Covers three features added in this session:
  1. Structured output strict mode + refusal detection
     (packages/ai/structured_output.py — is_strict(), updated system_instruction(),
      extract_refusal())
  2. MCP tools/list TTL caching
     (agent/mcp_client.py — list_tools() cache + invalidate_tools_cache())
  3. Model cost table additions
     (packages/ai/cost_tracker.py — GPT-5.6 family, Claude Sonnet 5, o3)
"""
from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── 1. Structured output strict mode ─────────────────────────────────────────


class TestIsStrict:
    """is_strict() detects strict: true inside json_schema."""

    from packages.ai.structured_output import is_strict

    def test_none_returns_false(self):
        from packages.ai.structured_output import is_strict
        assert is_strict(None) is False

    def test_json_object_not_strict(self):
        from packages.ai.structured_output import is_strict
        assert is_strict({"type": "json_object"}) is False

    def test_json_schema_without_strict_flag(self):
        from packages.ai.structured_output import is_strict
        fmt = {"type": "json_schema", "json_schema": {"name": "x", "schema": {}}}
        assert is_strict(fmt) is False

    def test_json_schema_with_strict_false(self):
        from packages.ai.structured_output import is_strict
        fmt = {"type": "json_schema", "json_schema": {"strict": False, "schema": {}}}
        assert is_strict(fmt) is False

    def test_json_schema_with_strict_true(self):
        from packages.ai.structured_output import is_strict
        fmt = {"type": "json_schema", "json_schema": {"name": "user", "strict": True, "schema": {}}}
        assert is_strict(fmt) is True

    def test_text_type_not_strict(self):
        from packages.ai.structured_output import is_strict
        assert is_strict({"type": "text"}) is False


class TestSystemInstructionStrictMode:
    """system_instruction() uses stronger language when strict: true."""

    def test_strict_mode_instruction_differs_from_non_strict(self):
        from packages.ai.structured_output import system_instruction
        schema = {"type": "object", "properties": {"id": {"type": "integer"}}}
        non_strict = system_instruction({"type": "json_schema", "json_schema": {"name": "r", "schema": schema}})
        strict = system_instruction({"type": "json_schema", "json_schema": {"name": "r", "strict": True, "schema": schema}})
        assert strict != non_strict

    def test_strict_instruction_includes_refusal_fallback(self):
        from packages.ai.structured_output import system_instruction
        schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        result = system_instruction({"type": "json_schema", "json_schema": {"name": "res", "strict": True, "schema": schema}})
        assert result is not None
        assert "refusal" in result.lower()

    def test_strict_instruction_includes_schema(self):
        from packages.ai.structured_output import system_instruction
        schema = {"type": "object", "required": ["id"]}
        result = system_instruction({"type": "json_schema", "json_schema": {"name": "item", "strict": True, "schema": schema}})
        assert result is not None
        assert "item" in result
        assert '"required"' in result

    def test_strict_no_schema_body_still_returns_instruction(self):
        from packages.ai.structured_output import system_instruction
        result = system_instruction({"type": "json_schema", "json_schema": {"strict": True}})
        assert result is not None
        assert "refusal" in result.lower()

    def test_non_strict_instruction_does_not_mention_refusal(self):
        from packages.ai.structured_output import system_instruction
        schema = {"type": "object"}
        result = system_instruction({"type": "json_schema", "json_schema": {"name": "plain", "schema": schema}})
        assert result is not None
        # Non-strict mode should not mention refusal to avoid confusing the model
        assert "refusal" not in result.lower()


class TestExtractRefusal:
    """extract_refusal() surfaces model refusals from provider response bodies."""

    def test_normal_content_returns_none(self):
        from packages.ai.structured_output import extract_refusal
        body = {
            "choices": [{"message": {"role": "assistant", "content": '{"id": 1}'}}]
        }
        assert extract_refusal(body) is None

    def test_native_refusal_field_returned(self):
        from packages.ai.structured_output import extract_refusal
        body = {
            "choices": [{"message": {"role": "assistant", "content": None, "refusal": "Cannot comply with schema."}}]
        }
        result = extract_refusal(body)
        assert result == "Cannot comply with schema."

    def test_native_refusal_only_when_content_is_none(self):
        from packages.ai.structured_output import extract_refusal
        # If content is present alongside refusal, don't treat it as a refusal
        body = {
            "choices": [{"message": {"role": "assistant", "content": '{"id": 2}', "refusal": "Something"}}]
        }
        assert extract_refusal(body) is None

    def test_proxy_convention_json_refusal_object(self):
        from packages.ai.structured_output import extract_refusal
        body = {
            "choices": [{"message": {"role": "assistant", "content": '{"refusal": "Schema too complex."}'}}]
        }
        result = extract_refusal(body)
        assert result == "Schema too complex."

    def test_json_with_extra_fields_not_treated_as_refusal(self):
        from packages.ai.structured_output import extract_refusal
        body = {
            "choices": [{"message": {"content": '{"refusal": "x", "id": 1}'}}]
        }
        # A JSON object with refusal AND other fields is real content, not a refusal sentinel
        assert extract_refusal(body) is None

    def test_empty_choices_returns_none(self):
        from packages.ai.structured_output import extract_refusal
        assert extract_refusal({"choices": []}) is None

    def test_non_dict_returns_none(self):
        from packages.ai.structured_output import extract_refusal
        assert extract_refusal(None) is None  # type: ignore[arg-type]
        assert extract_refusal("bad") is None  # type: ignore[arg-type]

    def test_missing_choices_key_returns_none(self):
        from packages.ai.structured_output import extract_refusal
        assert extract_refusal({}) is None


# ── 2. MCP tools/list TTL caching ────────────────────────────────────────────


class TestMCPToolsListCache:
    """list_tools() caches the result for ttlMs milliseconds."""

    @pytest.mark.asyncio
    async def test_second_call_uses_cache(self):
        """Second call within TTL must not issue an RPC."""
        from agent.mcp_client import MCPClient

        client = MCPClient("http://test-mcp:8008")
        tools_payload: dict[str, Any] = {"tools": [{"name": "read_file"}], "ttlMs": 30000}
        call_count = 0

        async def fake_rpc(method: str, params: Any = None) -> Any:
            nonlocal call_count
            call_count += 1
            return tools_payload

        client._rpc = fake_rpc  # type: ignore[assignment]

        t1 = await client.list_tools()
        t2 = await client.list_tools()
        assert t1 == [{"name": "read_file"}]
        assert t2 == t1
        assert call_count == 1  # only one RPC despite two calls

    @pytest.mark.asyncio
    async def test_cache_expires_and_refetches(self):
        """After the TTL elapses the next call issues a fresh RPC."""
        from agent.mcp_client import MCPClient

        client = MCPClient("http://test-mcp:8008")
        call_count = 0

        async def fake_rpc(method: str, params: Any = None) -> Any:
            nonlocal call_count
            call_count += 1
            return {"tools": [{"name": f"tool_{call_count}"}], "ttlMs": 100}

        client._rpc = fake_rpc  # type: ignore[assignment]

        t1 = await client.list_tools()
        # Artificially expire the cache
        client._tools_cache_expires_at = time.monotonic() - 1.0
        t2 = await client.list_tools()
        assert call_count == 2
        assert t1 != t2  # second call got fresh tools

    @pytest.mark.asyncio
    async def test_invalidate_clears_cache(self):
        """invalidate_tools_cache() forces a fresh RPC on the next call."""
        from agent.mcp_client import MCPClient

        client = MCPClient("http://test-mcp:8008")
        call_count = 0

        async def fake_rpc(method: str, params: Any = None) -> Any:
            nonlocal call_count
            call_count += 1
            return {"tools": [{"name": "t"}], "ttlMs": 60000}

        client._rpc = fake_rpc  # type: ignore[assignment]

        await client.list_tools()   # fills cache
        client.invalidate_tools_cache()
        await client.list_tools()   # must re-fetch
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_missing_ttl_uses_default(self):
        """When the server omits ttlMs the default TTL is applied."""
        from agent.mcp_client import MCPClient, _DEFAULT_TOOLS_TTL_MS

        client = MCPClient("http://test-mcp:8008")

        async def fake_rpc(method: str, params: Any = None) -> Any:
            return {"tools": []}  # no ttlMs

        client._rpc = fake_rpc  # type: ignore[assignment]

        await client.list_tools()
        remaining = client._tools_cache_expires_at - time.monotonic()
        expected_ttl = _DEFAULT_TOOLS_TTL_MS / 1000.0
        assert abs(remaining - expected_ttl) < 1.0  # within 1 second

    @pytest.mark.asyncio
    async def test_zero_ttl_from_server_uses_default(self):
        """ttlMs: 0 from the server is treated as absent (use default TTL)."""
        from agent.mcp_client import MCPClient

        client = MCPClient("http://test-mcp:8008")
        call_count = 0

        async def fake_rpc(method: str, params: Any = None) -> Any:
            nonlocal call_count
            call_count += 1
            return {"tools": [], "ttlMs": 0}

        client._rpc = fake_rpc  # type: ignore[assignment]

        await client.list_tools()
        await client.list_tools()  # should use cache
        assert call_count == 1  # default TTL > 0, so cache used

    def test_fresh_client_has_no_cache(self):
        from agent.mcp_client import MCPClient
        client = MCPClient("http://x")
        assert client._tools_cache is None
        assert client._tools_cache_expires_at == 0.0


# ── 3. Model cost table ───────────────────────────────────────────────────────


class TestModelCostTableUpdates:
    """New models are present in the cost table with sensible prices."""

    def _raw_table(self) -> "dict[str, tuple[float, float]]":
        from packages.ai.cost_tracker import _COST_TABLE
        return _COST_TABLE

    def _api_table(self) -> "dict[str, dict[str, float]]":
        from packages.ai.cost_tracker import get_cost_table
        return get_cost_table()

    def test_claude_sonnet_5_in_table(self):
        table = self._raw_table()
        assert "claude-sonnet-5" in table
        inp, out = table["claude-sonnet-5"]
        assert isinstance(inp, (int, float)) and inp >= 0
        assert isinstance(out, (int, float)) and out >= 0

    def test_gpt_56_sol_in_table(self):
        table = self._raw_table()
        assert "gpt-5.6-sol" in table
        inp, out = table["gpt-5.6-sol"]
        assert inp > 0 and out > 0  # Sol is a paid model

    def test_gpt_56_terra_in_table(self):
        assert "gpt-5.6-terra" in self._raw_table()

    def test_gpt_56_luna_in_table(self):
        assert "gpt-5.6-luna" in self._raw_table()

    def test_o3_in_table(self):
        assert "o3" in self._raw_table()

    def test_sol_more_expensive_than_terra_more_than_luna(self):
        table = self._raw_table()
        sol_out = table["gpt-5.6-sol"][1]
        terra_out = table["gpt-5.6-terra"][1]
        luna_out = table["gpt-5.6-luna"][1]
        assert sol_out > terra_out > luna_out

    def test_existing_models_unchanged(self):
        table = self._raw_table()
        # Ensure the new entries didn't accidentally overwrite existing ones
        assert "claude-sonnet-4-6" in table
        assert "gpt-4o" in table
        assert table["gpt-4o"] == (2.5, 10.0)

    def test_get_cost_table_includes_new_models(self):
        """get_cost_table() API exposes the new models with correct structure."""
        api = self._api_table()
        for model in ("claude-sonnet-5", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "o3"):
            assert model in api
            row = api[model]
            assert "input_per_million_usd" in row
            assert "output_per_million_usd" in row
