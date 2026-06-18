# Autonomy Charter — Telegram-Gated Self-Running Agency

> **Status:** Authoritative operating spec. This document fuses the platform's
> existing autonomy engines into one directive so the agency runs **fully
> autonomously for itself and every onboarded website**, pausing only at a
> **Telegram human-approval gate** for risky / outward-facing actions.
>
> **Companion:** [`MASTER_PROMPT.md`](./MASTER_PROMPT.md) is the copy-paste directive
> that operationalizes this charter. Deeper SDLC mechanics live in
> [`../architecture/autonomous-sdlc-loop.md`](../architecture/autonomous-sdlc-loop.md);
> the free-brain provider policy in
> [`../context/free-brain-provider-policy.md`](../context/free-brain-provider-policy.md).
> Legend below: ✅ wired · ⚠️ partial · 📋 design-only.

---

## 1. Mission & operating principles

The platform is an **autonomous software agency**. It maintains and improves itself
and every company it onboards — detecting and fixing bugs, generating features,
applying industry trends, and shipping through an agentic SDLC — **without waiting
for a human**, except at the gate.

1. **Autonomous by default, gated by exception.** Run the loop unattended; stop for a
   human only when an action is *risky* or *outward-facing* (§3).
2. **Free brain first.** Use free cloud LLMs (§2); never spend on paid models unless
   `allow_paid` is explicitly enabled.
3. **Never act alone.** Every change passes Verifier → JUDGE → `_local_safety_check`
   → bounded retries (≤3) before it can land. The free brain is sufficient *because*
   of this scaffolding, not in spite of it.
4. **Never silently drop work.** Anything that can't proceed lands in a typed paused
   state (`awaiting_approval`, `awaiting_repo_connection`, `budget_exceeded`, …),
   visible on the board — never lost.
5. **Respect each repo's reality.** Conform to the target repo's delivery policy;
   never force a PR where direct push is the norm, never push where protection forbids.
6. **Everything is observable.** Every autonomous decision is logged to KPIs
   (`agent/kpi.py`, `/api/kpi/public`) and the activity feed.

---

## 2. Brain policy (free cloud LLMs)

**Verdict on capability:** sufficient for the full loop. The resolver
`services/workflow_orchestrator.py::_resolve_brain_provider` (✅) calls `_pick(allow_paid=False)`
first and only escalates to a paid model when policy explicitly permits — so free is
the default path, not a fallback.

**Priority order** (`provider_router.py`, ✅):

```
NVIDIA NIM  →  Groq · Cerebras · SambaNova · DeepSeek · Mistral · Gemini (free tiers)
            →  Kimi web-bridge  →  local Ollama (qwen3-coder, deepseek-r1)
```

- **Role split:** reasoning model (deepseek-r1 / nemotron) for *plan* and *judge*;
  coder model (qwen3-coder) for *execute*. Task-aware via `router/classifier.py` +
  `router/registry.py`.
- **`allow_paid=false` is the durable default** (`scripts/insert_provider_policy.py`,
  `agents/store.py::cost_policy` = `local_only | allow_paid | budget_X`; policy doc
  📋 PR #603). Health checks + cooldowns + priority fallback already handle provider
  outages.
- **Honest limit + mitigation:** free models are weakest on very large multi-file
  refactors. Mitigation is structural, not a paid upgrade: the **CEO decomposes**
  (`services/ceo_dispatcher.py`, ✅) into bounded sub-tasks, and anything still risky
  routes to the **gate** (§3). A capability gap becomes a *gated decision*, never a
  silent bad merge.

---

## 3. The Gate Matrix (core artifact)

Three lanes. The orchestrator already exposes the machinery: a run can enter
`awaiting_approval` (`backend/server.py`, ✅) and resume via
`POST /api/workflow/orchestrator/approve/{run_id}` → `orchestrator.approve_async(...)`
(✅). The plan-gate engine also exposes `POST /workflow/{run_id}/approve|reject`
(`workflow/api.py`, ✅).

### 🟢 Autonomous — run, then notify-only
- Bug fixes derived from logs / CI failures
- Test additions & fixes; coverage backfill
- Internal refactors that don't touch §🔴 paths
- Documentation updates
- Patch-level dependency bumps
- Trend research, ingestion, and knowledge-base sync
- Plan / context generation; code-quality, SEO, and content **drafts**

### 🔴 Telegram GATE — pause for approve/reject before proceeding
- Changes to **auth / keys / billing / secrets** and sensitive paths:
  `admin_auth.py`, `key_store.py`, `agent/tools.py`, payments, infrastructure
- **Merges to a deployment branch** (master/main/release)
- **Deploys / releases / tags**
- **Destructive operations** (delete branch/file/data, history rewrite, force-push)
- **Major** (semver-major) dependency upgrades
- **Spend over the company budget** (would require `allow_paid` / `budget_X`)
- The **first unattended merge on a newly onboarded repo** (until the operator
  confirms its detected delivery policy)

### 🔵 Notify-only FYI — no action required
- Task started; autonomous-track plan ready
- Routine completions; daily KPI / health digest

> **Rule of thumb:** if uncertain whether an action is 🔴, treat it as 🔴 and gate it.
> The cost of an unnecessary ping is far lower than an ungated risky action.

---

## 4. Telegram gate protocol

```
run enters awaiting_approval
   └► NotificationDispatcher (telegram_service.py ✅) pushes a message:
        • run_id + company + goal
        • plan summary (steps)
        • risk reason (which 🔴 trigger fired)
        • inline [✅ Approve] [❌ Reject] buttons
   └► button callback → approve: POST /api/workflow/orchestrator/approve/{run_id}
                        reject : decline/cancel the run with a reason
   └► decision persisted (durable) + written to the activity feed / KPIs
   └► timeout: re-ping once; if still unanswered → safest path
        (hold the run / leave at an open PR — never auto-proceed on a 🔴 action)
```

- The bot (`telegram_bot.py`, ✅) already supports inline keyboards + callback
  handlers and an allowlist (`TELEGRAM_ALLOWED_USER_IDS` / `TELEGRAM_ADMIN_USER_IDS`).
- Notifications redact secrets/emails/IPs (`_redact_for_notification`, ✅) before send.
- Approvals are **scoped**: a user may approve only their own company's runs (admin: any).

**Bridge still to wire (⚠️ → see §6):** today `NotificationDispatcher` fires on task
*completion*; it does **not yet proactively push** when a run *enters*
`awaiting_approval`. Closing that bridge is what turns the existing pieces into a live
gate.

---

## 5. The five autonomous loops

Each loop is built from existing engines; the ⚠️/📋 markers flag what must still be
wired (consolidated in §6).

### Loop 1 — Self-heal from logs *(closed loop)*
```
runtime ERROR/CRITICAL  →  log_monitor (⚠️, rate-limited by signature)
   →  self_healing classifies (✅)  →  improvement_loop creates a fix task (✅)
      →  agentic SDLC (Loop 3) implements + verifies  →  PR
         →  CLOSE THE LOOP (⚠️): confirm the error signature no longer recurs
            in logs before marking the heal resolved; else re-open / escalate.
```

### Loop 2 — Feature generation
```
improvement_loop signals (TODO/FIXME, coverage gaps, perf) (✅)
   + portfolio WSJF scoring (agents/portfolio*.py ✅)
      →  ranked, capability-tagged tasks (auto task-gen from roadmap = ⚠️)
         →  Loop 3.
```

### Loop 3 — Agentic SDLC (the golden path)
```
CLASSIFY → PLAN → [🔴 gate?] → EXECUTE → VERIFY → JUDGE → land
```
- Driven by `services/workflow_orchestrator.py` (✅) + `agent/loop.py::AgentRunner` (✅),
  CEO decomposition (✅), per-task git worktrees (✅).
- **Repo-agnostic landing** per `RepoConnection` + detected `DeliveryPolicy`
  (📋 design — Phases 0–4 in `autonomous-sdlc-loop.md`). Until built, the loop stops at
  a reviewable PR. Merge to a deployment branch is always a 🔴 gate (§3).

### Loop 4 — Trends contextually applied
```
trend_watcher: 13 public sources, score relevance (✅)
   ≥0.6 → DetectedIssue in improvement loop (✅)
   ≥0.75 → auto-dispatch to Hermes for issue/PR (✅, needs HERMES_BASE_URL)
   →  knowledge_sync keeps the KB current (✅)
```
- **Per-company scoping (⚠️):** today relevance is scored against the *platform's*
  keyword set. For full autonomy, score each trend against **each onboarded company's
  detected stack** (`services/scanner.py` output on the Company graph) so a React shop
  gets React trends and an infra client gets infra trends. Resulting changes still pass
  the Gate Matrix.

### Loop 5 — Per-onboarded-site autonomy
- Onboarding (`services/onboarding.py`, ✅) scans the site, provisions specialists,
  seeds workflows, and starts 24×7 cadences (`services/company_agency.py`, ✅:
  health scan, security audit, stack-change, code-quality, trend watch, graph sync).
- **Capability split** (📋 `TaskCapability` design): `NONE` work (research/SEO/content/
  monitoring) runs for **URL-only** companies with no repo; `REPO_READ`/`REPO_WRITE`
  work pauses `awaiting_repo_connection` until a repo + token is connected, then
  auto-resumes — never fails, never fabricated.

---

## 6. Integration gaps to wire (follow-up implementation)

The loops above are real; these **bridges** close the loop end-to-end. Each is small
and additive — G1 is now wired; G2–G5 remain follow-up work:

| # | Bridge | Touch points | Lane | Status |
|---|--------|-------------|------|--------|
| G1 | **Proactive Telegram push on `awaiting_approval`** (the live gate) | `services/workflow_orchestrator.py::_notify_approval_gate` → `telegram_service.NotificationDispatcher.send_approval_gate`; `wfo:approve:<run_id>` / `wfo:reject:<run_id>` inline callbacks in `telegram_bot.py` | enables 🔴 | ✅ wired |
| G2 | **Closed-loop self-heal feedback** — confirm error signature gone post-fix | `agent/self_healing.py` (heal ledger: detected→fixing→verifying→resolved/regressed/awaiting_human) ↔ `agent/log_monitor.py::note_recurrence` | 🟢 | ✅ wired |
| G3 | **Auto issue→task intake** (GitHub issues / scanner signals → Task records) | webhook listener → `tasks/dispatcher.py` | 🟢/📋 | 📋 |
| G4 | **Per-company trend scoping** — score trends vs each company's detected stack | `agent/trend_watcher.py` + Company graph (`services/scanner.py`) | 🟢/🔴 | 📋 |
| G5 | **`RepoConnection` + `DeliveryPolicy` plumbing** (SDLC Phases 0–4) | per `autonomous-sdlc-loop.md` | enables Loop 3 landing | 📋 |

G1 also lands the **`TELEGRAM_CHAT_ID` single-operator convention**: one numeric
Telegram user ID covers bot auth (`TELEGRAM_ALLOWED_USER_IDS`/`TELEGRAM_ADMIN_USER_IDS`),
notification delivery (`TELEGRAM_NOTIFY_CHAT_IDS`), and the approval-gate push above —
see [`docs/telegram-bot.md`](../telegram-bot.md#step-3--configure-env).

Each bridge change to a risky path (auth/keys/`agent/tools.py`) follows the
`risky-module-review` skill and the CLAUDE.md coding rules.

---

## 7. Definition of "fully autonomous" — acceptance criteria

The platform is fully autonomous when **all** hold:

- [ ] A new runtime error appears in logs and is fixed end-to-end **without a human**,
      and the heal is only marked resolved after the error stops recurring (Loop 1 + G2).
- [ ] New features flow from signals/trends → WSJF-ranked tasks → shipped PRs
      autonomously (Loops 2 & 4).
- [ ] Every 🔴 action (merge to deploy branch, auth/secret change, deploy, destructive
      op, over-budget spend) **pauses for a Telegram approve/reject** and resumes only
      on approval (G1 + §3/§4).
- [ ] Trends are applied **per onboarded company's stack**, not just the platform (G4).
- [ ] An onboarded URL-only site gets its non-code agency immediately; code work waits
      on `awaiting_repo_connection` and auto-resumes on connect (Loop 5).
- [ ] **Zero dropped work** — everything blocked sits in a typed paused state.
- [ ] **Spend stays on the free brain** unless `allow_paid` is explicitly toggled (§2).
- [ ] Every autonomous decision is in KPIs + the activity feed (observable).

---

## 8. Safety invariants (carried from `agent/CLAUDE.md`)

1. Verifier / JUDGE must pass before any change lands — no bypass.
2. Bounded retries (≤3) on implement / heal / review loops.
3. Per-connection token only; never borrow the server token for a customer repo
   unless the operator opts in.
4. Sensitive paths (`admin_auth.py`, `key_store.py`, `agent/tools.py`, payments,
   infra) are **always** 🔴 — mandatory HITL regardless of any auto-merge setting.
5. The repo's delivery policy is authoritative; unknown/unreadable ⇒ safest path
   (open PR, no auto-merge) + operator confirmation.
6. `allow_paid=false` is the durable default; budget overruns pause, never silently spend.
