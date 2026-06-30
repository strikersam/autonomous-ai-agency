---
title: ADR-011: Knowledge Platform
status: accepted
date: 2026-06-29
---

# ADR-011: Knowledge Platform

## Context

V2.0 has no unified knowledge management. Each agent stores its own
context in memory — no long-term memory, no knowledge sharing between
agents, no semantic search.

V2.1 needs a centralized knowledge platform so agents can remember
across sessions, share knowledge, and find relevant information.

## Decision

Create `packages/knowledge/` with:
1. `KnowledgeStore` — unified store for short-term + long-term memory
2. Short-term: in-process (fast, ephemeral, conversation context)
3. Long-term: DB-persisted (durable, cross-session, shared)
4. Every agent shares the same store — no private agent memory
5. Keyword search now, semantic search (embeddings) in next iteration
6. Quality scoring + pruning to keep the store manageable

## Consequences

- Agents can recall knowledge from previous sessions
- Knowledge is shared — no duplication across agents
- Knowledge quality is tracked (access_count, quality_score)
- Low-quality knowledge is pruned automatically
- Works on free-tier infrastructure (no external vector DB needed)
