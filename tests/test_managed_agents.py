"""Tests for services/managed_agents.py — Managed Agents Dreams.

Uses importlib to load the module directly, bypassing agent deps.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    path = Path(__file__).parent.parent / "services" / "managed_agents.py"
    spec = importlib.util.spec_from_file_location("managed_agents", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["managed_agents"] = mod
    spec.loader.exec_module(mod)
    return mod


mod = _load_module()
SessionMemory = mod.SessionMemory
Dream = mod.Dream
ManagedAgentDreams = mod.ManagedAgentDreams


class TestSessionMemory:
    """Tests for SessionMemory dataclass."""

    def test_create(self):
        sm = SessionMemory(
            session_id="s1",
            agent_id="a1",
            content="hello",
            importance=0.5,
        )
        assert sm.session_id == "s1"
        assert sm.agent_id == "a1"
        assert sm.content == "hello"
        assert sm.importance == 0.5

    def test_default_importance(self):
        sm = SessionMemory(session_id="s1", agent_id="a1", content="hi")
        assert sm.importance == 0.5

    def test_default_tags(self):
        sm = SessionMemory(session_id="s1", agent_id="a1", content="hi")
        assert sm.tags == []

    def test_invalid_importance_raises(self):
        try:
            SessionMemory(session_id="s1", agent_id="a1", content="hi", importance=1.5)
            assert False, "Expected ValueError"
        except ValueError:
            pass

    def test_invalid_importance_negative(self):
        try:
            SessionMemory(session_id="s1", agent_id="a1", content="hi", importance=-0.1)
            assert False, "Expected ValueError"
        except ValueError:
            pass


class TestDream:
    """Tests for Dream dataclass."""

    def test_create(self):
        d = Dream(
            dream_id="d1",
            source_session_ids=["s1", "s2"],
            narrative="combined narrative",
            insights=["insight1"],
            consolidated_from=5,
        )
        assert d.dream_id == "d1"
        assert len(d.source_session_ids) == 2
        assert d.consolidated_from == 5

    def test_summary(self):
        d = Dream(
            dream_id="d1",
            source_session_ids=["s1"],
            narrative="some narrative text here",
            insights=["a", "b"],
        )
        summary = d.summary()
        assert "d1" in summary
        assert "narrative" in summary.lower()


class TestManagedAgentDreams:
    """Tests for ManagedAgentDreams."""

    def test_record_memory(self):
        mgr = ManagedAgentDreams(agent_id="agent-1")
        mem = mgr.record("task completed")
        assert mem.agent_id == "agent-1"
        assert mem.content == "task completed"
        assert mgr.memory_count == 1

    def test_record_with_tags(self):
        mgr = ManagedAgentDreams(agent_id="agent-1")
        mem = mgr.record("error occurred", tags=["error", "critical"], importance=0.9)
        assert "error" in mem.tags
        assert mem.importance == 0.9

    def test_consolidate_below_threshold(self):
        mgr = ManagedAgentDreams(agent_id="agent-1")
        mgr.record("m1")
        mgr.record("m2")
        dream = mgr.consolidate()
        assert dream is None  # default threshold is 5

    def test_consolidate_meets_threshold(self):
        mgr = ManagedAgentDreams(agent_id="agent-1")
        mgr._consolidation_threshold = 3
        mgr.record("m1")
        mgr.record("m2")
        mgr.record("m3")
        dream = mgr.consolidate()
        assert dream is not None
        assert dream.consolidated_from == 3
        assert mgr.dream_count == 1

    def test_consolidate_min_importance(self):
        mgr = ManagedAgentDreams(agent_id="agent-1")
        mgr._consolidation_threshold = 3
        mgr.record("low", importance=0.1)
        mgr.record("low2", importance=0.2)
        mgr.record("high", importance=0.9)
        dream = mgr.consolidate(min_importance=0.8)
        assert dream is None  # only 1 above threshold

    def test_replay_dream(self):
        mgr = ManagedAgentDreams(agent_id="agent-1")
        mgr._consolidation_threshold = 2
        mgr.record("first message")
        mgr.record("second message")
        dream = mgr.consolidate()
        result = mgr.replay(dream.dream_id)
        assert result is not None
        assert "first message" in result

    def test_replay_nonexistent(self):
        mgr = ManagedAgentDreams(agent_id="agent-1")
        assert mgr.replay("nope") is None

    def test_recent_dreams_order(self):
        mgr = ManagedAgentDreams(agent_id="agent-1")
        mgr._consolidation_threshold = 2
        mgr.record("batch1 a"); mgr.record("batch1 b")
        mgr.consolidate()
        mgr.record("batch2 a"); mgr.record("batch2 b")
        mgr.consolidate()
        recent = mgr.recent_dreams(limit=2)
        assert len(recent) == 2

    def test_memory_count(self):
        mgr = ManagedAgentDreams(agent_id="agent-1")
        assert mgr.memory_count == 0
        mgr.record("m1")
        mgr.record("m2")
        assert mgr.memory_count == 2

    def test_dream_count(self):
        mgr = ManagedAgentDreams(agent_id="agent-1")
        mgr._consolidation_threshold = 2
        mgr.record("m1"); mgr.record("m2")
        mgr.consolidate()
        assert mgr.dream_count == 1

    def test_threshold_setter(self):
        mgr = ManagedAgentDreams(agent_id="agent-1")
        mgr.consolidation_threshold = 10
        assert mgr.consolidation_threshold == 10

    def test_threshold_setter_invalid(self):
        mgr = ManagedAgentDreams(agent_id="agent-1")
        try:
            mgr.consolidation_threshold = 0
            assert False, "Expected ValueError"
        except ValueError:
            pass
