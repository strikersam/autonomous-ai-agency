<div align="center">

# Agency Core

### The autonomous AI platform for engineering teams — self-hosted, privacy-first, runs on your hardware.

[![Version](https://img.shields.io/badge/version-5.0.0-blue.svg)](https://github.com/strikersam/local-llm-server/releases/tag/v5.0.0)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/strikersam/local-llm-server/actions/workflows/ci.yml/badge.svg)](https://github.com/strikersam/local-llm-server/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.13-blue)](https://www.python.org/)

</div>

---

## What is Agency Core?

Agency Core is a **self-hosted autonomous AI platform** that turns your local GPU into a private team of AI specialists — a Dev Agent, a Release Agent, an Analyst, a Content writer, and a CEO orchestrator — all working together on real engineering and business tasks without sending your code or data to the cloud.

Point it at your codebase, describe what you want, and your agents will plan the work, write the code, open pull requests, handle approvals, and loop back to you only when a human decision is genuinely needed.

---

## Who is this for?

| You want… | Agency Core gives you… |
|-----------|------------------------|
| AI coding help without uploading code to OpenAI/Anthropic | Local LLMs (Qwen3-Coder, DeepSeek-R1) — your data never leaves your machine |
| A team of AI agents that can work autonomously overnight | CEO + specialist agent fleet with a structured task board and HITL approval gates |
| A drop-in OpenAI API for Cursor, Continue, Aider, Claude Code | `http://localhost:8000` — fully OpenAI-compatible with Bearer auth |
| Visibility into what your AI is doing and why | Langfuse observability, Logs screen, Agent job tracker |
| Admin control over who can use the AI and how much | Per-user role management, rate limiting, activation licensing |

---

## The Autonomous Agency — What your agents can do

Once onboarded, Agency Core runs a fleet of specialists orchestrated by a CEO agent. You talk to the CEO; it delegates to the right specialist and brings back results with evidence (PR links, test output, diffs).

### Out of the box your agents can:

**Development**
- Analyse a bug report, write a fix, open a PR, and wait for your approval before merging
- Run the full test suite, detect failures, and auto-fix the most common categories
- Perform a dependency audit and create a safe upgrade PR
- Review open PRs for security, performance, and correctness
- Generate and maintain API documentation from source code

**Content & Knowledge**
- Write SEO-optimised product descriptions from your catalogue
- Keep your internal wiki accurate — agents update docs when code changes
- Schedule weekly trend digests, changelogs, and release notes automatically

**Operations**
- Monitor CI/CD pipelines and alert you when something needs human attention
- Manage schedules, reminders, and recurring tasks
- Provide a real-time health dashboard for all running agents and runtimes

**Intelligence**
- Classify every incoming request and route it to the optimal local model (code → Qwen3-Coder, reasoning → DeepSeek-R1, fast replies → a smaller model)
- Build a company knowledge graph from your codebase, docs, and past decisions
- Run cost-vs-cloud analysis so you know the real TCO of every inference request

---

## How it works — From onboarding to autonomous work

### Step 1 — Onboard your instance

Open the web UI and run the 5-step setup wizard. You'll connect your Ollama instance (or the bundled one), generate your first API key, and configure which models to use for which tasks.

> 📸 _Screenshot: Setup wizard — model selection step_

### Step 2 — Describe your company

The Company screen is where Agency Core learns about your organisation. Paste your repo URL, describe your stack, and answer a short set of tailored questions. The system builds an internal knowledge graph that the agents use to give context-aware answers instead of generic ones.

> 📸 _Screenshot: Company screen — stack onboarding_

### Step 3 — Talk to your CEO agent

Open the Chat screen and describe what you want — in plain English, the same way you'd brief a senior engineer. The CEO agent breaks the request into a structured plan, assigns subtasks to the right specialist, and kicks off autonomous work.

> 📸 _Screenshot: Chat screen — CEO agent conversation_

### Step 4 — Watch the task board

Every agent job appears on the Task Board with live status: `queued → planning → executing → review → done`. You can drill into any task to see the plan, the steps taken, and the output produced.

> 📸 _Screenshot: Task Board — live agent jobs_

### Step 5 — Approve or redirect

When an agent needs a human decision — before merging a PR, before deploying to production, before sending an external message — it pauses and pings you. You approve, deny, or redirect, and the agent continues.

> 📸 _Screenshot: HITL approval gate_

---

## The V5 Control Plane — Screen by screen

| Screen | What it does |
|--------|-------------|
| **Dashboard** | Live health of all agents, runtimes, and recent activity at a glance |
| **Chat** | Conversational interface to the CEO agent; full history per session |
| **Task Board** | Kanban view of all agent jobs: queued, in-progress, awaiting approval, done |
| **Agents** | All registered specialist agents, their capabilities, and current workload |
| **Providers** | Connected LLM providers (Ollama, Bedrock, NIM) with health status and cost |
| **Runtimes** | Execution substrates — local Docker, internal loop, external harness |
| **Knowledge** | Internal wiki built and maintained by agents from your code and docs |
| **Schedules** | Recurring agent tasks — daily digests, weekly audits, CI monitors |
| **Skills** | The agent skill library — what each agent knows how to do |
| **Intelligence** | Routing policy editor — control which model handles which task type |
| **Logs** | Full trace of every LLM call, token count, latency, and cost |
| **Company** | Your organisation profile, stack description, and knowledge graph seed |
| **Admin** | User management, role assignment, instance activation, audit log |
| **Doctor** | Self-diagnostics — checks all dependencies, connectivity, and config |

> 📸 _Screenshot: Dashboard screen — full control plane_

---

## Quickstart

### Prerequisites

- Python 3.13+
- [Ollama](https://ollama.com/) running locally with at least one model pulled (e.g. `ollama pull qwen2.5-coder:7b`)
- Node 20+ (for the web UI)

### 1. Clone and install

```bash
git clone https://github.com/strikersam/local-llm-server.git
cd local-llm-server
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — set OLLAMA_BASE_URL, SECRET_KEY, MONGO_URL (or STORAGE_BACKEND=sqlite)
```

### 3. Start the server

```bash
uvicorn proxy:app --reload --port 8000
```

### 4. Open the UI

Visit [http://localhost:8000/v5](http://localhost:8000/v5) — the setup wizard will guide you through the rest.

### 5. Connect your AI coding tools

Point any OpenAI-compatible tool at `http://localhost:8000` with your generated API key:

```json
// Cursor — settings.json
{
  "cursor.ai.openaiBaseUrl": "http://localhost:8000",
  "cursor.ai.openaiApiKey": "your-api-key-here"
}
```

See [`client-configs/`](client-configs/) for Aider, Continue, Zed, VSCode, and Claude Code examples.

---

## Architecture in brief

```
┌─────────────────────────────────────────────────────┐
│  Web UI (React, /v5)          Remote Admin (Vercel) │
└────────────────────┬────────────────────────────────┘
                     │ HTTP / WebSocket
┌────────────────────▼────────────────────────────────┐
│  proxy.py  —  FastAPI, JWT auth, rate limiting       │
│  ├─ /v1/chat/completions  (OpenAI-compatible)        │
│  ├─ /api/chat/send         (Agency Core chat)        │
│  ├─ /api/agent/*           (job management)          │
│  └─ /api/activation/*      (licensing / users)       │
├─────────────────────────────────────────────────────┤
│  ModelRouter  —  task classification → model hint    │
│  ├─ Code tasks    → qwen3-coder                      │
│  ├─ Reasoning     → deepseek-r1                      │
│  └─ Fast replies  → smallest capable model           │
├─────────────────────────────────────────────────────┤
│  AgentRunner  —  plan → execute → verify loop        │
│  ├─ CEO agent (orchestrator)                         │
│  ├─ Dev / Release / Content / Analytics specialists  │
│  └─ HITL gates (approve / deny / redirect)           │
├─────────────────────────────────────────────────────┤
│  Runtimes  —  where agent code runs                  │
│  ├─ Internal loop (in-process, fast)                 │
│  └─ Docker agent (isolated, production-safe)         │
├─────────────────────────────────────────────────────┤
│  Storage  —  MongoDB (default) · SQLite (optional)   │
│  Observability  —  Langfuse traces + local cost model│
└─────────────────────────────────────────────────────┘
```

---

## Configuration reference

| Environment variable | Default | Description |
|---------------------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Where Ollama is listening |
| `SECRET_KEY` | *(required)* | JWT signing key — generate with `openssl rand -hex 32` |
| `MONGO_URL` | `mongodb://localhost:27017` | MongoDB connection string |
| `STORAGE_BACKEND` | `mongo` | Set to `sqlite` for zero-dependency storage |
| `LANGFUSE_HOST` | *(optional)* | Enable Langfuse observability |
| `LANGFUSE_PUBLIC_KEY` | *(optional)* | Langfuse project public key |
| `LANGFUSE_SECRET_KEY` | *(optional)* | Langfuse project secret key |
| `TELEGRAM_BOT_TOKEN` | *(optional)* | Enable Telegram remote control |
| `RENDER_BACKEND_URL` | *(optional)* | Public URL for the deployed backend (Render) |
| `ADMIN_EMAIL` | *(optional)* | First admin user — created on first boot |

Full variable list: [`docs/configuration.md`](docs/configuration.md)

---

## Deployment

### Local (development)
```bash
uvicorn proxy:app --reload --port 8000
```

### Docker (production)
```bash
docker build -f Dockerfile.backend -t agency-core-backend .
docker run -p 8000:8000 --env-file .env agency-core-backend
```

### Render + GitHub Pages (cloud)
Push to `master` — GitHub Actions automatically:
1. Builds and deploys the backend to Render
2. Builds the React frontend and deploys to GitHub Pages

Set `RENDER_DEPLOY_HOOK_URL` and `RENDER_BACKEND_URL` in your repository secrets.

---

## Development

```bash
# Run tests
pytest -x                    # fast-fail
pytest -v                    # verbose

# Activate git hooks (blocks commits without changelog entries)
git config core.hooksPath .claude/hooks

# Run the AI session watchdog
python scripts/ai_runner.py start
```

See [`CLAUDE.md`](CLAUDE.md) for the full contributor guide, skill map, and risky-module policy.

---

## Security

- All secrets via environment variables — nothing hardcoded
- Ed25519 instance activation signatures
- RBAC with three roles: `user`, `power_user`, `admin`
- Bearer token auth on all API endpoints
- Audit log for all admin actions
- Bandit SAST + CodeQL + secret scanning on every push

Found a vulnerability? Open a [security advisory](https://github.com/strikersam/local-llm-server/security/advisories/new).

---

## Roadmap

| Phase | Status | What |
|-------|--------|------|
| Phase 1 — Typed agent contract | ✅ Done | `AgentJobRequest` Pydantic contract, E2E tests |
| Phase 2 — ModelRouter wiring | ✅ Done | Single router for all request types |
| Phase 3 — One backend (SQLite) | 🔄 In progress | Drop Mongo from hot path, fold backends |
| Phase 4 — One runtime | 📋 Planned | Consolidate `runtimes/` + `agent/loop.py` |
| Phase 5 — Doctor + resilience | 📋 Planned | `/api/doctor`, partial-failure-tolerant UI |
| Phase 6 — Workflow engine | 📋 Planned | Persisted state machine, safe CEO agency |
| Phase 7 — Onboarding engine | 📋 Planned | URL → stack inference → specialist provisioning |

---

## License

MIT — see [LICENSE](LICENSE)

---

<div align="center">
<sub>Built for engineers who want the power of frontier AI without the cloud bill or the privacy compromise.</sub>
</div>
