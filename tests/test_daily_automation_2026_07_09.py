"""Daily automation tests — 2026-07-09.

Covers:
1. Agent time-awareness: get_current_time tool in AgentRunner._dispatch_tool
2. Token budget daily reset: TokenBudget.reset_daily() and maybe_auto_reset()
3. Proxy endpoint: POST /agent/budget/reset
"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# Feature 1: get_current_time agent tool
# ──────────────────────────────────────────────────────────────────────────────


class TestGetCurrentTimeTool:
    """Unit tests for the get_current_time dispatch path in AgentRunner."""

    def test_returns_utc_string(self, tmp_path: Path):
        from agent.loop import AgentRunner

        runner = AgentRunner(
            ollama_base="http://localhost:11434",
            workspace_root=tmp_path,
        )

        result = asyncio.run(
            runner._dispatch_tool("get_current_time", {})
        )

        assert isinstance(result, dict)
        assert "utc" in result
        assert "T" in result["utc"]
        assert result["utc"].endswith("Z")

    def test_returns_unix_timestamp(self, tmp_path: Path):
        from agent.loop import AgentRunner
        import time

        runner = AgentRunner(
            ollama_base="http://localhost:11434",
            workspace_root=tmp_path,
        )

        before = int(time.time())
        result = asyncio.run(
            runner._dispatch_tool("get_current_time", {})
        )
        after = int(time.time())

        assert before <= result["unix_timestamp"] <= after

    def test_returns_date_and_day_of_week(self, tmp_path: Path):
        from agent.loop import AgentRunner

        runner = AgentRunner(
            ollama_base="http://localhost:11434",
            workspace_root=tmp_path,
        )

        result = asyncio.run(
            runner._dispatch_tool("get_current_time", {})
        )

        assert "date" in result
        assert len(result["date"]) == 10  # YYYY-MM-DD
        assert result["date"][4] == "-" and result["date"][7] == "-"

        assert "day_of_week" in result
        assert result["day_of_week"] in (
            "Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday",
        )

    def test_unsupported_tool_still_raises(self, tmp_path: Path):
        from agent.loop import AgentRunner

        runner = AgentRunner(
            ollama_base="http://localhost:11434",
            workspace_root=tmp_path,
        )

        with pytest.raises(ValueError, match="Unsupported tool"):
            asyncio.run(
                runner._dispatch_tool("definitely_not_a_tool_xyz", {})
            )


# ──────────────────────────────────────────────────────────────────────────────
# Feature 2: Token budget daily reset
# ──────────────────────────────────────────────────────────────────────────────


class TestTokenBudgetDailyReset:
    """Unit tests for TokenBudget.reset_daily() and maybe_auto_reset()."""

    def test_reset_daily_clears_token_counters(self):
        from agent.token_budget import TokenBudget

        budget = TokenBudget()
        budget.set_cap("s1", cap=10_000)
        budget.record("s1", prompt_tokens=3_000, completion_tokens=1_000)
        assert budget.get("s1").total_tokens == 4_000

        count = budget.reset_daily()

        assert count == 1
        assert budget.get("s1").total_tokens == 0

    def test_reset_daily_preserves_caps(self):
        from agent.token_budget import TokenBudget

        budget = TokenBudget()
        budget.set_cap("s1", cap=50_000)
        budget.record("s1", prompt_tokens=5_000)

        budget.reset_daily()

        assert budget.get("s1").cap == 50_000

    def test_reset_daily_returns_correct_count(self):
        from agent.token_budget import TokenBudget

        budget = TokenBudget()
        for i in range(5):
            budget.set_cap(f"session-{i}", cap=1_000)

        count = budget.reset_daily()
        assert count == 5

    def test_reset_daily_on_empty_budget_returns_zero(self):
        from agent.token_budget import TokenBudget

        budget = TokenBudget()
        count = budget.reset_daily()
        assert count == 0

    def test_maybe_auto_reset_resets_when_never_reset_before(self):
        from agent.token_budget import TokenBudget

        budget = TokenBudget()
        budget.set_cap("sess", cap=1_000)
        budget.record("sess", prompt_tokens=500)

        reset_happened = budget.maybe_auto_reset()

        assert reset_happened is True
        assert budget.get("sess").total_tokens == 0

    def test_maybe_auto_reset_no_reset_when_same_day(self):
        from agent.token_budget import TokenBudget
        import time

        budget = TokenBudget()
        budget.set_cap("sess", cap=1_000)
        budget.record("sess", prompt_tokens=500)
        budget.reset_daily()  # reset now

        budget.record("sess", prompt_tokens=200)
        reset_happened = budget.maybe_auto_reset()  # still same day

        # counters not cleared again
        assert reset_happened is False
        assert budget.get("sess").total_tokens == 200

    def test_get_savings_report_not_broken_after_reset(self):
        from agent.token_budget import TokenBudget

        budget = TokenBudget()
        budget.set_cap("s1", cap=10_000)
        budget.record("s1", prompt_tokens=2_000)
        budget.reset_daily()
        budget.record("s1", prompt_tokens=500)

        report = budget.get_savings_report()
        assert report["total_sessions"] == 1
        assert report["total_tokens_used"] == 500


# ──────────────────────────────────────────────────────────────────────────────
# Feature 3: POST /agent/budget/reset proxy endpoint
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def proxy_client(tmp_path, monkeypatch):
    """Minimal proxy test client with a seeded API key via env var."""
    import os
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "proxy_test.db"))
    monkeypatch.setenv("API_KEYS", "test-key-xyz")

    # Ensure proxy module is re-evaluated with patched env
    import importlib
    import sys
    # Remove cached proxy module so it reloads with the env key
    for mod_name in list(sys.modules.keys()):
        if mod_name in ("proxy",):
            sys.modules.pop(mod_name)

    from fastapi.testclient import TestClient
    import proxy as proxy_mod
    client = TestClient(proxy_mod.app, raise_server_exceptions=False)
    yield client, "test-key-xyz"


class TestBudgetResetEndpoint:
    """Integration smoke test for POST /agent/budget/reset."""

    def test_reset_endpoint_returns_200_with_count(self, proxy_client):
        client, api_key = proxy_client

        # Reset is callable even with zero sessions
        resp = client.post(
            "/agent/budget/reset",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "sessions_reset" in body
        assert isinstance(body["sessions_reset"], int)
        assert "message" in body

    def test_reset_endpoint_without_auth_returns_401(self, proxy_client):
        client, _ = proxy_client

        resp = client.post("/agent/budget/reset")
        assert resp.status_code in (401, 403, 422)
