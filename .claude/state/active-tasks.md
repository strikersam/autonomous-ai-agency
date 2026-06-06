# Active Task Tracker

> **Living document** — updated by every agent session across all tools (Claude Code, Codex, Cursor, Aider, etc.)
> Rules: mark IN_PROGRESS when you start a task, DONE when verified, BUG_FOUND when you discover an issue,
> BUG_FIXED when resolved. Never delete rows — append new rows for re-attempts.

## Status Key

| Status | Meaning |
|--------|---------|
| `TODO` | Planned but not started |
| `IN_PROGRESS` | Being worked on this session |
| `DONE` | Implemented, tested, merged |
| `BLOCKED` | Waiting on external dependency |
| `BUG_FOUND` | Bug discovered during implementation |
| `BUG_FIXED` | Bug confirmed fixed (link the PR) |
| `DEFERRED` | Deprioritised — see Notes for why |

---

## Current Sprint Tasks

| # | Task | Status | PR / Branch | Notes | Updated |
|---|------|--------|-------------|-------|---------|
| 1 | Killer TODO Roadmap (docs only — 33-item backlog from 6 OSS repos) | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) | Draft PR created, CI running | 2026-06-05 |
| 2 | Dynamic Session Planning Workflow | `DONE` | [#424](https://github.com/strikersam/local-llm-server/pull/424) | Merged to master — SessionStart hook, active-tasks.md, AGENTS.md | 2026-06-06 |
| 3 | Eliminate duplicate CI runs (push: ["**"] + pull_request double-fire) | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) | ci.yml, e2e.yml, browser-e2e.yml narrowed to push: [main, master]; draft guards on e2e-mongodb + e2e-scanner-live | 2026-06-06 |

---

## Bug Log

| # | Bug Description | Found | Fixed | PR | Status |
|---|----------------|-------|-------|----|--------|
| 1 | NVIDIA NIM double `/v1` URL in `agent/loop.py` line 911 | 2026-06-03 | 2026-06-03 | #397 | `BUG_FIXED` |
| 2 | ProviderManager vs ProviderRouter type mismatch in `direct_chat.py` | 2026-06-03 | 2026-06-03 | #399 | `BUG_FIXED` |
| 3 | TaskBoardScreen create-task modal silently swallowed API errors | 2026-06-05 | 2026-06-05 | #406 parent | `BUG_FIXED` |

---

## Roadmap Items (from `docs/roadmap-killer-todos.md`)

| # | Item | Priority | Status | PR |
|---|------|----------|--------|-----|
| ★1 | 3-Phase Context-Pruner Middleware | P0 | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) |
| ★2 | Specialized Sub-Agents with Per-Role Models | P0 | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) |
| ★3 | Reasoning Token Budget + Toggle | P0 | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) |
| A1 | Hermes ChatML Prompt Format | P0 | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) |
| A2 | Multi-Hop ReAct Loop | P0 | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) |
| B1 | Nemotron Reward Model Scoring | P0 | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) |
| C1 | Structured Output / JSON Mode | P0 | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) |
| C2 | Function Calling (OpenAI-compatible) | P0 | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) |
| F1 | Precise Diff Application (Codebuff-style) | P0 | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) |
| ★4 | Skill/Procedural Memory | P1 | `TODO` | — |
| ★5 | Sandboxed Agent Execution | P1 | `TODO` | — |
| ★6 | Cost Analytics + FTS5 Memory + Constitution | P1 | `TODO` | — |
| ★7 | Adaptive Loop Halting | P1 | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) |
| A3 | Capability Registry + Dynamic Tool Discovery | P1 | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) |
| A4 | Async Task Queue | P1 | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) |
| A5 | Inter-Agent Message Bus | P1 | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) |
| B2 | SteerLM Steering Tokens | P1 | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) |
| B3 | Synthetic Training Data Pipeline | P1 | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) |
| B4 | NeMo Guardrails | P1 | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) |
| B5 | NIM Connection Pooling + Circuit Breaker | P1 | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) |
| C3 | Streaming Delta Reconstruction | P1 | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) |
| C4 | Chat History Persistence | P1 | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) |
| C5 | Context Window Management | P1 | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) |
| C6 | Prompt Caching | P1 | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) |
| D1 | Helm Chart | P1 | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) |
| D2 | Docker Compose Production Stack | P1 | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) |
| D3 | OpenTelemetry Distributed Tracing | P1 | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) |
| E1 | Cross-Harness Routing | P1 | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) |
| E2 | Self-Healing Agent Doctor | P1 | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) |
| F2 | MCP Server | P1 | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) |
| G1 | Per-Model Cost Attribution | P1 | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) |

---

## Session Log

| Date | Agent/Tool | Branch | Action |
|------|------------|--------|--------|
| 2026-06-05 | claude-sonnet-4-6 (Opus agent) | claude/llm-server-roadmap-pr-COcKN | Created roadmap TODO from 6 OSS repos research |
| 2026-06-06 | claude-sonnet-4-6 | claude/llm-server-roadmap-pr-COcKN | Implemented E1 Harness Routing, E2 Self-Healing, F2 MCP Proxy Tools, G1 Cost Attribution; 30+ integration tests + C6 wired
| 2026-06-06 | claude-sonnet-4-6 | claude/llm-server-roadmap-pr-COcKN | Integrated C4/C5 into chat_handlers + agent/loop; C6 Prompt Cache, D1 Helm Chart, D2 Compose Prod, D3 OTEL Tracing |
| 2026-06-06 | claude-sonnet-4-6 | claude/llm-server-roadmap-pr-COcKN | Implemented C3 Streaming Delta, C4 Chat History, C5 Context Window; 30+ tests |
| 2026-06-06 | claude-sonnet-4-6 | claude/llm-server-roadmap-pr-COcKN | Implemented B3 Synthetic Data, B4 Guardrails, B5 NIM Pool; 30+ tests |
| 2026-06-06 | claude-sonnet-4-6 | claude/llm-server-roadmap-pr-COcKN | Implemented A4 Task Queue, A5 Agent Bus, B2 SteerLM Steering; 35+ tests |
| 2026-06-06 | claude-sonnet-4-6 | claude/llm-server-roadmap-pr-COcKN | Implemented B1 Nemotron Reward Scoring, C2 Function Calling, A3 Capability Registry; 35+ tests |
