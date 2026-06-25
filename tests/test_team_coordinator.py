"""Tests for agents/team_coordinator.py — Grab Multi-Agent Support.

Uses importlib to load the module directly, bypassing agents/__init__.py deps.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    path = Path(__file__).parent.parent / "agents" / "team_coordinator.py"
    spec = importlib.util.spec_from_file_location("team_coordinator", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["team_coordinator"] = mod
    spec.loader.exec_module(mod)
    return mod


mod = _load_module()
Agent = mod.Agent
TeamCoordinator = mod.TeamCoordinator


class TestAgent:
    """Tests for Agent dataclass."""

    def test_create(self):
        a = Agent(agent_id="a1", name="TestAgent", capabilities=["code", "review"])
        assert a.agent_id == "a1"
        assert a.name == "TestAgent"
        assert a.available is True
        assert a.active_tasks == 0

    def test_has_capability(self):
        a = Agent(agent_id="a1", name="x", capabilities=["code"])
        assert a.has_capability("code") is True
        assert a.has_capability("design") is False

    def test_assign_and_load(self):
        a = Agent(agent_id="a1", name="x", capabilities=["code"], max_tasks=2)
        assert a.assign() is True
        assert a.active_tasks == 1
        assert a.load == 0.5
        assert a.assign() is True
        assert a.active_tasks == 2
        assert a.available is False
        assert a.assign() is False  # full

    def test_release(self):
        a = Agent(agent_id="a1", name="x", capabilities=["code"], max_tasks=2)
        a.assign()
        a.assign()
        assert a.available is False
        a.release()
        assert a.available is True
        assert a.active_tasks == 1

    def test_release_at_zero(self):
        a = Agent(agent_id="a1", name="x", capabilities=["code"])
        a.release()  # should not go negative
        assert a.active_tasks == 0

    def test_assign_unavailable(self):
        a = Agent(agent_id="a1", name="x", available=False, capabilities=["code"])
        assert a.assign() is False


class TestTeamCoordinator:
    """Tests for TeamCoordinator."""

    def test_add_agent(self):
        tc = TeamCoordinator(team_id="t1")
        tc.add_agent(Agent(agent_id="a1", name="A"))
        assert tc.agent_count == 1

    def test_add_duplicate_raises(self):
        tc = TeamCoordinator(team_id="t1")
        tc.add_agent(Agent(agent_id="a1", name="A"))
        try:
            tc.add_agent(Agent(agent_id="a1", name="A2"))
            assert False, "Expected ValueError"
        except ValueError:
            pass

    def test_remove_agent(self):
        tc = TeamCoordinator(team_id="t1")
        tc.add_agent(Agent(agent_id="a1", name="A"))
        tc.remove_agent("a1")
        assert tc.agent_count == 0

    def test_get_agent(self):
        tc = TeamCoordinator(team_id="t1")
        a = Agent(agent_id="a1", name="A")
        tc.add_agent(a)
        assert tc.get_agent("a1") is a
        assert tc.get_agent("nope") is None

    def test_find_capable(self):
        tc = TeamCoordinator(team_id="t1")
        tc.add_agent(Agent(agent_id="a1", name="A", capabilities=["code"]))
        tc.add_agent(Agent(agent_id="a2", name="B", capabilities=["design"]))
        assert len(tc.find_capable("code")) == 1
        assert len(tc.find_capable("design")) == 1
        assert len(tc.find_capable("security")) == 0

    def test_assign_task_prefers_least_loaded(self):
        tc = TeamCoordinator(team_id="t1")
        a1 = Agent(agent_id="a1", name="A", capabilities=["code"], max_tasks=3)
        a2 = Agent(agent_id="a2", name="B", capabilities=["code"], max_tasks=3)
        tc.add_agent(a1)
        tc.add_agent(a2)
        a1.assign()  # a1 has load 1/3
        result = tc.assign_task("code")
        assert result is not None
        assert result.agent_id == "a2"  # a2 was less loaded

    def test_assign_task_none_available(self):
        tc = TeamCoordinator(team_id="t1")
        assert tc.assign_task("code") is None

    def test_release_agent(self):
        tc = TeamCoordinator(team_id="t1")
        a = Agent(agent_id="a1", name="A", capabilities=["code"], max_tasks=1)
        tc.add_agent(a)
        a.assign()
        assert a.available is False
        tc.release_agent("a1")
        assert a.available is True

    def test_available_agents(self):
        tc = TeamCoordinator(team_id="t1")
        tc.add_agent(Agent(agent_id="a1", name="A", available=False))
        tc.add_agent(Agent(agent_id="a2", name="B", available=True))
        assert len(tc.available_agents()) == 1

    def test_team_load_empty(self):
        tc = TeamCoordinator(team_id="t1")
        assert tc.team_load() == 1.0

    def test_team_load(self):
        tc = TeamCoordinator(team_id="t1")
        a1 = Agent(agent_id="a1", name="A", max_tasks=2)
        a2 = Agent(agent_id="a2", name="B", max_tasks=2)
        tc.add_agent(a1)
        tc.add_agent(a2)
        a1.assign()
        assert tc.team_load() == 0.25  # (0.5 + 0) / 2

    def test_agents_by_capability_ordered(self):
        tc = TeamCoordinator(team_id="t1")
        a1 = Agent(agent_id="a1", name="A", capabilities=["code"], max_tasks=3)
        a2 = Agent(agent_id="a2", name="B", capabilities=["code"], max_tasks=3)
        tc.add_agent(a1)
        tc.add_agent(a2)
        a1.assign()
        ordered = tc.agents_by_capability("code")
        assert ordered[0].agent_id == "a2"  # less loaded first
