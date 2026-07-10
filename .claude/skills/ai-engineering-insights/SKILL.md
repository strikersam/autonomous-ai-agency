---
name: ai-engineering-insights
description: >
  AI-assisted engineering impact analysis — productivity metrics and code quality insights
---

# AI Engineering Insights Skill

**Inspired by:** [DX Q1 AI-Assisted Engineering Impact Report](https://getdx.com/report/ai-assisted-engineering-Q1-impact-report/)

**Purpose:** Track engagement, performance, and tool quality for AI engineering tools — the metrics engineering leaders use to justify spend and pick winning vendors.

## What's Unique About the DX Report

The DX report defines three metric pillars that local-llm-server now mirrors:

1. **Engagement** — DAU/WAU, sessions per user, tool diversity. Adoption is a leading indicator of value.
2. **Performance** — cycle-time delta (AI vs control), defect rate, throughput. Outcome metrics that show whether AI is actually moving the needle.
3. **Tool Quality** — per-tool acceptance rate, latency, token efficiency. Helps choose between vendors objectively.

## Module: `agents/ai_insights.py`

```python
from agents.ai_insights import (
    EngagementMetrics, PerformanceAnalytics, AIToolMetrics,
    UsageEvent, ToolKind, build_report,
)

eng = EngagementMetrics()
eng.record(UsageEvent("alice", "claude_code", ToolKind.AGENT, datetime.now(), accepted=True))
eng.weekly_active_users()  # → 1
```

## Integration Points

- **Telemetry pipeline** — emit `UsageEvent` from agent loops, completion endpoints, chat handlers.
- **Dashboard** — surface `build_report(...)` output in admin GUI.
- **Vendor reviews** — use `AIToolMetrics.tool_ranking()` to compare tools objectively.

## Key Design Choices

- **Plain dataclasses, no external deps** — drops cleanly into any service.
- **`statistics.median`** — resistant to outliers (a single 100-hour PR doesn't skew cycle-time delta).
- **Session detection by gap** — matches DX's definition of "engagement session".

## References

- DX Report: https://getdx.com/report/ai-assisted-engineering-Q1-impact-report/
- Quick-Note Issue: #264
