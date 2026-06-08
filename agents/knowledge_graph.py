"""Obsidian Knowledge Graph — KnowledgeNode and KnowledgeGraph with typed edges.

Issue: #232
Branch: fix/quick-note-232-obsidian
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple


class EdgeType(Enum):
    """Types of relationships between knowledge nodes."""

    REFERENCES = "references"
    DEPENDS_ON = "depends_on"
    RELATES_TO = "relates_to"
    PARENT_OF = "parent_of"
    CONTRADICTS = "contradicts"
    SUPPORTS = "supports"


@dataclass
class KnowledgeNode:
    """A node in the knowledge graph representing a concept or fact."""

    node_id: str
    label: str
    content: str = ""
    tags: List[str] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class KnowledgeGraph:
    """A directed graph of KnowledgeNodes with typed edges."""

    _nodes: Dict[str, KnowledgeNode] = field(default_factory=dict)
    _edges: Dict[str, Dict[str, EdgeType]] = field(default_factory=dict)
    _reverse_edges: Dict[str, Dict[str, EdgeType]] = field(default_factory=dict)

    def add_node(self, node: KnowledgeNode) -> None:
        """Add a node to the graph."""
        if node.node_id in self._nodes:
            raise ValueError(f"Node '{node.node_id}' already exists.")
        self._nodes[node.node_id] = node
        self._edges.setdefault(node.node_id, {})
        self._reverse_edges.setdefault(node.node_id, {})

    def remove_node(self, node_id: str) -> None:
        """Remove a node and all its edges from the graph."""
        if node_id not in self._nodes:
            raise KeyError(f"Node '{node_id}' not found.")
        for neighbor in list(self._edges.get(node_id, {})):
            self._reverse_edges[neighbor].pop(node_id, None)
        for neighbor in list(self._reverse_edges.get(node_id, {})):
            self._edges[neighbor].pop(node_id, None)
        self._edges.pop(node_id, None)
        self._reverse_edges.pop(node_id, None)
        self._nodes.pop(node_id)

    def add_edge(self, source: str, target: str, edge_type: EdgeType) -> None:
        """Add a directed edge between two nodes."""
        if source not in self._nodes:
            raise KeyError(f"Source node '{source}' not found.")
        if target not in self._nodes:
            raise KeyError(f"Target node '{target}' not found.")
        self._edges[source][target] = edge_type
        self._reverse_edges[target][source] = edge_type

    def remove_edge(self, source: str, target: str) -> None:
        """Remove a directed edge."""
        self._edges[source].pop(target, None)
        self._reverse_edges[target].pop(source, None)

    def get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        """Get a node by ID."""
        return self._nodes.get(node_id)

    def get_neighbors(self, node_id: str) -> List[Tuple[str, EdgeType]]:
        """Get outgoing edges from a node as (target_id, edge_type) pairs."""
        if node_id not in self._nodes:
            raise KeyError(f"Node '{node_id}' not found.")
        return list(self._edges.get(node_id, {}).items())

    def get_reverse_neighbors(self, node_id: str) -> List[Tuple[str, EdgeType]]:
        """Get incoming edges to a node as (source_id, edge_type) pairs."""
        if node_id not in self._nodes:
            raise KeyError(f"Node '{node_id}' not found.")
        return list(self._reverse_edges.get(node_id, {}).items())

    def shortest_path(self, start: str, end: str) -> Optional[List[str]]:
        """Find the shortest path between two nodes using BFS.

        Returns a list of node IDs in order, or None if no path exists.
        """
        if start not in self._nodes or end not in self._nodes:
            return None
        if start == end:
            return [start]
        queue: deque[List[str]] = deque([[start]])
        visited: Set[str] = {start}
        while queue:
            path = queue.popleft()
            current = path[-1]
            for neighbor in self._edges.get(current, {}):
                if neighbor == end:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])
        return None

    def connected_components(self) -> List[Set[str]]:
        """Find all connected components (treating edges as undirected)."""
        visited: Set[str] = set()
        components: List[Set[str]] = []

        for node_id in self._nodes:
            if node_id not in visited:
                component: Set[str] = set()
                stack = [node_id]
                while stack:
                    current = stack.pop()
                    if current not in visited:
                        visited.add(current)
                        component.add(current)
                        for neighbor in self._edges.get(current, {}):
                            if neighbor not in visited:
                                stack.append(neighbor)
                        for neighbor in self._reverse_edges.get(current, {}):
                            if neighbor not in visited:
                                stack.append(neighbor)
                components.append(component)
        return components

    def search_by_tag(self, tag: str) -> List[KnowledgeNode]:
        """Find all nodes with a given tag."""
        return [n for n in self._nodes.values() if tag in n.tags]

    def export_edges(self) -> List[Tuple[str, str, str]]:
        """Export all edges as (source, target, edge_type) tuples."""
        result: List[Tuple[str, str, str]] = []
        for src, targets in self._edges.items():
            for tgt, etype in targets.items():
                result.append((src, tgt, etype.value))
        return result

    def import_edges(self, edges: List[Tuple[str, str, str]]) -> None:
        """Import edges from (source, target, edge_type) tuples."""
        for src, tgt, etype_str in edges:
            etype = EdgeType(etype_str)
            self.add_edge(src, tgt, etype)

    @property
    def node_count(self) -> int:
        """Number of nodes in the graph."""
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        """Number of edges in the graph."""
        return sum(len(targets) for targets in self._edges.values())
