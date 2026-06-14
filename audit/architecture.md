# Architecture Audit — local-llm-server

*Audit Date: 2026-06-04*

---

## System Overview

`local-llm-server` is a self-hosted, OpenAI-compatible API proxy with a full AI platform layered on top. It sits in front of Ollama and adds auth, routing, multi-agent orchestration, observability, a web admin dashboard, Telegram bot control, and a React SPA frontend.

---

## Component Map

### Layer 1 — API Proxy (`proxy.py`, 1719 lines)

**Purpose:** Main FastAPI application. Entry point for all client connections.

**Responsibilities:**
- Bearer token + x-api-key authentication (dual-header support)
- Per-key in-memory rate limiting (sliding window, 60 RPM default)
- CORS middleware (defaults to `*` — needs tightening for production)
- Session middleware for admin UI
- Routes: `/v1/chat/completions`, `/v1/messages`, `/api/*`, `/admin/*`, `/agent/*`
- Startup validation: weak key detection, admin secret validation

**Issues:**
- At 1719 lines, `proxy.py` is a god file. Needs decomposition into sub-routers.
- Rate limiter is in-memory only — not distributed; breaks under horizontal scaling.
- `CORS_ORIGINS` defaults to `"*"` — should default to `null` (deny all) in production.
- API keys generated with prefix `"test-key-"` — misleading for production keys.

---

### Layer 2 — Chat Handlers (`chat_handlers.py`, 710 lines)

**Purpose:** Implements streaming and non-streaming chat for OpenAI and Ollama native formats.

**Key functions:**
- `handle_openai_chat_completions()` — translates OpenAI requests, calls Ollama, streams back
- `handle_ollama_native_chat()` — passthrough to Ollama native `/api/chat`

**Dependencies:** `router.ModelRouter`, `langfuse_obs.emit_chat_observation`

---

### Layer 3 — Model Router (`router/`)

**Files:** `model_router.py`, `classifier.py`, `registry.py`, `health.py`

**Selection priority:**
1. `X-Model-Override` header / `override_model` kwarg
2. `MODEL_MAP` env var alias table (Anthropic name → local model)
3. Heuristic: `classify_task()` → `best_model_for()` from registry
4. Default: `AGENT_EXECUTOR_MODEL`

**Strong points:** Well-documented, tested, singleton pattern with reset support for tests.

**Issues:**
- Health check TTL is 60s by default — stale model availability data during failover
- No circuit breaker for repeated Ollama failures
- `fallback_chain` logic is defined but automatic retry on failure is not wired in `chat_handlers.py`

---

### Layer 4 — Agent System (`agent/`)

**Files:** 50+ Python files covering loop, tools, memory, GitHub, scheduling, skills, terminal, watchdog, etc.

**Architecture:** Three-role plan-execute-verify loop.
```
Planner (deepseek-r1:32b) → AgentPlan
  └─ For each step:
       Executor (qwen3-coder:30b) → tool calls (read/write/search/github)
         └─ Verifier (deepseek-r1:32b) → VerificationResult
```

**Key risks:**
- `tools.py apply_diff()` writes arbitrary content to disk (path traversal protection exists via `_resolve_path`)
- Auto-commit (`git commit`) invoked from Python — no signature, no pre-commit hooks
- Agent loop `max_steps` guard exists but value is env-configurable — could be set too high
- No sandbox/container isolation for agent-executed code

---

### Layer 5 — Backend Server (`backend/server.py`)

**Purpose:** Separate FastAPI application running on port 8001. Serves the React dashboard.

**Endpoints include:** company graph, onboarding, skills, workflow orchestrator, secrets, agents, wiki, quick-notes, doctor, ping, status.

**Issues:**
- Two separate FastAPI apps (proxy on 8000, backend on 8001) with separate auth — increases attack surface and complexity
- No shared session store between apps — admin must authenticate separately

---

### Layer 6 — Frontend (`frontend/`)

**Stack:** React + Tailwind CSS (CRA-based, not Vite)
**Build output:** Static SPA served behind nginx or Vercel

**Screens:** Dashboard, AgentsScreen, DoctorScreen, CompanyScreen, OnboardingScreen, LogsScreen, SkillsScreen

**Issues:**
- CRA (Create React App) is deprecated upstream — should migrate to Vite
- `REACT_APP_BACKEND_URL` hardcoded to `https://relay.example.com` in CI build step
- ESLint issues identified in changelog (hooks exhaustive-deps, no-unused-vars)
- Bundle size not audited

---

### Layer 7 — Handlers (`handlers/`)

**Files:** `anthropic_compat.py`, `v3_auth.py`, `v3_models.py`

**Purpose:** Anthropic `/v1/messages` compatibility surface. Translates Anthropic API requests into Ollama format.

---

### Layer 8 — Services (`services/`)

**Files:** `company_agency.py`, `company_graph.py`, `company_graph_store.py`, `managed_agents.py`, `onboarding.py`, `scanner.py`, `skill_bindings.py`, `temporal_context.py`, `workflow_orchestrator.py`, `specialist.py`

**Purpose:** Business logic for the AI platform — company graph management, onboarding workflows, skill registry, temporal context.

**Issues:**
- `workflow_orchestrator.py` at 700+ lines is approaching god-file territory
- MongoDB + SQLite dual-backend adds significant complexity; SQLite path has had bugs (missing tables)

---

### Layer 9 — Tasks (`tasks/`)

**Files:** `api.py`, `automation.py`, `dispatcher.py`, `models.py`, `service.py`, `store.py`

**Purpose:** Background task queue with storage, dispatch, and automation.

---

### Layer 10 — WebUI (`webui/`)

**Files:** `config_store.py`, `providers.py`, `router.py`, `workspaces.py`, `url_guard.py`

**Purpose:** Config management, provider management, workspace isolation, URL safety guard.

---

### Layer 11 — Infrastructure

**Database:** MongoDB (primary) + SQLite (fallback/alternative)
**Observability:** Langfuse (LLM trace emission)
**Tunneling:** ngrok / cloudflared (for remote access to local server)
**Deployment:** Render (backend), Vercel/GitHub Pages (frontend), Cloudflare Workers (remote admin SPA)
**CI/CD:** GitHub Actions (20+ workflows)

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Client Layer                                     │
│  Claude Code │ Cursor │ Aider │ Continue │ Telegram Bot │ Dashboard  │
└─────────────────────────────────────────────────────────────────────┘
         │                          │                  │
   OpenAI/Anthropic           Telegram API        React SPA
   Bearer Auth                                   JWT Auth
         │                                            │
         ▼                                            ▼
┌────────────────────┐                    ┌──────────────────────┐
│    proxy.py        │                    │  backend/server.py   │
│    :8000           │                    │  :8001               │
│  Auth + Rate Limit │                    │  Dashboard API       │
│  CORS + Routing    │                    │  Company Graph       │
└────────┬───────────┘                    │  Workflow Orchestr.  │
         │                               └──────────┬───────────┘
    ┌────┴─────────────────────┐                    │
    │      Request Routing     │                    │
    ├────────────┬─────────────┤                    │
    │            │             │                    │
    ▼            ▼             ▼                    │
 /v1/messages  /v1/chat   /api/chat                │
 Anthropic     OpenAI     Ollama Native            │
 compat        handlers   handlers                 │
    │            │             │                    │
    └────────────┴─────────────┘                    │
                 │                                  │
         ┌───────┴──────────┐                       │
         │  router/         │                       │
         │  ModelRouter     │                       │
         │  classify_task() │                       │
         │  health_check()  │                       │
         └───────┬──────────┘                       │
                 │                                  │
         ┌───────▼──────────┐              ┌────────▼──────────┐
         │     Ollama       │              │    MongoDB / SQLite │
         │  qwen3-coder     │              │    (persistence)   │
         │  deepseek-r1     │              └───────────────────┘
         └──────────────────┘
                 ▲
         ┌───────┴──────────┐
         │   agent/         │
         │   AgentRunner    │
         │   Plan→Execute   │
         │   →Verify loop   │
         └──────────────────┘
```

---

## Severity Matrix

| Component | Severity | Issue |
|-----------|----------|-------|
| `proxy.py` god file | Medium | 1719 lines — hard to navigate and test |
| In-memory rate limiter | High | Not distributed — breaks under horizontal scale |
| CORS defaults to `*` | High | Allows any origin in production |
| `test-key-` prefix on production keys | Medium | Confusing naming convention |
| Dual FastAPI apps | Medium | Split auth surface, operational complexity |
| CRA deprecated | Medium | Frontend build toolchain needs migration |
| No circuit breaker for Ollama | Medium | Repeated failures cascade |
| No sandbox for agent code writes | High | Arbitrary filesystem writes without isolation |
| MongoDB + SQLite dual-backend | Medium | Complexity, SQLite bugs documented |

---

## Priority Fixes

1. **[HIGH]** Add Cloudflare/nginx rate limiting layer — remove reliance on in-memory rate limiter for production
2. **[HIGH]** Tighten CORS in production — require explicit `CORS_ORIGINS` env var, no wildcard default
3. **[HIGH]** Add path-based sandbox enforcement for agent workspace writes (already partially done — need unit tests)
4. **[MEDIUM]** Decompose `proxy.py` into sub-routers (auth, admin, chat, agent endpoints)
5. **[MEDIUM]** Migrate frontend from CRA to Vite
6. **[MEDIUM]** Add circuit breaker pattern to Ollama health check / chat handler fallback
7. **[LOW]** Rename API key prefix from `test-key-` to a production-appropriate prefix
