# CLAUDE.md — Master Architect Operating Manual

> **This file is the permanent operating manual for every AI agent working in this repository.**
> Read it BEFORE making any change. Every PR must comply with the rules herein.
> This document supersedes agent-specific instructions wherever there is a conflict.

---

## Before you read any source file: query graphify

This repo ships a pre-built knowledge graph at `graphify-out/graph.json` (auto-refreshed by
`.claude/hooks/graphify-refresh` on every session start and turn). **Query it before opening
raw source files** — it costs a fraction of the tokens of a `Read`/`Grep` pass over the codebase:

```bash
graphify query "how does model routing work"
graphify explain "AgentRunner"
graphify path "OnboardingScreen" "CompanyGraphStore"
cat graphify-out/GRAPH_REPORT.md        # free overview: god nodes, communities, suggested questions
graphify update .                       # refresh after you make changes
```

If `graphify` isn't on `PATH`: `python -m pip install graphifyy && graphify install && graphify update .`
Full reference: [`AGENTS.md`](AGENTS.md#graphify-knowledge-graph).

---

## 0. The Golden Rule

**No user-visible behaviour may change unless explicitly requested.**

Every existing behaviour is production behaviour. Before touching code, capture inputs, outputs, API responses, and UI states. After refactor, everything must still behave identically. If not — rollback.

---

## 1. What This Repo Does

(Also: Executive Mission)

### What the platform is
Autonomous AI Agency is a **self-hosted, OpenAI-compatible AI proxy and multi-agent platform** that:
1. Sits in front of Ollama (local LLM inference) and cloud providers (NVIDIA NIM, Cerebras, Groq, Anthropic)
2. Adds Bearer-token auth, rate limiting, CORS, and intelligent model routing
3. Implements a three-role plan→execute→verify agent orchestration loop
4. Hosts a fleet of specialist agents (quality, finance, research, agile, etc.)
5. Serves a React dashboard for administration, monitoring, and company graph management
6. Provides Langfuse observability, Telegram bot control, and GitHub integration

### Production deployment
- **Frontend**: Cloudflare Worker at `https://autonomous-ai-agency.strikersam.workers.dev`
- **Backend**: Render at `https://local-llm-server.onrender.com` (FastAPI, port 8001)
- **Database**: MongoDB (production) / SQLite (dev/CI)
- **Repository**: `https://github.com/strikersam/autonomous-ai-agency`

### Non-goals
- Not a SaaS — this is a self-hosted platform
- Not a framework — it's a product
- Not a playground — every change must be production-grade

### Success metrics
- CI green on every PR
- Zero regression in user-visible behaviour
- Loop readiness score: 100/100 (Grade A) — currently achieved
- Cold start < 30 seconds
- Dashboard initial load < 3 seconds

---

## 2. Architectural Principles

1. **Never duplicate logic** — one source of truth per concern
2. **Configuration over code** — workflows, providers, and agents are data-driven
3. **Composition over inheritance** — mix in capabilities, don't extend base classes
4. **Feature modules** — each feature owns its code, tests, and docs
5. **Dependency inversion** — depend on abstractions, not implementations
6. **Event-driven communication** — components communicate via events, not direct calls
7. **Backward compatibility** — no breaking API changes without a migration path
8. **Incremental migration** — one subsystem at a time, behind feature flags
9. **No hidden coupling** — every dependency is explicit and importable
10. **Everything observable** — every action is logged, every decision is traceable
11. **Everything testable** — every feature has unit + integration tests
12. **Secrets never in code** — environment variables only, validated at startup

---

## 3. Repository Constitution

**The AI must never violate these rules. Violations are blocking.**

### Forbidden patterns
| Rule | Description |
|------|-------------|
| No new provider implementation may bypass `ProviderManager` | All LLM calls go through `provider_router.py` |
| No module may read environment variables directly | Use `brain_policy.py` or `services/brain_config_store.py` |
| No module may write secrets to disk | Secrets are env-only, never persisted |
| No frontend API calls outside `frontend/src/api.js` | All HTTP calls go through the shared axios instance |
| No scheduler logic inside workers | Scheduler decides, workers execute |
| No worker updates UI directly | Workers emit events, UI subscribes |
| No duplicate authentication | One auth system: `get_current_user` / `get_optional_user` |
| No duplicate models | One `BrainConfig` model in `services/brain_config_store.py` |
| No circular imports | Use lazy imports inside functions if needed |
| No `os.environ.get()` outside of config modules | Centralize in `brain_policy.py` / `app_settings.py` |

### Required patterns
| Rule | Description |
|------|-------------|
| Every new endpoint must have a test | In `tests/test_*.py` |
| Every new workflow must be in `loops/registry.yaml` | Loop-audit gate enforces this |
| Every PR must update `CHANGELOG.md` + `docs/changelog.md` | Changelog parity gate enforces this |
| Every PR must pass `compileall` | CI enforces this |
| Every provider must support `health()` + `cost()` | Provider interface contract |

---

## 4. Current Architecture (As-Is)

### Codebase Map

### Bill of Materials

| Metric | Count |
|--------|-------|
| Python files | 628 |
| JS/JSX files | 85 |
| YAML files | 258 |
| Test files (Python) | 297 |
| Test files (JS) | 17 |
| Dockerfiles | 11 |
| API endpoints (backend) | 125 |
| API endpoints (proxy) | 86 |
| Scheduled workflows | 21 |
| Loop registry entries | 34 |
| Root-level Python files | 38 |
| Top-level directories | 48 |
| External providers | 7+ (NVIDIA, Cerebras, Groq, Anthropic, Ollama, OpenRouter, Google) |

### Current folder structure (problematic)
```
/                     ← 38 root-level .py files (should be in packages)
backend/              ← Main FastAPI app (server.py is 8700+ lines)
proxy.py              ← Second FastAPI app (3400+ lines, port 8000)
agent/                ← 70 .py files (agent loop, tools, skills, repowise)
agents/               ← 24 .py files (specialist agent profiles)
services/             ← 48 .py files (brain, watchdog, digest, etc.)
runtimes/             ← 11 adapters (hermes, goose, aider, etc.)
router/               ← Model routing + classifier
frontend/             ← React SPA (85 files)
worker/               ← Cloudflare Worker (index.js)
tests/                ← 297 test files
```

### Deployment topology
```
                    ┌─────────────────────────────┐
                    │   Cloudflare Worker (:443)  │
                    │   - Serves React SPA        │
                    │   - Proxies /api/* to Render│
                    │   - Proxies /agent/*        │
                    │   - Cron trigger (1/min)    │
                    └──────────┬──────────────────┘
                               │ HTTPS
                    ┌──────────▼──────────────────┐
                    │   Render (backend/server.py)│
                    │   - FastAPI :8001           │
                    │   - 125 endpoints           │
                    │   - MongoDB (production)    │
                    │   - Hermes in-process :8100 │
                    │   - Telegram bot (optional) │
                    │   - APScheduler             │
                    │   - 34 autonomous loops     │
                    └──────────┬──────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
     ┌────────▼───┐   ┌───────▼────┐   ┌──────▼─────┐
     │  MongoDB   │   │ NVIDIA NIM │   │ Cloudflare │
     │  (MongoDB  │   │ (free LLM) │   │  Workers   │
     │   Atlas)   │   │            │   │  (cron)    │
     └────────────┘   └────────────┘   └────────────┘
```

### External providers
| Provider | Env var | Module | Purpose |
|----------|---------|--------|---------|
| NVIDIA NIM | `NVIDIA_API_KEY` | `provider_router.py`, `brain_policy.py` | Free LLM (meta/llama-3.3-70b-instruct) |
| Cerebras | `CEREBRAS_API_KEY` | `provider_router.py`, `brain_config_store.py` | Free fast LLM (qwen-3-coder-480b) |
| Groq | `GROQ_API_KEY` | `provider_router.py`, `brain_config_store.py` | Free fast LLM (deepseek-r1-70b) |
| Anthropic | `ANTHROPIC_API_KEY` | `provider_router.py` | Paid LLM (Claude) |
| Ollama | `OLLAMA_BASE` | `provider_router.py` | Local LLM |
| GitHub OAuth | `GITHUB_CLIENT_ID/SECRET` | `social_auth.py`, `backend/server.py` | Social login |
| Google OAuth | `GOOGLE_CLIENT_ID/SECRET` | `social_auth.py`, `backend/server.py` | Social login |
| Telegram | `TELEGRAM_BOT_TOKEN` | `telegram_bot.py` | Bot control |

### Secrets inventory
| Secret | Stored in | Used by |
|--------|-----------|---------|
| `NVIDIA_API_KEY` | Render env (sync: false) | `brain_policy.py`, `provider_router.py` |
| `CEREBRAS_API_KEY` | Render env (sync: false) | `brain_config_store.py` |
| `GROQ_API_KEY` | Render env (sync: false) | `brain_config_store.py` |
| `ANTHROPIC_API_KEY` | Render env (sync: false) | `provider_router.py` |
| `GITHUB_CLIENT_ID/SECRET` | Render env (sync: false) | `social_auth.py` |
| `GOOGLE_CLIENT_ID/SECRET` | Render env (sync: false) | `social_auth.py` |
| `TELEGRAM_BOT_TOKEN` | Render env (sync: false) | `telegram_bot.py` |
| `GH_PAT` | Render env + GitHub Actions secrets | `backend/server.py`, workflows |
| `JWT_SECRET` | Render env (generated) | `backend/server.py` |
| `ADMIN_PASSWORD` | Render env | `backend/server.py` |
| `SERVICE_TOKEN` | Render env | `services/service_token.py` |
| `CLOUDFLARE_API_TOKEN` | GitHub Actions secrets | `deploy-cloudflare.yml` |
| `RENDER_BACKEND_URL` | GitHub Actions secrets | `deploy-frontend.yml` |

---

## 5. AI Provider Architecture

### Current state
- `provider_router.py` (1400+ lines) handles multi-provider failover
- `brain_policy.py` resolves the recommended free-cloud brain
- `services/brain_config_store.py` persists brain config to MongoDB/SQLite
- `services/brain_watchdog.py` monitors provider health + auto-failover
- `runtimes/adapters/` has 11 runtime adapters (hermes, goose, aider, etc.)

### Provider interface contract
Every provider MUST expose:
```python
class Provider:
    def generate(self, prompt: str, **kwargs) -> str: ...
    def chat(self, messages: list[dict], **kwargs) -> dict: ...
    def stream(self, messages: list[dict], **kwargs) -> Iterator[str]: ...
    def health(self) -> dict: ...
    def cost(self, input_tokens: int, output_tokens: int) -> float: ...
    def limits(self) -> dict: ...
```

### Fallback chain
```
Cerebras (free, fast) → Groq (free, fast) → NVIDIA NIM (free, always-on) → Ollama (local)
```
- 429 → immediate failover + exponential backoff
- 410 → permanent removal + long cooldown
- 419 → per-model skip (try next model on same provider)
- Brain watchdog triggers after 3 consecutive failures

---

## 6. Agent Architecture

### Current state
- `agent/loop.py` — AgentRunner (plan → execute → verify)
- `agent/agency.py` — CEO-coordinated multi-agent agency
- `agents/` — 24 specialist agent profiles
- `agent/sam.py` — SAM voice agent
- `agent/voice.py` — Voice command interface (STT)

### Agent lifecycle
```
Directive → Planner → Executor → Verifier → Result
                ↑                      ↓
              Memory ←─────────────────┘
```

---

## 7. Scheduler Architecture

### Current state
- `agent/scheduler.py` — APScheduler wrapper with durable store
- `services/scheduler_store.py` — MongoDB/SQLite persistence
- 21 GitHub Actions workflows (cron-triggered)
- 34 loop registry entries
- `force_cleanup()` runs on every cron tick + startup

### Known issues (fixed)
- Schedule multiplication: run-once tasks that failed (NVIDIA 410) persisted in DB
- Fix: nuclear `delete_many` at startup + `force_cleanup()` on every tick

---

## 8. Authentication Architecture

### Auth flows
| Flow | Module | Token type |
|------|--------|------------|
| Email/password | `backend/server.py` `/api/auth/login` | JWT (24h access + refresh) |
| GitHub OAuth | `social_auth.py` + `backend/server.py` `/api/auth/github/*` | JWT |
| Google OAuth | `social_auth.py` + `backend/server.py` `/api/auth/google/*` | JWT |
| API key | `proxy.py` `verify_api_key` | Bearer token |
| Service token | `services/service_token.py` | `X-Service-Token` header |
| Admin session | `admin_auth.py` | Session cookie |

### Auth dependency chain
```
get_optional_user(request) → get_current_user(request) → _require_admin(user)
                                                    ↓
                                          _user_or_service_token(request)  ← N5 dual-auth
```

---

## 9. Coding Rules

See `ENGINEERING_STANDARDS.md` for full coding standards. Key rules:
- Max 50 lines per function
- Type hints on all Python functions
- No `import *` — explicit imports only
- No commented-out code
- No `print()` — use `logging`
- No `os.environ.get()` outside config modules

## 10. Testing Constitution

### Testing Expectations

### Test structure
| Level | Location | Runner | Count |
|-------|----------|--------|-------|
| Unit (Python) | `tests/test_*.py` | pytest | 297 |
| Unit (JS) | `frontend/src/__tests__/*.test.js` | Jest | 17 |
| E2E | `tests/e2e/` | standalone scripts | 10 |
| Playwright | `tests/e2e/test_*.py` | pytest + playwright | included above |

### Test rules
1. Every new endpoint must have at least one test
2. Every bug fix must include a regression test
3. Tests must be hermetic — no shared mutable state between tests
4. The `client` fixture is function-scoped + calls `reset_store()` to avoid motor event-loop binding
5. `AGENCY_CEO_ENABLED=false` + `RUN_BACKGROUND_IN_WEB=false` + `TESTING=true` in conftest

---

## 10. CI/CD Standards

### Pipeline (22 checks)
| Check | Purpose |
|-------|---------|
| Test (Python 3.13) | Full pytest with MongoDB |
| Frontend test + build | Jest + npm run build |
| Lint check | Python compileall + secret scan |
| Bandit SAST | Security analysis |
| CodeQL | Code security |
| Loop audit | Registry drift detection |
| Changelog check | docs/changelog.md must be modified |
| Changelog parity | CHANGELOG.md == docs/changelog.md |
| E2E live server | Integration tests |
| Playwright | Browser tests |
| Security Gate | No new Bandit alerts |

### Deployment
- Merge to `master` → Cloudflare Worker auto-deploys
- Render auto-deploys via webhook
- GitHub Pages auto-deploys via `deploy-frontend.yml`

---

## 11. Rewrite Strategy

### Phased approach
```
Phase 1: Architecture Discovery (this document) ← YOU ARE HERE
Phase 2: Target Architecture Design (ARCHITECTURE.md)
Phase 3: Engineering Standards (ENGINEERING_STANDARDS.md)
Phase 4: Migration Plan (REWRITE_PLAN.md)
Phase 5: Controlled Migration (one subsystem at a time)
Phase 6: Cleanup (remove dead code, archive obsolete modules)
```

### Rules
- Do NOT rewrite everything at once
- Every subsystem: characterization tests → architecture → migration → verification → cleanup
- Keep the application working after every merge
- Feature flags for new implementations
- Old code deleted only after new code is verified in production

---

## 12. Changelog Rule

Every PR must update `CHANGELOG.md` AND `docs/changelog.md` (parity enforced by CI).
The changelog-check workflow skips PRs with `chore:`, `docs:`, `ci:`, `test:`, `style:`, `revert:`, `build:` prefixes.
All other PRs must add an entry under `## [Unreleased]` in both files.

## 13. Autonomous Development Policy

Every PR must:
1. ✅ Update `CHANGELOG.md` + `docs/changelog.md` (parity)
2. ✅ Update tests (new behaviour → new test; bug fix → regression test)
3. ✅ Pass `compileall` (no syntax errors)
4. ✅ Pass `loop_registry audit --check` (if touching workflows)
5. ✅ Pass `check_changelog_parity.py` (if touching changelogs)
6. ✅ All CI checks green before merge
7. ✅ Squash-merge to master (keeps history clean)

### Before writing any code
> Act as the Architecture Guardian. Review the planned changes against this constitution. Reject any implementation that introduces duplicate logic, additional coupling, new configuration sources, inconsistent abstractions, hidden dependencies, or technical debt. Only after the proposed design complies with the constitution may implementation begin.

---

## Key Commands

```bash
# Development
uvicorn backend.server:app --reload --port 8001

# Tests — ALWAYS run before committing
pytest -x                                  # Fast fail
pytest -v                                  # Verbose

# Loop audit
python agent/loop_registry.py audit --check

# Changelog parity
python scripts/check_changelog_parity.py

# Syntax check
python -m compileall -q .

# Frontend
cd frontend && npm test -- --watchAll=false --forceExit
cd frontend && npm run build
```

## Environment Variables (production)

| Variable | Default | Purpose |
|----------|---------|---------|
| `STORAGE_BACKEND` | `mongo` | `mongo` or `sqlite` |
| `NVIDIA_DEFAULT_MODEL` | `meta/llama-3.3-70b-instruct` | Free NVIDIA NIM model |
| `ACTIVATION_REQUIRED` | `true` | Set `false` for self-hosted |
| `RUN_BACKGROUND_IN_WEB` | `true` | Set `false` in tests |
| `AGENCY_CEO_ENABLED` | `true` | Set `false` in tests |
| `TESTING` | (unset) | Set `true` in tests |
| `RUN_HERMES_IN_PROCESS` | `true` | Hermes server on port 8100 |
| `SERVICE_TOKEN` | (unset) | Telegram mutating control |
| `BRAIN_WATCHDOG_MAX_FAILURES` | `3` | Failover threshold |
