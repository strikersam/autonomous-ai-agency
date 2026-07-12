"""Tests for agent/context_pruner.py — 3-Phase Context-Pruner Middleware."""
from __future__ import annotations

import time

import pytest

from agent.context_pruner import ContextPruner, _DEFAULT_PRUNE_AFTER_TOKENS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def pruner() -> ContextPruner:
    """A pruner with a tiny budget so tests can trigger pruning cheaply."""
    return ContextPruner(
        user_budget=500,
        assistant_budget=500,
        prune_after_tokens=10,  # trigger on tiny inputs
        cache_ttl=0,            # never skip due to cache
    )


@pytest.fixture()
def big_pruner() -> ContextPruner:
    """A pruner with a large budget (tests that pruning does NOT trigger)."""
    return ContextPruner(
        user_budget=999_999,
        assistant_budget=999_999,
        prune_after_tokens=_DEFAULT_PRUNE_AFTER_TOKENS,
        cache_ttl=300,
    )


# ---------------------------------------------------------------------------
# prune() — pass-through and triggering
# ---------------------------------------------------------------------------

def test_prune_empty_returns_empty(pruner: ContextPruner) -> None:
    assert pruner.prune([]) == []


def test_prune_pass_through_when_under_budget(big_pruner: ContextPruner) -> None:
    msgs = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello"},
    ]
    result = big_pruner.prune(msgs)
    # Under-budget context is returned unchanged (no pruning applied)
    assert result == msgs


def test_prune_triggers_on_small_budget(pruner: ContextPruner) -> None:
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "u"},
        {"role": "assistant", "content": "a"},
    ]
    result = pruner.prune(msgs)
    # Should return a list (may be same or pruned — just must not crash)
    assert isinstance(result, list)
    assert len(result) >= 1  # system always kept


# ---------------------------------------------------------------------------
# Phase 1: _phase1_truncate
# ---------------------------------------------------------------------------

def test_phase1_strips_think_tags(pruner: ContextPruner) -> None:
    msgs = [{"role": "assistant", "content": "Hello <think>deep thoughts</think> world"}]
    result = pruner._phase1_truncate(msgs)
    assert "<think>" not in result[0]["content"]
    assert "Hello" in result[0]["content"]
    assert "world" in result[0]["content"]


def test_phase1_strips_unclosed_think_tag(pruner: ContextPruner) -> None:
    msgs = [{"role": "assistant", "content": "prefix <think>reasoning that never ends"}]
    result = pruner._phase1_truncate(msgs)
    assert "<think>" not in result[0]["content"]


def test_phase1_truncates_long_tool_output(pruner: ContextPruner) -> None:
    long_content = "x" * 5000
    msgs = [{"role": "tool", "content": long_content}]
    result = pruner._phase1_truncate(msgs)
    assert len(result[0]["content"]) < 2200  # 2000 chars + ellipsis marker
    assert "truncated" in result[0]["content"]


def test_phase1_preserves_short_tool_output(pruner: ContextPruner) -> None:
    short_content = "tiny result"
    msgs = [{"role": "tool", "content": short_content}]
    result = pruner._phase1_truncate(msgs)
    assert result[0]["content"] == short_content


def test_phase1_handles_non_string_content(pruner: ContextPruner) -> None:
    msgs = [{"role": "user", "content": ["list", "content"]}]
    result = pruner._phase1_truncate(msgs)
    # Non-string content passes through unchanged
    assert result[0]["content"] == ["list", "content"]


# ---------------------------------------------------------------------------
# Phase 2: _phase2_backward_walk
# ---------------------------------------------------------------------------

def test_phase2_always_keeps_system(pruner: ContextPruner) -> None:
    msgs = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "u1"},
    ]
    kept, _ = pruner._phase2_backward_walk(msgs)
    roles = [m["role"] for m in kept]
    assert "system" in roles


def test_phase2_evicts_old_messages_over_budget() -> None:
    pruner = ContextPruner(
        user_budget=20,        # chars, not tokens — 5 chars per msg budget
        assistant_budget=20,
        prune_after_tokens=1,
        cache_ttl=0,
    )
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "oldest user message"},     # over budget → evict
        {"role": "assistant", "content": "oldest reply"},
        {"role": "user", "content": "new"},                     # recent → keep
        {"role": "assistant", "content": "ok"},
    ]
    kept, evicted = pruner._phase2_backward_walk(msgs)
    kept_contents = [m["content"] for m in kept]
    assert "sys" in kept_contents     # system always kept
    assert "new" in kept_contents     # most recent user kept
    assert len(evicted) > 0           # something was evicted


def test_phase2_no_eviction_when_within_budget(big_pruner: ContextPruner) -> None:
    msgs = [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    kept, evicted = big_pruner._phase2_backward_walk(msgs)
    assert evicted == []
    assert len(kept) == 3


# ---------------------------------------------------------------------------
# Phase 3: _phase3_xml_wrap
# ---------------------------------------------------------------------------

def test_phase3_no_eviction_returns_kept(pruner: ContextPruner) -> None:
    kept = [{"role": "user", "content": "hi"}]
    result = pruner._phase3_xml_wrap(kept, [])
    assert result == kept


def test_phase3_injects_history_into_system(pruner: ContextPruner) -> None:
    kept = [
        {"role": "system", "content": "sys prompt"},
        {"role": "user", "content": "current"},
    ]
    evicted = [{"role": "user", "content": "old turn"}]
    result = pruner._phase3_xml_wrap(kept, evicted)
    system_msg = next(m for m in result if m["role"] == "system")
    assert "<historical_memory_only>" in system_msg["content"]
    assert "old turn" in system_msg["content"]
    # Current messages still present
    user_msgs = [m for m in result if m["role"] == "user"]
    assert any("current" in m["content"] for m in user_msgs)


def test_phase3_prepends_system_when_none_exists(pruner: ContextPruner) -> None:
    kept = [{"role": "user", "content": "q"}]
    evicted = [{"role": "assistant", "content": "old a"}]
    result = pruner._phase3_xml_wrap(kept, evicted)
    assert result[0]["role"] == "system"
    assert "<historical_memory_only>" in result[0]["content"]


# ---------------------------------------------------------------------------
# touch() and caching
# ---------------------------------------------------------------------------

def test_touch_resets_timer() -> None:
    pruner = ContextPruner(
        user_budget=999_999,
        assistant_budget=999_999,
        prune_after_tokens=999_999,
        cache_ttl=3600,
    )
    # Simulate a recent prune so cache is warm
    pruner._last_pruned = time.time()
    msgs = [{"role": "user", "content": "small"}]
    # Cache is warm — should pass through without pruning
    result1 = pruner.prune(msgs)
    assert result1 == msgs

    # touch() clears the timer → next call must run pruning
    pruner.touch()
    assert pruner._last_pruned == 0.0
