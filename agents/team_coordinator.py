"""Grab Multi-Agent Support — Agent and TeamCoordinator with capability matching.

Issue: #234
Branch: fix/quick-note-234-multiagent
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Agent:
    """An agent with capabilities and workload tracking."""

    agent_id: str
    name: str
    capabilities: List[str] = field(default_factory=list)
    _active_tasks: int = 0
    max_tasks: int = 3
    available: bool = True

    def assign(self) -> bool:
        """Assign a task to this agent, incrementing workload."""
        if not self.available:
            return False
        if self._active_tasks >= self.max_tasks:
            return False
        self._active_tasks += 1
        if self._active_tasks >= self.max_tasks:
            self.available = False
        return True

    def release(self) -> None:
        """Release a task from this agent."""
        if self._active_tasks > 0:
            self._active_tasks -= 1
        self.available = self._active_tasks < self.max_tasks

    def has_capability(self, capability: str) -> bool:
        """Check if the agent has a specific capability."""
        return capability in self.capabilities

    @property
    def load(self) -> float:
        """Current workload as a fraction of max capacity."""
        if self.max_tasks == 0:
            return 1.0
        return self._active_tasks / self.max_tasks

    @property
    def active_tasks(self) -> int:
        """Number of currently assigned tasks."""
        return self._active_tasks


@dataclass
class TeamCoordinator:
    """Coordinates a team of agents, matching tasks to agents by capability."""

    team_id: str
    _agents: List[Agent] = field(default_factory=list)

    def add_agent(self, agent: Agent) -> None:
        """Add an agent to the team."""
        if any(a.agent_id == agent.agent_id for a in self._agents):
            raise ValueError(f"Agent '{agent.agent_id}' is already in the team.")
        self._agents.append(agent)

    def remove_agent(self, agent_id: str) -> None:
        """Remove an agent from the team."""
        self._agents = [a for a in self._agents if a.agent_id != agent_id]

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Find an agent by ID."""
        for agent in self._agents:
            if agent.agent_id == agent_id:
                return agent
        return None

    def find_capable(self, capability: str) -> List[Agent]:
        """Find all agents with a given capability."""
        return [a for a in self._agents if a.has_capability(capability)]

    def assign_task(self, capability: str) -> Optional[Agent]:
        """Assign a task to the best-fit available agent.

        Strategy: least-loaded available agent with the required capability.
        """
        capable = [
            a for a in self._agents
            if a.available and a.has_capability(capability)
        ]
        if not capable:
            return None
        capable.sort(key=lambda a: a.load)
        best = capable[0]
        if best.assign():
            return best
        return None

    def release_agent(self, agent_id: str) -> None:
        """Release a task from an agent."""
        agent = self.get_agent(agent_id)
        if agent is not None:
            agent.release()

    def available_agents(self) -> List[Agent]:
        """List all currently available agents."""
        return [a for a in self._agents if a.available]

    def agents_by_capability(self, capability: str) -> List[Agent]:
        """List agents with a capability, ordered by load."""
        capable = self.find_capable(capability)
        capable.sort(key=lambda a: a.load)
        return capable

    def team_load(self) -> float:
        """Average load across all team members."""
        if not self._agents:
            return 1.0
        return sum(a.load for a in self._agents) / len(self._agents)

    @property
    def agent_count(self) -> int:
        """Number of agents in the team."""
        return len(self._agents)
