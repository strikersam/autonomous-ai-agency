"""Tests for agents/knowledge_graph.py — Obsidian Knowledge Graph.

Uses importlib to load the module directly, bypassing agents/__init__.py deps.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    path = Path(__file__).parent.parent / "agents" / "knowledge_graph.py"
    spec = importlib.util.spec_from_file_location("knowledge_graph", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["knowledge_graph"] = mod
    spec.loader.exec_module(mod)
    return mod


mod = _load_module()
KnowledgeNode = mod.KnowledgeNode
KnowledgeGraph = mod.KnowledgeGraph
EdgeType = mod.EdgeType


class TestKnowledgeNode:
    """Tests for KnowledgeNode dataclass."""

    def test_create(self):
        node = KnowledgeNode(node_id="n1", label="Concept", content="desc")
        assert node.node_id == "n1"
        assert node.label == "Concept"
        assert node.content == "desc"

    def test_default_tags(self):
        node = KnowledgeNode(node_id="n1", label="x")
        assert node.tags == []

    def test_default_confidence(self):
        node = KnowledgeNode(node_id="n1", label="x")
        assert node.confidence == 1.0

    def test_with_tags(self):
        node = KnowledgeNode(node_id="n1", label="x", tags=["a", "b"])
        assert "a" in node.tags


class TestKnowledgeGraph:
    """Tests for KnowledgeGraph."""

    def test_add_node(self):
        g = KnowledgeGraph()
        g.add_node(KnowledgeNode(node_id="n1", label="Node 1"))
        assert g.node_count == 1
        assert g.get_node("n1").label == "Node 1"

    def test_add_duplicate_raises(self):
        g = KnowledgeGraph()
        g.add_node(KnowledgeNode(node_id="n1", label="x"))
        try:
            g.add_node(KnowledgeNode(node_id="n1", label="y"))
            assert False, "Expected ValueError"
        except ValueError:
            pass

    def test_remove_node(self):
        g = KnowledgeGraph()
        g.add_node(KnowledgeNode(node_id="n1", label="x"))
        g.remove_node("n1")
        assert g.node_count == 0
        assert g.get_node("n1") is None

    def test_remove_node_cleans_edges(self):
        g = KnowledgeGraph()
        g.add_node(KnowledgeNode(node_id="a", label="A"))
        g.add_node(KnowledgeNode(node_id="b", label="B"))
        g.add_edge("a", "b", EdgeType.REFERENCES)
        g.remove_node("a")
        assert g.edge_count == 0

    def test_add_edge(self):
        g = KnowledgeGraph()
        g.add_node(KnowledgeNode(node_id="a", label="A"))
        g.add_node(KnowledgeNode(node_id="b", label="B"))
        g.add_edge("a", "b", EdgeType.DEPENDS_ON)
        assert g.edge_count == 1
        neighbors = g.get_neighbors("a")
        assert len(neighbors) == 1
        assert neighbors[0][0] == "b"
        assert neighbors[0][1] == EdgeType.DEPENDS_ON

    def test_reverse_neighbors(self):
        g = KnowledgeGraph()
        g.add_node(KnowledgeNode(node_id="a", label="A"))
        g.add_node(KnowledgeNode(node_id="b", label="B"))
        g.add_edge("a", "b", EdgeType.REFERENCES)
        rev = g.get_reverse_neighbors("b")
        assert len(rev) == 1
        assert rev[0][0] == "a"

    def test_shortest_path_direct(self):
        g = KnowledgeGraph()
        g.add_node(KnowledgeNode(node_id="a", label="A"))
        g.add_node(KnowledgeNode(node_id="b", label="B"))
        g.add_edge("a", "b", EdgeType.RELATES_TO)
        path = g.shortest_path("a", "b")
        assert path == ["a", "b"]

    def test_shortest_path_nonexistent(self):
        g = KnowledgeGraph()
        g.add_node(KnowledgeNode(node_id="a", label="A"))
        assert g.shortest_path("a", "z") is None

    def test_shortest_path_self(self):
        g = KnowledgeGraph()
        g.add_node(KnowledgeNode(node_id="a", label="A"))
        assert g.shortest_path("a", "a") == ["a"]

    def test_connected_components(self):
        g = KnowledgeGraph()
        g.add_node(KnowledgeNode(node_id="a", label="A"))
        g.add_node(KnowledgeNode(node_id="b", label="B"))
        g.add_node(KnowledgeNode(node_id="c", label="C"))
        g.add_edge("a", "b", EdgeType.REFERENCES)
        comps = g.connected_components()
        assert len(comps) == 2  # a-b and c

    def test_search_by_tag(self):
        g = KnowledgeGraph()
        g.add_node(KnowledgeNode(node_id="a", label="A", tags=["python"]))
        g.add_node(KnowledgeNode(node_id="b", label="B", tags=["rust"]))
        results = g.search_by_tag("python")
        assert len(results) == 1
        assert results[0].label == "A"

    def test_export_import_edges(self):
        g = KnowledgeGraph()
        g.add_node(KnowledgeNode(node_id="a", label="A"))
        g.add_node(KnowledgeNode(node_id="b", label="B"))
        g.add_edge("a", "b", EdgeType.SUPPORTS)
        exported = g.export_edges()
        assert len(exported) == 1

        g2 = KnowledgeGraph()
        g2.add_node(KnowledgeNode(node_id="a", label="A"))
        g2.add_node(KnowledgeNode(node_id="b", label="B"))
        g2.import_edges(exported)
        assert g2.edge_count == 1

    def test_edge_count(self):
        g = KnowledgeGraph()
        g.add_node(KnowledgeNode(node_id="a", label="A"))
        g.add_node(KnowledgeNode(node_id="b", label="B"))
        assert g.edge_count == 0
        g.add_edge("a", "b", EdgeType.REFERENCES)
        assert g.edge_count == 1
