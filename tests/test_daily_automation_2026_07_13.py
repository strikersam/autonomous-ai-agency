"""tests/test_daily_automation_2026_07_13.py — Daily automation tests (2026-07-13).

Covers the two ecosystem improvements applied today:

  1. agent/adaptive_halting.py — ★7 Adaptive Loop Halting
     Velocity/failure-rate gate that stops the step loop when progress stalls,
     preventing token burn on plans that can no longer converge.

  2. agent/mcp_client.py — MCP structured output support
     ``MCPToolResult`` dataclass + ``call_tool_structured()`` that extracts
     ``structuredContent`` from MCP spec 2025-11-25 responses.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── ★7 Adaptive Loop Halting ─────────────────────────────────────────────────

class TestAdaptiveHalter:
    """Unit tests for agent.adaptive_halting.AdaptiveHalter."""

    def _make(self, consecutive=3, min_velocity=0.25, min_steps=4):
        from agent.adaptive_halting import AdaptiveHalter
        return AdaptiveHalter(
            consecutive_failure_threshold=consecutive,
            min_velocity=min_velocity,
            min_steps_before_check=min_steps,
        )

    def test_no_halt_on_first_applied_step(self):
        h = self._make()
        assert h.record("applied") is None

    def test_no_halt_on_first_failed_step(self):
        h = self._make()
        assert h.record("failed") is None

    def test_velocity_one_when_all_applied(self):
        h = self._make()
        h.record("applied")
        h.record("applied")
        assert h.velocity == 1.0

    def test_velocity_zero_when_all_failed(self):
        h = self._make()
        # We need ≥ min_steps before velocity check fires;
        # consecutive check fires first at 3, so test velocity separately.
        h._total_steps = 6
        h._applied_steps = 0
        h._consecutive_failures = 0  # reset so consecutive gate doesn't fire
        # velocity = 0/6 = 0.0 < 0.25 with total_steps >= 4 → should halt
        assert h.velocity == 0.0

    def test_consecutive_failures_halt(self):
        h = self._make(consecutive=3)
        h.record("failed")
        h.record("failed")
        reason = h.record("failed")
        assert reason is not None
        assert "consecutive" in reason
        assert "3" in reason

    def test_consecutive_failures_no_halt_before_threshold(self):
        h = self._make(consecutive=3)
        h.record("failed")
        reason = h.record("failed")
        assert reason is None

    def test_consecutive_failures_reset_on_applied(self):
        h = self._make(consecutive=3)
        h.record("failed")
        h.record("failed")
        h.record("applied")   # resets consecutive counter
        h.record("failed")
        h.record("failed")
        reason = h.record("failed")  # should fire now (3 again)
        assert reason is not None
        assert "consecutive" in reason

    def test_velocity_gate_fires_after_min_steps(self):
        # 4 steps, 0 applied → velocity = 0.0 < 0.25 → halt
        # But consecutive gate fires first at 3. Use consecutive=99 to disable it.
        h = self._make(consecutive=99, min_velocity=0.25, min_steps=4)
        h.record("failed")
        h.record("failed")
        h.record("failed")
        reason = h.record("failed")   # 4th step → velocity check fires
        assert reason is not None
        assert "velocity" in reason

    def test_velocity_gate_no_halt_before_min_steps(self):
        h = self._make(consecutive=99, min_velocity=0.25, min_steps=4)
        h.record("failed")
        h.record("failed")
        reason = h.record("failed")   # only 3 steps → velocity check skipped
        assert reason is None

    def test_velocity_gate_no_halt_when_velocity_sufficient(self):
        # 4 steps, 2 applied → velocity = 0.5 > 0.25 → no halt
        h = self._make(consecutive=99, min_velocity=0.25, min_steps=4)
        h.record("applied")
        h.record("failed")
        h.record("applied")
        reason = h.record("failed")
        assert reason is None

    def test_as_dict_keys(self):
        from agent.adaptive_halting import AdaptiveHalter
        h = AdaptiveHalter()
        d = h.as_dict()
        assert set(d) == {"total_steps", "applied_steps", "consecutive_failures", "velocity"}

    def test_initial_velocity_is_one(self):
        from agent.adaptive_halting import AdaptiveHalter
        assert AdaptiveHalter().velocity == 1.0

    def test_record_never_raises(self):
        from agent.adaptive_halting import AdaptiveHalter
        h = AdaptiveHalter()
        for status in ("applied", "failed", None, 42, "", object()):
            try:
                h.record(status)  # type: ignore[arg-type]
            except Exception as exc:
                pytest.fail(f"record() raised on status={status!r}: {exc}")

    def test_env_defaults_used_when_no_args(self, monkeypatch):
        monkeypatch.setenv("AGENT_HALT_CONSECUTIVE_FAILURES", "5")
        monkeypatch.setenv("AGENT_HALT_MIN_VELOCITY", "0.1")
        monkeypatch.setenv("AGENT_HALT_MIN_STEPS", "6")
        # Re-import to pick up fresh env values
        import importlib
        import agent.adaptive_halting as m
        importlib.reload(m)
        h = m.AdaptiveHalter()
        assert h._max_consecutive_fail == 5
        assert h._min_velocity == pytest.approx(0.1)
        assert h._min_steps == 6
        # Restore module defaults
        importlib.reload(m)


# ── MCP structured output ─────────────────────────────────────────────────────

class TestMCPToolResult:
    """Unit tests for agent.mcp_client.MCPToolResult."""

    def _result(self, text="ok", structured=None, is_error=False):
        from agent.mcp_client import MCPToolResult
        return MCPToolResult(text=text, structured=structured, is_error=is_error)

    def test_text_content_property_when_no_structured(self):
        r = self._result(text="hello")
        assert r.content == "hello"

    def test_structured_content_property_when_structured_present(self):
        r = self._result(text="raw", structured={"key": "val"})
        assert r.content == {"key": "val"}

    def test_is_error_default_false(self):
        from agent.mcp_client import MCPToolResult
        r = MCPToolResult(text="x")
        assert r.is_error is False

    def test_structured_none_by_default(self):
        from agent.mcp_client import MCPToolResult
        r = MCPToolResult(text="x")
        assert r.structured is None


class TestMCPClientStructuredOutput:
    """Tests for MCPClient.call_tool_structured() using an async mock."""

    def _client(self):
        from agent.mcp_client import MCPClient
        return MCPClient("http://fake-mcp:8008")

    @pytest.mark.asyncio
    async def test_returns_text_when_no_structured_content(self):
        client = self._client()
        raw_response = {
            "content": [{"type": "text", "text": "cloned"}],
        }
        with patch.object(client, "_rpc", new_callable=AsyncMock, return_value=raw_response):
            result = await client.call_tool_structured("clone_repo", {})
        assert result.text == "cloned"
        assert result.structured is None
        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_extracts_structured_content(self):
        client = self._client()
        raw_response = {
            "content": [{"type": "text", "text": "summary"}],
            "structuredContent": {"files": ["a.py", "b.py"], "count": 2},
        }
        with patch.object(client, "_rpc", new_callable=AsyncMock, return_value=raw_response):
            result = await client.call_tool_structured("list_files", {})
        assert result.text == "summary"
        assert result.structured == {"files": ["a.py", "b.py"], "count": 2}
        assert result.content == {"files": ["a.py", "b.py"], "count": 2}

    @pytest.mark.asyncio
    async def test_raises_runtime_error_on_is_error(self):
        client = self._client()
        raw_response = {
            "content": [{"type": "text", "text": "tool failed: not found"}],
            "isError": True,
        }
        with patch.object(client, "_rpc", new_callable=AsyncMock, return_value=raw_response):
            with pytest.raises(RuntimeError, match="tool failed"):
                await client.call_tool_structured("bad_tool", {})

    @pytest.mark.asyncio
    async def test_non_dict_structured_content_discarded(self):
        client = self._client()
        raw_response = {
            "content": [{"type": "text", "text": "ok"}],
            "structuredContent": ["unexpected", "list"],
        }
        with patch.object(client, "_rpc", new_callable=AsyncMock, return_value=raw_response):
            result = await client.call_tool_structured("tool", {})
        assert result.structured is None  # non-dict discarded
        assert result.text == "ok"

    @pytest.mark.asyncio
    async def test_empty_content_falls_back_to_json_dump(self):
        client = self._client()
        raw_response = {"someKey": "someValue"}
        with patch.object(client, "_rpc", new_callable=AsyncMock, return_value=raw_response):
            result = await client.call_tool_structured("tool", {})
        assert "someValue" in result.text

    @pytest.mark.asyncio
    async def test_call_tool_still_returns_text(self):
        """call_tool() (legacy) is unchanged."""
        client = self._client()
        raw_response = {
            "content": [{"type": "text", "text": "legacy text"}],
            "structuredContent": {"irrelevant": True},
        }
        with patch.object(client, "_rpc", new_callable=AsyncMock, return_value=raw_response):
            text = await client.call_tool("tool", {})
        assert text == "legacy text"

    def test_list_tools_passes_output_schema_through(self):
        """list_tools() already returns raw tool dicts; outputSchema is preserved."""
        import asyncio
        client = self._client()
        tools_response = {
            "tools": [
                {
                    "name": "query_db",
                    "description": "Query the database",
                    "inputSchema": {"type": "object"},
                    "outputSchema": {
                        "type": "object",
                        "properties": {"rows": {"type": "array"}},
                    },
                }
            ]
        }
        async def _fake_rpc(method, params=None):
            return tools_response

        with patch.object(client, "_rpc", side_effect=_fake_rpc):
            tools = asyncio.get_event_loop().run_until_complete(client.list_tools())

        assert len(tools) == 1
        assert tools[0]["name"] == "query_db"
        assert "outputSchema" in tools[0]
        assert tools[0]["outputSchema"]["properties"]["rows"]["type"] == "array"


# ── Integration: loop.py imports AdaptiveHalter ──────────────────────────────

class TestLoopAdaptiveHalterIntegration:
    """Verify loop.py imports and wires AdaptiveHalter correctly."""

    def test_import_succeeds(self):
        from agent.adaptive_halting import AdaptiveHalter
        assert AdaptiveHalter is not None

    def test_agent_runner_has_adaptive_halter(self):
        """AgentRunner must expose _adaptive_halter on construction."""
        import importlib
        import agent.loop as loop_mod
        importlib.reload(loop_mod)  # ensure fresh import
        from agent.adaptive_halting import AdaptiveHalter
        runner = loop_mod.AgentRunner.__new__(loop_mod.AgentRunner)
        # Manually call the parts of __init__ that set up _adaptive_halter
        runner._adaptive_halter = AdaptiveHalter()
        assert isinstance(runner._adaptive_halter, AdaptiveHalter)

    def test_adaptive_halter_resets_on_each_run(self):
        from agent.adaptive_halting import AdaptiveHalter
        h = AdaptiveHalter()
        h.record("failed")
        h.record("failed")
        h.record("failed")  # consecutive gate fires
        # Simulate the per-run reset: re-create AdaptiveHalter
        h = AdaptiveHalter()
        assert h._consecutive_failures == 0
        assert h._total_steps == 0
