# API Surfaces and Route Map

This file is the technical companion to the README.
If you want the human-friendly product story, start with [../README.md](../README.md).

---

## Main proxy (`proxy.py`)

### OpenAI-compatible
- `POST /v1/chat/completions`
- `GET /v1/models`
- `POST /v1/messages` (Anthropic-compatible messages)
- passthrough support for additional `/v1/*` routes

### Ollama-compatible
- `/api/*` passthrough for Ollama-native routes such as chat and generate

### Built-in admin and web UI
- `/admin/ui/*`
- `/admin/api/*`
- `/app`
- `/admin/app`
- `/ui/api/*`

### Agent and workflow surfaces
- `/agent/*` — agent sessions, memory, budgets, browser, voice, schedules, playbooks, terminal, skills, commits, scaffolding
- `/v2/agent/coordinate` — multi-agent coordination
- `/workflow/*` — CRISPY workflow engine

### Control-plane style routers mounted in the proxy
- `/api/auth/*`
- `/api/social/*`
- `/api/chat/*`
- `/api/models/*`
- `/api/providers/*`
- `/api/stats`
- `/api/activity`
- `/api/hardware/*`
- `/api/secrets/*`
- `/api/setup/*`
- `/api/observability/*`
- `/api/github/*`
- `/api/sync/*`
- `/api/tasks/*`
- `/api/agents/*`
- `/api/schedules/*`
- `/api/routing/*`
- `/runtimes/*`

---

## Separate hosted dashboard backend (`backend/server.py`)

The `backend/` app powers the separate React control plane and includes routes for:

- auth and social login
- chat sessions
- wiki pages and linting
- source ingestion
- providers and models
- API key management
- observability summaries and metrics
- platform info and activity
- GitHub repo, branch, file, and PR flows
- schedules and legacy scheduler compatibility routes
- governance: posture, policy, approvals, audit, sandboxes, and session budgets (`/api/governance/*`, admin-only)
- Telegram bot control-plane (`/api/telegram/*`)

### Telegram (`/api/telegram/*`)

- `GET  /api/telegram/diag` — unauthenticated diagnostic snapshot (bot token masked). Reports config (`run_telegram_bot`, `poller_disabled`, allow/admin IDs) **and live state**: `poller_last_poll_age_sec` / `poller_running_here` (is the getUpdates consumer draining updates in this process?) and `webhook` (`has_webhook`, `pending_update_count`, `last_error_message`). Use it when cards arrive but inline buttons do nothing.
- `POST /api/telegram/webhook` — inbound Telegram webhook (the non-polling delivery path). Authenticated by the `X-Telegram-Bot-Api-Secret-Token` header matched against `TELEGRAM_WEBHOOK_SECRET` (mismatch/unset → 403); no JWT. Active only when `TELEGRAM_WEBHOOK_ENABLED=true` + secret set, in which case startup registers the webhook and the getUpdates poller is not started. Dispatches to the same callback/message handlers as polling.

### Governance (`/api/governance/*`, admin-only)

Read and operate the governance layer. Every route requires an authenticated
admin. Policy authoring is propose-only — the live policy file is never written
over HTTP; a proposed change opens a pull request that a human reviews and merges.

- `GET  /api/governance/status` — mode, policy source/version, sandbox posture
- `GET  /api/governance/policy` — the effective (compiled) policy document
- `GET  /api/governance/policy/raw` — the raw `config/agent_policy.yaml` text (for the editor)
- `POST /api/governance/policy/reload` — re-read the policy file
- `POST /api/governance/policy/simulate` — dry-run a decision, no action taken
- `POST /api/governance/policy/validate` — validate a proposed policy + return a diff
- `POST /api/governance/policy/propose` — open a PR carrying a proposed policy (requires `GH_PAT`)
- `GET  /api/governance/audit` — recent audit events, filterable
- `GET  /api/governance/metrics` — counters for dashboards/Prometheus
- `GET/POST /api/governance/approvals[...]` — pending approvals and approve/deny
- `GET/POST/DELETE /api/governance/sandboxes[...]` — live sandboxes, reap, destroy
- `GET  /api/governance/budget[/{session_id}]` — live per-session budgets

### Connectors (`/api/connectors/*`, `backend/connectors_api.py`, admin-only)

The connector catalogue — the first step toward a Zapier/Make-style integration
library. Every route requires an authenticated admin (connectors reach external
services deployment-wide). Backed by `packages/integrations/connector_registry.py`.

- `GET  /api/connectors/` — list the connector catalogue (metadata only)
- `POST /api/connectors/webhook/send` — run the webhook action: POST a JSON event
  to a public URL. The URL clears the SSRF guard (`unsafe_target_reason`, rule 14)
  before the first request and redirects are never followed; a non-public target
  returns `{"ok": false, "error": "unsafe target: …"}` without reaching out.
### CRISPY Workflow engine (`/api/workflow/*`, `workflow/api.py`, admin-only)

The plan→execute→verify workflow runtime. Every route requires an authenticated
admin (the router carries no auth of its own; `backend/server.py` applies a
router-level admin dependency at mount time — the engine can write code). A run
pauses at the hard `awaiting_approval` gate before any code is written; no code
path can skip it.

- `POST /api/workflow/build` — create + start a run (returns 202; runs pre-gate phases async)
- `GET  /api/workflow/` — list runs, newest first (paginated, `status` filter)
- `GET  /api/workflow/{run_id}` — full run state (phases, slices, artifacts)
- `POST /api/workflow/{run_id}/approve` — lift the approval gate; begin post-gate execution
- `POST /api/workflow/{run_id}/reject` — reject the plan; the run fails
- `POST /api/workflow/{run_id}/resume` — resume a paused/interrupted run
- `POST /api/workflow/{run_id}/cancel` — cancel a non-terminal run
- `GET  /api/workflow/{run_id}/slices` · `POST /api/workflow/{run_id}/slices/{slice_id}/run`
- `GET  /api/workflow/{run_id}/artifacts[/{name}]` — artifact list / raw content
- `GET  /api/workflow/{run_id}/checks` · `POST /api/workflow/{run_id}/verify`
- `GET  /api/workflow/{run_id}/events` — positional, append-only event log (poll by `from_position`)
- `GET  /api/workflow/agents` — agent team composition (coder model ≠ reviewer model invariant)

### SEO / GEO / AIO (`/api/**/seo/*`, `backend/seo_api.py`)

Audit a website, then turn the findings into delivery artifacts. Every route
requires an authenticated user (`_get_current_user_thunk`), and every
company-scoped route additionally checks access to that company via
`get_company_access` — an audit belonging to another company answers `404`.

- `GET  /api/seo/checks` — the full SEO/GEO/AIO check catalog
- `POST /api/company/{company_id}/seo/audit` — run an audit and persist the evidence
- `GET  /api/company/{company_id}/seo/audits` — stored audits, most recent first
- `GET  /api/company/{company_id}/seo/audits/{audit_id}` — one complete report
- `GET  /api/company/{company_id}/seo/audits/{audit_id}/export` — export a stored audit
- `POST /api/company/{company_id}/seo/audits/{audit_id}/delegate` — create agent tasks from the delegation plan
- `POST /api/company/{company_id}/seo/audits/{audit_id}/roadmap` — Now/Next/Later roadmap, WSJF-scored
- `POST /api/company/{company_id}/seo/audits/{audit_id}/sprint` — a sprint plan from the same backlog
- `POST /api/company/{company_id}/seo/audits/{audit_id}/pipeline` — audit → portfolio → roadmap → sprint in one call
- `POST /api/company/{company_id}/seo/fix` — repo-aware auto-fixer against the company's workspace checkout

This backend is typically used with:
- `frontend/` on port `3000`
- `backend/server.py` on port `8001`

---

## Supporting technical docs

- [Feature guide](features.md)
- [Configuration reference](configuration-reference.md)
- [Architecture overview](architecture/overview.md)
- [Model routing guide](model-routing.md)
- [Claude Code setup](claude-code-setup.md)
