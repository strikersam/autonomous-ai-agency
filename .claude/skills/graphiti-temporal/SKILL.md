---
name: graphiti-temporal
description: >
  Temporal context graph for agent memory — track entity relationships and state changes over time
---

# Graphiti Temporal Context Skill

**Inspired by:** [Graphiti](https://github.com/getzep/graphiti) — temporal context graphs for AI agents

**Purpose:** Integrate Graphiti's temporal knowledge graph patterns into local-llm-server's agent memory and context management.

## What's Unique About Graphiti

Graphiti builds **temporal context graphs** (evolving knowledge graphs that track how facts change over time):
- **Temporal awareness** — knows what's true now vs what was true before
- **Provenance tracking** — maintains links to source data
- **Hybrid retrieval** — semantic + keyword + graph traversal
- **Incremental updates** — efficiently adds new information without full recomputation

Unlike traditional RAG (flat chunks), Graphiti gives agents **rich, structured context** that evolves with each interaction.

## Integration Opportunities

### 1. Agent Memory as Temporal Graph
Track agent decisions and outcomes:

```python
class AgentContextGraph:
    def add_interaction(self, timestamp, agent_id, action):
        """Record agent action with temporal metadata"""
    
    def query_at_time(self, entity, timestamp):
        """Query what was true at specific time"""
```

### 2. Multi-Agent Coordination
Track which agents worked on which tasks with temporal awareness.

### 3. Knowledge Queries
Query across relationships with SQL:

```sql
SELECT entity, fact, timestamp FROM context_graph
WHERE entity LIKE 'test_%'
  AND fact LIKE 'status:failed'
ORDER BY timestamp DESC;
```

## Database Schema

```sql
CREATE TABLE temporal_context (
    id TEXT PRIMARY KEY,
    entity TEXT NOT NULL,
    fact TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    provenance TEXT,
    agent_id TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_entity_time ON temporal_context(entity, timestamp DESC);
```

## Files to Create

- `services/temporal_context.py` — temporal graph implementation
- `db/temporal_store.py` — SQLite storage
- `tests/test_temporal_context.py` — tests

## References

- Graphiti: https://github.com/getzep/graphiti
- Quick-Note Issue: #263
