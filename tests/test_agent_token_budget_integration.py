"""Integration tests: TokenBudget wired into AgentRunner._chat_text (★3 roadmap).

These tests verify that:
  1. AgentRunner has a _token_budget attribute.
  2. set_token_budget() configures a cap for a session.
  3. _record_tokens() accumulates correctly and warns at 80%.
  4. _record_tokens() raises BudgetExceededError when the cap is hit.
  5. _record_tokens() is a no-op when session_id is None.
  6. The TokenBudget singleton per runner is independent of other runners.
"""
from __future__ import annotations

import pytest

from agent.loop import AgentRunner
from agent.token_budget import BudgetExceededError, TokenBudget


@pytest.fixture()
def runner(tmp_path) -> AgentRunner:
    return AgentRunner(ollama_base="http://localhost:11434", workspace_root=str(tmp_path))


# ---------------------------------------------------------------------------
# Basic attribute presence
# ---------------------------------------------------------------------------

def test_runner_has_token_budget_attr(runner: AgentRunner) -> None:
    assert hasattr(runner, "_token_budget")
    assert isinstance(runner._token_budget, TokenBudget)


def test_runner_has_set_token_budget_method(runner: AgentRunner) -> None:
    assert callable(getattr(runner, "set_token_budget", None))


def test_runner_has_record_tokens_method(runner: AgentRunner) -> None:
    assert callable(getattr(runner, "_record_tokens", None))


# ---------------------------------------------------------------------------
# set_token_budget
# ---------------------------------------------------------------------------

def test_set_token_budget_configures_cap(runner: AgentRunner) -> None:
    runner.set_token_budget("sess-1", cap=10_000)
    usage = runner._token_budget.get("sess-1")
    assert usage is not None
    assert usage.cap == 10_000


def test_set_token_budget_unlimited_is_zero(runner: AgentRunner) -> None:
    runner.set_token_budget("sess-0", cap=0)
    usage = runner._token_budget.get("sess-0")
    assert usage.cap == 0


# ---------------------------------------------------------------------------
# _record_tokens
# ---------------------------------------------------------------------------

def test_record_tokens_noop_for_none_session(runner: AgentRunner) -> None:
    runner._current_session_id = None
    # Must not raise; nothing is recorded
    runner._record_tokens(None, prompt_tokens=500, completion_tokens=200)


def test_record_tokens_accumulates_spend(runner: AgentRunner) -> None:
    runner.set_token_budget("sess-2", cap=100_000)
    runner._record_tokens("sess-2", prompt_tokens=100, completion_tokens=50)
    runner._record_tokens("sess-2", prompt_tokens=200, completion_tokens=100)
    usage = runner._token_budget.get("sess-2")
    assert usage.total_tokens == 450


def test_record_tokens_no_error_within_cap(runner: AgentRunner) -> None:
    runner.set_token_budget("sess-3", cap=1_000)
    runner._record_tokens("sess-3", prompt_tokens=100, completion_tokens=50)
    # 150 / 1000 — well within cap, no error


def test_record_tokens_raises_on_cap_exceeded(runner: AgentRunner) -> None:
    runner.set_token_budget("sess-4", cap=100)
    with pytest.raises(BudgetExceededError):
        runner._record_tokens("sess-4", prompt_tokens=200, completion_tokens=0)


def test_record_tokens_warns_at_80_pct(runner: AgentRunner, caplog) -> None:
    import logging
    runner.set_token_budget("sess-5", cap=1_000)
    # Spend 850 / 1000 (85%)
    with caplog.at_level(logging.WARNING, logger="qwen-agent"):
        runner._record_tokens("sess-5", prompt_tokens=850, completion_tokens=0)
    assert any("80%" in r.message or "85" in r.message for r in caplog.records)


def test_record_tokens_unlimited_never_raises(runner: AgentRunner) -> None:
    # cap=0 means unlimited — recording huge spend must not raise
    runner.set_token_budget("sess-6", cap=0)
    runner._record_tokens("sess-6", prompt_tokens=10_000_000, completion_tokens=10_000_000)


# ---------------------------------------------------------------------------
# Runner isolation
# ---------------------------------------------------------------------------

def test_runners_have_independent_budgets(tmp_path) -> None:
    r1 = AgentRunner(ollama_base="http://localhost:11434", workspace_root=str(tmp_path))
    r2 = AgentRunner(ollama_base="http://localhost:11434", workspace_root=str(tmp_path))
    r1.set_token_budget("shared-key", cap=50)
    r2.set_token_budget("shared-key", cap=50)

    # Spend on r1 does NOT affect r2
    r1._record_tokens("shared-key", prompt_tokens=40, completion_tokens=0)
    r2_usage = r2._token_budget.get("shared-key")
    assert r2_usage.total_tokens == 0
