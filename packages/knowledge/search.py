"""packages/knowledge/search.py — Semantic search for the knowledge platform.

Provides keyword-based and simple semantic search over the knowledge store.
Uses TF-IDF-like scoring for relevance ranking without requiring external
embeddings or vector databases — works on free-tier infrastructure.
"""
from __future__ import annotations

import logging
import math
from collections import Counter
from typing import Any

from packages.knowledge.store import KnowledgeEntry, get_knowledge_store

log = logging.getLogger("knowledge.search")


class SemanticSearch:
    """Semantic search over the knowledge store.

    Uses term frequency scoring (simplified TF-IDF) for relevance ranking.
    No external embeddings needed — works on free-tier infrastructure.

    Future enhancement: add embedding-based search when a free embedding
    model is available (e.g. via NVIDIA NIM or Ollama).
    """

    def __init__(self) -> None:
        self._store = get_knowledge_store()
        self._document_freq: Counter[str] = Counter()
        self._total_docs: int = 0

    async def search(
        self,
        query: str,
        limit: int = 5,
        min_score: float = 0.01,
    ) -> list[tuple[float, KnowledgeEntry]]:
        """Search the knowledge store for relevant entries.

        Args:
            query: Natural language search query
            limit: Maximum results
            min_score: Minimum relevance score (0.0-1.0)

        Returns:
            List of (score, entry) tuples sorted by relevance
        """
        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        # Get all entries from the store
        all_entries = list(self._store._short_term.values()) + list(self._store._long_term_cache.values())
        if not all_entries:
            return []

        # Update document frequencies for IDF calculation
        self._total_docs = len(all_entries)
        self._document_freq = Counter()
        for entry in all_entries:
            terms = set(self._tokenize(entry.content))
            for term in terms:
                self._document_freq[term] += 1

        # Score each entry
        results: list[tuple[float, KnowledgeEntry]] = []
        for entry in all_entries:
            score = self._score(query_terms, entry)
            if score >= min_score:
                results.append((score, entry))

        # Sort by score (descending), then by quality_score as tiebreaker
        results.sort(key=lambda x: (x[0] * x[1].quality_score), reverse=True)

        # Update access counts
        for _, entry in results[:limit]:
            entry.access_count += 1

        return results[:limit]

    async def find_similar(
        self,
        content: str,
        limit: int = 5,
    ) -> list[tuple[float, KnowledgeEntry]]:
        """Find knowledge entries similar to the given content.

        Args:
            content: Text to find similar knowledge for
            limit: Maximum results

        Returns:
            List of (similarity_score, entry) tuples
        """
        return await self.search(content, limit=limit)

    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenization: lowercase, split on non-alphanumeric."""
        import re
        tokens = re.findall(r'\b\w+\b', text.lower())
        # Remove very common stop words
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                      "have", "has", "had", "do", "does", "did", "will", "would",
                      "could", "should", "may", "might", "must", "can", "to", "of",
                      "in", "for", "on", "with", "at", "by", "from", "as", "into",
                      "through", "during", "before", "after", "above", "below",
                      "and", "or", "but", "if", "then", "else", "when", "where",
                      "why", "how", "all", "each", "every", "both", "few", "more",
                      "most", "other", "some", "such", "no", "not", "only", "own",
                      "same", "so", "than", "too", "very", "just", "also"}
        return [t for t in tokens if t not in stop_words and len(t) > 2]

    def _score(self, query_terms: list[str], entry: KnowledgeEntry) -> float:
        """Calculate relevance score using TF-IDF-like scoring.

        Args:
            query_terms: Tokenized search query
            entry: Knowledge entry to score

        Returns:
            Relevance score (0.0 - 1.0+)
        """
        entry_terms = self._tokenize(entry.content)
        tag_terms = self._tokenize(" ".join(entry.tags))
        all_entry_terms = entry_terms + tag_terms

        if not all_entry_terms:
            return 0.0

        entry_term_freq = Counter(all_entry_terms)
        entry_length = len(all_entry_terms)

        score = 0.0
        for term in query_terms:
            tf = entry_term_freq.get(term, 0)
            if tf == 0:
                continue
            # IDF: how rare is this term across all documents?
            df = self._document_freq.get(term, 0)
            if df == 0:
                idf = 1.0
            else:
                idf = math.log(1 + self._total_docs / df)
            # TF-IDF score
            score += (tf / entry_length) * idf

        # Normalize by query length
        if query_terms:
            score /= len(query_terms)

        return score


# Singleton
_search: SemanticSearch | None = None


def get_semantic_search() -> SemanticSearch:
    """Return the global semantic search singleton."""
    global _search
    if _search is None:
        _search = SemanticSearch()
    return _search
