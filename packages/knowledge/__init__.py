"""packages/knowledge/__init__.py — Knowledge Platform.

Long-term memory, short-term memory, semantic search, knowledge
graph, document indexing — all in one unified store.
"""
from packages.knowledge.store import (
    KnowledgeEntry, KnowledgeStore, get_knowledge_store,
)
from packages.knowledge.search import SemanticSearch, get_semantic_search

__all__ = [
    "KnowledgeEntry", "KnowledgeStore", "get_knowledge_store",
    "SemanticSearch", "get_semantic_search",
]
