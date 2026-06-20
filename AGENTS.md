# AGENTS.md — Source of Truth for All AI Agents

> **This file is the authoritative operating guide for every AI agent working in this repository.**
> All agents MUST read this file before starting work. It supersedes agent-specific instructions
> wherever there is a conflict.

---

## Repository Purpose

`local-llm-server` (Agency Core v5) is a **self-hosted, OpenAI-compatible AI proxy and multi-agent platform** that:

1. Sits in front of Ollama (local LLM inference) and exposes three API surfaces: OpenAI `/v1/*`, Anthropic `/v1/messages`, Ollama native `/api/*`
2. Adds Bearer token authentication, rate limiting, CORS, and intelligent model routing
3. Implements a three-role plan→execute→verify agent orchestration loop
4. Hosts a fleet of specialist agents (quality, finance, research, agile, etc.)
5. Serves a React dashboard for administration, monitoring, and company graph management
6. Provides Langfuse observability, Telegram bot control, and GitHub integration

**Production URL:** `https://local-llm-server.strikersam.workers.dev`
**Primary Owner:** strikersam@gmail.com

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│ Client: Claude Code / Cursor / Aider / Continue / Telegram / SPA    │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ HTTP (OpenAI / Anthropic / Ollama format)
                    Bearer Auth / JWT
                           │
            ┌──────────────▼──────────────┐
            │    proxy.py (FastAPI :8000)  │
            │  Auth → Rate Limit → Route   │
            └──────────────┬──────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    /v1/messages    /v1/chat/completions    /api/*
    Anthropic compat  OpenAI handlers    Ollama native
         │                 │                 │
         └─────────────────┼─────────────────┘
                           │
                  ┌────────▼──────────┐
                  │   router/          │
                  │   ModelRouter      │
                  │   classify_task()  │
                  └────────┬──────────┘
                           │
               ┌───────────▼───────────┐
               │        Ollama          │
               │   qwen3-coder:30b      │
               │   deepseek-r1:32b      │
               └───────────────────────┘
                           ▲
               ┌───────────┴───────────┐
               │   agent/AgentRunner    │
               │   Plan→Execute→Verify  │
               └───────────────────────┘
```

**Secondary backend:** `backend/server.py` (FastAPI :8001) — Dashboard API, Company Graph, Onboarding, Workflow Orchestrator, Secrets, Skills.

---

## Codebase Map

| Path | Purpose | LOC | Risk |
|------|---------|-----|------|
| `proxy.py` | Main entry point, auth, rate limit, routing | 1,719 | HIGH |
| `chat_handlers.py` | OpenAI/Ollama streaming handlers | 710 | Medium |
| `direct_chat.py` | Direct chat sessions, intent classification | 833 | Medium |
| `provider_router.py` | Multi-provider backend with fallback | 1,238 | Medium |
| `admin_auth.py` | Admin session auth (Windows + secret) | 154 | **RISKY** |
| `key_store.py` | API key CRUD, SHA-256 hashing, JSON persistence | 244 | **RISKY** |
| `langfuse_obs.py` | Langfuse trace emission | ~300 | Low |
| `rbac.py` | Role-based access control | ~400 | HIGH |
| `social_auth.py` | GitHub/Google OAuth | ~400 | HIGH |
| `agent/loop.py` | AgentRunner — plan/execute/verify loop | 1,122 | **RISKY** |
| `agent/tools.py` | WorkspaceTools — filesystem read/write | ~200 | **RISKY** |
| `agent/repowise.py` | RepowiseIntelligence — codebase analysis | 866 | Low |
| `router/model_router.py` | ModelRouter — central routing logic | ~400 | HIGH |
| `router/classifier.py` | Task classification | ~300 | Medium |
| `router/registry.py` | Model capability registry | ~400 | Medium |
| `handlers/anthropic_compat.py` | Anthropic API adapter | 708 | Medium |
| `backend/server.py` | Dashboard API server | 6,487 | HIGH |
| `services/workflow_orchestrator.py` | Workflow execution engine | 1,119 | HIGH |
| `services/company_graph_store.py` | Company knowledge graph persistence | 1,660 | Medium |
| `services/scanner.py` | Tech stack scanner (Playwright) | 1,377 | Medium |

---

## Coding Standards

All code in this repository MUST follow these standards. No exceptions.

### 1. Language & Runtime
- Python 3.13+ (no backports, no compatibility hacks)
- Type annotations on ALL public functions and methods
- Use `from __future__ import annotations` at top of every module

### 2. Async
- ALL I/O operations must be `async`
- FastAPI handlers must be `async def`
- Agent methods must be `async def`
- No blocking I/O in async context (no `requests.get()`, no `open()` without `aiofiles`)
- Exception: `WorkspaceTools` which uses sync file I/O (legacy, do not add new sync I/O)

### 3. Data Models
- Pydantic v2 models for ALL API request/response shapes
- No raw `dict` as function return types for external-facing data
- Use `Field(...)` with description, min/max constraints for all public schema fields

### 4. Logging
- Use `log = logging.getLogger("qwen-proxy")` at module level
- Use `logging`, never `print`
- Never log sensitive values (API keys, tokens, passwords, email addresses)
- Log at `INFO` for normal operations, `WARNING` for degraded states, `ERROR` for failures

### 5. Error Handling
- Never expose internal error details to API clients
- Use `HTTPException(status_code=..., detail="generic message")` + `log.exception()`
- Never catch and swallow exceptions silently

### 6. Security
- No hardcoded secrets, tokens, or keys in source code
- All config from environment variables
- API keys must be hashed before storage (SHA-256 is acceptable for key lookup)
- Admin secrets must not be logged, even partially

### 7. Comments
- Default to writing NO comments
- Only add a comment when the WHY is non-obvious (hidden constraint, workaround, invariant)
- Never write comments that describe WHAT the code does (use self-documenting names instead)

### 8. File Size
- No file should exceed 800 lines without architectural justification
- If a file exceeds 800 lines, create a decomposition issue before adding more code

---

## Security Requirements

### Must-Have for Every Change

1. **Auth checks**: Every new endpoint must use `verify_api_key` (for API surfaces) or `_get_admin_identity_from_request` (for admin surfaces). No unauthenticated endpoints except `/health`, `/version`, and `/api/doctor/public`.

2. **Input validation**: All user-provided data must be validated with Pydantic before use. Never use raw request body strings in business logic.

3. **No command injection**: subprocess calls must use list form — never `shell=True` with user-supplied data.

4. **Filesystem safety**: Agent-driven file writes must go through `WorkspaceTools._resolve_path()` which enforces workspace boundaries.

5. **Secrets in env**: If a new feature requires an API key or secret, document the env var in `docs/configuration-reference.md` and add it to `.env.example`.

### Risky Module Review Required

Before modifying ANY of these, invoke the `risky-module-review` skill:

| Module | Risk |
|--------|------|
| `admin_auth.py` | Session auth, cookie signing |
| `key_store.py` | API key storage, hash operations |
| `agent/tools.py` | Filesystem write surface |
| `proxy.py` (lines 195-292) | Auth middleware |
| `handlers/v3_auth.py` | JWT validation |
| `rbac.py` | Permission enforcement |
| `social_auth.py` | OAuth flows |

---

## Testing Requirements

### Mandatory Rules

1. **Run `pytest -x` before every commit.** The commit-msg hook will check for changelog updates but tests must pass before pushing.

2. **New features require new tests.** No PR merges without test coverage for the new code path.

3. **Bug fixes require regression tests.** Reproduce the bug in a failing test, then fix it, then verify the test passes.

4. **Coverage must not decrease.** Current estimated baseline: ~65%. Target: 80%.

5. **Test organization:**
   - Unit tests: `tests/test_<module_name>.py`
   - Integration tests: `tests/test_<feature>_integration.py`
   - E2E tests: `tests/e2e/`
   - Live/external tests (require credentials): mark with `@pytest.mark.live`

6. **No placeholder tests.** A test function body that is only `pass` fails review.

### Running Tests

```bash
# Standard — run before every push
pytest -x

# Verbose
pytest -v --tb=short

# Specific module
pytest -x tests/test_model_router.py

# With coverage
pytest --cov=. --cov-report=term-missing --cov-fail-under=70

# Skip live tests (default in CI)
pytest -x --ignore=tests/test_hardware.py --ignore=tests/test_backend_runtime_bootstrap.py

# Agent-specific tests
pytest -x tests/test_agent_runner.py tests/test_agent_tools.py
```

---

## Documentation Requirements

1. **Update `docs/changelog.md`** as part of every meaningful commit. See CLAUDE.md for changelog format.

2. **Update module-level CLAUDE.md** when changing module contracts, adding new tools, or modifying invariants.

3. **Update `docs/configuration-reference.md`** when adding new environment variables.

4. **Update `docs/api-surfaces.md`** when adding new API endpoints.

5. **Never let documentation lag implementation.** If you change behavior, update docs in the same PR.

---

## Deployment Process

### Local Development

```bash
# Activate virtualenv
source .venv/bin/activate

# Start proxy (port 8000) — for AI tools
uvicorn proxy:app --reload --port 8000

# Start backend (port 8001) — for dashboard
uvicorn backend.server:app --reload --port 8001

# Run tests
pytest -x
```

### Production

| Service | Platform | URL | Trigger |
|---------|----------|-----|---------|
| Proxy + Backend | Render | https://relay.example.com | Push to `master` |
| Frontend SPA | Vercel | (configured per deployment) | Push to `master` |
| Remote Admin | Cloudflare Workers | https://local-llm-server.strikersam.workers.dev | `wrangler deploy` |
| Static Site | GitHub Pages | (GitHub Pages URL) | Push to `gh-pages` |

### Deploy Backend

Push to `master` → `deploy-backend.yml` → Render redeploys automatically.

### Deploy Frontend

Push to `master` → `deploy-frontend.yml` → Vercel redeploys automatically.

---

## Release Process

1. Move `## [Unreleased]` to `## [vX.Y.Z] — YYYY-MM-DD` in `docs/changelog.md`
2. Run `pytest` — must be green
3. `git tag vX.Y.Z && git push origin vX.Y.Z`
4. CI runs on the tag; deployment to production is triggered
5. See `docs/runbooks/release.md` for the full checklist

---

## Monitoring Standards

### Health Checks

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /health` | None | Process liveness |
| `GET /api/doctor/public` | None | System-level checks (5 checks) |
| `GET /api/doctor/diagnostics` | JWT | Authenticated diagnostics (5 checks) |
| `GET /api/ping` | JWT | Backend liveness |
| `GET /api/status` | JWT | System status summary |

### Observability Stack

- **LLM traces:** Langfuse (`LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` required)
- **Error tracking:** Sentry (add `SENTRY_DSN` to env when configured)
- **Uptime monitoring:** Configure external monitoring for `/health` endpoints
- **Logs:** `LOG_LEVEL` env var controls verbosity (default: INFO)

### Alerts — What Should Wake You Up

- Any 5xx error rate >1% over 5 minutes
- Ollama health check failing for >60 seconds
- Agent session stuck (no progress for >10 minutes)
- Rate limit bucket near capacity (>80% of max keys)
- Memory usage >85%

---

## Bug Triage Process

1. **Reproduce** the bug locally (write a failing test if possible)
2. **Identify** the affected module and severity:
   - P0: Production down / data loss / security breach
   - P1: Major feature broken, no workaround
   - P2: Feature degraded, workaround exists
   - P3: Minor UX issue or edge case
3. **Assign** to appropriate subagent (Security, QA, Bug Fix)
4. **Fix** in a feature branch following coding standards
5. **Add regression test** before fixing
6. **Update changelog** and submit PR
7. For P0/P1: bypass changelog requirement, fix directly, document after

---

## PR Review Checklist

Every PR MUST meet all of these criteria before merge:

### Code Quality
- [ ] Type annotations on all public functions
- [ ] No hardcoded secrets or API keys
- [ ] No `print()` statements (use `logging`)
- [ ] No raw `dict` returns for API shapes (use Pydantic)
- [ ] No blocking I/O in async handlers
- [ ] File size under 800 lines (or justified)

### Security
- [ ] New endpoints have auth guards
- [ ] User input validated with Pydantic
- [ ] Risky modules reviewed (if applicable)
- [ ] No new CVEs introduced (pip-audit passes)

### Testing
- [ ] `pytest -x` passes
- [ ] New tests added for new functionality
- [ ] Regression test for any bug fix
- [ ] No placeholder (`pass`) tests

### Documentation
- [ ] `docs/changelog.md` updated under `[Unreleased]`
- [ ] Env vars documented if added
- [ ] API endpoints documented if added
- [ ] Module CLAUDE.md updated if contracts changed

### CI
- [ ] All GitHub Actions checks pass
- [ ] No new lint warnings
- [ ] Frontend builds successfully (if frontend changed)

---

## Definition of Done

A task is **Done** when:

1. ✅ Code is written, follows coding standards, has type annotations
2. ✅ Tests pass (`pytest -x` green)
3. ✅ New tests exist for the new/changed behavior
4. ✅ `docs/changelog.md` updated
5. ✅ PR review checklist complete
6. ✅ Branch merged to `master`
7. ✅ Deployment verified (for production changes)
8. ✅ Documentation updated (for user-visible changes)

---

## Autonomous Maintenance Rules

When operating in autonomous maintenance mode, agents MUST:

1. **Read before modifying.** Always read the current file before editing. Never assume content.
2. **Query graphify first.** Use `graphify query "..."` before opening source files — 30x token savings.
3. **Run baseline tests.** `pytest -x` before any change. If baseline is broken, report before fixing.
4. **Scope changes tightly.** Fix only what is requested. Do not refactor or clean up adjacent code unless explicitly asked.
5. **Update state after milestones.** Write to `.claude/state/` after completing significant steps.
6. **Commit incrementally.** Prefer small commits over large multi-change commits.
7. **Never force-push.** Use rebase-merge or regular merge. Never force-push to `master`.
8. **Never bypass CI.** Do not use `--no-verify` or skip hooks. If CI is broken, fix the root cause.
9. **Escalate uncertainty.** If a change may affect auth, billing, or agent filesystem writes, stop and ask before proceeding.

---

## Agent Escalation Rules

Autonomous agents MUST stop and request human review when:

1. Modifying any **RISKY MODULE** (see list above)
2. Discovering a **P0 security vulnerability** (immediate escalation)
3. A change affects **>5 files** in a core module (proxy.py, router/, agent/loop.py)
4. Tests are **consistently failing** and root cause is unclear after 2 attempts
5. A dependency upgrade introduces a **breaking change**
6. The change requires a **database migration**
7. The change requires modifying **GitHub Actions workflow** permissions
8. Uncertainty about whether a change **breaks backward compatibility**

---

## Production Safety Rules

These rules protect production deployments:

1. **Never merge to `master` without passing CI.** No exceptions.
2. **Never deploy to production without testing locally first.**
3. **Feature flags for risky features.** Gate new agent capabilities behind env vars.
4. **Database changes must be backward-compatible.** Old code must work with new schema.
5. **API changes must be backward-compatible.** Old clients must continue to work.
6. **Secrets are never in code.** Not even in test files. Use `pytest` fixtures for test secrets.
7. **Rate limits must be configured.** Never deploy without `RATE_LIMIT_RPM` set.
8. **CORS must be restricted.** Set `CORS_ORIGINS` explicitly. Never use `*` in production.

---

## Subagent Roles & Responsibilities

| Agent | Scope | Primary Tools | Escalates To |
|-------|-------|--------------|--------------|
| **Security Agent** | Vulnerability scanning, auth review, CVE monitoring, dependency audit | `risky-module-review`, `security-review`, `dependency-audit` | Human on P0/P1 |
| **QA Agent** | Test coverage, regression detection, test authoring, CI monitoring | `test-first-executor`, `council-review` | Bug Fix Agent |
| **Architecture Agent** | Code structure, technical debt, module boundaries, ADR authoring | `implementation-planner`, `modularity-review` | Human for large refactors |
| **DevOps Agent** | CI/CD workflows, Docker, Render/Vercel deployment, monitoring | `release-readiness`, `docs-sync` | Human for infra changes |
| **Documentation Agent** | README, CHANGELOG, API docs, runbooks, CLAUDE.md sync | `docs-sync`, `changelog-enforcer` | Architecture Agent |
| **Bug Fix Agent** | Reproduce, isolate, fix, test, PR for reported bugs | `test-first-executor`, `risky-module-review` | Security Agent for security bugs |

---

## Graphify Knowledge Graph

**Always query graphify before opening source files.**

```bash
# Query the knowledge graph (70x cheaper than reading source files)
graphify query "how does model routing work"
graphify explain "AgentRunner"
graphify query "where are API keys stored"

# Read the graph report (free overview)
cat graphify-out/GRAPH_REPORT.md

# Refresh the graph after code changes
graphify update .
```

If graphify is not installed:
```bash
python -m pip install graphifyy && graphify install && graphify update .
```

---

## State Persistence

Agents MUST write checkpoints after significant milestones:

| File | Content | Update When |
|------|---------|-------------|
| `.claude/state/agent-state.json` | Machine-readable session state | After each major step |
| `.claude/state/NEXT_ACTION.md` | Next step description | Before ending session |
| `.claude/state/checkpoint.jsonl` | Ordered step log | After each completed step |
| `.claude/state/session.log` | Activity log | Continuously |
| `.claude/state/runner.lock` | Active session lock | On start/stop |

---

## Quick Reference — Key Commands

```bash
# Development
source .venv/bin/activate
uvicorn proxy:app --reload --port 8000
uvicorn backend.server:app --reload --port 8001

# Testing
pytest -x                                          # Fast fail
pytest -v --tb=short                               # Verbose
pytest --cov=. --cov-report=term-missing           # With coverage
pytest -x tests/test_model_router.py               # Single file

# AI Runner
python scripts/ai_runner.py manifest               # List tools/commands
python scripts/ai_runner.py status                 # Session state
python scripts/ai_runner.py resume                 # Resume interrupted work

# Knowledge graph
graphify query "<question>"
graphify update .

# Key management
python generate_api_key.py

# Git hooks
git config core.hooksPath .claude/hooks            # Activate hooks
```

---

## Environment Variables — Critical Ones

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `OLLAMA_BASE` | `http://localhost:11434` | Yes | Ollama endpoint |
| `PROXY_PORT` | `8000` | No | Proxy listen port |
| `API_KEYS` | `` | Yes* | Comma-separated API keys (legacy) |
| `KEYS_FILE` | `` | Yes* | Path to keys.json (persistent store) |
| `ADMIN_SECRET` | `` | No | Admin dashboard secret (min 32 chars) |
| `CORS_ORIGINS` | `*` | Yes (prod) | CORS allowed origins — NEVER use `*` in prod |
| `RATE_LIMIT_RPM` | `60` | No | Requests per minute per key |
| `AGENT_PLANNER_MODEL` | `nvidia/nemotron-3-super-120b-a12b` | No | Planner LLM (reasoning-tuned 120B-a12b MoE on free NIM) |
| `AGENT_EXECUTOR_MODEL` | `nvidia/llama-3.3-nemotron-super-49b-v1` | No | Executor LLM (dense 49B, JSON-clean tool-calling) |
| `AGENT_VERIFIER_MODEL` | `nvidia/nemotron-3-super-120b-a12b` | No | Verifier LLM |
| `AGENT_JUDGE_MODEL` | `nvidia/nemotron-3-super-120b-a12b` | No | Judge LLM (release-gate verdict) |
| `STORAGE_BACKEND` | `mongo` | No | `mongo` or `sqlite` |
| `MONGO_URL` | `` | Yes (mongo mode) | MongoDB connection string |
| `LANGFUSE_PUBLIC_KEY` | `` | No | Langfuse observability |
| `LANGFUSE_SECRET_KEY` | `` | No | Langfuse observability |
| `ANTHROPIC_API_KEY` | `` | No | Anthropic fallback provider |
| `AGENT_WORKSPACE_ROOT` | `.` | Yes (prod) | Agent filesystem sandbox root |
| `GITHUB_TOKEN` | `` | No | GitHub API token for agent GitHub tools |
| `LOG_LEVEL` | `INFO` | No | Logging verbosity |

*At least one of `API_KEYS` or `KEYS_FILE` must be configured.

---

## Further Reading

| Topic | Location |
|-------|----------|
| Operating guide | `CLAUDE.md` |
| Architecture overview | `docs/architecture/overview.md` |
| Model routing | `docs/architecture/model-routing.md`, `router/CLAUDE.md` |
| Agent orchestration | `docs/architecture/agent-orchestration.md`, `agent/CLAUDE.md` |
| Configuration | `docs/configuration-reference.md` |
| Runbooks | `docs/runbooks/` |
| Changelog | `docs/changelog.md` |
| ADRs | `docs/adrs/` |
| Audit documents | `audit/` |
