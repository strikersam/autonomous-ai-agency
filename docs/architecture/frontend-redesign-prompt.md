# LLM Relay — Frontend Redesign Prompt (for Claude / a design assistant)

> Paste the block below into Claude (or a design tool). It captures the
> stabilized + decided Agency Core direction so the redesign reflects the new
> product, not the old buggy one. Companion context:
> `agency-core-audit-2026-05-22.md`, `agency-core-progress.md`.

---

You are a senior product designer + React engineer. Redesign the frontend of
"LLM Relay" — a self-hosted, OpenAI-compatible LLM proxy that is being
transformed into an autonomous "Agency Core" platform (a company-level AI agency
that plans, builds, fixes, tests, and maintains a company's digital estate).

Deliver a cohesive redesign: information architecture, key screens as
high-fidelity React + Tailwind mockups (single-file where possible), a component
inventory, and every meaningful UI state (loading / empty / partial-failure /
error / success). Prioritize clarity, calm, and low-surprise over feature
density. Current stack is React (Create React App). Keep it implementable.

== NORTH STAR ==
One coherent intelligent assistant — NOT a control panel full of toggles and
backend jargon. The user talks; the system orchestrates. Never expose internal
"modes," runtime names, or metadata-first UX.

== PRIMARY SURFACE: Unified Direct Chat (Claude Code-style) ==
- A single natural-language chat is the main entry point for coding, ops, and
  product tasks. No manual "Agent Mode" toggle: the system silently escalates to
  agent execution when it detects execution intent ("fix X in the repo and
  commit").
- Sticky context chips: current company, repo, and task — visible, switchable,
  never required to be understood.
- Humanized agent progress (replaces a raw "No active agents" panel): show the
  current phase as friendly labels ("Planning the change", "Editing files",
  "Running tests", "Verifying", "Opening PR"), a live event timeline, and a phase
  breadcrumb. Polished progress + graceful recovery messaging.
- Final outputs read like an assistant's answer (summary, diffs, links to
  PR/issue), not a tool dump.

== RESILIENT DASHBOARD ==
- Per-widget loading and error states. A single failing endpoint must NEVER blank
  the page or show a generic "Network Error". Show partial data + a non-blocking
  amber warning on the affected widget only.
- Widgets: provider/runtime health (one router, one runtime — show active model/
  provider, health, queue), recent jobs, open tasks/issues/PRs, cost/usage,
  monitoring signals.

== DOCTOR / DIAGNOSTICS ==
- A "Doctor" surface that runs preflight + health checks (runtime, GitHub/repo,
  CI-parity, dashboard/API) and answers operator questions like "why didn't this
  task run?" and "why did CI fail but local pass?" in plain language with a
  one-click rerun.

== COMPANY ONBOARDING / DISCOVERY (first-class flow) ==
- Input a production website URL (+ optional repos, docs, credentials, goals).
- The system inspects the site, infers the likely stack/industry (CMS, commerce,
  PIM/OMS/DAM, SEO, analytics, CRM, support), asks tailored follow-up questions,
  and provisions company-specific specialists.
- Design the step-by-step wizard, the "detected systems" review, and the
  tailored-questions screen.

== COMPANY GRAPH / OPERATING CONTEXT ==
- A persistent canonical view of the company: domain/industry, systems & tools,
  repos, environments, docs/knowledge, specialists, tasks/issues/PRs/incidents,
  quick actions, priorities. Make it browsable and the source of context for
  chat.

== TASK / JOB LIFECYCLE ==
- A board showing the disciplined workflow: classify -> clarify -> plan ->
  execute -> verify -> judge/release-gate -> monitor. Each job links to evidence
  (PR, issue, test run). Verified issue closure only — make trust visible.

== SAFE QUICK ACTIONS / QUICK NOTES ==
- Lightweight capture for quick notes / quick actions / domain-specific workflows
  (works across industries: retail, trading, SaaS, content, marketplace, ops).
  Safe by design — show what will happen before it happens.

== DESIGN PRINCIPLES ==
- Boring, reliable defaults. Progressive disclosure. No mode confusion. No
  exposed internals. Strong empty/loading/error states everywhere. Accessible,
  responsive, dark/light. A calm, trustworthy, modern aesthetic.

== DELIVERABLES ==
1. Information architecture / nav map.
2. High-fidelity mockups for: Direct Chat (idle, executing-with-progress,
   final-answer), Dashboard (healthy + partial-failure), Onboarding wizard,
   Company Graph, Task board, Doctor.
3. Reusable component inventory + the key UI states for each.
4. A short rationale tying each screen to the principle it serves.
