---
name: research-coordinator
description: >
  Multi-agent research coordination — deduplicate findings, assign work, and synthesize results
---

# Multi-Agent Research Coordinator Skill

**Inspired by:** [Build a Multi-Agent Research Assistant](https://machinelearningmastery.com/build-multi-agent-research-assistant/)

**Purpose:** Decompose research questions into parallel sub-tasks, dispatch them to specialized agents, and synthesize results.

## What's Unique

A coordinator builds a **dependency DAG** of research tasks (web search, doc reading, summarization, critique, synthesis) and runs them in topological order. Each role runs against a least-loaded specialist agent.

## Module: `agents/research_coordinator.py`

```python
from agents.research_coordinator import (
    ResearchOrchestrator, ResearchAgent, AgentRole,
)

def web_handler(task, ctx): return "found X, Y, Z"

orch = ResearchOrchestrator()
orch.register_agent(ResearchAgent("web1", AgentRole.WEB_SEARCHER, web_handler))
# ... register agents for all roles ...
orch.plan("How does feature X work?")
orch.run()
print(orch.synthesize())
```

## Default Plan Shape

```
web_search ──┐
             ├─→ summarize ─→ critique ─→ synthesize
doc_read  ───┘                  │
                                └────────────┘
```

## Roles

- `WEB_SEARCHER` — external knowledge
- `DOC_READER` — internal docs / repo
- `SUMMARIZER` — distills findings
- `CRITIC` — gap analysis
- `SYNTHESIZER` — final answer

## Quick-Note Issue: #238
