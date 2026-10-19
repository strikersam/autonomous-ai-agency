---
name: user-research
description: >
  User research skill — plan interviews, synthesize findings, and generate personas
---

# Skill: user-research

> **Module:** `agent/user_research_skill.py`
> **Agent tools registered:** `user_research_plan`, `user_research_qual`, `user_research_quant`, `user_research_synthesize`
> **Capability tag:** `user_research` (sub-tags: `plan`, `qualitative`, `quantitative`, `synthesis`)
> **Maturity:** stable

## Purpose

Structured user-research workflows for the agent platform. Implements the
four core capabilities adapted from the
[cookiy-ai/user-research-skill](https://github.com/cookiy-ai/user-research-skill)
reference architecture:

| Capability | Tool name | What it does |
|------------|-----------|--------------|
| **Plan** | `user_research_plan` | Produce a structured research plan (objectives, hypotheses, methods, sample size, timeline) from a research question. |
| **Qual** | `user_research_qual` | Extract themes, pain points, and desires from interview transcripts or open-ended survey responses. |
| **Quant** | `user_research_quant` | Compute descriptive statistics (mean, median, σ, distribution, segment cuts) for a numeric series. |
| **Synthesize** | `user_research_synthesize` | Combine qual + quant into a decision-ready research brief with executive summary, findings, and recommendations. |

## When to Use

- **Plan**: Before kicking off a new research initiative — defines scope, objectives, methods, and sample size.
- **Qual**: After collecting 3+ interview transcripts or open-ended responses — finds themes and pain points.
- **Quant**: After collecting numeric survey data or experiment metrics — produces the descriptive stats and segment cuts.
- **Synthesize**: After both qual and quant are available — produces the executive brief a stakeholder will read.

## Architecture

The skill is implemented as a **pure-function library with a thin tool-wrapping
layer**:

- All four capabilities are pure functions (`plan_research`, `analyze_qualitative`,
  `analyze_quantitative`, `synthesize_research`) that take and return
  Pydantic v2 models.
- The functions are then registered with the agent `ToolRegistry` via the
  `@registry.agent_tool` decorator, so the agent loop can invoke them
  like any other tool.
- **No LLM calls inside the skill.** The LLM is the executor that *uses* the
  tool; the tool provides the structural framework (Pydantic contracts,
  sample-size math, theme extraction heuristics, descriptive stats). This
  keeps the skill fast, testable, and free of hidden costs.

## Pydantic Models (extra="forbid")

All inputs and outputs use Pydantic v2 with `extra="forbid"` so the executor
cannot smuggle unknown fields past validation:

- `ResearchPlan` — output of Plan
- `ResearchObjective`, `ResearchHypothesis`, `ResearchMethod` — sub-models
- `QualAnalysis`, `QualTheme`, `QualQuote` — output of Qual
- `QuantAnalysis`, `QuantSegment` — output of Quant
- `ResearchBrief` — output of Synthesize

## Usage

### As a Python library

```python
from agent.user_research_skill import (
    plan_research, analyze_qualitative,
    analyze_quantitative, synthesize_research,
)

# 1. Plan
plan = plan_research(
    title="Why do users churn after onboarding?",
    primary_question="What causes week-1 churn?",
    audience="Product team",
    objectives=[{"statement": "Identify the top 3 friction points"}],
    methods=[{"method": "interview", "target_participants": 8}],
)
print(plan.target_sample_size)  # computed from method target + stats

# 2. Qual
qual = analyze_qualitative(
    source="8 customer interviews",
    transcripts=[
        "Login is broken and slow, hate it.",
        "Login is broken, otherwise fine.",
        "Love the new dashboard, but login is broken.",
    ],
)
for theme in qual.pain_points:
    print(theme.name, theme.frequency)

# 3. Quant
quant = analyze_quantitative(
    source="NPS survey Q4",
    values=[9, 9, 8, 10, 9, 8, 9, 10, 7, 9],
    metric_name="NPS",
    metric_type="rating",
)
print(quant.mean, quant.median, quant.stdev)

# 4. Synthesize
brief = synthesize_research(title="Q4 NPS + Interview Synthesis",
                             quant=quant, qual=qual)
print(brief.executive_summary)
print(brief.recommendations)
```

### As an agent tool

After `auto_register()` is called (or after `agent/capability_registry.py`
discovers the module), the agent loop can invoke:

```python
# In an agent prompt, the model can call:
{
  "tool": "user_research_plan",
  "args": {
    "title": "Onboarding friction study",
    "primary_question": "What blocks first-week activation?",
    "audience": "Product",
    "objectives": [{"statement": "Identify top 3 blockers"}],
    "methods": [{"method": "interview", "target_participants": 6}]
  }
}
```

…and receive a validated `ResearchPlan` back.

## Sample-Size Math

The `plan_research` function computes the target sample size from the
larger of:
1. The sum of `target_participants` across all methods.
2. The standard normal-approximation sample size for a proportion, with
   finite-population correction when `population_size` is supplied.

Formula: `n0 = z² · p(1-p) / e²`, then `n = n0 / (1 + (n0-1)/N)`.
Default `z=1.96` (95% confidence), `e=0.05`, `p=0.5`.

## Sentiment + Theme Heuristics

The `analyze_qualitative` function uses a small rule-based sentiment
classifier (positive / neutral / negative) and a keyword-based theme
extractor. Themes are filtered by `min_theme_frequency` (default 2) to
avoid single-mention noise. **Real production sentiment should use an
LLM call** — these heuristics are deliberately minimal so the skill
scaffolding is fast and testable.

## Tests

`tests/test_user_research_skill.py` covers:
- Plan: minimal plan, sample-size math, ID uniqueness, scope, extras rejection
- Qual: theme extraction, participant ID handling, sentiment, min-frequency filter
- Quant: basic stats, distributions, segments, edge cases
- Synthesize: quant-only, qual-only, combined, segment gap detection
- Tool registration: 4 tools, capability discovery, idempotency, OpenAI export
- End-to-end: plan → qual → synthesize

Run with:
```bash
pytest -x tests/test_user_research_skill.py -v
```

## Auto-Registration

The skill auto-registers with the module-level `ToolRegistry` singleton
on first import of `agent.user_research_skill`. To force registration
in a custom registry, call `register_user_research_tools(registry)`
explicitly.

## Files

| File | Purpose |
|------|---------|
| `agent/user_research_skill.py` | Pydantic models + 4 capability functions + tool registration |
| `tests/test_user_research_skill.py` | 35+ tests covering all capabilities and edge cases |
| `.claude/skills/user-research/SKILL.md` | This document |

## See Also

- `agent/capability_registry.py` — the dynamic tool registry
- `.claude/skills/research/SKILL.md` — general-purpose research skill (broader scope, this skill is user-research-specific)
- https://github.com/cookiy-ai/user-research-skill — the reference architecture this is adapted from
