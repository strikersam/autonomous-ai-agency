# 467 Public Site Truth Spec

> Issue #467 §5 required: "Public site truth spec"

---

## What Is the Public Site

The public site is the externally-facing web presence at `https://local-llm-server.strikersam.workers.dev` (Cloudflare Workers) and any associated GitHub Pages deployment.

The public site serves three audiences:
1. **Prospective users** — learn what the project does, how to install it, how to use it
2. **Contributors** — understand the architecture, how to contribute, coding standards
3. **The AI itself** — uses the public site as a ground-truth reference for what exists

---

## Current State

The public site consists of:
- `index.html` — Static landing page with feature overview and install instructions
- `github-pages-setup.html` — GitHub Pages deployment documentation
- Cloudflare Workers deployment at the domain above
- Vercel-hosted React dashboard (referenced in deployment docs)

**Truth problems:**
- `index.html` references features that are not implemented (e.g., specialist agents, autonomous workflows)
- No unified "this is what we have" page — features listed on the homepage include FLAKY and ADVERTISED-BUT-NOT-BUILT items
- The AI (AgentRunner) cannot use the public site as a reliable reference because the documentation and the code are out of sync

---

## Required: Public Site Truth Spec

The public site MUST reflect only what is **WORKING** and **TESTED**.

### Tier System for Features

Every feature on the public site must be labeled with one of these tiers:

| Tier | Label | Meaning | Example |
|------|-------|---------|---------|
| STABLE | ✅ Stable | Fully implemented, tested, maintained | OpenAI-compatible proxy, Ollama routing, Bearer auth |
| BETA | 🧪 Beta | Implemented but limited test coverage | Direct chat sessions, TrendWatcher |
| DEVELOPMENT | 🚧 Development | Partially implemented or known issues | Portfolio intelligence, Agile sprints |
| PLANNED | 📋 Planned | Designed but not implemented | Company onboarding, specialist families |
| REMOVED | ❌ Removed | Was here, now removed per spec | telegram_bot (moved to opt-in) |

### Feature Matrix Truth

The public site must include a feature matrix that maps directly to `docs/architecture/feature-matrix.md`.

**Current feature matrix has 12 features that should be demoted (per spec §I):**
- `async_agent_jobs` → DEVELOPMENT (FLAKY)
- `crispy_workflow` → DEVELOPMENT (FLAKY)
- `task_harness_runtime` → REMOVED (ADVERTISED-BUT-NOT-BUILT)
- `multi_agent_swarm` → REMOVED (ADVERTISED-BUT-NOT-BUILT)
- `openhands_runtime` → REMOVED (ADVERTISED-BUT-NOT-BUILT)
- `sidecar_runtimes` → REMOVED (ADVERTISED-BUT-NOT-BUILT)
- `openclaw_integration` → REMOVED (ADVERTISED-BUT-NOT-BUILT — docs exist, code does not)
- `quick_actions_ios` → REMOVED (ADVERTISED-BUT-NOT-BUILT)
- `machine_peer_sync` → REMOVED (ADVERTISED-BUT-NOT-BUILT)
- `jcode_runtime` → REMOVED (ADVERTISED-BUT-NOT-BUILT)
- `tunnels` → DEVELOPMENT (FLAKY — ngrok stable but package unmaintained)
- `telegram_bot` → DEVELOPMENT (explicitly should be gated/isolated/removed per spec)

### Architecture Page Truth

The public site's architecture page must accurately represent:
- What the proxy does (OpenAI / Anthropic / Ollama routing)
- What the agent runner does (plan→execute→verify→judge loop)
- What the workflow engine does (phase sequence enforcement)
- What the doctor does (public/auth split, partial check list)
- What the CEO agent does (partial — no dedupe, no branch-protection-safe loop, no verified close)

**Current mismatch:** The architecture page may show the CEO agent as fully autonomous when it's only partially implemented.

---

## Site Structure

```
/ (index.html)
  ├── Features (STABLE/BETA/DEVELOPMENT tiers)
  ├── Architecture (what we actually have)
  ├── Install Guide
  ├── API Reference
  ├── Configuration Reference
  ├── Changelog
  └── Contributing Guide
```

---

## Content Rules

1. **No FLAKY features listed as STABLE**
2. **No ADVERTISED-BUT-NOT-BUILT features listed at all** (move to PLANNED if appropriate)
3. **Every claim must be verifiable** — if the homepage says "multi-agent swarm", the test suite must have tests that verify it works
4. **The AI must be able to use the site as ground truth** — if the site says something is implemented, the code must actually implement it

---

## Update Triggers

The public site must be updated when:
1. A feature moves from DEVELOPMENT to STABLE (after tests added and passing)
2. A feature is demoted (per spec §I feature matrix discipline)
3. A new STABLE feature is added
4. A feature is removed (per spec directive, e.g., telegram_bot)

---

## Verification

Before any public site update is committed:
- Run `pytest -x` — all tests must pass
- Verify feature matrix tiers match `docs/architecture/feature-matrix.md`
- If adding a STABLE feature, verify `tests/` has coverage for it