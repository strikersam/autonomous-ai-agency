"""
Dream Memory Consolidation — pattern consolidation across AI sessions.

Inspired by the hippocampal replay theory: long-running AI systems accumulate
session artifacts, and periodically consolidating them into structured
memories improves future recall and context reuse.

Quick-Note Issue: #259
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class MemoryKind(str, Enum):
    """What kind of memory artifact this is."""

    SESSION_NOTE = "session_note"
    LEARNED_RULE = "learned_rule"
    BUG_PATTERN = "bug_pattern"
    ARCHITECTURAL_DECISION = "architectural_decision"
    CODE_SNIPPET = "code_snippet"


class ConsolidationPhase(str, Enum):
    """Current phase of the consolidation lifecycle."""

    COLLECTING = "collecting"
    DREAMING = "dreaming"
    CONSOLIDATED = "consolidated"


@dataclass
class DreamMemory:
    """
    A single memory fragment captured during AI sessions.

    Memories start as raw session notes and, after consolidation,
    become structured, queryable artifacts.
    """

    memory_id: str
    kind: MemoryKind
    content: str
    created_at: datetime = field(default_factory=datetime.now)
    tags: list[str] = field(default_factory=list)
    embedding_similarity: float = 0.0
    consolidated: bool = False
    consolidated_at: Optional[datetime] = None

    def mark_consolidated(self) -> None:
        self.consolidated = True
        self.consolidated_at = datetime.now()

    @property
    def age_hours(self) -> float:
        return (datetime.now() - self.created_at).total_seconds() / 3600

    @property
    def is_stale(self) -> bool:
        """Memories older than 24h that haven't been consolidated are stale."""
        return not self.consolidated and self.age_hours > 24

    def add_tag(self, tag: str) -> None:
        if tag not in self.tags:
            self.tags.append(tag)

    def matches_tag(self, tag: str) -> bool:
        return tag in self.tags


@dataclass
class PatternConsolidation:
    """
    Identifies clusters of related DreamMemory fragments and consolidates
    them into a higher-level pattern.
    """

    memories: list[DreamMemory] = field(default_factory=list)
    phase: ConsolidationPhase = ConsolidationPhase.COLLECTING

    def add_memory(self, memory: DreamMemory) -> None:
        self.memories.append(memory)
        self.phase = ConsolidationPhase.COLLECTING

    @property
    def memory_count(self) -> int:
        return len(self.memories)

    @property
    def consolidated_count(self) -> int:
        return sum(1 for m in self.memories if m.consolidated)

    @property
    def unconsolidated_count(self) -> int:
        return self.memory_count - self.consolidated_count

    @property
    def stale_count(self) -> int:
        return sum(1 for m in self.memories if m.is_stale)

    def find_clusters(self, min_similarity: float = 0.3) -> list[list[DreamMemory]]:
        """Group memories into clusters by tag overlap."""
        unconsolidated = [m for m in self.memories if not m.consolidated]
        if not unconsolidated:
            return []

        clusters: list[list[DreamMemory]] = []
        assigned: set[int] = set()

        for i, mem in enumerate(unconsolidated):
            if i in assigned:
                continue
            cluster = [mem]
            assigned.add(i)
            for j, other in enumerate(unconsolidated):
                if j in assigned:
                    continue
                similarity = self._tag_similarity(mem, other)
                if similarity >= min_similarity:
                    cluster.append(other)
                    assigned.add(j)
            if len(cluster) > 1:
                clusters.append(cluster)

        return clusters

    @staticmethod
    def _tag_similarity(a: DreamMemory, b: DreamMemory) -> float:
        """Jaccard similarity of tag sets."""
        set_a = set(a.tags)
        set_b = set(b.tags)
        if not set_a and not set_b:
            return 0.0
        union = len(set_a | set_b)
        intersection = len(set_a & set_b)
        if union == 0:
            return 0.0
        return intersection / union

    def consolidate(self) -> dict:
        """Run the full consolidation cycle."""
        self.phase = ConsolidationPhase.DREAMING
        clusters = self.find_clusters()
        consolidated_ids: list[str] = []

        for cluster in clusters:
            for mem in cluster:
                mem.mark_consolidated()
                consolidated_ids.append(mem.memory_id)

        self.phase = ConsolidationPhase.CONSOLIDATED
        return {
            "phase": self.phase.value,
            "clusters_found": len(clusters),
            "memories_consolidated": len(consolidated_ids),
            "consolidated_ids": consolidated_ids,
            "stale_remaining": self.stale_count,
        }

    def memories_by_kind(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for m in self.memories:
            counts[m.kind.value] = counts.get(m.kind.value, 0) + 1
        return counts

    def memories_by_tag(self, tag: str) -> list[DreamMemory]:
        return [m for m in self.memories if m.matches_tag(tag)]

    def summary(self) -> dict:
        return {
            "phase": self.phase.value,
            "total_memories": self.memory_count,
            "consolidated": self.consolidated_count,
            "unconsolidated": self.unconsolidated_count,
            "stale": self.stale_count,
            "clusters": len(self.find_clusters()),
            "by_kind": self.memories_by_kind(),
        }
