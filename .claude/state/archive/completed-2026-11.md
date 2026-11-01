# Completed Task Archive — November 2026

> Rows moved out of `.claude/state/active-tasks.md` when they closed (CLAUDE.md
> rule 44), so the SessionStart hook does not carry finished work.

| # | Task / Bug | Status | PR / Branch | Notes | Updated |
|---|------------|--------|-------------|-------|---------|
| 54 | **[daily-automation 2026-10-31]** Retire `nvidia/nemotron-3-super-120b-a12b` (HTTP 404 issue #1813) + promote ultra + add Gemini 4 Carbon | `DONE` (merged #1863) | `claude/intelligent-gates-ibfi0w` | All 14 file references to the retired model replaced with nemotron-3-ultra-550b-a55b; gemini-4-carbon added to config/llm/models.yaml; both changelogs updated; merged to master. | 2026-11-01 |
| 107 | **[daily-automation 2026-11-01]** Fix `claude-sonnet-5-5` cache-read fraction (was 10 %, should be 5 %) | `DONE` (merged #1871; follow-up #1877) | [#1871](https://github.com/strikersam/autonomous-ai-agency/pull/1871) | Rate checked against the pricing page (0.05x base input). Two 2026-09-30 tests pinned the old 10 % and were updated. Review found Anthropic cache reads were clamped to near-zero cost; fixed separately in #1877, including LLMProvider.cost pricing cached tokens at the cache-read rate. | 2026-11-01 |
