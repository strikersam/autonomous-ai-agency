<div align="center">

# Agency Core

### The autonomous AI platform for engineering teams — self-hosted, privacy-first, runs anywhere.

[![Version](https://img.shields.io/badge/version-5.0.0-blue.svg)](https://github.com/strikersam/local-llm-server/releases/tag/v5.0.0)
[![CI](https://github.com/strikersam/local-llm-server/actions/workflows/ci.yml/badge.svg)](https://github.com/strikersam/local-llm-server/actions/workflows/ci.yml)
[![Deploy](https://github.com/strikersam/local-llm-server/actions/workflows/deploy-backend.yml/badge.svg)](https://github.com/strikersam/local-llm-server/actions/workflows/deploy-backend.yml)
[![Python](https://img.shields.io/badge/python-3.13-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**[Live Demo](https://strikersam.github.io/local-llm-server/) · [API Docs](https://local-llm-server.onrender.com/docs) · [Changelog](docs/changelog.md)**

</div>

---

## What is Agency Core?

Agency Core is a **self-hosted autonomous AI platform** that turns any server — your laptop, a $10 VPS, or a GPU box — into a private AI team. It ships a CEO orchestrator agent and a fleet of domain specialists that work together on real engineering and business tasks: writing code, opening pull requests, running tests, updating docs, and managing recurring operations — all without sending your data to the cloud.

At its core it is also a **drop-in OpenAI-compatible proxy** for Ollama, so Cursor, Continue, Aider, Claude Code, and any other AI coding tool can point at `http://localhost:8000` and use your local models through a single authenticated endpoint.

---

## Why self-hosted autonomous agents?

| The problem | What Agency Core does instead |
|---|---|
| Frontier AI tools upload your code to third-party servers | Everything runs on hardware you control; data never leaves your perimeter |
| ChatGPT / Copilot give one-shot answers, not persistent work | Agents plan, execute, verify, and loop back only when a human decision is needed |
| Managing multiple AI tools means multiple accounts, keys, and bills | One platform, one API key, one dashboard — unlimited local inference |
| AI "agents" are demo toys that can't commit code or open PRs | Full git integration: branch → commit → PR → CI watch → HITL approval gate → merge |
| No visibility into what the AI did or why | Langfuse observability: every LLM call, token count, latency, cost, and decision trace |
| Cloud AI pricing scales with usage — costs explode at team scale | Marginal inference cost is electricity; scale a 50-person team for the same server bill |

---

## The autonomous agency — what your agents can do

Once onboarded, Agency Core runs a fleet of specialists coordinated by a CEO agent. You describe what you want in plain English; the CEO decomposes it into a structured plan, assigns subtasks to the right specialist, and returns results with evidence — PR links, test output, diffs, and reasoning traces.

### Engineering agents

- **Bug fixing**: analyse a bug report, write a fix, open a PR, watch CI, wait for your approval before merging
- **Dependency audit**: scan for CVEs, create a safe upgrade PR with passing tests
- **Code review**: check any PR for security holes, N+1 queries, missing error handling, and injection risks
- **Test generation**: write unit and integration tests for new or existing code
- **Refactoring**: identify tech debt hotspots, propose a refactor plan, execute on approval
- **Release management**: bump version, draft changelog, tag, verify CI, open the release PR
- **Documentation**: keep API docs, architecture records, and runbooks in sync with code changes

### Content & knowledge agents

- Write product descriptions, blog posts, or wiki articles from a brief
- Keep your internal knowledge base accurate — agents update docs when code changes
- Summarise and classify incoming GitHub issues, Slack threads, and support tickets
- Schedule weekly trend digests and release notes automatically

### Operations agents

- Monitor CI/CD pipelines and alert you when something needs a human decision
- Manage recurring schedules: daily summaries, weekly audits, on-call handoffs
- Classify every request to the optimal local model (code → Qwen3-Coder, reasoning → DeepSeek-R1)
- Provide real-time health diagnostics for all running agents, runtimes, and providers

---

## From onboarding to autonomous work — step by step

### Step 1 — Boot and activate

Deploy Agency Core (Docker, Render, or `uvicorn` locally). On first boot, open the web UI and run the **Setup Wizard** — it walks you through five steps:

1. Connect your Ollama instance (or enter a cloud provider key — Nvidia NIM, AWS Bedrock, Anthropic)
2. Generate your first API key
3. Create your admin account
4. Pull a model (`qwen2.5-coder:7b` for starters — free, no GPU required via Nvidia NIM)
5. Run a health check — the system confirms every dependency is reachable

The **Doctor** screen (accessible any time from the sidebar) repeats this check live: git binary, GitHub token, repo access, Langfuse connectivity, and all registered runtimes. Green across the board means you're ready.

> **No local GPU?** Set `LLM_PROVIDER=nvidia-nim` and `NVIDIA_API_KEY=<your-key>` to use Nvidia's free-tier hosted models. Zero local hardware required.

---

### Step 2 — Describe your company

Open the **Company** screen. Paste your repository URL and answer a short set of tailored questions about your stack, team size, and goals. Agency Core builds an internal knowledge graph so agents give context-aware answers ("use Pydantic v2 for this, that's what your codebase uses") instead of generic advice.

You can update this profile any time. Agents re-index it on each task cycle.

---

### Step 3 — Talk to the CEO agent

Open **Chat**. Describe what you want the way you'd brief a senior engineer:

> "There's a memory leak in the session manager reported in issue #142. Find the root cause, write a fix, and open a PR for my review."

The CEO agent:
1. Reads the issue and the relevant source files
2. Produces a structured plan — you can review and edit it before execution starts
3. Delegates to the Dev specialist
4. Returns a PR link, a summary of the fix, and the test results

Every conversation is persisted. Pick up where you left off across sessions.

---

### Step 4 — Watch the Task Board

Every agent job appears on the **Task Board** with live status:

```
queued → planning → executing → verifying → awaiting approval → done
```

Drill into any task to see:
- The original plan the CEO agent produced
- Every step the executing agent took (with diffs and tool call logs)
- The verification result (did the tests pass?)
- The judge's verdict (is the output production-ready?)
- A plain-English summary you can paste into Slack

---

### Step 5 — HITL approval gates

Agency Core never merges code, deploys to production, or sends external messages without your sign-off. When an agent reaches a gate it:

1. Pauses and surfaces the decision in your dashboard
2. Shows you exactly what will happen — the diff, the deploy command, the message body
3. Waits for your **Approve**, **Deny**, or **Redirect** (send back with comments)

Gates are configurable per task type: auto-approve low-risk operations like reformatting docs, require explicit sign-off on anything touching production.

---

### Step 6 — Schedule recurring work

Open **Schedules** and set up recurring agent tasks:

- **Daily**: summarise open PRs and surface anything blocked
- **Weekly**: dependency CVE audit, changelog draft, code quality report
- **Per-commit**: trigger a doc-sync agent on every merge to master
- **On-demand**: one-click "run all agents" for a sprint review

Agents run on schedule, push results to the Task Board, and only interrupt you when a human decision is needed.

---

## The V5 Control Plane — every screen

| Screen | What it does |
|--------|-------------|
| **Dashboard** | Live health of all agents, recent activity, and system metrics at a glance |
| **Chat** | Conversational interface to the CEO agent; full persistent history per session |
| **Task Board** | Kanban view of all agent jobs: queued → planning → executing → review → done |
| **Agents** | All registered specialists with capabilities, current workload, runtime, and model |
| **Providers** | Connected LLM providers (Ollama, AWS Bedrock, Nvidia NIM) with health and cost data |
| **Runtimes** | Execution substrates — internal loop, Docker agent, external harnesses (OpenCode, Aider, Goose) |
| **Knowledge** | Internal wiki maintained by agents from your code, docs, and past decisions |
| **Schedules** | Recurring agent tasks with cron-style timing and run history |
| **Skills** | The agent skill library — what each specialist knows how to do and when it activates |
| **Intelligence** | Routing policy editor — control which model handles which task type and at what cost tier |
| **Logs** | Full trace of every LLM call: token count, latency, provider, cost, and decision context |
| **Company** | Your organisation profile, tech stack, and knowledge graph seed data |
| **Admin** | User management, role assignment, instance activation, audit log, onboarding controls |
| **Doctor** | Self-diagnostics — checks every dependency, connectivity, and configuration item live |

---

## Screens

A visual tour of the dashboard. Screenshots reflect the most recent captured UI and are
regenerated from `scripts/sync_readme_gallery.py`.

<!-- README_UI_GALLERY:START -->
### 🛰 Control Plane

The command center: live agent health, recent activity, and system metrics at a glance.

<p align="center"><img src="docs/screenshots/readme/v4-control-plane.png" width="92%" alt="Control Plane dashboard"/></p>

### 🛬 Login

People can sign in through a simple starting page instead of touching raw config files.

<p align="center"><img src="docs/screenshots/readme/v4-login.png" width="92%" alt="Login"/></p>

### 🧙 Setup Wizard

The wizard helps you choose providers, models, runtimes, a default agent, and a cost policy.

<p align="center"><img src="docs/screenshots/readme/v4-setup-wizard.png" width="92%" alt="Setup Wizard"/></p>

### 💬 Chat

This is where people talk to the CEO agent directly, using the providers and rules you set up.

<p align="center"><img src="docs/screenshots/readme/v4-chat.png" width="92%" alt="Chat"/></p>

### 🗂 Task Board

This makes AI work visible. You can see what is waiting, running, blocked, in review, or done.

<p align="center"><img src="docs/screenshots/readme/v4-tasks-kanban.png" width="92%" alt="Kanban Task Board"/></p>

### 🤖 Agent Roster

This is your cast of AI helpers. Each agent can have its own model, runtime, specialty, and rules.

<p align="center"><img src="docs/screenshots/readme/v4-agents.png" width="92%" alt="Agent Roster"/></p>

### ⚙️ Runtimes

This shows the engines behind the scenes that actually run your AI work.

<p align="center"><img src="docs/screenshots/readme/v4-runtimes.png" width="92%" alt="Agent Runtimes"/></p>

### 🛣 Routing Policy

This is where you decide how smart, cheap, fast, or private the system should be when picking a model.

<p align="center"><img src="docs/screenshots/readme/v4-routing.png" width="92%" alt="Routing Policy"/></p>

### 🔌 Providers and Models

This is where you connect local and cloud AI sources and decide what models are available.

<p align="center">
  <img src="docs/screenshots/readme/v4-providers.png" width="48%" alt="Providers"/>
  &nbsp;
  <img src="docs/screenshots/readme/v4-models.png" width="48%" alt="Models"/>
</p>

### 📚 Knowledge

This is your team's memory: wiki pages, source material, and reusable context.

<p align="center"><img src="docs/screenshots/readme/v4-knowledge.png" width="92%" alt="Knowledge and Wiki"/></p>

### 🔭 Logs and activity

This helps you answer, ‘what just happened?’ — every LLM call, token count, latency, and cost.

<p align="center"><img src="docs/screenshots/readme/v4-logs.png" width="92%" alt="Logs"/></p>

### 🗓 Schedules

This is how you make AI jobs run later or run again automatically.

<p align="center"><img src="docs/screenshots/readme/v4-schedules.png" width="92%" alt="Schedules"/></p>

### 🧭 Settings and guardrails

Central settings keep defaults, policies, and integrations in one place instead of scattered config files.

<p align="center"><img src="docs/screenshots/readme/v4-settings.png" width="92%" alt="Settings"/></p>

### 🛡 Admin portal

This gives admins a simpler place to manage access, instance activation, and system behavior.

<p align="center"><img src="docs/screenshots/readme/v4-admin.png" width="92%" alt="Admin Portal"/></p>

### 📱 Mobile

The dashboard is responsive — sign in, run the setup wizard, and monitor agents from a phone.

<p align="center">
  <img src="docs/screenshots/readme/v4-login-mobile.png" width="32%" alt="Mobile login"/>
  &nbsp;
  <img src="docs/screenshots/readme/v4-setup-mobile.png" width="32%" alt="Mobile setup wizard"/>
</p>
<!-- README_UI_GALLERY:END -->

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│   React V5 SPA (GitHub Pages)     Remote Admin (Vercel)          │
└──────────────────┬───────────────────────────────────────────────┘
                   │ HTTPS / JWT Bearer
┌──────────────────▼───────────────────────────────────────────────┐
│  FastAPI Backend (Render / Docker)                                │
│  ├─ /v1/chat/completions     OpenAI-compatible proxy             │
│  ├─ /api/chat/send           Agency Core conversational API      │
│  ├─ /api/tasks/*             Task CRUD + async dispatcher        │
│  ├─ /api/agent/*             Agent job management + HITL gates   │
│  ├─ /api/doctor              Live system health diagnostics      │
│  ├─ /api/activation/*        Instance licensing + user mgmt      │
│  └─ /mcp-internal            MCP server for agent tool calls     │
├──────────────────────────────────────────────────────────────────┤
│  ModelRouter — task classification → optimal model selection     │
│  ├─ Code tasks      → Qwen3-Coder / DeepSeek-Coder              │
│  ├─ Reasoning       → DeepSeek-R1                                │
│  └─ Fast / chat     → smallest capable model                     │
├──────────────────────────────────────────────────────────────────┤
│  AgentRunner — plan → execute → verify → judge → summarise       │
│  ├─ CEO agent (orchestrator + domain classifier)                 │
│  ├─ Dev / Release / Content / Analytics / Infra specialists      │
│  └─ Workflow engine (persisted state machine, HITL gates)        │
├──────────────────────────────────────────────────────────────────┤
│  Task Dispatcher — async poll loop + crash-recovery reconciler   │
│  ├─ Per-task git worktree isolation (concurrent-safe execution)  │
│  └─ Opt-in external runtimes: Docker, OpenCode, Aider, Goose    │
├──────────────────────────────────────────────────────────────────┤
│  Storage (swappable at runtime)                                  │
│  ├─ MongoDB (default) — Motor async driver                       │
│  └─ SQLite (STORAGE_BACKEND=sqlite) — zero external deps         │
│  Observability — Langfuse traces + local TCO cost model          │
└──────────────────────────────────────────────────────────────────┘
```

---

## Quickstart

### Prerequisites

- Python 3.13+
- [Ollama](https://ollama.com/) with at least one model — **or** a free [Nvidia NIM](https://build.nvidia.com/) API key (no local GPU needed)
- Node 20+ (for the web UI)
- MongoDB — **or** set `STORAGE_BACKEND=sqlite` to skip it entirely

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
# Minimum required:
#   SECRET_KEY=$(openssl rand -hex 32)
#   STORAGE_BACKEND=sqlite          # skip MongoDB
#   ADMIN_EMAIL=you@example.com
#   ADMIN_PASSWORD=changeme
#
# Add one of:
#   OLLAMA_BASE_URL=http://localhost:11434   # local GPU
#   NVIDIA_API_KEY=nvapi-...                 # free cloud inference
```

### 3. Start the backend

```bash
uvicorn backend.server:app --reload --port 8001
```

### 4. Start the frontend (development)

```bash
cd frontend
npm install
REACT_APP_BACKEND_URL=http://localhost:8001 npm start
```

Visit [http://localhost:3000](http://localhost:3000) — the setup wizard appears on first boot.

### 5. Connect your AI coding tools

```jsonc
// Cursor — settings.json
{
  "cursor.ai.openaiBaseUrl": "http://localhost:8000",
  "cursor.ai.openaiApiKey": "your-api-key-here"
}
```

See [`client-configs/`](client-configs/) for Aider, Continue, Zed, VSCode, and Claude Code configs.

---

## Cloud deployment (Render + GitHub Pages)

Push to `master` — GitHub Actions does the rest automatically:

1. **CI**: Python 3.13 tests, frontend build, lint, SAST, secret scan, CVE audit
2. **Backend**: Docker build → Render deploy hook → health check
3. **Frontend**: React build → GitHub Pages

**Required repository secrets:**

| Secret | Where to get it |
|---|---|
| `RENDER_DEPLOY_HOOK_URL` | Render dashboard → service → Settings → Deploy Hook |
| `RENDER_BACKEND_URL` | Your Render service URL (e.g. `https://my-service.onrender.com`) |

Live demo:
- **Frontend**: `https://strikersam.github.io/local-llm-server/`
- **Backend API**: `https://local-llm-server.onrender.com/docs`

> **Render free tier note**: the backend sleeps after 15 minutes of inactivity and takes ~30 s to wake. Upgrade to Starter ($7/mo) to eliminate cold starts in production.

---

## Configuration reference

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | *(required)* | JWT signing key — `openssl rand -hex 32` |
| `STORAGE_BACKEND` | `mongo` | Set to `sqlite` for zero-dependency storage |
| `MONGO_URL` | `mongodb://localhost:27017` | MongoDB connection string |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama server |
| `LLM_PROVIDER` | `ollama` | `ollama` · `nvidia-nim` · `deepseek` · `bedrock` · `anthropic` |
| `NVIDIA_API_KEY` | *(optional)* | Nvidia NIM free-tier models — no local GPU required |
| `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` | *(optional)* | AWS Bedrock (Claude Opus, Titan) |
| `ANTHROPIC_API_KEY` | *(optional)* | Direct Anthropic API |
| `DEEPSEEK_API_KEY` | *(optional)* | DeepSeek cloud API |
| `GITHUB_TOKEN` | *(optional)* | Required for agents that open PRs, review code, or read issues |
| `LANGFUSE_HOST` + `_PUBLIC_KEY` + `_SECRET_KEY` | *(optional)* | Observability traces |
| `TELEGRAM_BOT_TOKEN` | *(optional)* | Remote control via Telegram |
| `ADMIN_EMAIL` + `ADMIN_PASSWORD` | *(optional)* | First admin — created on first boot |
| `RUNTIME_DOCKER_ENABLED` | `false` | Enable Docker agent runtime |
| `RUNTIME_OPENHANDS_ENABLED` | `false` | Enable OpenHands runtime |
| `RUNTIME_AIDER_ENABLED` | `false` | Enable Aider runtime |

Full reference: [`docs/configuration.md`](docs/configuration.md)

### Provider priority chain

Agency Core tries providers in order until one responds:

```
AWS Bedrock (15) → Nvidia NIM (10) → DeepSeek (8) → Anthropic (7) → HuggingFace (5) → Ollama (3)
```

Only providers with keys configured are tried. Set just the keys you have.

---

## Security

- **No secrets in source** — all configuration via environment variables; nothing hardcoded
- **Ed25519 instance activation** — tamper-evident licensing signatures
- **RBAC**: three roles — `user`, `power_user`, `admin`
- **Bearer token auth** on every API endpoint; JWT with configurable expiry
- **Audit log** for all admin actions (user creation, key generation, role changes)
- **Bandit SAST** + **CodeQL** + **GitHub secret scanning** on every push
- **Dependency CVE audit** on every PR via pip-audit
- **Per-task git worktree isolation** — concurrent agents cannot clobber each other's in-flight edits
- **Crash-recovery reconciler** — stranded `IN_PROGRESS` tasks are automatically re-queued on restart

Found a vulnerability? Open a [security advisory](https://github.com/strikersam/local-llm-server/security/advisories/new) — please don't file a public issue.

---

## Development

```bash
# Run tests — always before committing
pytest -x            # fast-fail mode
pytest -v            # verbose with full output

# Activate git hooks (blocks commits missing changelog entries)
git config core.hooksPath .claude/hooks

# Generate a new API key
python generate_api_key.py

# AI session watchdog (auto-resume AI coding sessions)
python scripts/ai_runner.py start
python scripts/ai_runner.py status
python scripts/ai_runner.py resume
```

See [`CLAUDE.md`](CLAUDE.md) for the full contributor guide, skill map, risky-module policy, and AI agent working rules.

---

## Roadmap

| Phase | Status | Description |
|---|---|---|
| Phase 1 — Typed agent contract | ✅ Done | `AgentJobRequest` / `AgentJobResult` Pydantic contract, E2E tests |
| Phase 2 — ModelRouter wiring | ✅ Done | Single router for all request types; classification → model hint |
| Phase 3 — SQLite + one backend | ✅ Done | Swappable storage adapter, dead-router removal, zero-dep option |
| Phase 4 — Runtime resilience | ✅ Done | Crash-recovery reconciler, worktree isolation, opt-in external runtimes |
| Phase 5 — Doctor & dashboard resilience | ✅ Done | `/api/doctor` endpoint, `useSafeData` hook, live DoctorScreen |
| Phase 6 — Workflow engine | 🔄 In progress | Persisted state machine, safe CEO agency (branch/PR safety) |
| Phase 7 — Onboarding engine | 📋 Planned | URL → stack inference → tailored questions → specialist provisioning |
| Phase 8 — Multi-tenant | 📋 Planned | Organisation isolation, per-tenant model budgets, SSO |

---

## License

MIT — see [LICENSE](LICENSE)

---

<div align="center">
<sub>Built for engineers who want the power of frontier AI without the cloud bill or the privacy compromise.</sub>
</div>
