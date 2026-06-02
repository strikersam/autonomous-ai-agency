"""
Temporal context graph inspired by Graphiti (https://github.com/getzep/graphiti).

Tracks how facts change over time, maintains provenance to source data,
and supports hybrid retrieval (semantic + keyword + graph traversal).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

log = logging.getLogger("temporal_context")


@dataclass
class TemporalFact:
    """A fact at a specific point in time"""

    entity: str  # e.g., "pr_100", "test_auth", "agent_session_123"
    fact: str  # e.g., "status:approved", "completion_rate:0.95"
    timestamp: datetime
    provenance: Optional[str] = None  # source: commit, issue, URL
    agent_id: Optional[str] = None  # which agent recorded this
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "entity": self.entity,
            "fact": self.fact,
            "timestamp": self.timestamp.isoformat(),
            "provenance": self.provenance,
            "agent_id": self.agent_id,
            "metadata": self.metadata,
        }


class TemporalContextGraph:
    """
    Temporal context graph for agent interactions.

    Tracks:
    - What was true at specific times
    - Who recorded each fact (agent_id)
    - Source of each fact (provenance)
    - How facts change over time
    """

    def __init__(self):
        # In-memory graph (backend: could be SQLite or Postgres)
        self.facts: list[TemporalFact] = []
        self._index: dict[str, list[int]] = {}  # entity -> fact indices

    def add_fact(
        self,
        entity: str,
        fact: str,
        timestamp: Optional[datetime] = None,
        provenance: Optional[str] = None,
        agent_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> TemporalFact:
        """Add a temporal fact to the graph"""
        if timestamp is None:
            timestamp = datetime.now()

        temporal_fact = TemporalFact(
            entity=entity,
            fact=fact,
            timestamp=timestamp,
            provenance=provenance,
            agent_id=agent_id,
            metadata=metadata or {},
        )

        self.facts.append(temporal_fact)

        # Index by entity for fast lookup
        if entity not in self._index:
            self._index[entity] = []
        self._index[entity].append(len(self.facts) - 1)

        log.debug(
            f"Added fact: {entity}={fact} @{timestamp} from {agent_id or 'unknown'}"
        )
        return temporal_fact

    def get_fact_at_time(self, entity: str, timestamp: datetime) -> Optional[str]:
        """Get what was true about an entity at a specific time"""
        if entity not in self._index:
            return None

        # Find the most recent fact before or at the given timestamp
        matching_facts = [
            self.facts[i]
            for i in self._index[entity]
            if self.facts[i].timestamp <= timestamp
        ]

        if not matching_facts:
            return None

        latest = max(matching_facts, key=lambda f: f.timestamp)
        return latest.fact

    def get_history(
        self,
        entity: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> list[TemporalFact]:
        """Get history of an entity between two times"""
        if entity not in self._index:
            return []

        if start_time is None:
            start_time = datetime.min
        if end_time is None:
            end_time = datetime.now()

        history = [
            self.facts[i]
            for i in self._index[entity]
            if start_time <= self.facts[i].timestamp <= end_time
        ]

        return sorted(history, key=lambda f: f.timestamp)

    def get_current_state(self, entity: str) -> Optional[str]:
        """Get current state of an entity (most recent fact)"""
        if entity not in self._index:
            return None

        indices = self._index[entity]
        if not indices:
            return None

        latest_fact = self.facts[max(indices, key=lambda i: self.facts[i].timestamp)]
        return latest_fact.fact

    def query_facts(
        self,
        entity_pattern: Optional[str] = None,
        fact_pattern: Optional[str] = None,
        since: Optional[timedelta] = None,
    ) -> list[TemporalFact]:
        """Query facts with pattern matching"""
        results = []

        cutoff_time = datetime.now() - since if since else datetime.min

        for fact in self.facts:
            if fact.timestamp < cutoff_time:
                continue

            entity_match = (
                entity_pattern is None
                or entity_pattern.lower() in fact.entity.lower()
            )
            fact_match = (
                fact_pattern is None or fact_pattern.lower() in fact.fact.lower()
            )

            if entity_match and fact_match:
                results.append(fact)

        return sorted(results, key=lambda f: f.timestamp, reverse=True)

    def get_provenance(self, entity: str, fact: str) -> Optional[str]:
        """Get source (provenance) of a specific fact"""
        if entity not in self._index:
            return None

        for i in self._index[entity]:
            temporal_fact = self.facts[i]
            if temporal_fact.fact == fact:
                return temporal_fact.provenance

        return None

    def export_json(self) -> str:
        """Export graph as JSON"""
        return json.dumps([f.to_dict() for f in self.facts], default=str, indent=2)

    def stats(self) -> dict:
        """Get graph statistics"""
        if not self.facts:
            return {
                "total_facts": 0,
                "entities": 0,
                "time_span_days": 0,
            }

        entities = set(f.entity for f in self.facts)
        timestamps = [f.timestamp for f in self.facts]
        time_span = (max(timestamps) - min(timestamps)).days

        agents = set(f.agent_id for f in self.facts if f.agent_id)

        return {
            "total_facts": len(self.facts),
            "entities": len(entities),
            "agents": len(agents),
            "time_span_days": time_span,
            "earliest_timestamp": min(timestamps).isoformat(),
            "latest_timestamp": max(timestamps).isoformat(),
        }


# Example usage / test patterns

def demo_agent_tracking():
    """Example: track agent actions over time"""
    graph = TemporalContextGraph()

    now = datetime.now()

    # Agent A works on a task
    graph.add_fact(
        entity="task_123",
        fact="assigned_to:agent_a",
        timestamp=now - timedelta(hours=2),
        agent_id="agent_a",
        provenance="issue #100",
    )

    # Task moves to testing
    graph.add_fact(
        entity="task_123",
        fact="status:in_progress",
        timestamp=now - timedelta(hours=1),
        agent_id="agent_a",
        provenance="commit abc123",
    )

    # Agent B reviews and approves
    graph.add_fact(
        entity="task_123",
        fact="status:approved",
        timestamp=now - timedelta(minutes=30),
        agent_id="agent_b",
        provenance="pr_review#1",
    )

    # Query current state
    print(f"Current status: {graph.get_current_state('task_123')}")

    # Query history
    history = graph.get_history("task_123")
    print(f"History: {len(history)} events")

    # Query facts from last hour
    recent = graph.query_facts(since=timedelta(hours=1))
    print(f"Last hour: {len(recent)} facts")

    # Stats
    print(f"Stats: {graph.stats()}")
# refresh diff
