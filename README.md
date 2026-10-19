<div align="center">

<img src="docs/assets/sam-logo.svg" alt="SAM, the face of Autonomous AI Agency" width="160" />

# Autonomous AI Agency

### An AI company that runs itself, on your servers.

**Paste a website URL and get a CTO-grade audit in minutes. Then a CEO agent and a fleet of
specialists get to work: they plan, write code, test it, and open PRs, around the clock.
The only thing they ask you for is the merge.**

Self-hosted · MIT · Your servers, your models, your data

[![Version](https://img.shields.io/badge/version-5.0.0-blue.svg)](https://github.com/strikersam/autonomous-ai-agency/releases/tag/v5.0.0)
[![CI](https://github.com/strikersam/autonomous-ai-agency/actions/workflows/ci.yml/badge.svg)](https://github.com/strikersam/autonomous-ai-agency/actions/workflows/ci.yml)
[![Deploy](https://github.com/strikersam/autonomous-ai-agency/actions/workflows/deploy-backend.yml/badge.svg)](https://github.com/strikersam/autonomous-ai-agency/actions/workflows/deploy-backend.yml)
[![Python](https://img.shields.io/badge/python-3.13-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**[▶ Try it live, free](https://autonomous-ai-agency.strikersam.workers.dev/) · [⚡ Run it in one command](#-run-it-in-one-command) · [🤪 Meet SAM](#-meet-sam) · [🧰 Agency Harness](harness/README.md) · [🔬 See the proof](proof/README.md) · [💬 Get help](#need-assistance)**

<a href="brag-output/brag.mp4"><img src="brag-output/brag.jpg" alt="Autonomous AI Agency: paste a URL, get a CTO-grade audit, and stand up a CEO-coordinated fleet of specialist agents that run 24×7 on your own hardware." width="760" /></a>

_▶ **[Watch the tour](brag-output/brag.mp4)** (61 s): paste a URL → stack scan → audit → specialist fleet → plan, execute, verify → your approval → 24×7 → meet SAM → it keeps learning → autonomy on a leash._

</div>

---

## In 30 seconds

| | |
|---|---|
| 🔎 **It reads your business** | Paste a URL. It scans the stack and runs a deterministic SEO / GEO / AIO / security audit with a 0–100 score and every finding priced. |
| 🏢 **It staffs itself** | It provisions the specialist agents that business needs, coordinated by a CEO agent with a C-suite advisory board (CFO, CSO, COO, CMO, CPO, Counsel). |
| 🛠 **It ships, and checks its own work** | Every change goes through plan → execute → verify. It byte-compiles and runs the tests before accepting a step. An LLM grading its own diff doesn't count. |
| 🧯 **It fixes itself, and learns** | Errors on the dashboard become fix tasks automatically. Failures turn into lessons the planner reads next time. Every hour it mines its own sessions for failures that keep repeating and files them as improvements. The CEO stops repeating directives that keep failing. |
| 🛡 **It stays on a leash** | Approval gates, a kill switch, per-agent daily spend caps, a canary credential, a policy engine and an audit trail. Nothing merges or deploys without you. |
| 🤪 **It has a face** | **SAM**, a googly-eyed little creature, floats in the corner of every screen. Tell it what to do and it runs the agency. |

---

## 🤪 Meet SAM

<img src="docs/assets/sam-logo.svg" alt="SAM" width="96" align="right" />

SAM (System Autonomy Manager) is the googly-eyed avatar in the corner of every screen and your
one-tap line to the agency. Type or speak to it: "brief me", "create a task to add dark mode to
billing", "triage the queue", "fix the alerts", or anything else in plain English. Commands that
create or approve work run as deterministic code, and loosening a safety control waits for your
**Confirm** tap. Realtime voice runs over [LiveKit](docs/SAM_VOICE_LIVEKIT.md). SAM is on for
admins by default (Settings → Platform controls → Integrations).

---

## ⚡ Run it in one command

No cloud account, no database server, no Docker. SQLite storage, the dashboard, and the 24×7
autonomy loops all run in one process.

```bash
git clone https://github.com/strikersam/autonomous-ai-agency.git
cd autonomous-ai-agency
./scripts/quickstart.sh          # or: make up
```

Open **http://localhost:8001/** and sign in with the credentials the script prints. The script is
idempotent: it writes a local `.env` with safe defaults, sets up a virtualenv, builds the
dashboard and launches everything. First run takes a few minutes; after that it starts in seconds.

> **Want top-tier output for free?** Put a free [NVIDIA NIM](https://build.nvidia.com) key
> (`NVIDIA_API_KEY=nvapi-...`) in `.env` and restart. No GPU needed. Docker Compose, Render and
> troubleshooting: **[docs/local-setup.md](docs/local-setup.md)**.

**Requirements:** Python 3.11+ and Node 20+ (Node only builds the UI; `--api-only` skips it).

---

## How it works

```mermaid
flowchart LR
    U([You / SAM]) -->|goal or URL| CEO[CEO agent]
    A[Audit + stack scan] --> CEO
    AL[Alerts bell] -->|auto fix tasks| CEO
    CEO -->|directives| Q[(Task queue)]
    Q --> P[Planner]
    P --> E[Executor]
    E --> V{Verifier<br/>compile + tests}
    V -->|fail| E
    V -->|pass| PR[Pull request]
    PR -->|you merge| SHIP([Shipped])
    V -.lessons.-> P
    Q -.outward-facing.-> G{{Your approval}}
    G --> P
```

1. **Work comes in** from you (dashboard, SAM, Telegram, a quick note from your phone), from the audit, from the alerts bell, or from the CEO's own 24×7 assessment cycle.
2. **The CEO decides**, grounded in live state, its own past decisions, and C-suite advice for business questions. It drops directives that keep failing.
3. **Specialists execute** through the plan → execute → verify loop, on whichever of a dozen runtimes fits (internal agent, Hermes, goose, aider, OpenHands, OpenCode, Claude Code, E2B, Docker, and more).
4. **Every LLM call** goes through one router with automatic failover across free and paid providers.
5. **You merge.** Outward-facing work (deploys, auth, secrets) waits for your approval before it even runs.

The full change history is in [docs/changelog.md](docs/changelog.md).

---

## 🧰 The Agency Harness

Everything that makes the agents behave, packaged so you can use it **without** running the
agency: 70+ skills, subagents, slash commands, the agent-discipline rules, MCP connector setup
and the autonomous-loop pattern. It lives in [**`harness/`**](harness/README.md) and installs
into any repo:

```bash
./harness/install.sh /path/to/your-repo          # copies; add --link to symlink
```

Works with Claude Code, Codex, Cursor and Gemini CLI.

---

## Repository map

| Path | What's there |
|---|---|
| [`harness/`](harness/README.md) | Reusable, open-source-ready agent harness: skills, subagents, commands, rules, connectors |
| `proxy.py`, `handlers/`, `router/`, `packages/` | The AI gateway: OpenAI / Anthropic / Ollama surfaces, auth, model routing, provider failover |
| `agent/`, `agents/`, `services/`, `tasks/`, `workflow/`, `runtimes/` | The agency: CEO, specialists, plan → execute → verify loop, task queue, agent runtimes |
| `backend/`, `frontend/` | Dashboard API (FastAPI) and React dashboard |
| `config/` | Model catalogue, providers, agent policy, sandbox profiles |
| `loops/`, `.github/workflows/` | The autonomous loop fleet and its registry |
| `docs/` | Guides, runbooks, ADRs ([index](docs/README.md)) |
| `scripts/`, `tests/`, `evals/` | Tooling, the pytest suite, agent evals |
| `deploy/`, `docker/`, `Dockerfile*`, `render.yaml` | Deployment (Helm, Docker, Render, Cloudflare) |
| [`scripts/local/`](scripts/local/) | Local launchers (`start_server.sh` / `.ps1`, proxy, Ollama, tunnels, Claude Code setup); `install.sh` / `install.ps1` stay at the root |

---

## What it does

| Area | Highlights | More |
|---|---|---|
| **AI gateway** | Drop-in OpenAI `/v1/*`, Anthropic `/v1/messages` and Ollama `/api/*`; task-aware routing with failover across free and paid providers; token quotas, PII/secret sanitiser and honest per-call cost tracking | [model-routing.md](docs/model-routing.md) · [api-surfaces.md](docs/api-surfaces.md) |
| **The agency** | URL → onboarding, a CEO agent with a C-suite advisory board, specialists on a dozen runtimes, self-healing from its own errors, zero-key web reach, WSJF portfolio | [platform-guide.md](docs/platform-guide.md) · [features.md](docs/features.md) |
| **Audit engine** | Deterministic SEO / GEO / AIO / security audit with a 0–100 score, priced findings, a PDF report and Screaming-Frog-compatible CSVs | [seo-audit.md](docs/seo-audit.md) · [proof/audits/](proof/audits/) |
| **Interfaces** | React dashboard, SAM voice, Telegram, GitHub, and any OpenAI-compatible client including Claude Code | [claude-code-setup.md](docs/claude-code-setup.md) · [telegram-bot.md](docs/telegram-bot.md) |

Try the audit on its own, no signup and read-only:

```bash
pip install -r requirements.txt
PYTHONPATH=. python scripts/run_seo_audit.py --website-url https://yourcompany.com --output-dir ./my-audit
```

---

## Autonomy with a leash

Nothing merges, deploys or messages externally without your approval. On top of that:

| Guardrail | Where |
|---|---|
| **Kill switch** halts all autonomous work, mid-run included | `AGENCY_KILL_SWITCH` |
| **Per-agent daily caps** in dollars and tokens | `AGENT_DAILY_USD_CAP` · `AGENT_DAILY_KTOKENS_CAP` |
| **Canary credential** that blocks and alerts on a leak | `AGENCY_CANARY_ENABLED` |
| **Policy engine** over tools, filesystem, network, shell, GitHub, MCP and more | [`config/agent_policy.yaml`](config/agent_policy.yaml) |
| **Approval gates** with a TTL; expiry denies | [`packages/governance/approvals.py`](packages/governance/approvals.py) |
| **Hardened sandboxes**: no capabilities, non-root, read-only rootfs, no network by default | [`config/sandbox_profiles.yaml`](config/sandbox_profiles.yaml) |
| **Audit trail** with agent identity on every action, secrets redacted | [`packages/governance/`](packages/governance/) |

Governance ships in observe mode: rules are evaluated and logged, and nothing is blocked until
you switch to enforcement. Guide and threat model: [docs/governance/](docs/governance/README.md).

**Models.** The free sandbox runs on free-tier models with failover; it shows the loop end to
end, not production quality. Production runs on your keys (Claude, OpenAI-compatible, Bedrock,
NVIDIA NIM, Groq, Cerebras, DeepSeek, local Ollama) through the same router. No data leaves
your server.

---

## Don't trust it, check the proof

Most "autonomous agent" projects show you a demo video. Here are artifacts instead:

| Proof | What it shows |
|---|---|
| [**This repo is maintained by its own agents**](proof/agent-built.md) | A large share of the merged pull requests here were opened by AI agent sessions: self-healing systems, provider failover, CI hardening, releases. It's the public commit history, and one GitHub search verifies it. |
| [**Real audit output**](proof/audits/) | The audit engine run against this project's own site. Findings, scores and the agent delegation plan are committed unedited, including our own imperfect score. |
| [**24-hour live sandbox**](https://autonomous-ai-agency.strikersam.workers.dev/) | Onboard any site, watch specialists get provisioned, talk to the CEO agent. It resets every 24 hours. No signup wall. |

---

## Screens

<details>
<summary>Dashboard screenshots (captured from a live deployment)</summary>

Regenerate with `python scripts/capture_screens.py`, then `python scripts/sync_readme_gallery.py`.

<!-- README_UI_GALLERY:START -->
### 💬 Chat — unified assistant

Talk to the CEO agent directly; it decomposes goals and routes work to the right specialists.

<p align="center"><img src="docs/screenshots/v5/chat.png" width="92%" alt="💬 Chat — unified assistant"/></p>

### 📊 Dashboard — system overview

Live agent health, recent activity, and system metrics at a glance.

<p align="center"><img src="docs/screenshots/v5/dashboard.png" width="92%" alt="📊 Dashboard — system overview"/></p>

### 🗂 Tasks — job lifecycle board

Every AI job made visible: waiting, running, blocked, in review, or done.

<p align="center"><img src="docs/screenshots/v5/tasks.png" width="92%" alt="🗂 Tasks — job lifecycle board"/></p>

### 🤖 Agents — autonomous team

Your specialist roster — each with its own model, runtime, specialty, and guardrails.

<p align="center"><img src="docs/screenshots/v5/agents.png" width="92%" alt="🤖 Agents — autonomous team"/></p>

### 🗓 Schedules — autopilot jobs

Recurring and scheduled autonomous work.

<p align="center"><img src="docs/screenshots/v5/schedules.png" width="92%" alt="🗓 Schedules — autopilot jobs"/></p>

### ⚡ Skills — agentic capabilities

Reusable runtime skills bound to specialists.

<p align="center"><img src="docs/screenshots/v5/skills.png" width="92%" alt="⚡ Skills — agentic capabilities"/></p>

### 🎯 Portfolio — WSJF roadmap

Prioritised initiatives, sprints, and agile health.

<p align="center"><img src="docs/screenshots/v5/portfolio.png" width="92%" alt="🎯 Portfolio — WSJF roadmap"/></p>

### 📈 Intelligence — trends & competitors

Trend and competitor signals scoped to each onboarded company's stack.

<p align="center"><img src="docs/screenshots/v5/intelligence.png" width="92%" alt="📈 Intelligence — trends & competitors"/></p>

### 📚 Knowledge — docs & sources

Wiki pages, source material, and reusable context — your team's memory.

<p align="center"><img src="docs/screenshots/v5/knowledge.png" width="92%" alt="📚 Knowledge — docs & sources"/></p>

### 🔌 Providers — models, Ollama & MCP

Connect free/cloud/local AI sources and choose which models are available.

<p align="center"><img src="docs/screenshots/v5/providers.png" width="92%" alt="🔌 Providers — models, Ollama & MCP"/></p>

### 🔭 Logs — traces & observability

Every LLM call: tokens, latency, cost, and decision context.

<p align="center"><img src="docs/screenshots/v5/logs.png" width="92%" alt="🔭 Logs — traces & observability"/></p>

### 🐙 GitHub — repos & PRs

Connect repositories and manage the agent's delivery surface.

<p align="center"><img src="docs/screenshots/v5/github.png" width="92%" alt="🐙 GitHub — repos & PRs"/></p>

### 🏢 Company — operating context

An onboarded company's detected stack, systems, and SEO/health.

<p align="center"><img src="docs/screenshots/v5/company.png" width="92%" alt="🏢 Company — operating context"/></p>

### ✨ Onboarding — setup wizard

Scan a website and stand up its specialist agency in minutes.

<p align="center"><img src="docs/screenshots/v5/onboarding.png" width="92%" alt="✨ Onboarding — setup wizard"/></p>

### 🔁 Loops — autonomous fleet

Every autonomous loop catalogued: readiness score, maturity, self-heal coverage, drift status, and cost estimate.

<p align="center"><img src="docs/screenshots/v5/loops.png" width="92%" alt="🔁 Loops — autonomous fleet"/></p>

### 🩺 Doctor — diagnostics

System self-checks and autonomy readiness probes.

<p align="center"><img src="docs/screenshots/v5/doctor.png" width="92%" alt="🩺 Doctor — diagnostics"/></p>

### 🛡 Admin — users & access

Manage users, roles, instance activation, and onboarding gates.

<p align="center"><img src="docs/screenshots/v5/admin.png" width="92%" alt="🛡 Admin — users & access"/></p>

### 📱 Mobile

Responsive layout — sign in, view the dashboard, and work the task board from a phone.

<p align="center">
  <img src="docs/screenshots/v5/mobile-login.png" width="30%" alt="Mobile login"/>
  &nbsp;
  <img src="docs/screenshots/v5/mobile-dashboard.png" width="30%" alt="Mobile dashboard"/>
  &nbsp;
  <img src="docs/screenshots/v5/mobile-tasks.png" width="30%" alt="Mobile task board"/>
</p>
<!-- README_UI_GALLERY:END -->

</details>

---

## Architecture and security

A React SPA (Cloudflare Worker) over a FastAPI backend (Render or Docker), MongoDB or SQLite
storage, one LLM router for every model call, and a persisted workflow state machine with
human-in-the-loop gates. Secrets are env-only, every endpoint is authenticated with
three-role RBAC, tasks run in per-task git worktrees, and CI runs Bandit, CodeQL, secret
scanning, dependency CVE audits and SBOM generation. Details:
[platform-guide.md](docs/platform-guide.md#architecture) ·
[threat model](docs/governance/threat-model.md).

MIT. See [LICENSE](LICENSE).

## Need assistance?

The software is free and always will be (MIT). If you'd like a hand putting it to work, or advice on AI adoption in general, I'm happy to help.

> I built this platform end to end: multi-provider LLM routing with failover, multi-agent orchestration, human-approval workflows, observability, and a CI pipeline where the agents ship their own code ([proof](proof/agent-built.md)). I consult on AI strategy and agentic automation. I can deploy this platform on your infrastructure with top-tier models, onboard your company, and tune the specialist fleet to your stack. A hands-on 2-week pilot is the usual starting point. Early design partners get generous terms in exchange for a public case study.

- 📧 **strikersam@gmail.com**: send your URL and what you'd like automated first
- 📋 [**Request a pilot or ask a question**](https://github.com/strikersam/autonomous-ai-agency/issues/new?template=pilot-request.yml): a public form, answered within 48 hours
- Or [run the audit on your own site](#what-it-does) and send me the report. I'll walk you through what the fleet would do about it, free.

## Contributing

Issues and PRs are welcome. [**CONTRIBUTING.md**](CONTRIBUTING.md) covers dev setup, coding standards and the PR checklist. [**SECURITY.md**](SECURITY.md) covers vulnerability disclosure. [A large share of merged PRs here are agent-authored](proof/agent-built.md), so reading a few recent ones is the fastest way to see the quality bar.

If you'd rather point an agent at a gap than fix it yourself, [open an issue](https://github.com/strikersam/autonomous-ai-agency/issues/new). The fleet's inbound-issue triage may pick it up.

---

<div align="center">

<img src="docs/assets/sam-logo.svg" alt="SAM" width="56" />

**Autonomous AI Agency**: the AI team that works while you sleep, on a server you own.

<sub>For engineers and operators who want the leverage of frontier AI without the cloud bill, the privacy compromise or the headcount.</sub>

<br/><br/>

[![Star History Chart](https://api.star-history.com/svg?repos=strikersam/autonomous-ai-agency&type=Date)](https://star-history.com/#strikersam/autonomous-ai-agency&Date)

If this is useful to you, a star helps other people with the same problem find it.

</div>
