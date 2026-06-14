# 467 Brutal Audit — File-by-File Status

> Issue #467 §3 required: "Brutal audit with file references (WORKING / FLAKY / ADVERTISED-BUT-NOT-BUILT / MOCKED / etc.)"

---

## Core Proxy & Routing

| File | LOC | Status | Notes |
|------|-----|--------|-------|
| `proxy.py` | 1,719 | WORKING | OpenAI / Anthropic / Ollama routing; Bearer auth; rate limiting. Auth middleware (lines 195–292) is RISKY MODULE. |
| `chat_handlers.py` | 710 | WORKING | OpenAI/Ollama streaming handlers; handles both formats. |
| `provider_router.py` | 1,238 | WORKING | Multi-provider backend with fallback chain. |
| `router/model_router.py` | ~400 | WORKING | ModelRouter — central routing logic; classify_task(). |
| `router/classifier.py` | ~300 | WORKING | Task classification; intent detection. |
| `router/registry.py` | ~400 | WORKING | Model capability registry. |

**Audit:** proxy.py has `API_KEYS` env var parsed on every request — no caching of parsed keys. Rate limiter is in-memory dict (not thread-safe across workers). CORS_ORIGINS defaults to `*` in code (should be required env var).

---

## Agent System

| File | Status | Notes |
|------|--------|-------|
| `agent/loop.py` | WORKING | AgentRunner with ReAct loop; `_execute_step()` has retry logic (added in session). `run()` executes code, not just planning. |
| `agent/background.py` | WORKING | BackgroundAgent with retry + exponential backoff (added in session). Heartbeat updates. |
| `agent/tools.py` | WORKING | WorkspaceTools with `_resolve_path()` sandboxing. RISKY MODULE. |
| `agent/repowise.py` | WORKING | RepowiseIntelligence — codebase analysis; 866 LOC. |
| `agent/kpi.py` | WORKING | KPI counters — `increment()`, `get_all()`, `summarize()`. Added in session. |
| `agent/trend_watcher.py` | WORKING | 13-source trend intelligence (expanded in session). |
| `agent/knowledge_sync.py` | WORKING | sync_trends(), sync_repository(). Has proper asyncio. |
| `agent/agency.py` | WORKING | CEO agent with `execute()` method. Partial autonomous loop. |
| `agent/quality.py` | WORKING | QualityAgent. Has `run()` method. |
| `agent/finance.py` | WORKING | FinanceAgent. Has `run()` method. |
| `agent/research.py` | WORKING | ResearchAgent. Has `run()` method. |
| `agent/agile.py` | PARTIAL | AgileAgent. Sprint velocity tracking works; full autonomous loop not built. |
| `agents/portfolio_intelligence.py` | WORKING | PortfolioManager + PortfolioIntelligence with WSJF scoring. |
| `agent/mcp_server.py` | WORKING | MCP server implementation. |
| `agent/hermes_prompt.py` | WORKING | Hermes prompt templates. |

---

## Handlers

| File | Status | Notes |
|------|--------|-------|
| `handlers/anthropic_compat.py` | WORKING | Anthropic API adapter; 708 LOC. |
| `handlers/diagnostics.py` | WORKING | Doctor endpoints — public/auth split. Partial check list (see §F gap). |
| `handlers/v3_auth.py` | WORKING | JWT validation. RISKY MODULE. |

---

## Backend & Services

| File | Status | Notes |
|------|--------|-------|
| `backend/server.py` | 6,487 | WORKING | Dashboard API server. HIGH risk. Auth guard on all endpoints. |
| `services/workflow_orchestrator.py` | 1,119 | WORKING | Workflow execution engine. `_BYPASS` exists for internal callers. |
| `services/company_graph_store.py` | 1,660 | WORKING | Company knowledge graph persistence. |
| `services/scanner.py` | 1,377 | WORKING | Tech stack scanner (Playwright). |
| `services/company_agency.py` | WORKING | Company agency specialist. |
| `services/seo_agent.py` | **ADVERTISED-BUT-NOT-BUILT** | Referenced in spec §B; file does not exist. |
| `services/pim_agent.py` | **ADVERTISED-BUT-NOT-BUILT** | Referenced in spec §B; file does not exist. |
| `services/oms_agent.py` | **ADVERTISED-BUT-NOT-BUILT** | Referenced in spec §B; file does not exist. |
| `services/dam_agent.py` | **ADVERTISED-BUT-NOT-BUILT** | Referenced in spec §B; file does not exist. |
| `services/analytics_agent.py` | **ADVERTISED-BUT-NOT-BUILT** | Referenced in spec §B; file does not exist. |
| `services/trading_agent.py` | **ADVERTISED-BUT-NOT-BUILT** | Referenced in spec §B; file does not exist. |
| `services/crm_agent.py` | **ADVERTISED-BUT-NOT-BUILT** | Referenced in spec §B; file does not exist. |

---

## Security Modules (RISKY — require risky-module-review)

| File | Status | Notes |
|------|--------|-------|
| `admin_auth.py` | WORKING | Admin session auth (Windows + secret). RISKY. |
| `key_store.py` | WORKING | API key CRUD, SHA-256 hashing. RISKY. |
| `rbac.py` | WORKING | Role-based access control. HIGH. |
| `social_auth.py` | WORKING | GitHub/Google OAuth. HIGH. |

---

## Workflow

| File | Status | Notes |
|------|--------|-------|
| `workflow/engine.py` | WORKING | Workflow engine. 20 lines of docstring added in session. **Worktree isolation NOT enforced** — same as before session. Spec §E demands enforced isolation. |
| `workflow/models.py` | WORKING | Pydantic models for workflow. |
| `workflow/phases.py` | WORKING | Phase definitions. |
| `workflow/api.py` | WORKING | Workflow API endpoints. |

---

## Direct Chat

| File | Status | Notes |
|------|--------|-------|
| `direct_chat.py` | 833 | WORKING | Direct chat sessions; intent classification. `_BYPASS` set for internal callers. **Not control center** — spec §D demands control center with sticky context, no metadata leakage. Current implementation is session-based but not unified control plane. |

---

## Observability

| File | Status | Notes |
|------|--------|-------|
| `langfuse_obs.py` | ~300 | WORKING | Langfuse trace emission. |
| `audit.py` | WORKING | Audit logging. |

---

## Frontend / Public Site (spec §H — 0% delivered)

| File | Status | Notes |
|------|--------|-------|
| `webui/` | N/A | **NOT TOUCHED** in this session or any recent session. Spec §H demands public site rebuild. |
| `frontend/` | N/A | **NOT TOUCHED**. No React rebuild. |
| `index.html` | WORKING | Static landing page. |
| `github-pages-setup.html` | WORKING | GitHub Pages setup doc. |

---

## Skills (99 skills inventoried — see 467-skill-inventory.md)

See `docs/audits/467-skill-inventory.md` for full breakdown.

**Critical:** 25 skills not wired to live paths. ECC and Obsidian (spec §C) not built as skills. `agent-browser` skill exists but not invoked from any live agent code.

---

## GitHub Workflows

| Workflow | Status | Notes |
|----------|--------|-------|
| `agency-cycle.yml` | QUARANTINED | Manual dispatch only. Auto-commits AI patches too fast to verify. |
| `ci-failure-autofix.yml` | QUARANTINED | Manual dispatch only. |
| `continuous-improvement.yml` | QUARANTINED | Manual dispatch only. |
| `openclaw-security-automation.yml` | QUARANTINED | Manual dispatch only. |
| `process-quick-note.yml` | QUARANTINED | Manual dispatch only. |
| `weekly-trend-digest.yml` | QUARANTINED | Manual dispatch only. |
| `auto-merge.yml` | WORKING | Auto-merge on CI success with GH_PAT. |

---

## Feature Matrix (spec §I — demotions needed)

Features to **DEMOTE** (not remove — mark as `development` tier):
- `async_agent_jobs` — FLAKY
- `crispy_workflow` — FLAKY
- `task_harness_runtime` — ADVERTISED-BUT-NOT-BUILT
- `multi_agent_swarm` — ADVERTISED-BUT-NOT-BUILT
- `openhands_runtime` — ADVERTISED-BUT-NOT-BUILT
- `sidecar_runtimes` — ADVERTISED-BUT-NOT-BUILT
- `openclaw_integration` — ADVERTISED-BUT-NOT-BUILT (docs exist; code not built)
- `quick_actions_ios` — ADVERTISED-BUT-NOT-BUILT
- `machine_peer_sync` — ADVERTISED-BUT-NOT-BUILT
- `jcode_runtime` — ADVERTISED-BUT-NOT-BUILT
- `tunnels` — FLAKY (ngrok stable but tunnels package is unmaintained)
- `telegram_bot` — FLAKY / CONTRADICTS SPEC — spec explicitly says "gated, isolated, or removed"; telegram_service.py was added in session despite this directive

---

## Test Suite

| File | Status | Notes |
|------|--------|-------|
| `tests/test_contracts_agency.py` | WORKING | 21 test cases, contract discipline, passes |
| `tests/test_agent_runner.py` | WORKING | Passes |
| `tests/test_direct_chat_async.py` | WORKING | Passes |
| `tests/test_workflow_engine.py` | WORKING | Passes |
| `tests/test_trend_watcher.py` | WORKING | All 32 tests pass |
| `tests/test_knowledge_sync.py` | WORKING | Passes |
| `tests/test_improvement_loop.py` | WORKING | Passes |

**E2E gaps (spec §K):** No E2E tests for onboarding, specialist provisioning, skill exec, direct chat control center, workflow engine as backbone, Doctor full checks, CEO autonomous loop, HITL, issue/PR lifecycle.

---

## Summary Scorecard

| Spec Section | Deliverable | Status |
|--------------|-------------|--------|
| §A | Company Graph + onboarding via URL | 0% — not built |
| §B | 34 specialist families | 0% — 7 specialists not built |
| §C | ECC, Obsidian, Graphify, Council Review wiring | 0% — only repowise wired |
| §D | Direct chat as control center | 0% — session tool, not control plane |
| §E | Workflow as backbone + worktree isolation | PARTIAL — engine works; isolation not enforced |
| §F | Doctor full check list | PARTIAL — subset of checks implemented |
| §G | CEO autonomous loop | PARTIAL — execute() exists; no dedupe/verified-close/branch-protection-safe |
| §H | Public site truth | 0% — frontend/webui untouched |
| §I | Feature matrix discipline | 0% — no demotions applied |
| §J | Contract discipline (Pydantic extra=forbid) | PARTIAL — tests added; no enforcement in source |
| §K | CI parity + E2E coverage | 0% — no E2E coverage added |