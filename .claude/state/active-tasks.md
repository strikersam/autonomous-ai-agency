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
| 2 | Dynamic Session Planning Workflow (this task) | `IN_PROGRESS` | [#406](https://github.com/strikersam/local-llm-server/pull/406) | hooks + tracker + AGENTS.md update | 2026-06-05 |
| 3 | Agentic Portfolio Management (WSJF) + v5 Portfolio screen | `DONE` | #423, #426 | portfolio.py, agile health/retro, v5 board | 2026-06-06 |
| 4 | Autonomous Portfolio Intelligence (signals → initiatives, 6h cron) | `DONE` | [#427](https://github.com/strikersam/local-llm-server/pull/427) | portfolio_intelligence.py + refresh workflow + UI provenance | 2026-06-06 |
| 5 | Fix social login (Google & GitHub OAuth) | `DONE` | `claude/social-login-google-github-BBGoT` | 3 bugs fixed in backend/server.py — see bug log #4-6 | 2026-06-06 |
| 6 | Portfolio refresh workflow → reuse RENDER_BACKEND_URL secret | `IN_PROGRESS` | claude/portfolio-refresh-backend-url | point cron ping at existing secret | 2026-06-06 |
| 7 | FreeBuff agent (free NVIDIA models) + Telegram phone control (#416) | `DONE` | [#431](https://github.com/strikersam/local-llm-server/pull/431) merged | FreeBuffAgent + /freebuff/* endpoints + Telegram inline buttons + unlimited rate limit; tests + docs | 2026-06-06 |
| 8 | FreeBuff always-on Telegram bot (24×7 Render/Docker, embedded mode) | `IN_PROGRESS` | `claude/freebuff-telegram-deploy` | embedded in-process agent + launcher + Dockerfile.telegram + render worker + deploy docs | 2026-06-06 |
| 9 | SEO/GEO/AEO/AIO audit engine + repo fixer + revenue portfolio (#533, PR #534 plan) | `DONE` | `claude/cool-davinci-494siy` | 97-check engine, WSJF delegation, auto-fixer, API, 124 tests — see docs/seo-audit.md | 2026-06-12 |
| 10 | Autonomous agile ceremonies (standup/retro/sprint-planning) + Delivery Manager role (35th specialist family) | `DONE` | `claude/agentic-agile-workflows-8ymf4d` | agents/agile_ceremonies.py (standup/sprint-retro/backlog-retro/sprint-plan, 17 tests) + agile-ceremonies.yml cron (standup/retro/plan) + `delivery` specialist family (35th) bound to agentic-agile/agentic-portfolio, matrix + docs regenerated | 2026-06-14 |

---

## Bug Log

| # | Bug Description | Found | Fixed | PR | Status |
|---|----------------|-------|-------|----|--------|
| 1 | NVIDIA NIM double `/v1` URL in `agent/loop.py` line 911 | 2026-06-03 | 2026-06-03 | #397 | `BUG_FIXED` |
| 2 | ProviderManager vs ProviderRouter type mismatch in `direct_chat.py` | 2026-06-03 | 2026-06-03 | #399 | `BUG_FIXED` |
| 3 | TaskBoardScreen create-task modal silently swallowed API errors | 2026-06-05 | 2026-06-05 | #406 parent | `BUG_FIXED` |
| 4 | GitHub+Google share `session["oauth_state"]` — CSRF check always fails on multi-tab/provider-switch | 2026-06-06 | 2026-06-06 | `claude/social-login-google-github-BBGoT` | `BUG_FIXED` |
| 5 | Google redirect_uri via `url_for` breaks behind proxy — token exchange rejected by Google | 2026-06-06 | 2026-06-06 | `claude/social-login-google-github-BBGoT` | `BUG_FIXED` |
| 6 | GitHub OAuth URL missing `redirect_uri`; no timeout on httpx clients in login flows | 2026-06-06 | 2026-06-06 | `claude/social-login-google-github-BBGoT` | `BUG_FIXED` |
| 7 | Google login still "Invalid OAuth state" — session cookie doesn't survive Cloudflare↔Render hop + Render cold-start SESSION_SECRET rotation. Moved login state to server-side `oauth_states` collection | 2026-06-06 | 2026-06-06 | `claude/social-login-oauth-state-store` | `BUG_FIXED` |
| 8 | Social login 500 "Internal server error" — `_valid_login_state` subtracted naive MongoDB `created_at` from aware `now()` → TypeError (unhandled). Normalised naive datetime to tz-aware | 2026-06-06 | 2026-06-06 | `claude/social-login-naive-datetime-fix` | `BUG_FIXED` |
| 9 | Agent `write_file` workspace-isolation leak: `tests/test_e2e_agent_chat.py::TestAgentFullPRWorkflow::test_agent_full_pr_workflow` monkeypatches `_CHAT_AGENT_WORKSPACE_ROOT` to `tmp_path` and mocks an executor `write_file("src/main.py", "def hello(): return 'Hello Agent'")` step. Running the full suite (`pytest -q --ignore=tests/e2e`, 2026-06-14) left a real `src/main.py` with that exact content at the repo root — the agent write escaped the isolated `tmp_path` workspace into the live checkout. Root cause not yet isolated (suspects: `agent/loop.py` MCP-first `write_file` dispatch ~line 1051, or `WorkspaceTools` default-root fallback in `agent/tools.py`). Needs `risky-module-review`. | 2026-06-14 | — | — | `BUG_FOUND` |

---

## Roadmap Items (from `docs/roadmap-killer-todos.md`)

| # | Item | Priority | Status | PR |
|---|------|----------|--------|-----|
| ★1 | 3-Phase Context-Pruner Middleware | P0 | `TODO` | — |
| ★2 | Specialized Sub-Agents with Per-Role Models | P0 | `TODO` | — |
| ★3 | Reasoning Token Budget + Toggle | P0 | `TODO` | — |
| A1 | Hermes ChatML Prompt Format | P0 | `TODO` | — |
| A2 | Multi-Hop ReAct Loop | P0 | `TODO` | — |
| B1 | Nemotron Reward Model Scoring | P0 | `TODO` | — |
| C1 | Structured Output / JSON Mode | P0 | `TODO` | — |
| C2 | Function Calling (OpenAI-compatible) | P0 | `TODO` | — |
| F1 | Precise Diff Application (Codebuff-style) | P0 | `TODO` | — |
| ★4 | Skill/Procedural Memory | P1 | `TODO` | — |
| ★5 | Sandboxed Agent Execution | P1 | `TODO` | — |
| ★6 | Cost Analytics + FTS5 Memory + Constitution | P1 | `TODO` | — |
| ★7 | Adaptive Loop Halting | P1 | `TODO` | — |
| A3 | Capability Registry + Dynamic Tool Discovery | P1 | `TODO` | — |
| A4 | Async Task Queue | P1 | `TODO` | — |
| A5 | Inter-Agent Message Bus | P1 | `TODO` | — |
| B2 | SteerLM Steering Tokens | P1 | `TODO` | — |
| B3 | Synthetic Training Data Pipeline | P1 | `TODO` | — |
| B4 | NeMo Guardrails | P1 | `TODO` | — |
| B5 | NIM Connection Pooling + Circuit Breaker | P1 | `TODO` | — |
| C3 | Streaming Delta Reconstruction | P1 | `TODO` | — |
| C4 | Chat History Persistence | P1 | `TODO` | — |
| C5 | Context Window Management | P1 | `TODO` | — |
| C6 | Prompt Caching | P1 | `TODO` | — |
| D1 | Helm Chart | P1 | `TODO` | — |
| D2 | Docker Compose Production Stack | P1 | `TODO` | — |
| D3 | OpenTelemetry Distributed Tracing | P1 | `TODO` | — |
| E1 | Cross-Harness Routing | P1 | `TODO` | — |
| E2 | Self-Healing Agent Doctor | P1 | `TODO` | — |
| F2 | MCP Server | P1 | `TODO` | — |
| G1 | Per-Model Cost Attribution | P1 | `TODO` | — |

---

## Session Log

| Date | Agent/Tool | Branch | Action |
|------|------------|--------|--------|
| 2026-06-05 | claude-sonnet-4-6 (Opus agent) | claude/llm-server-roadmap-pr-COcKN | Created roadmap TODO from 6 OSS repos research |
| 2026-06-05 | claude-sonnet-4-6 | claude/llm-server-roadmap-pr-COcKN | Built dynamic session planning workflow |
| 2026-06-14 | claude-sonnet-4-6 | claude/agentic-agile-workflows-8ymf4d | Implemented autonomous agile ceremonies (agents/agile_ceremonies.py + agile-ceremonies.yml cron) and added `delivery` (Delivery Manager) as the 35th specialist family |
