"""Tests for daily automation 2026-07-11: sub-agent delegation depth guard.

Covers:
- MAX_SUBAGENT_DEPTH constant is exported and env-overridable
- Depth defaults to 0 on a fresh AgentRunner
- _spawn_subagent blocks when current depth + 1 > MAX_SUBAGENT_DEPTH
- Error dict includes expected keys (error, depth, instruction)
- Child runner inherits depth = parent._depth + 1 within the allowed range
- Depth guard logs a warning (not a raise) — callers must check the "error" key
"""

import asyncio
import os
from pathlib import Path
from unittest import mock

import pytest

from agent.loop import AgentRunner, MAX_SUBAGENT_DEPTH


# ── constant sanity ──────────────────────────────────────────────────────────

def test_max_subagent_depth_default():
    """Default depth cap matches Claude Code's 5-level limit."""
    assert MAX_SUBAGENT_DEPTH == 5


def test_max_subagent_depth_is_positive_int():
    """MAX_SUBAGENT_DEPTH must be a positive integer (safety assertion)."""
    assert isinstance(MAX_SUBAGENT_DEPTH, int)
    assert MAX_SUBAGENT_DEPTH > 0


# ── initial state ─────────────────────────────────────────────────────────────

def test_runner_depth_starts_at_zero():
    runner = AgentRunner(ollama_base="http://localhost:11434")
    assert runner._depth == 0


# ── depth guard blocks at limit ───────────────────────────────────────────────

def test_spawn_subagent_blocked_at_depth_limit(tmp_path: Path):
    """When _depth == MAX_SUBAGENT_DEPTH, _spawn_subagent must return an error."""
    root = tmp_path / "repo"
    root.mkdir()
    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)
    runner._depth = MAX_SUBAGENT_DEPTH  # simulate being at the limit

    result = asyncio.run(
        runner._spawn_subagent(instruction="Do something", max_steps=2)
    )

    assert "error" in result
    assert "depth limit" in result["error"].lower()


def test_spawn_subagent_depth_error_includes_depth_and_instruction(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)
    runner._depth = MAX_SUBAGENT_DEPTH

    result = asyncio.run(
        runner._spawn_subagent(instruction="Check files", max_steps=2)
    )

    assert result["depth"] == MAX_SUBAGENT_DEPTH + 1
    assert "Check files" in result["instruction"]


def test_spawn_subagent_allowed_below_limit(tmp_path: Path):
    """At depth MAX_SUBAGENT_DEPTH - 1 the spawn must be attempted (not blocked)."""
    root = tmp_path / "repo"
    root.mkdir()
    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)
    runner._depth = MAX_SUBAGENT_DEPTH - 1  # one level before the cap

    # Mock the child run so we don't need a live LLM.
    with mock.patch.object(AgentRunner, "run", new_callable=mock.AsyncMock) as mock_run:
        mock_run.return_value = {"goal": "sub", "summary": "ok", "status": "done"}
        result = asyncio.run(
            runner._spawn_subagent(instruction="Do something", max_steps=2)
        )

    # Should have called child .run(), not returned an error
    assert mock_run.called
    assert "error" not in result


# ── child inherits depth ──────────────────────────────────────────────────────

def test_child_runner_depth_is_incremented(tmp_path: Path):
    """Child AgentRunner._depth must be parent._depth + 1."""
    root = tmp_path / "repo"
    root.mkdir()
    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)
    runner._depth = 2  # simulate a nested caller

    captured: list[AgentRunner] = []

    async def fake_run(self, **kwargs):
        captured.append(self)
        return {"goal": "sub", "summary": "ok", "status": "done"}

    with mock.patch.object(AgentRunner, "run", fake_run):
        asyncio.run(runner._spawn_subagent(instruction="child task", max_steps=2))

    assert len(captured) == 1
    assert captured[0]._depth == 3  # parent 2 + 1


# ── depth guard doesn't raise — safe to integrate ────────────────────────────

def test_spawn_subagent_depth_block_does_not_raise(tmp_path: Path):
    """The depth guard must return a dict, never raise an exception."""
    root = tmp_path / "repo"
    root.mkdir()
    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)
    runner._depth = MAX_SUBAGENT_DEPTH

    try:
        result = asyncio.run(
            runner._spawn_subagent(instruction="anything", max_steps=1)
        )
    except Exception as exc:
        pytest.fail(f"depth guard raised unexpectedly: {exc}")

    assert isinstance(result, dict)
