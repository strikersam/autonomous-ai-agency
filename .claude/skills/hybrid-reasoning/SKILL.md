---
name: hybrid-reasoning
description: >
  Hybrid AI combining deterministic rule engines with LLM reasoning
  for efficient, auditable, and reliable decision-making.
triggers:
  - "hybrid reasoning"
  - "rule engine"
  - "deterministic fallback"
  - "routing decisions"
  - any change to agents/hybrid_reasoning.py
references:
  - agents/hybrid_reasoning.py
  - tests/test_hybrid_reasoning.py
  - Quick-Note Issue #237
---

# Skill: hybrid-reasoning (Hybrid AI)

## Purpose

Dual-path architecture: a DeterministicEngine handles well-defined logic
(reliable, fast, auditable) and an LLMReasoner handles ambiguous/fuzzy cases.
The HybridSystem routes each query to the right path.

## Components

| Class | Role |
|---|---|
| `Rule` | Named condition-action pair with priority |
| `DeterministicEngine` | Rule evaluation engine (priority-ordered) |
| `LLMReasoner` | Pluggable LLM reasoning fallback |
| `HybridSystem` | Orchestrator with decision tracking |

## Quick Start

```python
from agents.hybrid_reasoning import DeterministicEngine, LLMReasoner, HybridSystem, Rule

system = HybridSystem()
system.set_deterministic_rules([
    Rule("greet", lambda i: i.get("text") == "hello", lambda i: "Hi there!", priority=10),
])
result = system.query({"text": "hello"})
print(result.answer)         # "Hi there!"
print(result.mode.value)     # "deterministic"
```

## Testing

```bash
pytest tests/test_hybrid_reasoning.py -v
```

## Branch

`fix/quick-note-237-hybrid-ai`
