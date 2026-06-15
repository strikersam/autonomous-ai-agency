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
| 11 | SEO audit: browser-use fetch (Akamai bypass), honest revenue model, demoable UI tab + downloads | `IN_PROGRESS` | `claude/cool-davinci-494siy` | services/seo_fetch.py (httpx/Playwright/auto-escalate), diminishing-returns revenue curve, CompanyScreen SEO tab + CSV/JSON/MD downloads; 13 new fetch tests. Live Akamai bypass needs Playwright browsers in deploy | 2026-06-13 |
| 12 | Fix specialist provisioning timeout + masked "something went wrong" errors (onboarding/SEO/gucci.com scan) | `DONE` | `claude/specialist-seo-scan-errors-pov08i` | onboarding.py Step 8 now backgrounded via asyncio.create_task; runtimes/control.py uses asyncio.to_thread for docker compose; api.js fmtErr() no longer masks e.message, added default/long-call axios timeouts; 1 new regression test | 2026-06-14 |
| 13 | Unblock PR #638 CI (4 pre-existing master bugs found while making #12 mergeable) | `DONE` | `claude/specialist-seo-scan-errors-pov08i` | (1) `.github/scripts/implement_agent.py` had 2968 trailing NUL bytes breaking py_compile; (2) `CompanyScreen.jsx` truncated `exp` instead of `export default CompanyScreen;`, broke npm build; (3) `proxy.py` alias `owned_by` was `llm-relay-alias` vs test's `autonomous-ai-agency-alias`; (4) `test_brain_priority_scanner.py::test_scanner_imports_cleanly` did `sys.modules.pop("services.scanner")` creating a duplicate WebsiteScanner class, breaking monkeypatch in all 9 `test_onboarding_provisioning.py` tests when run in full suite. Full `pytest -x` (2823 tests) now green | 2026-06-14 |
| 14 | Fix orchestrator P1 error-cascade (AttributeError 'dict'/'NoneType' has no attribute 'passed'/'company_id' + "Future exception was never retrieved" + stall-requeue loop flooding the activity feed) | `DONE` | `claude/agency-error-cascade-d2eoaw` | Root cause: `restore_in_flight()` rehydrated phase outputs as raw dicts (not Pydantic models) and left runs with no reconstructable `_request` as queued/running, so `execute(None, resume_run_id=...)` crashed on `req.company_id`/`req.user_id`, and the post-loop `run.verification.passed` check crashed on a dict. Fixed via `_PHASE_OUTPUT_MODELS` reconstruction + fail-fast on missing `_request` (workflow_orchestrator.py, orchestrator_supervisor.py), and `_QueueEntry.wait` flag so fire-and-forget `enqueue()` never calls `set_exception()` (orchestrator_queue.py). 5 new regression tests; full `pytest -x` (2868 tests) green | 2026-06-15 |
| 15 | Autonomy Charter + Master Goal Prompt (full-autonomy spec, Telegram-gated) | `DONE` | [#652](https://github.com/strikersam/autonomous-ai-agency/pull/652) | `docs/autonomy/AUTONOMY_CHARTER.md` (Gate Matrix, brain policy, 5 autonomous loops, G1-G5 gap table, acceptance criteria) + `docs/autonomy/MASTER_PROMPT.md` (CEO operating prompt) | 2026-06-15 |
| 16 | G1 — Proactive Telegram approval-gate push (`awaiting_approval` → inline Approve/Reject) + `TELEGRAM_CHAT_ID` single-operator convention | `DONE` | [#652](https://github.com/strikersam/autonomous-ai-agency/pull/652) | `WorkflowOrchestrator._notify_approval_gate()` → `NotificationDispatcher.send_approval_gate()`; `telegram_bot.py` `wfo:approve\|reject:<run_id>` callbacks (`approve_async`/`cancel_run`, not-found/already-resolved handling); `TELEGRAM_CHAT_ID` fallback for ALLOWED/ADMIN/NOTIFY chat IDs via `_resolve_bot_user_ids()`. New tests: `test_telegram_approval_gate.py`, `TestApprovalGateNotification`, `wfo:` callback tests in `test_telegram_freebuff.py`. Full `pytest -x` (2898 tests) green | 2026-06-15 |
| 17 | G2 — Closed-loop self-heal feedback (confirm error signature gone post-fix) | `TODO` | — | `agent/self_healing.py` ↔ `agent/log_monitor.py` ↔ `agent/improvement_loop.py`; see `AUTONOMY_CHARTER.md` §6 | — |
| 18 | G3 — Auto issue→task intake (GitHub issues / scanner signals → Task records) | `TODO` | — | webhook listener → `tasks/dispatcher.py`; see `AUTONOMY_CHARTER.md` §6 | — |
| 19 | G4 — Per-company trend scoping (score trends vs each company's detected stack) | `TODO` | — | `agent/trend_watcher.py` + Company graph (`services/scanner.py`); see `AUTONOMY_CHARTER.md` §6 | — |
| 20 | G5 — `RepoConnection` + `DeliveryPolicy` plumbing (GitHub-only scope; SDLC Phases 0-4) | `TODO` | — | per `docs/architecture/autonomous-sdlc-loop.md`; see `AUTONOMY_CHARTER.md` §6 | — |

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
| 10 | `.github/workflows/ci-failure-autofix.yml` called Anthropic API with `claude-sonnet-4-20250514` (original Claude Sonnet 4) — Anthropic retires this model on the Claude API 2026-06-15, would break the autofix workflow starting tomorrow. Updated to `claude-sonnet-4-6` to match the workflow's own header comment | 2026-06-14 | 2026-06-14 | `claude/nifty-pasteur-hvjqzn` | `BUG_FIXED` |
| 11 | `tests/test_onboarding_provisioning.py` (9 tests) fail with `['Blocked: target URL is not a safe public address (SSRF protection)']` ONLY in full/large-batch runs — the `wired` fixture's `monkeypatch.setattr(scanner_mod.WebsiteScanner, "scan_website", fake_scan_website)` stops taking effect once enough other test modules have run first, so `services.onboarding._scan_website` invokes the real (SSRF-blocked, headless-render-attempting) `WebsiteScanner.scan_website` for `*.example-*.com` hosts. Passes in isolation and in every small pairwise combination tried. **Reproduced identically on `origin/master` (`f34c5b3`)** with the same 53-file batch (`9 failed, 628 passed`) — confirmed pre-existing on master, independent of this branch's 8 changed files. Needs `risky-module-review` (touches `services/scanner.py` SSRF guard + async event-loop/CompanyAgency activation interplay, also logs `CompanyAgency: activation failed ...: Event loop is closed`, possibly related to bug #9). | 2026-06-14 | 2026-06-14 | `c6b7520` (#638), merged into `claude/agentic-agile-workflows-8ymf4d` via `c339ac4` | `BUG_FIXED` |
| 12 | CI "Test (Python 3.13)" jobs on `claude/agentic-agile-workflows-8ymf4d` hung 30+ min (vs master's ~2.5 min) on commit `4e6b087` — branch lacked master's `c6b7520`/#638 fix for the blocking `subprocess.run(["docker","compose",...])` call in `runtimes/control.py` reached via `services/onboarding.py`'s synchronous `await agency.activate_company(...)`. Resolved by merging `origin/master` (`c6b7520`) into the branch (merge commit `c339ac4`). | 2026-06-14 | 2026-06-14 | `c339ac4` | `BUG_FIXED` |
| 13 | Orchestrator P1 error-cascade flooding activity feed: `restore_in_flight()` rehydrated checkpointed phase outputs as raw dicts, so the post-execute `run.verification.passed` check raised `AttributeError: 'dict' object has no attribute 'passed'`; runs restored with no persisted `_request` stayed `queued`/`running` and were re-enqueued by the supervisor as `execute(None, resume_run_id=...)`, raising `AttributeError: 'NoneType' object has no attribute 'company_id'`. Both exceptions were `set_exception()`'d onto fire-and-forget `OrchestratorQueue.enqueue()` futures nobody awaits, so asyncio logged "Future exception was never retrieved" on GC for every retry — an endless stall→requeue→crash loop spamming P1 alerts for run IDs `wfo_2595df77ed1f`, `wfo_9f2a3ee2b1da`, `wfo_841a0518c956`, `wfo_a5151d808fa4`, `wfo_e6a9f78caf4e`, `wfo_bcea91a8ce81`, `wfo_23faf405831a`, `wfo_bf62ba125f00`, `wfo_ba879e94a168`. | 2026-06-15 | 2026-06-15 | `claude/agency-error-cascade-d2eoaw` | `BUG_FIXED` |

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
| 2026-06-14 | claude-sonnet-4-6 | claude/nifty-pasteur-hvjqzn | Daily automation: researched Anthropic/Claude Code/Codex 2026-06 industry news; found Claude Sonnet 4 / Opus 4 retire on the Claude API 2026-06-15 — fixed `.github/workflows/ci-failure-autofix.yml` (`claude-sonnet-4-20250514` → `claude-sonnet-4-6`), added `tests/test_daily_2026_06_14.py` regression guard |
