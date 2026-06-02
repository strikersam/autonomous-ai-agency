"""Tests for agents.memory_consolidation — Dream Memory Consolidation."""

from __future__ import annotations

import importlib.util
import sys

import pytest

# Load the module directly to bypass agents/__init__.py dependency chain
_MEM_SPEC = importlib.util.spec_from_file_location(
    "memory_consolidation", "agents/memory_consolidation.py"
)
_mem = importlib.util.module_from_spec(_MEM_SPEC)
sys.modules["memory_consolidation"] = _mem
_MEM_SPEC.loader.exec_module(_mem)

ConsolidationPhase = _mem.ConsolidationPhase
DreamMemory = _mem.DreamMemory
MemoryKind = _mem.MemoryKind
PatternConsolidation = _mem.PatternConsolidation


def _make_memory(
    memory_id: str = "m1",
    kind: MemoryKind = MemoryKind.SESSION_NOTE,
    content: str = "test content",
    tags: list[str] | None = None,
) -> DreamMemory:
    return DreamMemory(memory_id=memory_id, kind=kind, content=content, tags=tags or [])


class TestDreamMemory:
    def test_mark_consolidated(self):
        m = _make_memory()
        assert m.consolidated is False
        m.mark_consolidated()
        assert m.consolidated is True
        assert m.consolidated_at is not None

    def test_age_hours_is_positive(self):
        m = _make_memory()
        assert m.age_hours >= 0

    def test_is_stale_false_when_consolidated(self):
        m = _make_memory()
        m.mark_consolidated()
        assert m.is_stale is False

    def test_is_stale_false_when_recent(self):
        m = _make_memory()
        assert m.is_stale is False

    def test_add_tag(self):
        m = _make_memory()
        m.add_tag("python")
        m.add_tag("testing")
        m.add_tag("python")  # duplicate
        assert len(m.tags) == 2

    def test_matches_tag(self):
        m = _make_memory(tags=["python", "async"])
        assert m.matches_tag("python") is True
        assert m.matches_tag("rust") is False


class TestPatternConsolidation:
    def test_initial_phase_is_collecting(self):
        pc = PatternConsolidation()
        assert pc.phase == ConsolidationPhase.COLLECTING

    def test_add_memory_increments_count(self):
        pc = PatternConsolidation()
        pc.add_memory(_make_memory("m1"))
        pc.add_memory(_make_memory("m2"))
        assert pc.memory_count == 2

    def test_consolidated_count(self):
        pc = PatternConsolidation()
        m1 = _make_memory("m1")
        m2 = _make_memory("m2")
        m1.mark_consolidated()
        pc.add_memory(m1)
        pc.add_memory(m2)
        assert pc.consolidated_count == 1
        assert pc.unconsolidated_count == 1

    def test_stale_count(self):
        pc = PatternConsolidation()
        from datetime import datetime, timedelta
        m = _make_memory("old")
        m.created_at = datetime.now() - timedelta(hours=48)
        pc.add_memory(m)
        assert pc.stale_count == 1

    def test_find_clusters_empty_when_all_consolidated(self):
        pc = PatternConsolidation()
        m = _make_memory("m1")
        m.mark_consolidated()
        pc.add_memory(m)
        assert pc.find_clusters() == []

    def test_find_clusters_groups_by_tag_overlap(self):
        pc = PatternConsolidation()
        pc.add_memory(_make_memory("m1", tags=["python", "async"]))
        pc.add_memory(_make_memory("m2", tags=["python", "testing"]))
        pc.add_memory(_make_memory("m3", tags=["rust", "async"]))
        clusters = pc.find_clusters(min_similarity=0.3)
        assert len(clusters) >= 1

    def test_find_clusters_no_overlap(self):
        pc = PatternConsolidation()
        pc.add_memory(_make_memory("m1", tags=["python"]))
        pc.add_memory(_make_memory("m2", tags=["rust"]))
        clusters = pc.find_clusters(min_similarity=0.3)
        assert clusters == []

    def test_tag_similarity_jaccard(self):
        m1 = _make_memory(tags=["a", "b"])
        m2 = _make_memory(tags=["b", "c"])
        sim = PatternConsolidation._tag_similarity(m1, m2)
        assert sim == pytest.approx(1 / 3)

    def test_tag_similarity_zero_when_no_tags(self):
        m1 = _make_memory(tags=[])
        m2 = _make_memory(tags=[])
        assert PatternConsolidation._tag_similarity(m1, m2) == 0.0

    def test_consolidate_runs_full_cycle(self):
        pc = PatternConsolidation()
        pc.add_memory(_make_memory("m1", tags=["python", "async"]))
        pc.add_memory(_make_memory("m2", tags=["python", "testing"]))
        result = pc.consolidate()
        assert result["phase"] == "consolidated"
        assert result["clusters_found"] >= 0

    def test_memories_by_kind(self):
        pc = PatternConsolidation()
        pc.add_memory(_make_memory("m1", kind=MemoryKind.SESSION_NOTE))
        pc.add_memory(_make_memory("m2", kind=MemoryKind.BUG_PATTERN))
        pc.add_memory(_make_memory("m3", kind=MemoryKind.SESSION_NOTE))
        counts = pc.memories_by_kind()
        assert counts["session_note"] == 2
        assert counts["bug_pattern"] == 1

    def test_memories_by_tag(self):
        pc = PatternConsolidation()
        pc.add_memory(_make_memory("m1", tags=["python", "async"]))
        pc.add_memory(_make_memory("m2", tags=["rust", "async"]))
        results = pc.memories_by_tag("async")
        assert len(results) == 2

    def test_summary_shape(self):
        pc = PatternConsolidation()
        pc.add_memory(_make_memory("m1"))
        s = pc.summary()
        assert s["phase"] == "collecting"
        assert s["total_memories"] == 1
        assert "by_kind" in s
