---
name: financial-analyst
description: >
  Agentic CFO for autonomous financial analysis of AI infrastructure spend.
  Computes burn rate, runway, gross margin, and ROI-based budget reallocation.
triggers:
  - "analyze costs"
  - "budget optimization"
  - "financial report"
  - "runway analysis"
  - any change to agents/financial_analyst.py
references:
  - agents/financial_analyst.py
  - tests/test_financial_analyst.py
  - Quick-Note Issue #236
---

# Skill: financial-analyst (Agentic CFO)

## Purpose

Autonomous financial analysis for AI infrastructure costs. Ingests cost lines,
computes standard CFO metrics, and emits per-line budget recommendations.

## When to Use

- After adding new cost lines to the infrastructure budget
- Monthly financial review cycles
- Before scaling any AI service that incurs cost
- When runway drops below 6 months (triggers CUT recommendations)

## Components

| Class | Role |
|---|---|
| `CostLine` | Single budget line item (name, monthly_cost, revenue_attributed) |
| `FinancialMetrics` | Core metrics: burn rate, runway, gross margin |
| `BudgetOptimizer` | Greedy ROI-weighted budget reallocation |
| `FinancialAgent` | Recommendation engine: CUT / SCALE / HOLD / INVESTIGATE |

## Quick Start

```python
from agents.financial_analyst import (
    CostLine, FinancialMetrics, FinancialAgent,
)

metrics = FinancialMetrics(
    monthly_revenue=50_000,
    monthly_costs=35_000,
    cash_on_hand=200_000,
    cost_lines=[
        CostLine("gpu", 20_000, revenue_attributed=40_000, category="cogs"),
        CostLine("api", 5_000, revenue_attributed=50_000, category="operations"),
    ],
)

agent = FinancialAgent()
recs = agent.assess(metrics)
for line_name, rec in recs.items():
    print(f"{line_name}: {rec.value}")
```

## Decision Rules

| Condition | Recommendation |
|---|---|
| runway < 6 months | CUT lowest-ROI line |
| gross_margin < 0.40 | INVESTIGATE COGS lines |
| line.roi > 5.0 and category in {sales, R&D} | SCALE |
| line.roi < 0.5 and not strategic | CUT |
| otherwise | HOLD |

## Testing

```bash
pytest tests/test_financial_analyst.py -v
```

18 tests covering CostLine, FinancialMetrics, BudgetOptimizer, and FinancialAgent.

## Branch

`fix/quick-note-236-agentic-cfo`
