# PR #634 Implementation Tracker

> **PR**: [Free NVIDIA brain + UI-controlled provider policy + no silent spend](https://github.com/strikersam/autonomous-ai-agency/pull/634)
> **Started**: June 14, 2026
> **Status**: Phase 1 ✅ → Phase 2 🔄 → Phase 3–6 ⏳

---

## Phase 1 — Stop the bleeding + paid kill switch ✅

| # | Task | Files | Done |
|---|------|-------|------|
| 1 | Durable `provider_policy` doc + `GET/PUT /api/providers/policy` | `backend/server.py` | ✅ |
| 2 | `_resolve_brain_provider` reads `allow_paid` | `services/workflow_orchestrator.py` | ✅ |
| 3 | `.github/scripts/provider_policy.py` failsafe fetcher | New file | ✅ |
| 4 | `generate_context.py` NVIDIA-first, Anthropic gated | `.github/scripts/generate_context.py` | ✅ |
| 5 | `apply_review.py` gated behind `allow_paid` | `.github/scripts/apply_review.py` | ✅ |
| 6 | `review_agent.py` gated behind `allow_paid` | `.github/scripts/review_agent.py` | ✅ |
| 7 | `implement_agent.py` gated behind `allow_paid` | `.github/scripts/implement_agent.py` | ⬜ |
| 8 | `ci-failure-autofix.yml` gated behind `allow_paid` | `.github/workflows/ci-failure-autofix.yml` | ✅ |
| 9 | Frontend kill switch toggle | `frontend/src/v5/screens/ProvidersScreen.jsx`, `frontend/src/api.js` | ✅ |
| 10 | Unit tests for policy | `tests/test_provider_policy.py` | ✅ |
| 11 | Runbook: NVIDIA_API_KEY as GH secret + Render env var | `docs/` | ⬜ |

---

## Phase 2 — Per-surface assignment in the UI 🔄

| # | Task | Files | Done |
|---|------|-------|------|
| 1 | Extend provider policy with `surfaces` map | `backend/server.py` | ⬜ |
| 2 | `resolve_provider_for(surface)` dispatch function | `services/workflow_orchestrator.py` | ⬜ |
| 3 | Wire chat surface to `resolve_provider_for("chat")` | `backend/server.py` (chat handler) | ⬜ |
| 4 | Wire scanner surface | `services/scanner.py` | ⬜ |
| 5 | Wire CEO surface | `services/ceo_dispatcher.py` | ⬜ |
| 6 | Wire SDLC surface | `services/company_agency.py` | ⬜ |
| 7 | Wire internal agent surface | `runtimes/adapters/internal_agent.py` | ⬜ |
| 8 | Record `llm_provenance` per call | All call sites | ⬜ |
| 9 | Per-surface matrix in ProvidersScreen.jsx | `frontend/src/v5/screens/ProvidersScreen.jsx` | ⬜ |
| 10 | Drag-to-reorder provider priority | `frontend/src/v5/screens/ProvidersScreen.jsx` | ⬜ |

---

## Phase 3 — Persistence hardening (#537, #524) ⏳

| # | Task | Files | Done |
|---|------|-------|------|
| 1 | `seed_default_providers()` never overwrites user fields | `backend/server.py` | ⬜ |
| 2 | Priority round-trips durable store | `backend/server.py` | ⬜ |
| 3 | Rehydrate policy + records on boot | `backend/server.py` | ⬜ |
| 4 | Regression test: paid never auto-selected | `tests/` | ⬜ |

---

## Phase 4 — Onboarding fixes (#593, #619, PR #623) ⏳

| # | Task | Files | Done |
|---|------|-------|------|
| 1 | Fix NameError crash in onboarding/provider resolver | `backend/server.py` | ⬜ |
| 2 | Fix `fmtErr(null)` returning truthy + add axios timeout | `frontend/src/api.js` | ⬜ |
| 3 | Defer company persistence to Confirm step | `frontend/src/v5/screens/OnboardingScreen.jsx` | ⬜ |
| 4 | Make `createCompany` idempotent | `backend/server.py` | ⬜ |

---

## Phase 5 — Reliability (#522) ⏳

| # | Task | Files | Done |
|---|------|-------|------|
| 1 | Async approve + run queue (return 202, background execute) | `services/workflow_orchestrator.py` | ⬜ |
| 2 | Per-phase timeout + retry + provider failover | `services/workflow_orchestrator.py` | ⬜ |
| 3 | Heartbeat + stall watchdog → P1 alert | `services/workflow_orchestrator.py` | ⬜ |
| 4 | Deterministic supervisor (code, not LLM) | `services/` | ⬜ |
| 5 | Concurrency semaphore on queue | `services/orchestrator_queue.py` | ⬜ |

---

## Phase 6 — Green tests + housekeeping ⏳

| # | Task | Files | Done |
|---|------|-------|------|
| 1 | Fix scanner: `DetectedSystem` has no `category` (#605) | `services/scanner.py` | ⬜ |
| 2 | Triage #622: CI syntax check false positive | `.github/` | ⬜ |
| 3 | Triage #624: subdomain enumeration layer | `services/scanner.py` | ⬜ |
| 4 | Triage #625: Friday maintenance fixes | Various | ⬜ |
| 5 | Triage #626: wrangler-action v3 | `.github/` | ⬜ |
| 6 | Triage #627: implementation for #488 | Various | ⬜ |
| 7 | Triage #628: deploy secret config + CI restart | `.github/`, `render.yaml` | ⬜ |
| 8 | Triage #629: context model + heartbeat follow-up | `services/workflow_orchestrator.py` | ⬜ |
| 9 | Triage #630: skip orchestrator exec tests when LLM unreachable | `tests/` | ⬜ |
| 10 | Triage #631: nifty-pasteur changes | Various | ⬜ |
| 11 | `pytest -x` fully green | `tests/` | ⬜ |
| 12 | Update `docs/changelog.md` | `CHANGELOG.md` | ⬜ |

---

## Verification checklist (final)

- [ ] `pytest -x` green
- [ ] No-spend proof: allow_paid=false + NVIDIA → zero Anthropic calls
- [ ] UI: flip surface → next run uses chosen provider (llm_provenance)
- [ ] Persistence: priority −50 survives restart
- [ ] Onboarding: wizard end-to-end, no duplicate companies, real error text
