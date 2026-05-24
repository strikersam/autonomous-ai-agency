<div align="center">

# LLM Relay

### Your own private AI assistant that actually works — for your whole team.

**No monthly per-seat bill. No data leaving your control. No vendor lock-in.**

[![Version](https://img.shields.io/badge/version-5.0.0-4D8CFF?style=for-the-badge)](docs/changelog.md)
[![Stars](https://img.shields.io/github/stars/strikersam/local-llm-server?style=for-the-badge&color=FFD43B&logo=github)](https://github.com/strikersam/local-llm-server/stargazers)
[![CI](https://img.shields.io/github/actions/workflow/status/strikersam/local-llm-server/ci.yml?style=for-the-badge&label=CI&logo=github-actions)](https://github.com/strikersam/local-llm-server/actions)
[![License](https://img.shields.io/badge/license-Open%20Source-22C55E?style=for-the-badge)](LICENSE)

[**What is this?**](#what-is-this) · [**Who is it for?**](#who-is-it-for) · [**How it works**](#how-it-works-plain-english) · [**Quick start**](#quick-start) · [**Getting activated**](#getting-activated) · [**For developers**](#for-developers)

</div>

---

## What is this?

**LLM Relay is a self-hosted AI platform** — you install it on your own server (or laptop), and it gives your team access to powerful AI tools without paying per-user fees to OpenAI, Anthropic, or similar services.

Think of it like having your own private ChatGPT, but:
- **Your data never leaves your server** — nothing is sent to third parties
- **One installation serves your whole team** — no per-seat pricing
- **It works with every major AI service** — swap between local models and cloud providers in one click
- **It runs itself** — autonomous agents scan your codebase for issues and fix them overnight while you sleep

> **Not technical?** You only need to follow the [Quick Start](#quick-start) steps. Everything else is taken care of automatically.

---

## Who is it for?

| If you are… | LLM Relay helps you… |
|-------------|----------------------|
| A **small engineering team** | Get AI coding help without $20/month per developer |
| A **startup** | Run AI on your own infrastructure, keep IP private |
| A **solo developer** | Point every AI tool (Cursor, Claude Code, Aider) at one server |
| A **business owner** | Let your team use AI through a controlled, audited gateway |
| A **developer building AI tools** | Get a clean OpenAI-compatible API to build against |

---

## How it works (plain English)

Imagine LLM Relay as a **smart telephone exchange** for AI:

```
Your team's tools                 LLM Relay               AI Providers
─────────────────    ─────────────────────────────    ─────────────────
Cursor (coding)  →  │  Checks who's asking         │ → Local Ollama model
Claude Code      →  │  Picks the best model        │ → NVIDIA free cloud
ChatGPT clients  →  │  Logs usage & cost           │ → OpenAI GPT-4o
Custom scripts   →  │  Runs autonomous agents      │ → Anthropic Claude
                    │  Shows you a dashboard       │
                    └─────────────────────────────┘
```

Everyone on your team connects their tools to `http://your-server:8000` instead of directly to OpenAI. LLM Relay handles the rest — routing requests to the cheapest available model, enforcing usage limits, and keeping an audit trail.

### The autonomous agency

Beyond routing, LLM Relay runs a small team of AI agents in the background:

- **Dev Agent** — runs your tests every 15 minutes; if something breaks, it diagnoses and fixes it automatically
- **Security Agent** — scans for vulnerabilities (CVEs, leaked secrets, unsafe dependencies) and files fixes
- **Reviewer Agent** — conducts code review on recent changes
- **Release Agent** — checks weekly if the codebase is ready to ship, updates the changelog

These agents work like a night-shift team — you check the dashboard in the morning and find issues fixed, PRs ready, and a status report waiting.

---

## Quick start

### Step 1 — Install

**On Mac or Linux:**
```bash
git clone https://github.com/strikersam/local-llm-server
cd local-llm-server
cp .env.example .env          # create your config file
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn proxy:app --port 8000
```

**On Windows:**
```powershell
git clone https://github.com/strikersam/local-llm-server
cd local-llm-server
copy .env.example .env
.\install.ps1
.\run.bat
```

Open `http://localhost:8000` in your browser. You'll see the admin dashboard.

### Step 2 — Set your admin password

Edit `.env` and set:
```
ADMIN_SECRET=choose-a-strong-password-here
```

Restart the server. Log in at `http://localhost:8000/admin`.

### Step 3 — Get activated

LLM Relay requires a one-time activation before onboarding users. This is free — see [Getting activated](#getting-activated) below.

### Step 4 — Add AI providers

In the dashboard, go to **Providers** and add at least one:

| Provider | Cost | Setup |
|----------|------|-------|
| **NVIDIA NIM** | Free tier available | Paste your API key (get one at [build.nvidia.com](https://build.nvidia.com)) |
| **Ollama** (local) | Free, needs a GPU or Apple Silicon | [Install Ollama](https://ollama.com), run `ollama pull qwen2.5-coder` |
| **OpenAI** | Pay per token | Paste your OpenAI API key |
| **Anthropic** | Pay per token | Paste your Anthropic API key |

You only need one to start. NVIDIA NIM is free and requires no hardware.

### Step 5 — Connect your tools

Once the server is running, point your AI tools at it:

**Cursor** — Settings → AI → OpenAI API Base URL → `http://localhost:8000/v1`

**Claude Code** — `claude --api-base-url http://localhost:8000`

**Continue (VS Code)** — see `client-configs/continue/` for a ready-made config

**Any OpenAI SDK** — just set `OPENAI_BASE_URL=http://localhost:8000/v1`

---

## Getting activated

LLM Relay uses a **one-time instance activation** to prevent unauthorized copying and to ensure you get proper support. This is free and takes less than 24 hours.

**How it works:**

1. When you first open the app, you'll see your **Instance ID** — a unique code for your installation
2. Click **"Open email draft"** to send it to [strikersam@gmail.com](mailto:strikersam@gmail.com)
3. You'll receive a signed **activation code** by reply, usually within a few hours
4. Paste the code into the activation screen — you're done

**Why is this required?**

The activation code is cryptographically signed with a private key that only the repo owner holds. This means:
- Even if someone forks the repo and removes the UI check, they can't generate valid activation codes
- Each code is tied to your specific Instance ID — it can't be reused elsewhere
- The relay service validates the same token server-side, so there's no way to bypass it

**After activation**, admins control which users can proceed through onboarding via the **Admin → Activation & Onboarding** panel.

---

## For admins — managing your team

### Allowing users to onboard

After your instance is activated:
1. Go to **Admin → Activation & Onboarding**
2. Under **User Onboarding Access**, type a user's ID or email
3. Click **Allow** — that user can now complete the setup wizard

Users who aren't on the list see a friendly "request access" message and can email you directly.

### Revoking access

Click **Revoke** next to any user to remove their onboarding access. The audit log tracks every change with timestamps.

### Monitoring usage

The **Dashboard** shows live metrics:
- Which models are being used and how much they cost
- Which team members are most active
- Agent status and recent autonomous actions
- System health (CPU, memory, model response times)

---

## For developers

### Architecture overview

```
proxy.py              — FastAPI entry point, auth middleware, model routing
backend/server.py     — Main app server: users, tasks, agents, workspaces
activation.py         — Instance activation (Ed25519 signed JWT)
activation_api.py     — Activation REST API + per-user onboarding gate
router/               — Model routing: classifier, registry, health checks
agent/loop.py         — AgentRunner: plan → execute → verify cycle
handlers/             — Anthropic + Ollama native API compatibility
frontend/src/v5/      — React V5 dashboard (all screens, activation gate)
```

### Running tests

```bash
pytest -x              # fast fail — run before every commit
pytest -v              # verbose output
```

### Environment variables

All config is in `.env`. Key variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `ADMIN_SECRET` | Admin dashboard password | `a-very-strong-password` |
| `API_KEYS` | Comma-separated bearer tokens for API access | `sk-abc,sk-xyz` |
| `OLLAMA_BASE` | Ollama server URL | `http://localhost:11434` |
| `NVIDIA_API_KEY` | NVIDIA NIM API key | `nvapi-...` |
| `OPENAI_API_KEY` | OpenAI API key | `sk-...` |
| `ANTHROPIC_API_KEY` | Anthropic API key | `sk-ant-...` |
| `LANGFUSE_PUBLIC_KEY` | Observability (optional) | `pk-lf-...` |
| `MONGO_URL` | MongoDB for multi-user backend (optional) | `mongodb://localhost:27017` |

### Coding rules

1. Type annotations on all public functions
2. No secrets in source — all config via environment variables
3. Pydantic models for all API I/O
4. Async for all I/O
5. Log with `logging`, not `print`
6. Any change to auth files (`admin_auth.py`, `key_store.py`) requires a risky-module-review
7. Every meaningful commit updates `docs/changelog.md`

### Model routing

LLM Relay automatically routes requests based on your configured strategy:

| Strategy | Behaviour |
|----------|-----------|
| `free_first` | Tries NVIDIA NIM or local Ollama before paid APIs |
| `local_first` | Prefers Ollama; falls back to cloud only if unavailable |
| `quality_first` | Always uses the highest-capability model |
| `cost_optimised` | Picks the cheapest model that can handle the task |

Configure in `.env` as `ROUTING_STRATEGY=free_first`.

### Contributing

PRs welcome. Please run `pytest -x` and update `docs/changelog.md` before submitting. See `CLAUDE.md` for the full contribution guide.

---

## What's new

See [docs/changelog.md](docs/changelog.md) for the full history.

**v5.0.0** (current)
- **V5 dashboard** — redesigned React UI with 20+ screens: Tasks kanban, Agent Roster, Schedules, Runtimes, Routing Policy, Knowledge Base, Logs, and more
- **Typed agent contract** — `AgentJobRequest`/`AgentJobResult` Pydantic models with `extra="forbid"` enforce strict API boundaries between the scheduler and runners
- **ModelRouter wiring** — all chat paths (proxy and web UI) now route through `ModelRouter.route()` for task-aware model selection before provider fallback
- **HITL resume endpoint** — `POST /api/chat/resume/{session_id}` lets the UI send human approve/deny/input decisions to paused agent jobs
- **Instance activation system** — Ed25519-signed phone-home licensing with per-user onboarding control
- **Real E2E CI** — GitHub Actions spins up MongoDB + the full server and runs 30+ assertions with no mocks
- **Security hardening** — runtime read endpoints require authentication; audit trail for all role changes

---

<div align="center">

**Questions?** Email [strikersam@gmail.com](mailto:strikersam@gmail.com) or open an issue.

Made with ☕ by [@strikersam](https://github.com/strikersam)

</div>
