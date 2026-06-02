"""Managed Agents Dreams — session memory and dream consolidation for managed agents.

Issue: #260
Branch: fix/quick-note-260-managed-agents
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


@dataclass
class SessionMemory:
    """An individual memory snapshot from an agent session."""

    session_id: str
    agent_id: str
    content: str
    importance: float = 0.5
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.importance <= 1.0:
            raise ValueError("importance must be between 0.0 and 1.0")


@dataclass
class Dream:
    """A consolidated dream built from multiple session memories."""

    dream_id: str
    source_session_ids: List[str]
    narrative: str
    insights: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: List[str] = field(default_factory=list)
    consolidated_from: int = 0

    def summary(self) -> str:
        """Return a brief summary of the dream."""
        lines = [f"Dream {self.dream_id}:"]
        lines.append(f"  Consolidated from {self.consolidated_from} memories")
        lines.append(f"  Insights: {len(self.insights)}")
        lines.append(f"  Narrative length: {len(self.narrative)} chars")
        return "\n".join(lines)


@dataclass
class ManagedAgentDreams:
    """Manages recording session memories and consolidating them into dreams."""

    agent_id: str
    _memories: List[SessionMemory] = field(default_factory=list)
    _dreams: List[Dream] = field(default_factory=list)
    _consolidation_threshold: int = 5

    def record(self, content: str, importance: float = 0.5,
               tags: Optional[List[str]] = None,
               metadata: Optional[Dict[str, Any]] = None) -> SessionMemory:
        """Record a new session memory for this agent."""
        memory = SessionMemory(
            session_id=uuid4().hex[:12],
            agent_id=self.agent_id,
            content=content,
            importance=importance,
            tags=tags or [],
            metadata=metadata or {},
        )
        self._memories.append(memory)
        return memory

    def consolidate(self, min_importance: float = 0.0) -> Optional[Dream]:
        """Consolidate unconsolidated memories into a dream.

        Creates a dream when the number of unprocessed memories meets or
        exceeds the consolidation threshold. Only memories with importance
        >= min_importance are considered.

        Returns None if insufficient memories to consolidate.
        """
        unprocessed = [
            m for m in self._memories
            if m.importance >= min_importance
        ]
        if len(unprocessed) < self._consolidation_threshold:
            return None

        session_ids = [m.session_id for m in unprocessed]
        all_content = "\n".join(m.content for m in unprocessed)
        all_tags = sorted(set(t for m in unprocessed for t in m.tags))

        # Extract insights: key sentences or patterns across memories
        insights = self._extract_insights(unprocessed)

        dream = Dream(
            dream_id=uuid4().hex[:12],
            source_session_ids=session_ids,
            narrative=all_content,
            insights=insights,
            tags=all_tags,
            consolidated_from=len(unprocessed),
        )
        self._dreams.append(dream)
        return dream

    def _extract_insights(self, memories: List[SessionMemory]) -> List[str]:
        """Extract insight statements from a batch of memories."""
        insights: List[str] = []
        high_importance = [m for m in memories if m.importance >= 0.7]
        if high_importance:
            insights.append(
                f"High-priority themes from {len(high_importance)} memories: "
                + "; ".join(m.content[:60] for m in high_importance[:3])
            )
        tag_counts: Dict[str, int] = {}
        for m in memories:
            for t in m.tags:
                tag_counts[t] = tag_counts.get(t, 0) + 1
        top_tags = sorted(tag_counts, key=tag_counts.get, reverse=True)[:3]
        if top_tags:
            insights.append(f"Top tags: {', '.join(top_tags)}")
        return insights

    def replay(self, dream_id: str) -> Optional[str]:
        """Replay a dream's narrative by ID."""
        for dream in self._dreams:
            if dream.dream_id == dream_id:
                return dream.narrative
        return None

    def recent_dreams(self, limit: int = 5) -> List[Dream]:
        """Return the most recent dreams, newest first."""
        return sorted(self._dreams, key=lambda d: d.created_at, reverse=True)[:limit]

    @property
    def memory_count(self) -> int:
        """Total number of recorded memories."""
        return len(self._memories)

    @property
    def dream_count(self) -> int:
        """Total number of consolidated dreams."""
        return len(self._dreams)

    @property
    def consolidation_threshold(self) -> int:
        """The threshold for triggering consolidation."""
        return self._consolidation_threshold

    @consolidation_threshold.setter
    def consolidation_threshold(self, value: int) -> None:
        if value < 1:
            raise ValueError("consolidation_threshold must be at least 1")
        self._consolidation_threshold = value
