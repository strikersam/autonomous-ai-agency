---
name: managed-agents-dreams
description: >
  Session memory recording and dream consolidation for managed agents — offline experience replay
---

# Skill: Managed Agents Dreams

## Purpose
Manages session memory recording and dream consolidation for managed agents (`services/managed_agents.py`).

## Usage
```python
from services.managed_agents import ManagedAgentDreams

mgr = ManagedAgentDreams(agent_id="writer-1")
mgr.record("Wrote chapter 3", importance=0.8, tags=["writing"])
mgr.record("Fixed typo", importance=0.3, tags=["editing"])
# ... accumulate 5+ memories ...
dream = mgr.consolidate()
print(dream.summary())
```

## Key Classes
- **SessionMemory** — single memory snapshot with importance (0.0-1.0)
- **Dream** — consolidated narrative from multiple memories
- **ManagedAgentDreams** — recording, consolidation, replay

## Testing
```bash
python -m pytest tests/test_managed_agents.py -v
```

## Related Issues
- Issue #260: Managed Agents Dreams
