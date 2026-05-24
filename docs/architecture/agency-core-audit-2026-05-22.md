# Agency Core — Ruthless Architecture Audit & Migration Plan

> Date: 2026-05-22
> Author: principal-architect pass (commissioned)
> Status: PROPOSAL — no code changes until approved
> Branch: `fix/reliability-hardening-2026-05-22`

This document is the mandated "before coding" deliverable: Sections 1–5
(brutal truth, Keep/Salvage/Replace/Remove, chosen foundation, the new Agency
Core, migration plan). It is grounded in the actual repository state, not
generic advice.

---

## Section 1 — The Brutal Truth

The repository is not one product. It is **four overlapping product attempts
fused into a single tree**, none of which fully owns its responsibility:

1. **An OpenAI-compatible LLM proxy / provider router** — `proxy.py` (61 KB),
   `provider_router.py` (47 KB), `chat_handlers.py`, `handlers/`. *This is the
   real, differentiated, mostly-working core.*
2. **A second web-app backend** — `backend/server.py`, a separate FastAPI app
   with its own bcrypt/JWT auth and a **MongoDB (Motor)** dependency. This is a
   parallel universe to `proxy.py` with a second auth model and a second source
   of truth.
3. **A sprawling autonomous-agent kitchen sink** — `agent/` (103 files,
   ~13.7k LOC): `agency.py`, `voice.py`, `browser.py`, `self_healing.py`,
   `improvement_loop.py`, `trend_watcher.py`, `security_scanner.py`,
   `knowledge_sync.py`, `v4_router.py`, and ~40 more. This is the "loose bundle
   of buggy agent features."
4. **A GitHub-Actions autonomous-bot fleet** — `agency-cycle.yml`,
   `ci-failure-autofix.yml` (auto-commits AI-generated patches to branches),
   `continuous-improvement.yml`, `openclaw-security-automation.yml`,
   `process-quick-note.yml` (26 KB), `weekly-trend-digest.yml`. These mutate the
   repo on their own, faster than any human can verify.

### Root causes (not symptoms)

- **No typed contract at the agent boundary.** `AgentRunner(` is constructed
  from `proxy.py` (×4), `backend/server.py`, `direct_chat.py`, and
  `runtimes/adapters/internal_agent.py` — each passing a slightly different
  kwarg set. The changelog is a graveyard of `TypeError: unexpected keyword
  argument 'provider_chain'`, missing `.plan()`, missing `metadata=`, stale
  `tool_callback`/`model_overrides`. **These are all the same bug**: the agent
  is invoked across module boundaries with positional/kwarg coupling and no
  Pydantic request/response contract and no contract test. It will recur on the
  next refactor.

- **Routing is smeared across five places**: `provider_router.py`,
  `router/model_router.py`, `routing/`, `runtimes/routing.py`,
  `agent/v4_router.py`. "Local vs remote default", Bedrock affinity, NIM
  fallback, and cooldown logic live in different files. Nobody can answer "where
  is the routing decision made?" in one sentence.

- **Three execution substrates compete.** `agent/loop.py` (`AgentRunner`),
  `runtimes/` (adapters + its own routing/control/manager/health), and
  `backend/server.py` each think they own task execution. `tasks/dispatcher.py`
  + `tasks/service.py` try to reconcile them and crash when a method is missing
  (`get_runtime` AttributeError in the changelog). **Idle runtimes are the
  visible symptom of this reconciliation failure.**

- **The autonomous bots are the bug factory.** `ci-failure-autofix` commits
  AI patches directly to branches; `agency-cycle` dispatches CEO directives;
  `process-quick-note`/`openclaw` run unattended. They generate change velocity
  that exceeds verification capacity. This is the literal "fixing the fixer"
  treadmill and the single largest operator-burden driver.

- **MongoDB in the hot path breaks CI.** The changelog shows the Motor client
  default timeout was 30 s, silently stalling every auth/login test. A network
  database for a single-node self-hosted proxy is the wrong default and the
  direct cause of local-vs-CI divergence.

- **Dead clutter erodes trust in the map.** Root `agent_loop.py` (5 lines),
  `agent_models.py` (16), `agent_tools.py` (4), `agent_state.py` (4),
  `agent_prompts.py` (12) are shims duplicating `agent/`. Untracked
  `tmp_test_pattern.md`/`scaffold_test_xyz.md` leaked into `.claude/skills/`
  from a test run. The CLAUDE.md "Codebase Map" no longer matches reality.

**Bottom line:** the system fails not because individual features are bad, but
because there is no spine. There is no single typed execution contract, no
single router, no single backend, no single runtime, and no gate between
autonomous change and verified change.

---

## Section 2 — Keep / Salvage / Replace / Remove

| Subsystem | Verdict | Why | Operator burden |
|---|---|---|---|
| `proxy.py` OpenAI-compat proxy + auth middleware | **KEEP** (canonical ASGI app) | Differentiated, works, is the natural single control plane | Reduces |
| `provider_router.py` provider selection (Bedrock/NIM/Ollama affinity) | **SALVAGE** | Logic is valuable but it's a 47KB monolith; extract a clean `ProviderPolicy` and make it the *only* router | Reduces after consolidation |
| `admin_auth.py`, `key_store.py`, `secrets_store.py`, `rbac.py` | **KEEP** (consolidate to one) | Governance/secrets are core and security-sensitive; keep one auth model | Reduces |
| `tasks/` (taskboard, store, models, dispatcher) | **SALVAGE** | Org/task/board concept is core to an agency; needs typed job contract + one runtime | Reduces |
| `agent/loop.py` `AgentRunner` | **REPLACE** (interface) | Keep the plan→execute→verify idea; replace the untyped constructor with a typed `AgentJobRequest`/`AgentJobResult` contract | Reduces a whole bug class |
| `router/`, `routing/`, `runtimes/routing.py`, `agent/v4_router.py` | **REMOVE / fold into one** | Five routers = nobody owns routing | Reduces |
| `backend/server.py` (2nd FastAPI + MongoDB) | **REPLACE** | Fold app-domain endpoints into `proxy.py`; drop Mongo for sqlite (already used in `.data/`, `direct_chat_sessions.db`) | Big reduction |
| MongoDB / Motor dependency | **REMOVE from hot path** | Network DB breaks CI parity; sqlite is the boring reliable default for single-node | Big reduction |
| `runtimes/adapters/` opencode/aider/goose/openclaw | **DEFER → experimental lane** | Multiple coding runtimes destabilize the golden path; pick ONE production runtime | Reduces |
| `direct_chat.py` (intent dispatch, doctor) | **SALVAGE** | This becomes the single human surface; needs the workflow state machine + sticky context, minus mode leakage | Reduces |
| `agent/doctor.py` + `runtimes/health.py` | **KEEP → promote** | Foundation of a claw-code-style doctor; consolidate into one diagnostics surface | Big reduction |
| `agent/voice.py`, `agent/browser.py`, `improvement_loop.py`, `trend_watcher.py`, `self_healing.py` | **DEFER → experimental lane** | Conceptually nice, operationally destabilizing; gate behind flags, off by default | Reduces |
| `frontend/` (React dashboard) | **KEEP** | Real UI; make data loading partial-failure tolerant (allSettled already started) | Neutral→Reduces |
| `webui/`, `remote-admin/`, `admin_gui.py` | **REMOVE / pick one** | Three+ UIs for the same job | Reduces |
| Autonomous workflows: `agency-cycle`, `ci-failure-autofix`, `continuous-improvement`, `openclaw-security-automation`, `process-quick-note`, `weekly-trend-digest` | **QUARANTINE** (manual `workflow_dispatch` only) | They create unverified churn; re-enable selectively after core is stable + gated | Huge reduction |
| `ci.yml`, `changelog-check.yml`, `pull-request.yml`, `security-scan.yml` | **KEEP / harden** | Legit guardrails; make CI==local parity canonical | Reduces |
| Root shims: `agent_loop.py`, `agent_models.py`, `agent_tools.py`, `agent_state.py`, `agent_prompts.py` | **REMOVE** | Dead duplicates of `agent/` | Reduces |
| `telegram_bot.py`, `commercial_equivalent.py`, `cost_insights.py`, `infra_cost.py`, `social_auth.py` | **DEFER / evaluate** | Peripheral; not in golden path | Neutral |
| Knowledge: `agent/knowledge_sync.py`, `memory/`, wiki/sources | **SALVAGE** | Company graph / knowledge is core to the agency vision; needs one canonical store | Reduces |
| Untracked `tmp_test`/`scaffold_test` pattern files | **REMOVE + gitignore** | Test leakage | Reduces |

---

## Section 3 — The Chosen Foundation

A hybrid, adopting the strongest idea from each reference and discarding the
rest.

- **Claude Code → interaction contract.** Direct chat is the *single* top-level
  human surface. No mode toggles, no metadata-first UX, no backend leakage.
  Intent is classified internally; the user just talks.

- **oh-my-codex → workflow discipline.** Execution is a **typed state machine**,
  not "chat + tools": `classify → clarify → plan → select specialist →
  preflight/doctor → bind context → execute → verify → judge/release-gate →
  summarize → monitor → reopen`. State is persisted so a job survives restarts
  (fixes "runtime went idle, lost the work").

- **claw-code → doctor-first.** A real `doctor` gate runs *before* execution and
  is the first thing run when anything is wrong: runtime doctor, GitHub/repo
  doctor, CI-parity doctor, dashboard/API doctor, onboarding doctor, plus
  "why didn't this task run?" diagnostics. Consolidates `agent/doctor.py` +
  `runtimes/health.py`.

- **CompanyHelm → isolated reliable runtime.** **One** production runtime:
  git-worktree-per-task isolation, safe defaults, multi-repo capable, can run
  tests and reproduce CI. Every other runtime (opencode/aider/goose/openclaw) is
  demoted behind an experimental flag and never in the default path.

- **local-llm-server → what's worth keeping.** Provider routing/proxy
  (consolidated to one), governance/secrets/admin (one auth), org/task/board,
  knowledge graph, and company-specific specialist routing.

Guiding principle for every call: **boring, reliable defaults; one dominant path;
simpler at the core even if some edge features are deferred.**

---

## Section 4 — The New Agency Core

A single ASGI control plane (`proxy.py`) exposing the OpenAI-compat surface
**and** the agency control plane, backed by sqlite, with one router, one runtime,
one agent contract, one doctor.

```
                ┌─────────────────────────────────────────────┐
   Direct Chat  │  Interaction layer (Claude Code-style)        │
   (single UI)  │  intent classify · clarify · sticky context   │
                └───────────────────────┬─────────────────────┘
                                        │  AgentJobRequest (typed)
                ┌───────────────────────▼─────────────────────┐
                │  Workflow Engine (oh-my-codex state machine)  │
                │  plan→specialist→preflight→bind→exec→verify   │
                │  →judge→summarize→monitor→reopen  (persisted) │
                └───┬───────────────┬───────────────┬─────────┘
                    │               │               │
            ┌───────▼──────┐ ┌──────▼───────┐ ┌─────▼─────────┐
            │ Doctor /     │ │ One Runtime  │ │ One Provider  │
            │ Diagnostics  │ │ (worktree    │ │ Router        │
            │ (claw-code)  │ │  isolation,  │ │ (Bedrock/NIM/ │
            │              │ │  CompanyHelm)│ │  Ollama)      │
            └──────────────┘ └──────────────┘ └───────────────┘
                    │
            ┌───────▼───────────────────────────────────────────┐
            │  Company Graph (sqlite): company · domain · systems │
            │  · repos · envs · docs/knowledge · workflows ·       │
            │  specialists · tasks/issues/PRs · quick actions      │
            └─────────────────────────────────────────────────────┘
                    ▲
            ┌───────┴───────────────────────────────────────────┐
            │  Onboarding / Discovery Engine: URL → infer stack → │
            │  detect systems → tailored questions → provision    │
            │  company-specific specialists                       │
            └─────────────────────────────────────────────────────┘
```

### The seven pillars (concrete mapping)

1. **Onboarding/discovery engine** — NEW. Input: production URL (+ optional
   repos/docs/creds/goals). Inspects the site (fetch + heuristics), infers stack
   (CMS/commerce/PIM/OMS/DAM/SEO/analytics/CRM/support), asks tailored questions,
   builds the company profile, provisions specialists. Greenfield; built on top
   of the stable core, not entangled with it.
2. **Company graph** — NEW canonical sqlite store; absorbs scattered
   memory/knowledge/sources. The durable operating context.
3. **Workflow-first execution engine** — REPLACES ad-hoc chat+tools. Typed state
   machine, persisted, restart-safe.
4. **One isolated runtime** — CONSOLIDATES `runtimes/` + `agent/loop.py` into a
   single worktree-isolated production runtime; others gated.
5. **Direct chat as the human interface** — SALVAGE `direct_chat.py`; remove mode
   leakage; sticky company/repo/task context.
6. **Doctor/diagnostics/parity** — PROMOTE `agent/doctor.py` + `runtimes/health.py`
   into one surface + a canonical `make doctor` / `/api/doctor`.
7. **Safe agency automation** — REDESIGN CEO/specialists: dedupe (started in
   `agency.py`), no infinite loops, branch+PR-safe, verified issue closure,
   domain-aware specialist routing driven by the company graph.

### The single typed contract (kills the recurring bug class)

```python
# agent/contract.py  (new, the spine)
class AgentJobRequest(BaseModel):
    goal: str
    repo: str | None = None
    workspace_root: str | None = None
    mode: Literal["plan", "execute", "verify"] = "execute"
    metadata: dict[str, Any] = Field(default_factory=dict)
    # provider/runtime selection live behind policy objects, NOT loose kwargs

class AgentJobResult(BaseModel):
    status: Literal["completed", "blocked", "failed", "degraded"]
    summary: str
    artifacts: list[Artifact] = []
    events: list[ProgressEvent] = []
```

Every call site (`proxy.py`, `direct_chat.py`, `runtimes/adapters/`, tasks)
constructs an `AgentJobRequest` — never loose kwargs. A contract test asserts no
caller passes anything else. **This single change retires `provider_chain`,
`metadata`, `tool_callback`, `model_overrides` drift permanently.**

---

## Section 5 — Migration Plan (minimal chaos, all on PR, CI green at each step)

Work in small, individually-green commits on the PR branch. Merge only when CI is
fully green E2E. Each phase is independently shippable.

**Phase 0 — Stabilize & quarantine (no behavior change).**
- Finish the in-flight reliability fixes already staged on this branch.
- Quarantine autonomous workflows to `workflow_dispatch`-only (stop the churn
  machine) — `agency-cycle`, `ci-failure-autofix`, `continuous-improvement`,
  `openclaw-security-automation`, `process-quick-note`, `weekly-trend-digest`.
- Delete dead root shims + untracked test-pattern leakage; gitignore the latter.
- Make `make ci-parity` the canonical CI==local command; document it.

**Phase 1 — The spine: typed agent contract.**
- Introduce `agent/contract.py` (`AgentJobRequest`/`AgentJobResult`).
- Migrate all `AgentRunner(` call sites to the contract; add a contract test that
  fails if any caller passes unknown kwargs.
- Outcome: signature-drift bug class is gone.

**Phase 2 — One router.**
- Extract `ProviderPolicy` from `provider_router.py`; delete `routing/`,
  `runtimes/routing.py`, `agent/v4_router.py`; route everything through it.
- Tests in `tests/test_model_router.py` updated (per CLAUDE.md rule).

**Phase 3 — One backend, sqlite.**
- Fold `backend/server.py` app-domain endpoints into `proxy.py`; standardize on
  sqlite; remove Motor/MongoDB from the default path (keep an optional adapter).
- Outcome: CI parity becomes structural; no 30 s Mongo stalls.

**Phase 4 — One runtime.**
- Consolidate `runtimes/` + `agent/loop.py` into a single worktree-isolated
  production runtime; demote opencode/aider/goose/openclaw behind a flag.
- Fix `tasks/dispatcher.py`↔runtime reconciliation so idle never means "lost."

**Phase 5 — Doctor & dashboard resilience.**
- Consolidate doctors; add `/api/doctor` + `make doctor`.
- Frontend: partial-failure tolerance everywhere (extend the allSettled fix);
  endpoint-specific diagnostics instead of one generic network error.

**Phase 6 — Workflow engine + safe agency.**
- Implement the persisted state machine; redesign CEO/specialists to be
  branch/PR-safe with verified issue closure and domain-aware routing.

**Phase 7 — Onboarding/discovery + company graph (the product vision).**
- Build URL→stack-inference→tailored-questions→specialist-provisioning on top of
  the now-stable core.

### Acceptance check
The result is successful only if: the core is simpler and stronger; direct chat
feels like one coherent assistant; onboarding-from-URL is first-class; company
agency instantiation is in the design; Git/GitHub/CI/test/runtime pain is
structurally reduced; unstable features no longer destabilize the core; and the
agents reduce maintenance burden instead of creating it.
