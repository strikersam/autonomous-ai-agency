"""
Obsidian-style knowledge graph integration for agent memory.

Inspired by Obsidian's bidirectional linking and knowledge management.
Implements a graph structure for agent learnings and decisions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Set

log = logging.getLogger("knowledge_graph")


@dataclass
class KnowledgeNode:
    """A node in the knowledge graph"""

    id: str
    title: str
    content: str
    node_type: str  # "decision", "learning", "error", "pattern"
    tags: Set[str] = field(default_factory=set)
    backlinks: Set[str] = field(default_factory=set)
    forward_links: Set[str] = field(default_factory=set)

    def add_link(self, target_id: str):
        """Add forward link to another node"""
        self.forward_links.add(target_id)

    def add_backlink(self, source_id: str):
        """Add backlink from another node"""
        self.backlinks.add(source_id)


class KnowledgeGraph:
    """
    Obsidian-style bidirectional knowledge graph.

    Implements:
    - Bidirectional linking (forward/backlinks)
    - Tagging system
    - Search across nodes
    - Connected component analysis
    """

    def __init__(self):
        self.nodes: dict[str, KnowledgeNode] = {}

    def add_node(
        self,
        node_id: str,
        title: str,
        content: str,
        node_type: str,
        tags: Optional[Set[str]] = None,
    ) -> KnowledgeNode:
        """Add a node to the graph"""
        node = KnowledgeNode(
            id=node_id,
            title=title,
            content=content,
            node_type=node_type,
            tags=tags or set(),
        )
        self.nodes[node_id] = node
        log.debug(f"Added node: {node_id}")
        return node

    def link_nodes(self, source_id: str, target_id: str):
        """Create bidirectional link between nodes"""
        if source_id in self.nodes and target_id in self.nodes:
            self.nodes[source_id].add_link(target_id)
            self.nodes[target_id].add_backlink(source_id)
            log.debug(f"Linked {source_id} → {target_id}")

    def search_by_tag(self, tag: str) -> list[KnowledgeNode]:
        """Find all nodes with a tag"""
        return [n for n in self.nodes.values() if tag in n.tags]

    def search_by_type(self, node_type: str) -> list[KnowledgeNode]:
        """Find all nodes of a type"""
        return [n for n in self.nodes.values() if n.node_type == node_type]

    def find_related(self, node_id: str, depth: int = 2) -> list[KnowledgeNode]:
        """Find related nodes up to depth"""
        if node_id not in self.nodes:
            return []

        visited = set()
        to_visit = [(node_id, 0)]
        related = []

        while to_visit:
            current_id, current_depth = to_visit.pop(0)
            if current_id in visited or current_depth > depth:
                continue

            visited.add(current_id)
            node = self.nodes[current_id]

            if current_depth > 0:  # Don't include the query node itself
                related.append(node)

            if current_depth < depth:
                for link_id in node.forward_links | node.backlinks:
                    if link_id not in visited:
                        to_visit.append((link_id, current_depth + 1))

        return related

    def get_stats(self) -> dict:
        """Get graph statistics"""
        if not self.nodes:
            return {"nodes": 0, "edges": 0}

        edge_count = sum(len(n.forward_links) for n in self.nodes.values())
        type_counts = {}
        for node in self.nodes.values():
            type_counts[node.node_type] = type_counts.get(node.node_type, 0) + 1

        return {
            "total_nodes": len(self.nodes),
            "total_edges": edge_count,
            "node_types": type_counts,
        }
