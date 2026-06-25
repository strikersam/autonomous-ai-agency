# Skill: Agentic Portfolio Management

## Purpose
Initiative-level portfolio management (`agents/portfolio.py`) that sits one level
above agentic-agile. Ranks initiatives (epics) with **WSJF** (Weighted Shortest
Job First), allocates finite team capacity, lays work onto a **Now/Next/Later**
roadmap, and rolls sprint delivery progress up from agentic-agile.

## Usage
```python
from agents.portfolio import PortfolioManager
from agents.agile_sprints import AgileManager

pf = PortfolioManager()
pf.add_initiative("Checkout v2", business_value=8, time_criticality=5, risk_reduction=3, job_size=4)
pf.add_initiative("Search relevance", business_value=5, time_criticality=2, risk_reduction=2, job_size=8)

ranked = pf.prioritized()                 # highest WSJF first
alloc = pf.allocate_capacity(capacity=8)  # what fits this increment
roadmap = pf.plan_roadmap(capacity_per_horizon=8)  # Now / Next / Later

# Roll delivery up from the agile sprints that implement each initiative
am = AgileManager()
sprint = am.create_sprint("Sprint 5")
pf.link_sprint(ranked[0].initiative_id, sprint.sprint_id)
progress = pf.rollup_progress(am)
```

## WSJF
`WSJF = Cost of Delay / Job Size`, where
`Cost of Delay = business_value + time_criticality + risk_reduction`.
Higher WSJF is scheduled sooner. Use a relative scale (modified Fibonacci:
1, 2, 3, 5, 8, 13, 20) for each component.

## Key Classes
- **Initiative** — epic with WSJF inputs, status, owner, linked sprints, horizon
- **PortfolioManager** — CRUD, `prioritized()`, `allocate_capacity()`, `plan_roadmap()`, `rollup_progress()`, `metrics()`
- **CapacityAllocation** — committed vs deferred initiatives, utilization
- **PortfolioMetrics** — totals, average WSJF, status counts
- **InitiativeProgress** — per-initiative sprint roll-up

## Skill actions (via SkillBindings)
`add_initiative`, `prioritize`, `allocate_capacity`, `roadmap`, `get_metrics`.

## Testing
```bash
python -m pytest tests/test_portfolio.py -v
```

## Related
- Skill: `agentic-agile` (sprint/story level — the layer below)
- Specialist family: `portfolio` (Portfolio Manager)
- Issue #233: Agentic Agile
