# Skill: Obsidian Knowledge Graph

## Purpose
Implements an Obsidian-compatible knowledge graph (`agents/knowledge_graph.py`) with typed edges,
BFS shortest-path, connected components, and import/export.

## Usage
```python
from agents.knowledge_graph import KnowledgeGraph, KnowledgeNode, EdgeType

g = KnowledgeGraph()
g.add_node(KnowledgeNode(node_id="n1", label="Python", tags=["language"]))
g.add_node(KnowledgeNode(node_id="n2", label="FastAPI", tags=["framework"]))
g.add_edge("n1", "n2", EdgeType.SUPPORTS)

path = g.shortest_path("n1", "n2")  # ["n1", "n2"]
```

## Key Classes
- **KnowledgeNode** — labeled node with content, tags, confidence
- **KnowledgeGraph** — directed graph, typed edges, BFS, components, export
- **EdgeType** — REFERENCES, DEPENDS_ON, RELATES_TO, PARENT_OF, CONTRADICTS, SUPPORTS

## Testing
```bash
python -m pytest tests/test_knowledge_graph.py -v
```

## Related Issues
- Issue #232: Obsidian Knowledge Graph
