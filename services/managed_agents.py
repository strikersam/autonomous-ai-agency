"""
Managed Agents Dream Consolidation

Inspired by Claude's Managed Agents with Dreams feature.
Implements session consolidation, memory replay, and learning from past interactions.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("managed_agents")


@dataclass
class Dream:
    """A consolidation of learned patterns from a session"""

    id: str
    timestamp: datetime
    patterns: list[str]  # Patterns learned
    successes: int = 0
    failures: int = 0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "patterns": self.patterns,
            "successes": self.successes,
            "failures": self.failures,
            "metadata": self.metadata,
        }


@dataclass
class SessionMemory:
    """Memory from a single agent session"""

    session_id: str
    agent_id: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    decisions: list[dict] = field(default_factory=list)
    outcomes: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)

    def duration_seconds(self) -> float:
        """Get session duration"""
        end = self.ended_at or datetime.now()
        return (end - self.started_at).total_seconds()

    def success_rate(self) -> float:
        """Calculate success rate"""
        if not self.outcomes:
            return 0.0
        successes = sum(1 for o in self.outcomes if o.get("success"))
        return successes / len(self.outcomes)


class ManagedAgentDreams:
    """
    Consolidate learning from agent sessions into reusable patterns.

    Inspired by Claude's Managed Agents with Dreams:
    - Replay successful decision patterns
    - Extract generalizable insights
    - Build persistent agent memory
    """

    def __init__(self):
        self.sessions: dict[str, SessionMemory] = {}
        self.dreams: list[Dream] = []
        self.pattern_cache: dict[str, float] = {}  # pattern -> success rate

    def record_session(self, session: SessionMemory):
        """Record a completed session"""
        self.sessions[session.session_id] = session
        log.info(
            f"Recorded session {session.session_id} "
            f"(success_rate: {session.success_rate():.1%})"
        )

        # Extract patterns if session was successful
        if session.success_rate() > 0.7:
            self._consolidate_dreams(session)

    def _consolidate_dreams(self, session: SessionMemory):
        """Extract learning patterns from session"""
        patterns = []

        # Pattern 1: Successful decision sequences
        for decision in session.decisions:
            if decision.get("success"):
                patterns.append(f"decision:{decision['type']}")

        # Pattern 2: Error recovery
        for error in session.errors:
            if error.get("resolved"):
                patterns.append(f"recovery:{error['type']}")

        # Pattern 3: Agent characteristics
        patterns.append(f"agent:{session.agent_id}")

        if patterns:
            dream = Dream(
                id=f"dream_{len(self.dreams)}",
                timestamp=datetime.now(),
                patterns=patterns,
                successes=sum(1 for o in session.outcomes if o.get("success")),
                failures=sum(1 for o in session.outcomes if not o.get("success")),
            )
            self.dreams.append(dream)
            log.info(f"Consolidated dream: {dream.id} with {len(patterns)} patterns")

    def replay_patterns(self, agent_id: str, limit: int = 5) -> list[str]:
        """Get successful patterns for an agent to replay"""
        relevant_dreams = [d for d in self.dreams if f"agent:{agent_id}" in d.patterns]
        relevant_dreams.sort(key=lambda d: d.successes - d.failures, reverse=True)

        patterns = set()
        for dream in relevant_dreams[:limit]:
            patterns.update(dream.patterns)

        return list(patterns)

    def get_agent_memory(self, agent_id: str) -> dict:
        """Get consolidated memory for an agent"""
        agent_sessions = [
            s for s in self.sessions.values() if s.agent_id == agent_id
        ]

        if not agent_sessions:
            return {}

        avg_duration = sum(s.duration_seconds() for s in agent_sessions) / len(
            agent_sessions
        )
        avg_success = sum(s.success_rate() for s in agent_sessions) / len(
            agent_sessions
        )

        return {
            "agent_id": agent_id,
            "total_sessions": len(agent_sessions),
            "avg_session_duration_sec": avg_duration,
            "avg_success_rate": avg_success,
            "patterns": self.replay_patterns(agent_id),
            "total_dreams": len([d for d in self.dreams if f"agent:{agent_id}" in d.patterns]),
        }

    def export_dreams(self) -> str:
        """Export all dreams as JSON"""
        return json.dumps([d.to_dict() for d in self.dreams], default=str, indent=2)

    def stats(self) -> dict:
        """Get memory statistics"""
        if not self.sessions:
            return {"sessions": 0, "dreams": 0}

        all_outcomes = [o for s in self.sessions.values() for o in s.outcomes]
        success_count = sum(1 for o in all_outcomes if o.get("success"))

        return {
            "total_sessions": len(self.sessions),
            "total_dreams": len(self.dreams),
            "overall_success_rate": (
                success_count / len(all_outcomes) if all_outcomes else 0.0
            ),
            "patterns_learned": len(set(p for d in self.dreams for p in d.patterns)),
        }
