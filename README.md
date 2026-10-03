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

**[▶ Try it live, free](https://autonomous-ai-agency.strikersam.workers.dev/) · [⚡ Run it in one command](#-run-it-in-one-command) · [🤪 Meet SAM](#-meet-sam) · [🔬 See the proof](proof/README.md) · [💬 Get help](#need-assistance)**

<a href="brag-output/brag.mp4"><img src="brag-output/brag.jpg" alt="Autonomous AI Agency: paste a URL, get a CTO-grade audit, and stand up a CEO-coordinated fleet of specialist agents that run 24×7 on your own hardware." width="760" /></a>

_▶ **[Watch the tour](brag-output/brag.mp4)**: paste a URL → stack scan → audit → specialist fleet → plan, execute, verify → your approval → 24×7, self-hosted._

</div>

---

## In 30 seconds

| | |
|---|---|
| 🔎 **It reads your business** | Paste a URL. It scans the stack and runs a deterministic SEO / GEO / AIO / security audit with a 0–100 score and every finding priced. |
| 🏢 **It staffs itself** | It provisions the specialist agents that business needs, coordinated by a CEO agent with a C-suite advisory board (CFO, CSO, COO, CMO, CPO, Counsel). |
| 🛠 **It ships, and checks its own work** | Every change goes through plan → execute → verify. It byte-compiles and runs the tests before accepting a step. An LLM grading its own diff doesn't count. |
| 🧯 **It fixes itself** | Errors on the dashboard become fix tasks automatically. Failures turn into lessons the planner reads next time. The CEO stops repeating directives that keep failing. |
| 🛡 **It stays on a leash** | Approval gates, a kill switch, per-agent daily spend caps, a canary credential, a policy engine and an audit trail. Nothing merges or deploys without you. |
| 🤪 **It has a face** | **SAM**, a googly-eyed little creature, floats in the corner of every screen. Tell it what to do and it runs the agency. |

---

## 🤪 Meet SAM

<img src="docs/assets/sam-logo.svg" alt="SAM" width="96" align="right" />

SAM (System Autonomy Manager) is the agency's logo and your one-tap line to the whole operation.
It floats in the bottom-left corner of every screen, on desktop and phone. Its eyes follow your
cursor, swirl while it thinks, and its mouth moves while it talks. Type to it, tap the 🎤 and
speak, or open full realtime voice over [LiveKit](docs/SAM_VOICE_LIVEKIT.md).

SAM doesn't just chat. The commands below are executed by deterministic code, so nothing that
creates or approves work depends on a free-tier model deciding to call a tool:

| Say | SAM does | Who |
|---|---|---|
| "**Brief me**" / "sitrep" | Live report on the CEO loop, queue depth and approval gate. No LLM involved. | Admins |
| "**Create a task to** add dark mode to billing" | Queues the job for the agents. Deploys and other outward-facing work still park for your approval. | Admins |
| "**Triage the queue**" | Runs the CEO's own triage now: approves what doesn't need you, rejects duplicates, leaves deploys/auth for you. | Admins |
| "**Fix the alerts**" | Reads the alerts bell and queues one fix task per real error, de-duplicated. | Everyone |
| Anything else | Answers from live agency state, guided by the operator's standing rules and what you've told it before. | Everyone |

**Turn it on:** Settings → Platform controls → Integrations → **SAM floating avatar**. It's off by
default and admin-only. Switch **SAM avatar audience** to *All users* to widen it. Delegation
and triage stay admin-only either way.

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

<details>
<summary><strong>Contents</strong></summary>

- [In 30 seconds](#in-30-seconds)
- [Meet SAM](#-meet-sam)
- [Run it in one command](#-run-it-in-one-command)
- [How it works](#how-it-works)
- [What's new](#whats-new)
- [Don't trust it, check the proof](#dont-trust-it-check-the-proof)
- [Everything it does](#everything-it-does)
- [Autonomy with a leash](#autonomy-with-a-leash)
- [Start with the audit](#start-with-the-audit)
- [Who this is for](#who-this-is-for)
- [Honest model economics](#honest-model-economics)
- [Screens](#screens)
- [Architecture, security, license](#architecture-security-license)
- [Need assistance?](#need-assistance)
- [Contributing](#contributing)

</details>

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

---

## What's new

The full log is in [**docs/changelog.md**](docs/changelog.md). The highlights from the last few weeks:

- 🤪 **SAM is the face of the agency** (2026-10-03). A floating avatar on every screen that can brief you, delegate work and run CEO triage. It's also the new logo.
- 🧠 **The CEO learns from its own results** (2026-09-26). Directives it invented that keep failing aren't reissued until newer evidence outweighs the old (`CEO_PLAYBOOK_ENFORCE`).
- 🧯 **The agency triages its own work** (2026-09-26). Parked tasks that don't need a human get approved, duplicates get rejected, and error alerts become fix tasks. You're asked at merge time.
- 🛑 **Kill switch + per-agent daily caps** (2026-09-26). `AGENCY_KILL_SWITCH` halts all autonomous work mid-run. `AGENT_DAILY_USD_CAP` and `AGENT_DAILY_KTOKENS_CAP` bound each agent per day.
- 🪤 **Canary credential** (2026-09-26). A decoy token planted in the agents' environment. If it shows up in an LLM request or outbound URL, the action is blocked and you get a Telegram alert.
- 🛡 **AI gateway hardening** (2026-09-30). Request-id hygiene, size limits, security headers, per-consumer token quotas, prompt policy, PII/secret sanitiser, usage metrics and upstream retries. All are live toggles.
- 🚫 **Operator model deny-list** (2026-10-01). Block model ids (globs allowed) before they're ever dispatched, live from the dashboard.
- 🎯 **Smarter planner memory** (2026-09-27). Lessons are ranked by relevance to the task (keyword + TF-IDF rank fusion), not just by how loud they are.
- 🔐 **Agent memory redacts secrets and PII** before it touches disk, and **no two processes can run the same task** (atomic checkout).
- 🔌 **More free brains**. SiliconFlow and Mistral as free fallbacks, OpenRouter's free models now route, Claude Opus 5.5 / Sonnet 5.5 in the catalog, and paid Claude no longer leads the fallback chain.
- 💼 **C-suite advisory** (2026-09-16). A grounded CFO/CSO/COO/CMO/CPO/Counsel layer with its own tab in the Company hub and a REST API.
- ⚡ **One-command local setup** (2026-09-19). `./scripts/quickstart.sh`, as above.

---

## Don't trust it, check the proof

Most "autonomous agent" projects show you a demo video. Here are artifacts instead:

| Proof | What it shows |
|---|---|
| [**This repo is maintained by its own agents**](proof/agent-built.md) | A large share of the merged pull requests here were opened by the agent fleet: self-healing systems, provider failover, CI hardening, releases. It's the public commit history, and one GitHub search verifies it. |
| [**Real audit output**](proof/audits/) | The audit engine run against this project's own site. Findings, scores and the agent delegation plan are committed unedited, including our own imperfect score. |
| [**24-hour live sandbox**](https://autonomous-ai-agency.strikersam.workers.dev/) | Onboard any site, watch specialists get provisioned, talk to the CEO agent. It resets every 24 hours. No signup wall. |

---

## Everything it does

Every row links to the module, doc or test that implements it.

### 🧠 The AI gateway

| Capability | What it is | More |
|---|---|---|
| **OpenAI-compatible proxy** | Drop-in `/v1/*` for any OpenAI SDK client, with Bearer auth, rate limiting and CORS in front of your models. | [api-surfaces.md](docs/api-surfaces.md) |
| **Anthropic + Ollama surfaces** | The same proxy speaks Anthropic `/v1/messages` and native Ollama `/api/*`. Three API shapes, one gateway. | [features.md](docs/features.md) |
| **Routing + failover across 18 provider backends** | Task-aware model selection across NVIDIA NIM, Cerebras, Groq, Mistral, SiliconFlow, OpenRouter, Google, Anthropic, OpenAI, Ollama, LM Studio, vLLM and more. Failover, backoff and cooldown on `429`/`410`, and a retired model is benched for an hour. | [model-routing.md](docs/model-routing.md) · [`config/llm/providers.yaml`](config/llm/providers.yaml) |
| **Gateway hardening** | Token quotas, prompt policy, PII/secret sanitiser, usage metrics, upstream retries and a response cache, each a live toggle. | [`packages/gateway/`](packages/gateway/) |
| **Reasoning-budget control** | `reasoning_budget: low\|medium\|high\|max` maps to the right per-provider thinking budget on any supported model. | [features.md](docs/features.md) |
| **Honest cost tracking** | Every call priced per model, with prompt-cache reads billed at the provider's discount rate. | [`packages/ai/cost_tracker.py`](packages/ai/cost_tracker.py) |

### 🏢 The agency

| Capability | What it is | More |
|---|---|---|
| **URL → agency onboarding** | Scan a site's stack and stand up the specialists that business needs, each with a role persona. | [platform-guide.md](docs/platform-guide.md) |
| **CEO-coordinated fleet** | A CEO agent decomposes plain-English goals, remembers its past decisions, learns which directives fail, and delegates to specialists. | [`agent/agency.py`](agent/agency.py) |
| **SAM** | The floating avatar and voice agent: brief, delegate, triage, fix alerts. | [Meet SAM](#-meet-sam) · [`agent/sam_orchestrator.py`](agent/sam_orchestrator.py) |
| **Plan → Execute → Verify** | A three-role loop that byte-compiles and tests its own changes before accepting them. | [`agent/loop.py`](agent/loop.py) |
| **C-suite advisory** | Grounded CFO/CSO/COO/CMO/CPO/Counsel advice that researches, cites and remembers. | [`agent/executive_advisory.py`](agent/executive_advisory.py) |
| **40 autonomous loops** | Health, security, stack drift, code quality, trend watch, docs sync and more, on a durable scheduler, each catalogued with readiness and cost. | [loops/registry.yaml](loops/registry.yaml) |
| **Self-healing** | The fleet researches its own errors, files fix tasks against itself, and mines past sessions for recurring friction. | [`agent/self_healing.py`](agent/self_healing.py) |
| **Zero-key web reach** | Read-only, SSRF-guarded internet for every agent: fetch, search, RSS, YouTube transcripts. No API keys. | [`agent/web_reach.py`](agent/web_reach.py) |
| **Portfolio + WSJF** | Initiatives ranked by WSJF and turned into executable tasks automatically. | [Screens](#screens) |

### 🔎 The audit engine

| Capability | What it is | More |
|---|---|---|
| **SEO / GEO / AIO audit** | Deterministic checks across Technical SEO, Content, Security, Social, **GEO** (generative engines) and **AIO** (answer engines). You get a 0–100 score, revenue at risk, and a CTO-grade PDF. Works on bot-protected sites too. | [seo-audit.md](docs/seo-audit.md) · [proof/audits/](proof/audits/) |
| **Screaming-Frog-compatible exports** | CSVs that drop into existing SEO workflows. | [seo-audit.md](docs/seo-audit.md) |
| **Repo-aware auto-fix** | Connect a repo and the agent proposes dry-run diffs; `apply=true` writes them. | [seo-audit.md](docs/seo-audit.md) |

### 💻 Interfaces

| Capability | What it is | More |
|---|---|---|
| **React dashboard** | Home, Assistant, Work, Company, Insights and Settings hubs, fully responsive on mobile. | [Screens](#screens) |
| **135 platform controls** | Every operator switch (autonomy, routing, gateway, integrations) lives in Settings → Platform controls and applies live. No redeploys. | [platform-controls.md](docs/platform-controls.md) |
| **Voice** | SAM in the browser, plus full-duplex realtime voice over LiveKit. | [SAM_VOICE_LIVEKIT.md](docs/SAM_VOICE_LIVEKIT.md) |
| **Telegram** | Drive the agency and approve gated work from your phone. | [telegram-bot.md](docs/telegram-bot.md) |
| **GitHub** | Connect repos. Agents open PRs, and CI is where they ship their own code. | [proof/agent-built.md](proof/agent-built.md) |
| **Claude Code / any OpenAI client** | Point your existing tools at the proxy. | [claude-code-setup.md](docs/claude-code-setup.md) |

Exhaustive reference: [**docs/features.md**](docs/features.md) · [**docs/platform-guide.md**](docs/platform-guide.md).

---

## Autonomy with a leash

Autonomy is only safe when it's bounded, attributable and reversible.

| Guardrail | What it does | Where |
|---|---|---|
| **Three-tier trust** | Read-only → dry-run → gated writes. Nothing merges, deploys or messages externally without your approval. | [platform-controls.md](docs/platform-controls.md) |
| **Kill switch** | One toggle halts scheduled jobs, workflow runs, agent commits and agent LLM calls, mid-run included. Your own proxy and dashboard traffic keep working. | `AGENCY_KILL_SWITCH` |
| **Daily caps per agent** | Dollar and token ceilings per agent per day. Free-tier models cost $0 and never trip it. | `AGENT_DAILY_USD_CAP` · `AGENT_DAILY_KTOKENS_CAP` |
| **Canary credential** | A decoy token that blocks the action and alerts you if an agent ever leaks the environment. | `AGENCY_CANARY_ENABLED` |
| **Policy engine** | Declarative rules over 14 surfaces (tools, filesystem, network, credentials, shell, GitHub, Docker, database, MCP, browser, memory, providers, runtime, sub-agents). | [`config/agent_policy.yaml`](config/agent_policy.yaml) |
| **Agent identity + audit trail** | Every action has an agent id, owner and session. Each audit row has 20 fields and secrets are redacted before storage. | [`packages/governance/`](packages/governance/) |
| **Approval gates** | High-risk actions hold for a human, with a TTL. Expiry **denies**. | [`packages/governance/approvals.py`](packages/governance/approvals.py) |
| **Hardened sandboxes** | All capabilities dropped, non-root, read-only rootfs, no network by default. Docker locally, Firecracker micro-VMs in production. | [`config/sandbox_profiles.yaml`](config/sandbox_profiles.yaml) |
| **Supply chain** | Image and dependency CVEs (ranked by whether our code imports the package), CycloneDX SBOM, and a CI posture guard. | [`.github/workflows/supply-chain.yml`](.github/workflows/supply-chain.yml) |

Governance **ships in observe mode**. Rules are evaluated and audited; nothing is blocked until you
switch to enforcement after seeing what the rules *would* have caught. `GET /api/governance/status`
reports what is actually in force. Guide and threat model: [docs/governance/](docs/governance/README.md).

---

## Start with the audit

It's the lowest-risk thing an agency can do: **read-only analysis**. No signup, no repo access.

- Deterministic checks across six pillars, with a **0–100 score** overall and per pillar
- **Revenue at risk**: pass your monthly organic revenue and every finding is priced (a clearly labelled estimate, never an invented loss)
- **An agent-ready delegation plan**: each finding becomes a WSJF-prioritised work package assigned to a specialist. That's the handoff from audit to agency.

```bash
pip install -r requirements.txt
PYTHONPATH=. python scripts/run_seo_audit.py --website-url https://yourcompany.com --output-dir ./my-audit
```

---

## Who this is for

- **You pay per seat for AI dev/ops tools** and want the same leverage on infrastructure you control, with no metering and no lock-in.
- **You need agents that can write to production** without the false choice between no gates (too risky) and a human on every step (too slow).
- **You're evaluating autonomous-agent platforms** and want one that runs on its own codebase in public, with its PR history as evidence.
- **You care where your data goes.** Your code, customer data and prompts never pass through a third-party relay.

If you only want help writing code in one repo, a coding assistant (Claude Code, Cursor, Aider) is a better fit.

## Honest model economics

- The **free sandbox** runs on free-tier models (NVIDIA NIM, Groq, Cerebras, Mistral, SiliconFlow, OpenRouter free) with automatic failover. It demonstrates the loop end to end. It isn't the output quality you'd run a company on.
- **Production runs on your keys.** Claude, OpenAI-compatible endpoints, AWS Bedrock, NVIDIA NIM, Groq, Cerebras, DeepSeek and local Ollama all go through the same router. Point the brain at a top-tier model from the Providers screen and every specialist upgrades with no redeploy.
- **No data leaves your server.** No cloud relay, no usage telemetry, no per-seat pricing.

---

## Screens

> Captured from a live deployment. Regenerate with `python scripts/capture_screens.py`, then `python scripts/sync_readme_gallery.py`.

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

---

## Architecture, security, license

The stack is a React SPA (Cloudflare Worker) over a FastAPI backend (Render or Docker), with swappable MongoDB/SQLite storage, one LLM router for every model call, and a persisted workflow state machine with human-in-the-loop gates. The full diagram and an honest feature-maturity matrix are in [docs/platform-guide.md](docs/platform-guide.md#architecture).

Security posture:
- Secrets are env-only and never written to disk or logs.
- JWT auth on every endpoint, with three-role RBAC.
- Per-task git worktree isolation.
- Bandit SAST, CodeQL and secret scanning on every push; dependency CVE audit on every PR.
- Container image scanning and an SBOM on every image change.
- Least-privilege agent sandboxes, and an identity-attributed audit trail for every agent action.

Threat model and honest limits: [docs/governance/threat-model.md](docs/governance/threat-model.md).

MIT. See [LICENSE](LICENSE).

## Need assistance?

The software is free and always will be (MIT). If you'd like a hand putting it to work, or advice on AI adoption in general, I'm happy to help.

> I built this platform end to end: multi-provider LLM routing with failover, multi-agent orchestration, human-approval workflows, observability, and a CI pipeline where the agents ship their own code ([proof](proof/agent-built.md)). I consult on AI strategy and agentic automation. I can deploy this platform on your infrastructure with top-tier models, onboard your company, and tune the specialist fleet to your stack. A hands-on 2-week pilot is the usual starting point. Early design partners get generous terms in exchange for a public case study.

- 📧 **strikersam@gmail.com**: send your URL and what you'd like automated first
- 📋 [**Request a pilot or ask a question**](https://github.com/strikersam/autonomous-ai-agency/issues/new?template=pilot-request.yml): a public form, answered within 48 hours
- Or [run the audit on your own site](#start-with-the-audit) and send me the report. I'll walk you through what the fleet would do about it, free.

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
