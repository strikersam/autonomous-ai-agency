# Free NVIDIA brain + UI-controlled provider policy + no silent spend

> **Self-contained implementation brief / draft-PR body.** An agent (Claude, Codex, or the
> in-repo agency runtime) can execute it cold with zero prior conversation context.
> Branch: `feat/free-brain-provider-policy`. Keep as **draft** until Phase 1+2 are green.

---

## Why this PR exists (context)

PR #603 ("autonomy hardening", epic issue #504) landed but the platform kept burning the
owner's **Anthropic** credits (~$20, balance now negative), onboarding broke, and several
days of work are stuck in unmerged draft PRs. Goal of this PR:

1. A **powerful free cloud brain** (NVIDIA NIM) runs everything — brain/CEO + all agents.
2. **One UI place** (Providers screen) chooses which LLM powers brain/CEO and every surface —
   *nothing hidden in config*.
3. A **UI policy switch** turns paid providers off so nothing silently bills again.
4. Open issues/PRs read and fixed so the platform is healthy and autonomous again.

### Root cause of the $20 burn (verified in-repo)
The runtime brain resolver (`services/workflow_orchestrator.py:_resolve_brain_provider`,
line 178) **already** prefers free providers and only falls through to paid Anthropic when no
free provider is configured. The leak is the **GitHub Actions agent scripts**, which run on
cron and use Claude Opus directly or as a fallback — they never read the runtime policy:

- `.github/scripts/generate_context.py` → uses `claude-opus-4-8`, *requires* `ANTHROPIC_API_KEY`
  (generated the last 3 commits: issue #485/#504 plans).
- `.github/scripts/apply_review.py`, `review_agent.py`, `implement_agent.py` → Opus fallback.
- `.github/workflows/ci-failure-autofix.yml` → calls `api.anthropic.com` inline.

A partial gate convention exists (`never_use_paid_providers`, `cost_policy` in
`agents/store.py`, `agent/autonomy_gate.py`) but is not wired to these scripts or the UI.

### Decisions (locked with the owner)
- Free brain = **NVIDIA NIM** (qwen3-coder-480b / nemotron-ultra-253b / deepseek), `NVIDIA_API_KEY`.
- Paid = **UI policy toggle**, default **OFF** (not deleted — break-glass only).
- One UI place controls brain/CEO + every surface; durable; nothing secret in config.

---

## Design: one UI-controlled Provider Policy (single source of truth)

A durable **provider policy** singleton, edited only from the Providers screen, read by every
LLM call site *and* by CI:

```jsonc
provider_policy = {
  "allow_paid": false,            // UI kill switch (default OFF)
  "surfaces": {                   // per-surface assignment; "auto" = priority order
    "brain": "nvidia-nim", "ceo": "auto", "chat": "auto", "task": "auto",
    "sdlc": "auto", "scanner": "auto", "context": "auto", "review": "auto"
  }
  // per-provider ordering already exists via the `priority` field
}
```

Stored in the existing durable store (the `providers` collection/table already persists via
`db/sqlite_store.py`; add a sibling `provider_policy` doc). **Reuse, do not rebuild:**
- `_list_configured_provider_records()` — `backend/server.py:3424`
- `_resolve_brain_provider()` — `services/workflow_orchestrator.py:178` (extend with `surface`)
- `get_provider_role_tags()` — `workflow_orchestrator.py:303` (already powers the 🧠 BRAIN badge)
- Provider CRUD + UI — `frontend/src/v5/screens/ProvidersScreen.jsx`, `backend/server.py:4781-4936`
- `seed_default_providers()` — `backend/server.py:2350`

---

## Implementation plan + TO-DO (check off as you go)

### Phase 1 — Stop the bleeding + paid kill switch (do first, ship alone if needed)
- [ ] Add durable `provider_policy` doc (`allow_paid` default `false`) + GET/PUT
      `/api/providers/policy` (auth-gated) in `backend/server.py`.
- [ ] In `_resolve_brain_provider`, replace the implicit `_has_usable_free_provider()`
      last-resort with the explicit `allow_paid` flag: paid selectable **only** if `allow_paid`.
- [ ] New `.github/scripts/provider_policy.py`: `fetch_policy()` GETs
      `${RENDER_BACKEND_URL}/api/providers/policy` (token from secret); on any failure returns
      `{allow_paid: false}` (fail safe) + the ordered chain.
- [ ] `generate_context.py`: NVIDIA-first; Anthropic **only if** `allow_paid`; drop the hard
      `ANTHROPIC_API_KEY` requirement.
- [ ] `apply_review.py`, `review_agent.py`, `implement_agent.py`: remove unconditional Opus
      fallback; gate behind `allow_paid` (folds in draft **PR #623** for `implement_agent.py`).
- [ ] `ci-failure-autofix.yml`: gate the inline Anthropic call behind `allow_paid`.
- [ ] Runbook note: confirm `NVIDIA_API_KEY` is a GH Actions secret **and** a Render env var.

### Phase 2 — Per-surface assignment in the UI (the "one place")
- [ ] Extend `_resolve_brain_provider(surface=...)` to honor an explicit per-surface
      provider_id before priority order. Add one `resolve_provider_for(surface)` used by every
      call site: chat (`_build_provider_router`), scanner (`services/scanner.py`), CEO
      (`services/ceo_dispatcher.py`), SDLC (`services/company_agency.py`), internal agent
      (`runtimes/adapters/internal_agent.py`), `agent/loop.py`, `agent/agency.py`.
- [ ] Record `llm_provenance` per call so the UI shows what actually ran.
- [ ] `ProvidersScreen.jsx`: add a **Policy** panel atop the Providers tab — "Allow paid
      providers" toggle, a per-surface matrix (brain/CEO/chat/task/SDLC/scanner/context/review →
      provider dropdown or "Auto (priority order)"), drag-to-reorder priority.
- [ ] `frontend/src/api.js`: add `getProviderPolicy` / `updateProviderPolicy`.

### Phase 3 — Persistence hardening (issues #537, #524)
- [ ] `seed_default_providers()`: **never overwrite** user-set fields (`priority`, `is_default`,
      `default_model`, `api_key`, surface assignments); seed only missing records/fields.
- [ ] Ensure `priority` round-trips the durable store; rehydrate policy + records on boot.
- [ ] Regression test: paid never auto-selected when `allow_paid=false` and a free provider
      exists; priority −50 survives restart (issue #537 acceptance).

### Phase 4 — Onboarding fixes (issues #593, #619; PR #623)
- [ ] Fix the `NameError` ("ice") crash in the onboarding/provider resolver path (PR #623).
- [ ] `frontend/src/api.js` `fmtErr(null)` returns a truthy "Something went wrong." masking
      `e?.message` — fix + add an axios timeout (issue #619 bug 1).
- [ ] Defer company persistence to a single **Confirm** step; make create idempotent — no
      duplicate companies (issue #619 bugs 2-4). Role-registry rewrite (#593 P3/P4) is OUT of scope.

### Phase 5 — Reliability for hands-off autonomy (issue #522) [larger; may split to own PR]
- [ ] Async approve + run queue (return 202, background execute, concurrency semaphore).
- [ ] Per-phase timeout + retry + failover down the ordered chain (resolver already supports
      `exclude_base_urls`).
- [ ] Heartbeat + stall watchdog → P1 alert; deterministic (code, not LLM) supervisor so
      supervision survives zero LLM availability.

### Phase 6 — Green the tests + housekeeping
- [ ] Fix issue **#605**: scanner raises `'DetectedSystem' object has no attribute 'category'`
      (`tests/test_scanner_headless.py`) — align scanner code with the `DetectedSystem` model.
- [ ] Triage auto-created draft PRs (#622, #624, #625, #626, #627, #628, #629, #630, #631):
      merge real fixes folded above, close superseded plan-only drafts.
- [ ] Update `docs/changelog.md` (repo rule) and `.claude/state/active-tasks.md`.

---

## Verification / acceptance
- `pytest -x` green, incl. new policy/gate regression + the #605 scanner fix.
- **No-spend proof**: with `allow_paid=false` + NVIDIA configured, no Anthropic call is
  reachable in CI scripts or `_resolve_brain_provider`; `llm_provenance` shows NVIDIA across
  brain/chat/task/SDLC.
- **UI**: flip a surface to a provider + set allow_paid off → next orchestrator run uses the
  chosen provider (verify via `llm_provenance` / run record).
- **Persistence**: set priority −50, redeploy/restart, value persists (#537 acceptance).
- **Onboarding**: wizard end-to-end (scan → preview → Confirm), no duplicate company, real
  error text on a forced failure.

## Open-PR / issue disposition (read + acted on)
| PR / Issue | Action |
|------------|--------|
| #623 onboarding NameError + two-pass resolver | Fold into Phase 1/4, then merge/close |
| #629 context model + orchestrator heartbeat | Fold into Phase 1/5 |
| #628 deploy secret config | Use for `RENDER_BACKEND_URL` + `NVIDIA_API_KEY` wiring |
| #619 onboarding plan | Implement in Phase 4, close plan PR |
| #622/#624/#625/#626/#627/#630/#631 | Triage: merge real fixes, close stale plan/auto drafts |
| Issues #524/#537/#522/#593/#605 | Addressed by Phases 2/3/5/4/6 |

---

## SELF-CONTAINED AGENT PROMPT (paste to run cold)

> You are working in `strikersam/autonomous-ai-agency` (FastAPI + React v5, MongoDB with a
> `db/sqlite_store.py` durable fallback). Implement this brief. **Hard rule: never call a
> paid LLM (Anthropic/Opus) unless the provider policy `allow_paid` is `true`; default is
> `false`.** The free brain is NVIDIA NIM via `NVIDIA_API_KEY`.
>
> Work phase by phase (Phase 1 → 6); after each phase run `pytest -x` and commit. Reuse the
> existing functions named in "Design" — do not create parallel systems. Follow CLAUDE.md
> (type hints, async I/O, Pydantic I/O, `logging` not print, update `docs/changelog.md` under
> `[Unreleased]`). Any change to `admin_auth.py`/`key_store.py`/`agent/tools.py`/auth paths →
> run the `risky-module-review` skill. Router changes → update `tests/test_model_router.py`.
>
> Deliverables: (1) the `provider_policy` durable doc + GET/PUT endpoints; (2) the paid kill
> switch honored by the runtime resolver AND all four CI agent scripts + `ci-failure-autofix`;
> (3) the Providers-screen Policy panel (paid toggle + per-surface matrix + reorder); (4)
> persistence so priority/policy survive restart; (5) onboarding fixes; (6) green tests incl.
> the #605 scanner fix and a regression test proving paid is never auto-selected when
> `allow_paid=false`. Verify with the "Verification / acceptance" checklist before marking
> ready-for-review.
