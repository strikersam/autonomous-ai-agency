---
name: multi-agent
description: "Multi-agent team coordination — task delegation, shared state, and inter-agent communication"
---

# Skill: Multi-Agent Coordinator

## Purpose
Team coordination system (`agents/team_coordinator.py`) for multi-agent workloads
with capability matching and load-balanced task assignment.

## Usage
```python
from agents.team_coordinator import TeamCoordinator, Agent

tc = TeamCoordinator(team_id="dev-team")
tc.add_agent(Agent(agent_id="coder-1", name="Codex", capabilities=["code"], max_tasks=3))
tc.add_agent(Agent(agent_id="reviewer-1", name="ReviewBot", capabilities=["review"], max_tasks=2))

assigned = tc.assign_task("code")  # picks least-loaded capable agent
```

## Key Classes
- **Agent** — capability set, workload tracking, assign/release
- **TeamCoordinator** — registry, capability matching, load-balanced assignment

## Testing
```bash
python -m pytest tests/test_team_coordinator.py -v
```

## Related Issues
- Issue #234: Grab Multi-Agent Support
