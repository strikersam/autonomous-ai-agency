# Competitor Analysis — Autonomous AI Agency

> Deep dive requested 2026-09. Every product-capability claim about **this repo**
> was re-derived from source on `master` (per CLAUDE.md rules 45–47), not from
> prose that may have drifted. Claims about **external products** are from public
> knowledge and tagged accordingly.

## 1. Fix the framing first: these are two different markets

The nine names on the onboarding "competitors" list are not one peer group.

| Name | Category | Actually a competitor? |
|------|----------|------------------------|
| OpenAI, Anthropic, DeepMind, x.ai | Foundation-model labs | **No** — they are our *suppliers*. We route calls to them via `packages/ai/router.py`. |
| CrewAI | Agent framework (OSS library) | Partial — overlaps our agent loop, but ships as a library, not a hosted agency. |
| n8n, Make, Zapier | Workflow / automation platforms | **Yes** — direct overlap on "orchestrate multi-step automated work." |
| Botpress | Conversational-agent builder | Partial — overlaps our chat + human-gate surface. |

Benchmarking the agency against DeepMind is a category error. The honest
competitor set is **five**: CrewAI, n8n, Make, Zapier, Botpress.

## 2. What this repo actually is (verified on `master`)

- **OpenAI-compatible proxy** (`proxy.py`) with three API surfaces (OpenAI `/v1/*`,
  Anthropic `/v1/messages`, Ollama `/api/*`), Bearer auth, rate limiting, CORS.
- **Multi-provider LLM router** (`packages/ai/router.py`) with a failover chain
  (NVIDIA NIM → TokenIn → Cerebras → Groq → Ollama), health watchdog, cost tiers.
- **plan → execute → verify agent loop** (`agent/loop.py`, `AgentRunner`) with a
  Verifier that must pass before `apply_diff()` runs.
- **CRISPY workflow engine** (`workflow/` — `engine.py`, `api.py`, `models.py`)
  with a hard `awaiting_approval` gate baked into the status machine. Backed by
  `tests/test_workflow_engine.py`, `test_workflow_models.py`, `test_crispy_workflow.py`.
- **40 autonomous loops** (`loops/registry.yaml`, verified count) — scheduled
  workflows + in-process daemons.
- **React dashboard** (`frontend/src/v5/`) — ~30 screens (providers, loops,
  schedules, governance, knowledge graph, tasks, agents…).
- **Integrations** (`packages/integrations/`): MCP registry + Render only.

## 3. Where we already beat the competitor set — keep and market these

| Strength | Why competitors don't have it |
|----------|-------------------------------|
| Multi-provider failover + cost-aware routing | n8n/Make/Zapier call one model per node; no failover chain, no cost tiering. |
| Verifier-gated autonomous code changes | CrewAI and n8n have no mandatory verify-before-apply safety gate. |
| Self-hosted, no per-task SaaS metering | Zapier/Make charge per task/operation; this runs on your own infra. |
| Hard human-approval gate as a *state-machine invariant* | Botpress/n8n approvals are optional nodes a builder can omit; ours is `awaiting_approval`, unskippable by design. |

## 4. The gaps worth closing (ranked by value ÷ effort)

### Gap A — The workflow engine is built but unreachable  ← **highest leverage**

**Finding (verified):** `workflow/api.py` defines `workflow_router` with 15+
endpoints (`/workflow/build`, `/approve`, `/reject`, `/resume`, `/cancel`,
`/slices`, `/artifacts`, `/checks`, `/verify`, `/events`, `/agents`). It is
**not mounted** in `backend/server.py` or `proxy.py` (`grep` returns nothing),
and there is **no frontend screen** for it (no `WorkflowScreen.jsx` among the v5
screens). We built n8n's actual differentiator — a visual, gated, multi-phase
workflow runtime — and left it switched off.

**Also found:** the `workflow_router` endpoints take only `Depends(_engine)` —
**no `get_current_user` / `_require_admin` dependency.** Mounting as-is would
violate CLAUDE.md rule 10 (every new endpoint authenticated). Auth must be added
in the same change that mounts it.

**Steal-from:** n8n's execution-history view, Make's per-step visual replay.

**PRs:**
- **PR2** — add auth to `workflow_router`, mount it, document in
  `docs/api-surfaces.md`, add a mount + auth test.
- **PR3** — `WorkflowScreen.jsx`: list runs, show the phase timeline, expose the
  approve/reject buttons the API already supports.

### Gap B — Connector catalog is nearly empty

**Finding (verified):** `packages/integrations/` contains only `mcp_registry.py`
(~10 registered entries) and Render helpers. Telegram + GitHub live elsewhere.
There is no third-party connector/trigger catalog.

**Reality check:** this is the Zapier/Make moat and it is genuinely large
(Zapier ships 6,000+ connectors). Do **not** try to match it. The realistic play
is a *connector registry abstraction* + a handful of high-value connectors
(Slack, HTTP-webhook trigger, Google Sheets), each its own small PR, plus a
catalog UI. Sequenced after Gap A.

### Gap C — Approval gates are hard-coded, not configurable

**Finding (verified):** the workflow gate is a fixed `awaiting_approval` state,
and CLAUDE.md rule 40 ("stop and ask a human before…") is policy in prose, not a
per-workflow setting. Botpress lets builders place approval nodes where they
want. Lower priority — our unskippable gate is arguably safer than a configurable
one; making it configurable trades safety for flexibility and should wait until a
user actually asks.

## 5. Recommended PR sequence

| PR | Scope | Risk | Changelog |
|----|-------|------|-----------|
| 1 | This document | none | exempt (`docs:`) |
| 2 | Auth + mount `workflow_router`; doc + test | low | required |
| 3 | `WorkflowScreen.jsx` UI over the mounted API | low | required |
| 4+ | Connector registry + first connector (Slack/webhook) | med | required |

**Not on the roadmap:** anything model-training-related, or attempting to
out-connector Zapier by volume. Those are losing bets for a self-hosted platform.
