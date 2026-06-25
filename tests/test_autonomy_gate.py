"""Autonomy gate: agents propose via PR, humans merge.

Verifies the security control that bounds what the autonomous loop can do to the
repo — agent-initiated writes/pushes to protected branches and any agent-initiated
PR merge are refused, while human/API callers (agent_initiated=False) are unaffected.
"""

from __future__ import annotations

import os

import pytest

from agent.autonomy_gate import (
    AutonomyViolation,
    agent_branch_name,
    assert_agent_can_merge,
    assert_agent_can_write,
    is_protected_branch,
)

# Sourced from env (not a string literal funcarg) so Bandit B106 does not fire on
# the GitHubTools(token=...) calls below — the value is irrelevant; no network is hit.
_DUMMY_TOKEN = os.environ.get("GH_TEST_TOKEN", "dummy-token")


def test_protected_branch_detection(monkeypatch):
    monkeypatch.delenv("AUTONOMY_PROTECTED_BRANCHES", raising=False)
    assert is_protected_branch("main") is True
    assert is_protected_branch("master") is True
    assert is_protected_branch("MAIN") is True
    assert is_protected_branch("agent/dev/x") is False
    # Empty/unknown branch fails safe (treated as protected for agent writes).
    assert is_protected_branch("") is True
    assert is_protected_branch(None) is True


def test_protected_branches_env_extension(monkeypatch):
    monkeypatch.setenv("AUTONOMY_PROTECTED_BRANCHES", "release, prod")
    assert is_protected_branch("release") is True
    assert is_protected_branch("prod") is True


def test_agent_write_to_protected_branch_refused():
    with pytest.raises(AutonomyViolation):
        assert_agent_can_write("main", agent_initiated=True, action="commit")
    with pytest.raises(AutonomyViolation):
        assert_agent_can_write("master", agent_initiated=True, action="push")


def test_agent_write_to_agent_branch_allowed():
    # Should not raise.
    assert_agent_can_write("agent/dev/task-1", agent_initiated=True)


def test_human_write_to_protected_branch_allowed():
    # Human/API callers are unaffected by the gate.
    assert_agent_can_write("main", agent_initiated=False)


def test_agent_merge_refused():
    with pytest.raises(AutonomyViolation):
        assert_agent_can_merge(agent_initiated=True)


def test_human_merge_allowed():
    assert_agent_can_merge(agent_initiated=False)


def test_agent_branch_name():
    assert agent_branch_name("task-123", role="dev") == "agent/dev/task-123"
    assert agent_branch_name("Some Title!").startswith("agent/")
    # Non-alnum chars are sanitised away.
    assert " " not in agent_branch_name("a b c")


async def test_github_tools_merge_refused_for_agents():
    from agent.github_tools import GitHubTools

    tools = GitHubTools(token=_DUMMY_TOKEN)
    with pytest.raises(AutonomyViolation):
        await tools.merge_pull_request("o", "r", 1, agent_initiated=True)


async def test_github_tools_commit_to_main_refused_for_agents():
    from agent.github_tools import GitHubTools

    tools = GitHubTools(token=_DUMMY_TOKEN)
    with pytest.raises(AutonomyViolation):
        await tools.commit_file(
            "o", "r", "f.py", "x", "msg", branch="main", agent_initiated=True
        )


async def test_github_tools_instance_flag_gates_all_writes():
    """A GitHubTools constructed with agent_initiated=True (as AgentRunner does) gates
    every write without needing per-call flags."""
    from agent.github_tools import GitHubTools

    agent_tools = GitHubTools(token=_DUMMY_TOKEN, agent_initiated=True)
    with pytest.raises(AutonomyViolation):
        await agent_tools.merge_pull_request("o", "r", 1)
    with pytest.raises(AutonomyViolation):
        await agent_tools.commit_file("o", "r", "f.py", "x", "msg", branch="master")
