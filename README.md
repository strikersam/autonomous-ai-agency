<div align="center">

# Autonomous AI Agency

**Paste your website URL. Get a CTO-grade audit in minutes.
Then let the agency that produced it go to work — on your infrastructure.**

Self-hosted · MIT · Your servers, your models, your data

<a href="brag-output/brag.mp4"><img src="brag-output/brag.jpg" alt="Autonomous AI Agency — paste a URL, get a CTO-grade audit, and stand up a CEO-coordinated fleet of specialist agents that run 24×7 on your own hardware." width="760" /></a>

_▶ **[Watch the tour](brag-output/brag.mp4)** — paste a URL → stack scan → CTO-grade audit → specialist fleet → Plan · Execute · Verify → your approval gate → 24×7, self-hosted._

[![Version](https://img.shields.io/badge/version-5.0.0-blue.svg)](https://github.com/strikersam/autonomous-ai-agency/releases/tag/v5.0.0)
[![CI](https://github.com/strikersam/autonomous-ai-agency/actions/workflows/ci.yml/badge.svg)](https://github.com/strikersam/autonomous-ai-agency/actions/workflows/ci.yml)
[![Deploy](https://github.com/strikersam/autonomous-ai-agency/actions/workflows/deploy-backend.yml/badge.svg)](https://github.com/strikersam/autonomous-ai-agency/actions/workflows/deploy-backend.yml)
[![Python](https://img.shields.io/badge/python-3.13-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**[▶ Try it live — free sandbox](https://autonomous-ai-agency.strikersam.workers.dev/) · [🔬 See the proof](proof/README.md) · [⚡ Run it locally](#-run-it-locally-in-one-command) · [💬 Need a hand?](#need-assistance)**

</div>

---

## ⚡ Run it locally in one command

No cloud account, no database server, no Docker. SQLite storage, the dashboard,
and the 24×7 autonomy loops — all in one process.

```bash
git clone https://github.com/strikersam/autonomous-ai-agency.git
cd autonomous-ai-agency
./scripts/quickstart.sh          # or: make up
```

Then open **http://localhost:8001/** and sign in with the credentials the script
prints. The script is idempotent — it writes a local `.env` with safe defaults,
sets up a virtualenv, builds the dashboard, and launches everything. First run
takes a few minutes; later runs start in seconds.

> Want top-tier output? Drop a **free** [NVIDIA NIM](https://build.nvidia.com) key
> (`NVIDIA_API_KEY=nvapi-...`) into `.env` and restart — no GPU required. Full
> options, the Docker Compose path, and troubleshooting are in
> **[docs/local-setup.md](docs/local-setup.md)**.

**Requirements:** Python 3.11+ and Node 20+ (Node only for building the UI; use
`--api-only` to skip it).

---

<details>
<summary><strong>Contents</strong></summary>

- [Run it locally in one command](#-run-it-locally-in-one-command)
- [Don't trust it — check the proof](#dont-trust-it--check-the-proof)
- [What it is](#what-it-is)
- [Everything it does](#everything-it-does)
- [Who this is for](#who-this-is-for)
- [Start with the audit](#start-with-the-audit--no-signup-no-repo-access-no-trust-required)
- [Then the agency takes over](#then-the-agency-takes-over--at-your-pace)
- [How the agents keep themselves honest](#how-the-agents-keep-themselves-honest)
- [How the agents are governed](#how-the-agents-are-governed)
- [Honest model economics](#honest-model-economics)
- [Screens](#screens)
- [Architecture, security, license](#architecture-security-license)
- [What's new](#whats-new)
- [Need assistance?](#need-assistance)
- [Contributing](#contributing)

</details>

## Don't trust it — check the proof

Most "autonomous agent" projects show you a demo video. Here are artifacts instead:

| Proof | What it shows |
|---|---|
| [**This repo is maintained by its own agents**](proof/agent-built.md) | A large share of the merged pull requests in this repository were opened by the agent fleet — self-healing systems, provider failover, CI hardening, releases. Not a demo: the public commit history, verifiable with one GitHub search. |
| [**Real audit output**](proof/audits/) | The SEO/GEO/AIO audit engine run against this project's own site — findings, scores, and the agent delegation plan, committed unedited (yes, including our own imperfect score). |
| [**24-hour live sandbox**](https://autonomous-ai-agency.strikersam.workers.dev/) | Onboard any site, watch specialists get provisioned, talk to the CEO agent. The environment resets every 24 hours. No signup wall, nothing to uninstall. |

---

## What it is

Autonomous AI Agency is a **self-hosted platform that turns one website URL into a
working AI operations team**. It scans your site's tech stack, provisions the
specialist agents your business actually needs, and runs them 24×7 on hardware you
control — with human approval gates on anything that ships. Under the hood: an
OpenAI-compatible proxy, multi-provider model routing with automatic failover, a
three-role plan → execute → verify agent loop, a governance layer, and full
observability. MIT licensed.

This page is the short version — the full tour (every screen, schedule, runtime,
and config variable) lives in [**docs/platform-guide.md**](docs/platform-guide.md).

## Everything it does

The headline capabilities, each with a deeper page. Nothing here is only prose —
every row links to the module, doc, or test that implements it.

### 🧠 The AI gateway

| Capability | What it is | More |
|---|---|---|
| **OpenAI-compatible proxy** | Drop-in `/v1/*` for any OpenAI SDK client, with Bearer-token auth, rate limiting, and CORS in front of your models. | [features.md](docs/features.md) · [api-surfaces.md](docs/api-surfaces.md) |
| **Anthropic + Ollama surfaces** | The same proxy also speaks Anthropic `/v1/messages` and native Ollama `/api/*` — three API shapes, one gateway. | [features.md](docs/features.md) |
| **Multi-provider routing + failover** | Task-aware model selection across NVIDIA NIM, TokenIn, Cerebras, Groq, Ollama, Anthropic, OpenAI-compatible endpoints and AWS Bedrock, with automatic failover, backoff, and cooldown on `429`/`410`. | [model-routing.md](docs/model-routing.md) |
| **Reasoning-budget control** | `reasoning_budget: low\|medium\|high\|max` on any request maps to the right per-provider thinking budget — one readable field, any supported model. | [features.md](docs/features.md) |
| **Context pruning** | Long chats are auto-trimmed before forwarding, so you don't hit context-limit errors on multi-turn sessions. | [request-flow.md](docs/request-flow.md) |

### 🏢 The agency

| Capability | What it is | More |
|---|---|---|
| **URL → agency onboarding** | Scan a site's stack and stand up the specialist agents that business needs, in minutes. | [platform-guide.md](docs/platform-guide.md) |
| **CEO-coordinated specialist fleet** | A CEO agent decomposes plain-English goals and delegates to a roster of specialists, each with its own model, runtime, and guardrails. | [specialists-skills-matrix.md](docs/specialists-skills-matrix.md) |
| **Plan → Execute → Verify loop** | A three-role agent loop that byte-compiles and tests its own changes before accepting them — not an LLM grading its own diff. | [`agent/loop.py`](agent/loop.py) · [autonomy/](docs/autonomy/) |
| **C-suite business advisory** | A grounded CFO/CSO/COO/CMO/CPO/Counsel layer that researches, cites, and remembers — for pricing, GTM, and risk questions, not just code. | [`agent/executive_advisory.py`](agent/executive_advisory.py) |
| **Autonomous loops + scheduler** | Standing schedules (health, security, stack-drift, code-quality, trend watch, docs sync) run themselves on a durable APScheduler store. | [loops/registry.yaml](loops/registry.yaml) · [autonomy/](docs/autonomy/) |
| **Self-healing & self-improvement** | The fleet researches its own errors, files fix tasks against itself, and mines past sessions for recurring friction. | [`agent/self_healing.py`](agent/self_healing.py) |
| **Zero-key web reach** | Every agent gets read-only, SSRF-guarded internet access — fetch, search, RSS, YouTube transcripts — no API keys. | [`agent/web_reach.py`](agent/web_reach.py) |
| **Runtime adapters** | Hand work to Hermes, goose, aider and other runtimes through one interface, all under the same policy and budget. | [platform-guide.md](docs/platform-guide.md) |

### 🔎 The audit engine

| Capability | What it is | More |
|---|---|---|
| **SEO / GEO / AIO audit** | Deterministic checks across Technical SEO, Content, Security, Social, **GEO** (generative-engine) and **AIO** (answer-engine) — a 0–100 score, revenue-at-risk pricing, and CTO-grade PDF. | [seo-audit.md](docs/seo-audit.md) · [proof/audits/](proof/audits/) |
| **Screaming-Frog-compatible exports** | CSV exports that drop into existing SEO workflows. | [seo-audit.md](docs/seo-audit.md) |
| **Repo-aware auto-fix** | Connect a repo and the agent proposes dry-run diffs for fixable findings; `apply=true` writes them. | [seo-audit.md](docs/seo-audit.md) |

### 🛡 Governance, safety & ops

| Capability | What it is | More |
|---|---|---|
| **Three-tier trust model** | Read-only → dry-run → gated writes. Nothing merges, deploys, or messages externally without your approval. | [platform-controls.md](docs/platform-controls.md) |
| **Governance layer** | Agent identity, a declarative policy engine over 14 surfaces, enforced cost ceilings, TTL approval gates, and a redacted audit trail. | [governance/](docs/governance/README.md) |
| **Hardened sandboxes + supply chain** | Least-privilege container profiles, image/dependency CVE scanning, CycloneDX SBOM, and a CI posture guard. | [governance/](docs/governance/README.md) |
| **Observability** | Every LLM call — tokens, latency, cost, decision context — with Langfuse integration. | [langfuse-observability.md](docs/langfuse-observability.md) |
| **Persistent memory** | Cross-session memory so the agency compounds context instead of starting cold. | [persistent-memory-system.md](docs/persistent-memory-system.md) |
| **Knowledge graph** | The codebase itself is a queryable graph, so agent sessions query structure instead of re-reading source. | `graphify query "..."` (see [CLAUDE.md](CLAUDE.md)) |

### 💻 Interfaces

| Capability | What it is | More |
|---|---|---|
| **React dashboard** | Chat, Tasks, Agents, Schedules, Skills, Portfolio, Intelligence, Knowledge, Providers, Logs, GitHub, Company, Onboarding, Loops, Doctor, Admin — plus a responsive mobile layout. | [Screens](#screens) |
| **Telegram bot control** | Drive the agency from your phone. | [telegram-bot.md](docs/telegram-bot.md) |
| **GitHub integration** | Connect repos; agents open PRs, and CI is where the agents ship their own code. | [proof/agent-built.md](proof/agent-built.md) |
| **Use it from Claude Code / any OpenAI client** | Point your existing tools at the proxy. | [claude-code-setup.md](docs/claude-code-setup.md) |

Full, exhaustive reference: [**docs/features.md**](docs/features.md) · [**docs/platform-guide.md**](docs/platform-guide.md).

## Who this is for

- **You're paying per-seat for an AI dev/ops tool** and want the same leverage on infrastructure you control, with no usage metering and no vendor lock-in.
- **You need AI agents that write to production systems** but every tool you've tried either has no approval gates (too risky) or requires a human in the loop for everything (too slow). The three-tier trust model is built for exactly this middle ground.
- **You're evaluating "autonomous coding agent" platforms** and want to see one running on its own codebase in public, with its own PR history as evidence, rather than a demo video.
- **You care where your data goes.** Self-hosted means your code, your customer data, and your prompts never transit a third-party inference relay.

If none of those describe you, this is probably more platform than you need — a single-repo coding assistant (Claude Code, Cursor, Aider) is a better fit for "just help me write code."

## Start with the audit — no signup, no repo access, no trust required

The entry point is deliberately the lowest-risk thing an agency can do: **read-only analysis**.

- **Deterministic checks** across six pillars: Technical SEO, Content, Security headers, Social, **GEO** (generative-engine optimization: llms.txt, AI-crawler access, citable anchors) and **AIO** (answer-engine optimization: JSON-LD structured data, E-E-A-T markup)
- **0–100 health score**, overall and per pillar
- **Revenue-at-risk quantification** — pass your monthly organic revenue and every finding is priced (a clearly-labeled model estimate, never a fabricated loss)
- **Screaming-Frog-compatible CSV exports** — drops into existing SEO workflows
- **Repo-aware auto-fix** — connect a repo later and the agent proposes dry-run diffs for fixable findings (`apply=true` writes them)
- **An agent-ready delegation plan** — every finding comes back as a WSJF-prioritized work package assigned to a specialist. That's the handoff from "audit" to "agency."

```bash
# Self-hosted, from a clone:
pip install -r requirements.txt
PYTHONPATH=. python scripts/run_seo_audit.py --website-url https://yourcompany.com --output-dir ./my-audit
```

Engine docs: [docs/seo-audit.md](docs/seo-audit.md) · Example output: [proof/audits/](proof/audits/)

## Then the agency takes over — at your pace

Trust is granted in steps, never all at once:

1. **Read-only** — audits, uptime/TLS monitoring, stack-drift detection, CVE scans. Zero write access.
2. **Dry-run** — agents propose diffs, draft PRs, draft replies. You read everything before it exists anywhere real.
3. **Gated writes** — agents open PRs, update docs, triage tickets. Nothing merges, deploys, or messages externally without your explicit approval. High-stakes actions always pause; you choose which low-risk classes of work to auto-approve.

After onboarding, the standing schedules run themselves: website health, security audit, stack-change detection, code-quality scan, trend watch, and docs sync. You talk to a CEO agent in plain English ("fix the memory leak in issue #142"); it decomposes the job, delegates to the right specialist, and returns results with evidence — PR link, test output, reasoning trace.

Full roster, screens, loop engineering, and configuration: [docs/platform-guide.md](docs/platform-guide.md).

## How the agents keep themselves honest

Consistent with the "check the proof" ethos above, none of this is described only in prose — every line links to the module or test file that implements it:

| Practice | What it actually does | Where |
|---|---|---|
| **Empirical verification** | Before a step is accepted, the agent byte-compiles what it changed and runs the matching tests — not just an LLM judging its own diff. | [`agent/loop.py`](agent/loop.py) (`AGENT_EMPIRICAL_VERIFY`) |
| **Reviewable plan specs** | Every plan is saved as a markdown spec you can read and approve before implementation starts, not just an internal object. | [`services/spec_store.py`](services/spec_store.py) · `GET/POST /api/specs/*` |
| **Independent cross-verification** | Changes touching auth, keys, or sessions get a second, independent agent re-check before being accepted — one that never writes code, only critiques. | [`agent/verification_strategies.py`](agent/verification_strategies.py) |
| **Session retrospection** | The agency mines its own past sessions for recurring friction and files fix tasks against itself — self-improvement from lived experience, not just live signals. | [`services/session_retro.py`](services/session_retro.py) |
| **Inbound issue triage** | Bug reports and feature requests get classified and routed into the fix pipeline automatically, closing the loop from "someone complained" to "a specialist is on it." | [`services/issue_triage.py`](services/issue_triage.py) |
| **Proactive rate-limit pacing** | Free-tier model calls are paced to stay under quota instead of just reacting to errors after they happen. | [`packages/ai/rate_limiter.py`](packages/ai/rate_limiter.py) |
| **Agent readiness self-audit** | The repo scores its own fitness for autonomous work — style/validation, tests, docs, dev environment, observability, security, task discovery — and tells you what's missing. | `make agent-readiness` → [`docs/AGENT_READINESS.md`](docs/AGENT_READINESS.md) |

Full gap analysis and every new configuration variable: [docs/AGENT_AUTONOMY_ROADMAP.md](docs/AGENT_AUTONOMY_ROADMAP.md).

## How the agents are governed

Autonomy is only safe if it is bounded, attributable, and reversible. The
governance layer ([`packages/governance/`](packages/governance/)) gives every
agent action an identity, a policy verdict, a cost ceiling, and an audit row —
modelled on [Docker AI Governance](https://www.docker.com/blog/docker-ai-governance-unlock-agent-autonomy-safely/)
and adapted to this platform's topology.

| Control | What it does | Where |
|---|---|---|
| **Agent identity** | Every action carries a stable agent id, an owner, a policy group, and a per-run session — so "who did this?" has an answer. | [`packages/governance/identity.py`](packages/governance/identity.py) |
| **Policy engine** | Declarative rules over 14 surfaces (tools, filesystem, network, credentials, shell, GitHub, Docker, database, MCP, browser, memory, providers, runtime, sub-agent spawn). Organisation baseline rules cannot be loosened by a group. | [`config/agent_policy.yaml`](config/agent_policy.yaml) |
| **Cost ceilings** | Six enforced per-session limits — tool calls, spend, tokens, duration, recursion depth, retries. A policy file cannot stop a runaway loop; a counter can. | [`packages/governance/enforcement.py`](packages/governance/enforcement.py) |
| **Approval gates** | High-risk actions (merge, delete, deploy, container build) hold for a human. TTL-bounded, and expiry **denies**. | [`packages/governance/approvals.py`](packages/governance/approvals.py) |
| **Audit trail** | Who / what / when / why / where / cost — 20 fields, secrets redacted *before* storage, SIEM-shippable as one-line JSON. | [`packages/governance/audit.py`](packages/governance/audit.py) |
| **Hardened sandboxes** | Least-privilege profiles: all capabilities dropped, non-root, no-new-privileges, read-only rootfs and no network by default. Docker locally, Firecracker micro-VMs in production. | [`config/sandbox_profiles.yaml`](config/sandbox_profiles.yaml) |
| **Supply chain** | Image CVE scanning, dependency CVEs, CycloneDX SBOM, Dockerfile lint, and a posture guard that fails CI on a privileged container or a mounted Docker socket. | [`.github/workflows/supply-chain.yml`](.github/workflows/supply-chain.yml) |

**It ships in observe mode.** Rules are evaluated and audited; nothing is
blocked until an operator deliberately switches to enforcement, after watching
what the rules *would* have caught. `GET /api/governance/status` reports what is
actually in force — including `isolation: none` when no sandbox backend is
available — because a dashboard that overstates containment is worse than none.
Enforcement covers **every execution path**, not only in-process tool calls, so a
restriction cannot be routed around by dispatching to a runtime instead.

Guide, gap analysis, and threat model: [docs/governance/](docs/governance/README.md).

## Honest model economics

- The **free 24h sandbox** runs on free-tier models (Cerebras, Groq, NVIDIA NIM) with automatic failover. It demonstrates the orchestration loop end to end; it is *not* the output quality you'd run a company on.
- **Production runs on your infrastructure with your keys.** Anthropic Claude, OpenAI-compatible endpoints, AWS Bedrock, NVIDIA NIM, Groq, Cerebras, DeepSeek, and local Ollama are all supported by the same router — point the brain at a top-tier model from the Providers screen and every specialist upgrades instantly, no redeploy.
- **No data leaves your server.** No cloud relay, no usage telemetry, no shared inference endpoint, no per-seat pricing.

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

The stack is a React SPA (Cloudflare Worker / GitHub Pages) over a FastAPI backend (Render / Docker) with swappable MongoDB/SQLite storage, a ModelRouter for task-aware model selection, and a persisted workflow state machine with HITL gates — the full diagram and the honest feature-maturity matrix are in [docs/platform-guide.md](docs/platform-guide.md#architecture).

Security posture: no secrets in source (env-only, validated at startup) · JWT Bearer auth on every endpoint · three-role RBAC · per-task git worktree isolation · Bandit SAST + CodeQL + secret scanning on every push · dependency CVE audit on every PR · container image CVE scanning + SBOM on every image change · least-privilege agent sandboxes (all capabilities dropped, non-root, no-new-privileges) · identity-attributed audit trail for every agent action · audit log for all admin actions. Threat model and honest limits: [docs/governance/threat-model.md](docs/governance/threat-model.md).

MIT — see [LICENSE](LICENSE)

## What's new

The latest change log lives in [**docs/changelog.md**](docs/changelog.md). Recent highlights:

- **Routing failover chain completed for Gemini 3.x and Fable 5.1** (2026-09-14) — `claude-fable-5-1` and four Gemini 3.x models are now reachable through the watchdog/failover chain, not just capability checks.
- **Anthropic server-side refusal fallbacks + refusal observability** (2026-09-01) — opt-in server-side re-run of content-refused requests, and a `WARNING` log with the refusal category instead of a silent empty response.
- **Claude 5 family in the model catalog & router** (2026-08) — `claude-sonnet-5` (1M context, adaptive thinking) and `claude-opus-5` route correctly through the proxy; new deployments that set only `ANTHROPIC_API_KEY` default to Sonnet 5.

<details>
<summary>More releases</summary>

- **`reasoning_budget` shorthand** — `low\|medium\|high\|max` maps to per-provider thinking budgets on any supported model.
- **Chat-path context pruning** — long `/v1/chat/completions` conversations are auto-trimmed before forwarding.
- **Structured output strict mode + refusal handling** — the OpenAI `json_schema` + `strict: true` pattern, translated for providers that don't support it natively.
- **MCP `tools/list` TTL caching** — honours the `ttlMs` field to cut redundant round-trips.

</details>

## Need assistance?

The software is free and always will be (MIT). If you'd like a hand putting it to work — or advice on AI adoption in general — I'm happy to assist.

> I built this platform end-to-end: multi-provider LLM routing with failover, multi-agent orchestration, human-approval workflows, observability, and a CI pipeline where the agents themselves ship the code ([proof](proof/agent-built.md)). I consult on AI strategy and agentic automation, and I can assist with deploying this platform on your own infrastructure with top-tier models (Claude, GPT — all supported), onboarding your company, and tuning the specialist fleet to your stack. A hands-on 2-week pilot is the usual starting point; early design partners get generous terms in exchange for a public case study.

- 📧 **strikersam@gmail.com** — tell me your URL and what you'd like automated first
- 📋 [**Request a pilot / ask a question**](https://github.com/strikersam/autonomous-ai-agency/issues/new?template=pilot-request.yml) — public form, answered within 48 hours
- Or simply [run the audit on your own site](#start-with-the-audit--no-signup-no-repo-access-no-trust-required) and send me the report — I'll walk you through what the fleet would do about it, free.

## Contributing

Issues and PRs are welcome. [**CONTRIBUTING.md**](CONTRIBUTING.md) covers dev setup, coding standards, and the PR checklist; [**SECURITY.md**](SECURITY.md) covers vulnerability disclosure. Since [a large share of merged PRs here are agent-authored](proof/agent-built.md), the fastest way to see the expected quality bar is to read a few recent ones.

If you'd rather point an agent at a specific gap than write the fix yourself, [open an issue](https://github.com/strikersam/autonomous-ai-agency/issues/new) describing it — the fleet's own inbound-issue triage may pick it up.

---

<div align="center">

**Autonomous AI Agency** — the AI team that works while you sleep, on a server you own.

<sub>Built for engineers and operators who want the leverage of frontier AI without the cloud bill, the privacy compromise, or the headcount.</sub>

<br/><br/>

[![Star History Chart](https://api.star-history.com/svg?repos=strikersam/autonomous-ai-agency&type=Date)](https://star-history.com/#strikersam/autonomous-ai-agency&Date)

If this is useful to you, a star helps other people with the same problem find it.

</div>
