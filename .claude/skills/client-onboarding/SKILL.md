---
name: client-onboarding
description: >
  Onboard a new client/company onto this platform's real Agentic OS: create the
  company record, scan its websites/repos, auto-provision specialist agents,
  activate its 24x7 agency runtime, and know exactly which "OS" building blocks
  (memory, integrations, dashboard) already exist versus which are roadmap gaps.

  ADAPTED FROM: a third-party giveaway skill ("agentic-os-installer" by Gennaro
  Santoro / Operations Heroes) that described a generic vault + Google-suite +
  skill-pack installer. That skill's product (Obsidian vault, Gmail/Calendar/
  Drive wiring, "skill packs") does not exist in this repo and its promotional
  content (Skool community link) does not belong here. This is a clean-room
  rewrite that keeps the useful idea — "stand up a working agency OS for a
  client from a short checklist" — and maps every step to the real module that
  already implements it in this codebase, per CLAUDE.md architecture rules.
triggers:
  - "onboard a new client"
  - "onboard a new company"
  - "set up a new agency for"
  - "add a client to the platform"
  - "provision specialists for"
references:
  - services/onboarding.py
  - services/company_graph_store.py
  - services/specialist.py
  - services/company_agency.py
  - models/company_graph.py
  - backend/company_api.py
  - frontend/src/v5/screens/OnboardingScreen.jsx
  - CLAUDE.md
---

# Skill: client-onboarding

## Fill these in

| Fill in | What it is | Example |
|---|---|---|
| `COMPANY_NAME` | Display name for the new client company | Bright Studio |
| `WEBSITE_URLS` | Public site(s) to scan for stack/systems detection | ["https://brightstudio.com"] |
| `REPO_URLS` | Optional repos to scan for code-level detection | ["https://github.com/brightstudio/app"] |
| `OWNER_ID` | User account that owns/administers this company | strikersam@gmail.com's user id |

If any are missing, run onboarding with what you have — `website_urls` can be
empty and specialists can still be provisioned manually afterward.

## What this maps to (real code, not a generic scaffold)

| Giveaway-skill concept | This repo's actual implementation |
|---|---|
| "Scaffold the memory layer / vault" | `CompanyGraphStore` (`services/company_graph_store.py:52`) persists `Company`, `CompanyGraph`, `Specialist`, `Workflow`, `KnowledgeItem`, `Connector`, `ApprovalPolicy` (Mongo primary / SQLite fallback). There is no notes vault — knowledge lives in `KnowledgeItem` records (`create_knowledge_item`/`search_knowledge`, `company_graph_store.py:337-378`). Agent-runtime memory (separate concern) lives in `agent/memory.py` and `agent/persistent_memory.py`. |
| "Wire in the Google suite (Gmail/Calendar/Drive)" | **Does not exist yet.** `packages/auth/oauth.py` only implements Google OAuth2 *login* (`GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`, `/api/auth/google/login`) — no Gmail, Calendar, or Drive API integration. Do not tell a client this is available; if they need it, file it as a new `Connector` type (see `models/company_graph.py`) rather than faking it. |
| "Drop in requested skill packs (research, content, ops, data)" | `SpecialistService.provision_specialists_for_company` (`services/specialist.py`) auto-provisions specialists from a ~33-family catalog (engineering, qa, security, devops, data, ml, frontend, backend, marketing, research, support, trading, portfolio, agile, ...) based on systems detected during scanning — not a manual pack install. |
| "Build the command-center dashboard" | Already built: `frontend/src/v5/screens/DashboardScreen.jsx` (health/stats/activity/providers/tasks), `AgentsScreen.jsx`, `CompanyScreen.jsx`, `SkillsScreen.jsx`. Nothing to scaffold — the new company just needs to be onboarded into it. |
| "Brand it and write a README" | Company display name + branding lives on the `Company` record itself (`models/company_graph.py`); no separate README artifact is generated per client. |

## Workflow

### Step 1 — Create the company and kick off onboarding

Via API (`backend/company_api.py`):

```bash
# Create company record (router prefix is /api/company, see backend/company_api.py:96)
# body shape is CompanyCreateRequest (models/company_graph.py:1966): name + domain required
curl -X POST "$API_BASE/api/company" \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"name": "COMPANY_NAME", "domain": "brightstudio.com"}'

# Start the real onboarding pipeline for that company_id
curl -X POST "$API_BASE/api/company/{company_id}/onboarding/start" \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"website_urls": WEBSITE_URLS, "repo_urls": REPO_URLS}'
```

Or programmatically, from `services/onboarding.py`:

```python
from services.onboarding import OnboardingService

service = OnboardingService()
progress = await service.start_onboarding(
    company_id="company_123",
    website_urls=["https://brightstudio.com"],
    repo_urls=[],
)
```

This runs the fixed 8-step pipeline (`OnboardingService.ONBOARDING_STEPS`):
`create_company → scan_websites → scan_repositories → detect_systems →
provision_specialists → create_workflows → complete → activate_agency`.

### Step 2 — Poll progress

```bash
curl "$API_BASE/api/company/{company_id}/onboarding" -H "Authorization: Bearer $JWT"
```

Or via UI: `frontend/src/v5/screens/OnboardingScreen.jsx` renders the same
`OnboardingProgress` model live.

### Step 3 — Verify specialists were provisioned

```bash
curl "$API_BASE/api/company/{company_id}/specialists" -H "Authorization: Bearer $JWT"
```

Expect specialists matching the systems `scan_websites`/`scan_repositories`
detected (e.g. a Next.js site + Stripe → `frontend`, `ecommerce`, `payments`
specialists). If the list is empty, call
`POST /api/company/{company_id}/specialists` to provision manually, or
re-run onboarding with `auto_provision_specialists=True`.

### Step 4 — Confirm the 24x7 agency runtime is live

The final `activate_agency` step calls `CompanyAgency.activate_company()`
(`services/company_agency.py`) in the background. Confirm via the Doctor
endpoint (`GET /api/company/doctor/public`) or `AgentsScreen.jsx` in the
dashboard — specialists should show as running, not just provisioned.

### Step 5 — Note real gaps instead of pretending they're solved

If the client asks for Gmail/Calendar/Drive automation, a notes vault, or
manually-curated "skill packs": these are not implemented. Log them as a
`Connector`/`KnowledgeItem` feature request (see `models/company_graph.py`)
or a task in `.claude/state/active-tasks.md` rather than fabricating the
integration. Do not add a dependency on an external community/product link —
this platform is self-hosted (CLAUDE.md §1, Non-goals).

## Acceptance checks

- [ ] Company record created (`GET /api/company/{company_id}` returns 200)
- [ ] Onboarding progress reaches `complete` then `activate_agency`
- [ ] At least one specialist provisioned and visible in `AgentsScreen.jsx`
- [ ] Doctor/health check for the company shows green
- [ ] Any requested-but-unsupported integration (Gmail/Calendar/Drive, vault)
      is explicitly called out as unsupported, not silently skipped
