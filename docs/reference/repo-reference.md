# Repository reference

> Facts about the system, moved out of `CLAUDE.md` on 2026-10-08 so the file every agent
> reads at session start holds the rules and the commands, not reference tables
> (AI-native SDLC playbook: keep CLAUDE.md short; anything stale costs context every session).
> These are facts, not instructions: the rules are `CLAUDE.md` §1–§2 and nowhere else.

---

## What this repo is

A **self-hosted, OpenAI-compatible AI proxy and multi-agent platform**. It sits in front
of Ollama and the cloud providers, adds Bearer-token auth, rate limiting, CORS and model
routing, runs a three-role plan→execute→verify agent loop over a fleet of specialist
agents, and serves a React dashboard for administration and company-graph management.
Langfuse observability, Telegram bot control, and GitHub integration are built in.

It is a product, not a framework, and not a SaaS. Every change is production-grade.

| | |
|---|---|
| Repository | `https://github.com/strikersam/autonomous-ai-agency` |
| Frontend | Cloudflare Worker — `https://autonomous-ai-agency.strikersam.workers.dev` |
| Backend | Render — `https://local-llm-server.onrender.com` (FastAPI, port 8001) |
| Database | MongoDB in production, SQLite in dev/CI |

The repository was previously named `local-llm-server`; older documents, PR links, and
the Render service name still carry that name.

---

## Architecture reference

### Deployment topology

```
        Cloudflare Worker (:443)          Serves the React SPA, proxies /api/*
                  │                       and /agent/* to Render, cron 1/min
                  ▼
        Render — backend/server.py        FastAPI :8001, MongoDB, Hermes
        FastAPI :8001                     in-process :8100, APScheduler,
                  │                       Telegram bot, 37 autonomous loops
        ┌─────────┼─────────┐
        ▼         ▼         ▼
     MongoDB   NVIDIA    Cloudflare
      Atlas      NIM       cron
```

`proxy.py` is a second FastAPI app on port 8000 exposing three API surfaces: OpenAI
`/v1/*`, Anthropic `/v1/messages`, and Ollama native `/api/*`.

### Providers

| Provider | Env var | Purpose |
|----------|---------|---------|
| NVIDIA NIM | `NVIDIA_API_KEY` | Free LLM (`nvidia/nemotron-3-super-120b-a12b`) |
| Cerebras | `CEREBRAS_API_KEY` | Fast LLM (`gpt-oss-120b`, paid tier — see CHANGELOG 2026-08-29) |
| Groq | `GROQ_API_KEY` | Free fast LLM (`openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.8-27b` — `deepseek-r1-70b` deprecated self-serve Aug 2026) |
| Anthropic | `ANTHROPIC_API_KEY` | Paid LLM (Claude) |
| Ollama | `OLLAMA_BASE` | Local LLM |
| GitHub / Google OAuth | `*_CLIENT_ID` / `*_CLIENT_SECRET` | Social login (`packages/auth/oauth.py`) |
| Telegram | `TELEGRAM_BOT_TOKEN` | Bot control (`telegram_bot.py`) |

Provider health and auto-failover live in `packages/ai/watchdog.py`; the failover
threshold is `BRAIN_WATCHDOG_MAX_FAILURES` (default 3). Runtime adapters (hermes, goose,
aider, and 8 others) are in `runtimes/adapters/`.

All secrets are stored as Render environment variables with `sync: false`, except
`CLOUDFLARE_API_TOKEN` and `RENDER_BACKEND_URL` which are GitHub Actions secrets, and
`GH_PAT` which is both.

### Auth flows

| Flow | Module | Token |
|------|--------|-------|
| Email/password | `backend/server.py` `/api/auth/login` | JWT (24h access + refresh) |
| GitHub / Google OAuth | `packages/auth/oauth.py`, `backend/server.py` | JWT |
| API key | `proxy.py` `verify_api_key` | Bearer |
| Service token | `packages/auth/service_token.py` | `X-Service-Token` |
| Admin session | `packages/auth/admin.py` | Session cookie |
| JWT validation | `handlers/v3_auth.py` | JWT |

Dependency chain: `get_optional_user` → `get_current_user` → `_require_admin`, with
`_user_or_service_token` for dual-auth endpoints.

### Agent loop

```
Directive → Planner → Executor → Verifier → Result
                ↑                      ↓
              Memory ←─────────────────┘
```

`agent/loop.py` drives it (`AgentRunner`); `agent/agency.py` coordinates the multi-agent
agency under a CEO; `agents/` holds 24 specialist profiles.

`agent/web_reach.py` gives every agent zero-key, read-only internet access —
`fetch_url`, `youtube_transcript`, `web_search`, `fetch_rss` — registered through
`agent/capability_registry.py` and advertised in `agent/prompts.py::build_tool_prompt`.
The Executor can call them mid-step. This is what makes closed-loop self-healing work:
`agent/self_healing.py` and `agent/improvement_loop.py` schedule their fixes through the
same Executor, so a fix can research an error or a changed dependency before writing the
patch. `agent/trend_watcher.py` covers the scheduled counterpart, scanning 13 public
sources. Rule 14 governs every URL any of this touches.

### Scheduler

`packages/scheduler/scheduler.py` wraps APScheduler over a durable store
(`packages/scheduler/store.py`). `force_cleanup()` runs on every cron tick and at
startup — this is deliberate, and it is what stops failed run-once tasks from
multiplying in the database.

---

## Bill of materials

Re-derived 2026-08-10. If you are reading this more than a few months later, re-run the
commands rather than trusting the numbers.

| Metric | Count | Command |
|--------|-------|---------|
| Python files | 901 | `find . -name '*.py' -not -path './.git/*' -not -path './node_modules/*' \| wc -l` |
| Python test files | 431 | `find tests -name 'test_*.py' \| wc -l` |
| Frontend JS/JSX | 102 | `find frontend/src -name '*.js' -o -name '*.jsx' \| wc -l` |
| Frontend test files | 14 | `find frontend/src -name '*.test.js' \| wc -l` |
| GitHub workflows | 41 | `ls .github/workflows/*.yml \| wc -l` |
| Loop registry entries | 37 | `python3 -c "import yaml;print(len(yaml.safe_load(open('loops/registry.yaml'))['loops']))"` |
| `backend/server.py` | 10,666 lines | `wc -l < backend/server.py` |
| `proxy.py` | 4,116 lines | `wc -l < proxy.py` |

The two largest files are both far past the 800-line limit in rule 28 and are being
migrated. Do not treat them as licence to add more; see `REWRITE_PLAN.md`.

---

## Environment variables

The full list is `docs/configuration-reference.md` and `.env.example`. The ones that
change behaviour most:

| Variable | Default | Purpose |
|----------|---------|---------|
| `STORAGE_BACKEND` | `mongo` | `mongo` or `sqlite` |
| `MONGO_URL` | — | Required in mongo mode |
| `OLLAMA_BASE` | `http://localhost:11434` | Ollama endpoint |
| `CORS_ORIGINS` | `*` | **Never `*` in production** (rule 41) |
| `RATE_LIMIT_RPM` | `60` | Per-key request limit |
| `AGENT_WORKSPACE_ROOT` | `.` | Agent filesystem sandbox root |
| `NVIDIA_DEFAULT_MODEL` | `nvidia/nemotron-3-super-120b-a12b` | Free NVIDIA NIM model |
| `AGENT_{PLANNER,EXECUTOR,VERIFIER,JUDGE}_MODEL` | `nvidia/nemotron-3-super-120b-a12b` | Per-role LLMs (judge falls back to the verifier's model) |
| `BRAIN_WATCHDOG_MAX_FAILURES` | `3` | Failover threshold |
| `ACTIVATION_REQUIRED` | `true` | `false` for self-hosted |
| `RUN_HERMES_IN_PROCESS` | `true` | Hermes on port 8100 |
| `TESTING` / `AGENCY_CEO_ENABLED` / `RUN_BACKGROUND_IN_WEB` | — | Test flags (rule 33) |

---
