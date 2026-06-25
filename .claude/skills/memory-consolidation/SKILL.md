---
name: memory-consolidation
description: >
  Dream Memory Consolidation for clustering session artifacts into
  structured, queryable memories with tag-based similarity.
triggers:
  - "memory consolidation"
  - "consolidate memories"
  - "session artifact clustering"
  - "pattern replay"
  - any change to agents/memory_consolidation.py
references:
  - agents/memory_consolidation.py
  - tests/test_memory_consolidation.py
  - Quick-Note Issue #259
---

# Skill: memory-consolidation (Dream Memory)

## Purpose

Inspired by hippocampal replay: long-running AI systems accumulate session
artifacts, and periodically consolidating them into structured memories
improves future recall and context reuse.

## Consolidation Lifecycle

COLLECTING → DREAMING → CONSOLIDATED

## Memory Kinds

- `SESSION_NOTE` — General session observations
- `LEARNED_RULE` — Patterns/corrections to persist
- `BUG_PATTERN` — Recurring bug signatures
- `ARCHITECTURAL_DECISION` — ADR-like records
- `CODE_SNIPPET` — Reusable code fragments

## Quick Start

```python
from agents.memory_consolidation import DreamMemory, MemoryKind, PatternConsolidation

pc = PatternConsolidation()
pc.add_memory(DreamMemory("m1", MemoryKind.BUG_PATTERN, "null deref in auth", tags=["bug", "auth"]))
pc.add_memory(DreamMemory("m2", MemoryKind.BUG_PATTERN, "timeout on login", tags=["bug", "auth"]))
result = pc.consolidate()
print(result)  # clusters found, memories consolidated
```

## Testing

```bash
pytest tests/test_memory_consolidation.py -v
```

## Branch

`fix/quick-note-259-memory-dreams`
