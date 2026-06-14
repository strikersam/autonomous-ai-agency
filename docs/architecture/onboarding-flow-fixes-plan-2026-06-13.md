# Plan: Onboarding Flow Bug Fixes + Wire AI-Tailored Questions

> **Status:** Plan only — no implementation yet. This document is the output of an
> investigation session; a follow-up session should execute the "Agent Prompt" below.
> **Relates to:** #593 (Tailored Onboarding, Editable Companies & Dynamic Roles) — this
> plan is a tractable slice of #593's P1/P2 (load-bearing AI questions, editable/confirm
> flow), plus four standalone bugs found during manual QA of the V5 onboarding wizard.
> It deliberately does **not** attempt #593's Role Registry rewrite (P3/P4) — that
> remains a separate, larger effort.

## Context — bugs reported during manual QA

1. URL scan sometimes fails with the generic message **"Website scan failed: Something
   went wrong."** with no actionable detail.
2. **Company records are created immediately** when the user enters a URL and clicks
   "Inspect & discover" (Discovery step) — before any review or confirmation. The
   company shows up in the admin's company list even if the user abandons the wizard.
   There should be a single **"Confirm"** action on the *last* page that actually
   persists the company.
3. For **non-admin users**, the email gate (mailto to strikersam@gmail.com) should
   appear *after* the agent/specialist preview is shown — not before the wizard even
   starts. Today `NonAdminGate` blocks non-admins from the entire wizard up front.
4. **Agent provisioning** ("DoneStep" — "Loading specialists...") sometimes **spins
   forever**.
5. Are the **"tailored questions"** (QuestionsStep) actually tailored per company, or
   hardcoded? → **Confirmed: hardcoded today.** The backend has a working AI-tailored
   question generator that the frontend never calls (see below) — this is exactly gap
   #2 from #593 ("Answers aren't all load-bearing").
6. Scan for and fix any other bugs found along the way in this flow.

## Root-cause findings (already investigated — do not re-derive)

### (1) & partly (4): "Something went wrong" masks the real error everywhere

- `frontend/src/api.js:135-145` — `fmtErr(detail)` returns the **literal string**
  `'Something went wrong.'` when `detail == null`. Every call site in the codebase
  does:
  ```js
  api.fmtErr(e?.response?.data?.detail) || e?.message || 'Something went wrong.'
  ```
  Because `fmtErr(null)` is already truthy, `e?.message` (e.g. `"timeout of 60000ms
  exceeded"`, `"Network Error"`, `"Request failed with status code 502"`) is **never
  shown** for any error without a JSON `detail` body — i.e. exactly the
  network-error / proxy-timeout / non-JSON-error-page case. This single bug masks the
  real cause behind every "Something went wrong" message app-wide, not just URL scan.
  The fix: `fmtErr` should return `''` (falsy) for `detail == null` so the `||` chain
  falls through to `e?.message`.

- `frontend/src/api.js:44-47` — the shared axios instance (`API = axios.create({...})`)
  has **no request timeout**. A slow website scan
  (`services/scanner.py` — static fetch → headless Chromium fallback → builtwith.com
  off-page fallback) can legitimately take 30-90s. With no client timeout, a hung
  backend call spins indefinitely on the frontend.

### (4): Agent provisioning "loading forever" — blocking subprocess in async path

- `DoneStep` (`frontend/src/v5/screens/OnboardingScreen.jsx:587-613`) calls
  `api.startOnboarding(companyId, { skip_website_scan: true, skip_repo_scan: true,
  auto_provision_specialists: true })` → `POST /{company_id}/onboarding/start`
  (`backend/company_api.py:957`) → `OnboardingService.start_onboarding()`
  (`services/onboarding.py:104`) → after specialist provisioning (fast), **Step 8
  "activate_agency"** (`services/onboarding.py:364-409`) →
  `CompanyAgencyService.activate_company(start_runtimes=True, create_schedules=True)`
  (`services/company_agency.py:294`) → for each *unique* runtime assigned to the
  company's specialists, `_start_runtime()` (`services/company_agency.py:649`) →
  **`runtimes/control.py:start_runtime()`** (line 303).
- `start_runtime()` (`runtimes/control.py:310-315`) calls **`subprocess.run(["docker",
  "compose", "up", "-d", "--no-deps", "--no-recreate", container_name], check=True,
  capture_output=True, timeout=120)`** — a **blocking synchronous call inside an
  `async def`**, no `asyncio.to_thread`/executor. In any environment where `docker`
  exists but `docker compose` doesn't return promptly (or the daemon socket is
  unresponsive), this call **blocks the entire FastAPI event loop for up to 120
  seconds per unique runtime, serially**. A typical e-commerce onboarding provisions
  5-8 specialist families → up to 8 distinct runtimes → up to ~16 minutes of total
  event-loop-blocking, during which the **whole backend is unresponsive to every
  request**, not just this one.
- Combined with the missing axios timeout above, the frontend `DoneStep` request to
  `/onboarding/start` never resolves within any reasonable time → "Loading
  specialists..." forever. This explains "sometimes" — it depends on whether `docker`
  is present/responsive and how many distinct runtimes the detected systems map to
  (`system_to_family` in `services/specialist.py:149-175`).

### (2) & (3): Company creation flow / non-admin gate placement

- `DiscoveryStep.handleScan()` (`OnboardingScreen.jsx:214-306`) calls
  `api.createCompany(...)` **immediately** on "Inspect & discover" — before any system
  detection, review, or confirmation — and `onCompanyCreated` persists the new
  `company.id` to `localStorage` right away.
- `GET /api/company` (`list_companies`, `backend/company_api.py:351-391`) returns
  **all** companies to admin users with no draft/incomplete filter — every abandoned
  onboarding attempt leaves a permanent half-configured company visible in the admin
  dashboard.
- `Company` (`models/company_graph.py:999`) has no "draft"/"unconfirmed" concept —
  `onboarding_status` starts at `"not_started"` and the company is fully "real" from
  creation.
- `NonAdminGate` (`OnboardingScreen.jsx:104-168`) is rendered **instead of** the
  entire wizard for non-admins — `if (!isAdmin) return <NonAdminGate/>` at line 702 —
  so non-admins never see the URL scan, detected systems, or specialist preview before
  being asked to email the admin.

### (5): Tailored questions are hardcoded today

- `QUESTION_SETS` (`OnboardingScreen.jsx:17-48`) is a static map keyed by
  `detectSiteType()` (4 hardcoded questions for each of 5 site types). `QuestionsStep`
  (`OnboardingScreen.jsx:507-580`) reads straight from this constant and never calls
  the backend.
- The backend endpoint `POST /api/company/{id}/onboarding/questions`
  (`backend/company_api.py:1093`, `generate_onboarding_questions`) already does the
  right thing: builds a prompt from `domain` + `site_type` + `detected_systems`, calls
  the LLM for exactly 4 tailored questions, validates the shape, and **falls back to
  equivalent hardcoded questions** (`_get_fallback_questions`, line 1350) if the LLM is
  unavailable or returns garbage. **This endpoint is currently unused by the
  frontend.**
- `POST /{company_id}/onboarding/answers` (`backend/company_api.py:1196`) for
  submitting answers → remediation tasks is also unused by `QuestionsStep` (answers
  today only go to `localStorage`).

## Implementation Plan

Split into independently-revertible commits, in this order (each should keep
`pytest -x` green and add a `docs/changelog.md` entry under `## [Unreleased]`):

### A. Fix error-message masking (`frontend/src/api.js`)
- `fmtErr(detail)`: return `''` for `detail == null` instead of `'Something went
  wrong.'`. Re-check existing call sites — they all use
  `api.fmtErr(...) || e?.message || 'Something went wrong.'`, so this is a pure
  improvement (more specific messages surface everywhere, not just onboarding).
- Add a sensible default request timeout to the shared `API` axios instance (e.g.
  45s), with a longer explicit per-call `timeout` override for the known-slow calls:
  `scanWebsite`, `scanRepo`, `startOnboarding` (e.g. 90-120s). On a timeout
  (`error.code === 'ECONNABORTED'`), surface `"Scan is taking longer than expected —
  please retry."` instead of a bare network error.

### B. Make runtime activation non-blocking (`runtimes/control.py`,
`services/company_agency.py`, `services/onboarding.py`)
- `start_runtime()` in `runtimes/control.py`: replace the blocking
  `subprocess.run(["docker", "compose", ...], timeout=120)` with a non-blocking
  equivalent (`asyncio.create_subprocess_exec` + `asyncio.wait_for`, or
  `await asyncio.to_thread(subprocess.run, ...)`), and shorten the timeout
  substantially (e.g. 10s) so a slow/unresponsive `docker compose` falls back to
  `_start_local_runtime`/`_remote_runtime_response` quickly instead of stalling the
  event loop. Apply the same treatment to `stop_runtime()` if it has the same pattern.
- Decouple the slow "activate_agency" step (Step 8 of
  `OnboardingService.start_onboarding`, `services/onboarding.py:364-409`) from the
  synchronous `/onboarding/start` response: once specialists are provisioned (Step 5,
  fast), kick off `activate_company(start_runtimes=True, create_schedules=True)` as a
  background task (`asyncio.create_task`) and return the HTTP response immediately
  with `activate_agency` step marked `"status": "in_progress"`. Activation completion
  can be observed via the existing `GET /{company_id}/onboarding` progress endpoint
  (`backend/company_api.py:914`) — extend it to report agency-activation status if not
  already tracked.
- `DoneStep` (`OnboardingScreen.jsx:583-657`): call `listSpecialists` regardless of
  whether `startOnboarding` has fully completed — the specialist list should render as
  soon as provisioning (the fast part) is done, independent of runtime activation (the
  slow part). Show a small "Activating 24x7 runtimes..." indicator that can resolve
  later/async without blocking the "Go to Company Graph" button.

### C. Defer company persistence to a final "Confirm" step + relocate the email gate
- Add `is_draft: bool = True` (default `True`) to `Company`
  (`models/company_graph.py:999`). `list_companies`
  (`backend/company_api.py:351`) excludes drafts by default; add an
  `include_drafts: bool = Query(False)` param for the admin Companies tab if it needs
  to see in-progress drafts.
- `DiscoveryStep` still needs a `company_id` to call the per-company scan endpoints —
  keep creating the company on first scan, but it is created as a **draft**
  (`is_draft=True`, the new default). Walk the wizard exactly as today through
  Systems → Details → Questions → specialist/agent preview (DoneStep renamed/repurposed
  as a **preview**, not yet provisioning).
- The wizard's final step gains a single **"Confirm"** action, gated by role:
  - **Admin:** "Confirm & Activate" — sets `is_draft=False`, persists onboarding
    answers (`submit_onboarding_answers`), and triggers `/onboarding/start`
    (specialist provisioning + agency activation per plan B).
  - **Non-admin:** clicking confirm shows the existing `NonAdminGate` mailto flow
    (`OnboardingScreen.jsx:104-168`), pre-filled with the company's domain, detected
    systems, and answers. The company **stays a draft** (`is_draft=True`, hidden from
    the admin's default company list) until the admin manually confirms/converts it
    from the (drafts-visible) admin view.
- Move the non-admin gate from "blocks the entire wizard"
  (`if (!isAdmin) return <NonAdminGate/>`, `OnboardingScreen.jsx:702`) to "blocks only
  the final confirmation" — non-admins walk through Discovery → Systems → Details →
  Questions → agent/specialist preview exactly like admins, and only hit the email
  gate at the very end.
- Out of scope / follow-up: cleanup job for abandoned drafts (TTL-based deletion of
  `is_draft=True` companies with no activity after N days) — note this as a follow-up
  in the PR description, don't block this PR on it.

### D. Wire AI-tailored questions to the frontend (`QuestionsStep`)
- `frontend/src/api.js`: add
  - `generateOnboardingQuestions(companyId, { domain, site_type, detected_systems,
    business_category })` → `POST /api/company/{id}/onboarding/questions`
  - `submitOnboardingAnswers(companyId, { answers, site_type, detected_systems })` →
    `POST /api/company/{id}/onboarding/answers`
- `QuestionsStep` (`OnboardingScreen.jsx:507-580`): on mount, call
  `generateOnboardingQuestions` with the real `siteType`, `companyId`'s domain, and
  detected systems; render the returned `questions` array using the existing
  `yesno`/`select`/`multi`/`freeform` renderers (the shape returned by
  `generate_onboarding_questions` matches `QUESTION_SETS` entries already — same `id`,
  `label`, `type`, `options`, `placeholder` fields). Show a brief loading state while
  the AI call is in flight (it's an LLM round-trip). Fall back to the local
  `QUESTION_SETS` only if the *request itself* fails outright (network error) — the
  backend already has its own LLM-failure fallback (`_get_fallback_questions`), so a
  successful response is always usable.
- On "Continue" (`onNext`), call `submitOnboardingAnswers` with the collected answers
  in addition to the existing `localStorage` persistence, so answers become
  load-bearing (#593 gap #2) — at minimum this should land the existing
  answers→remediation-tasks behavior; deeper "every answer provisions something" work
  (#593 P2 `ProvisioningBinding`) is out of scope for this PR.

### E. General bug sweep
- While implementing A-D, scan `OnboardingScreen.jsx`, the onboarding routes in
  `backend/company_api.py`, `services/onboarding.py`, and `services/company_agency.py`
  for other latent issues surfaced along the way (e.g. duplicate website/company
  creation races on retry, error-state UI gaps, `resume_onboarding` interactions with
  the new draft/confirm flow). Fix opportunistically; give each its own commit +
  changelog entry rather than bundling into A-D.

## Testing
- Extend `tests/test_company_graph.py` / `tests/test_onboarding_provisioning.py` /
  `tests/test_phase6_workflow.py` for: draft-company exclusion from `list_companies`,
  non-blocking `start_runtime` (mock `subprocess`/`asyncio.create_subprocess_exec` and
  assert the event loop isn't blocked / a short timeout is honored), and the new
  AI-question endpoint wiring (mock `call_llm`).
- Add a regression test for `fmtErr(null) === ''` and for the axios timeout config.
- Manual QA via the `agent-browser`/`run` skill: full wizard walk-through as admin
  (confirm creates a non-draft company) and as a non-admin (confirm sends email, no
  non-draft company created/visible to admin).
- `pytest -x` before starting and after each commit.

## Open question for @strikersam
- "Can you run this at 1:00 am today?" — that time has already passed by the time this
  plan was written. Did you mean: (a) schedule the *implementation* to run overnight,
  (b) something about a cron/scheduled scan job, or (c) just proceed whenever ready?
  Defaulting to (c) — proceed on request — unless told otherwise.

---

## Agent Prompt (paste this to start the implementation session)

```
Implement the plan in docs/architecture/onboarding-flow-fixes-plan-2026-06-13.md on
branch claude/url-scan-agent-provision-bugs-lt6gk1 (already exists, checked out).

Read that plan doc first — it contains the full context, root-cause findings (with
exact file/line references), and a 5-part implementation plan (A-E). Do not re-derive
the root causes; they're already confirmed. Implement parts A through E in order, each
as its own commit with a docs/changelog.md entry under ## [Unreleased] (per
CLAUDE.md's changelog rule — commits without one are rejected by the commit-msg hook
unless prefixed chore:/docs:/style:/ci:/test:).

Key files you'll touch:
- frontend/src/api.js (fmtErr, axios timeout, new generateOnboardingQuestions /
  submitOnboardingAnswers clients)
- frontend/src/v5/screens/OnboardingScreen.jsx (QuestionsStep AI wiring, DoneStep
  decoupled specialist loading, draft/confirm flow, NonAdminGate relocation)
- runtimes/control.py (start_runtime non-blocking subprocess)
- services/company_agency.py (activate_company as background task)
- services/onboarding.py (start_onboarding step 8 decoupling)
- backend/company_api.py (list_companies draft filter, Company is_draft field usage)
- models/company_graph.py (Company.is_draft field)

Before starting: run `pytest -x` to confirm baseline is green. Read agent/CLAUDE.md
and router/CLAUDE.md only if you touch those areas (you shouldn't for this plan).
admin_auth.py / key_store.py are NOT touched by this plan — if you find yourself
needing to, stop and use the risky-module-review skill first.

After each part (A-E):
1. Run `pytest -x`.
2. Update docs/changelog.md.
3. Commit with a descriptive message.

After all parts: do a manual QA pass via the agent-browser or run skill — walk through
the onboarding wizard as both an admin user and a non-admin user, confirming:
- URL scan either succeeds with real detected systems, or fails with a SPECIFIC
  message (not "Something went wrong").
- No company appears in the admin Companies list until "Confirm" is clicked on the
  final step.
- Non-admins can walk the full wizard (scan → systems → details → questions → agent
  preview) and only hit the email gate at the final confirm step.
- QuestionsStep shows AI-generated questions (check network tab / backend logs for the
  POST to /onboarding/questions and a "source": "ai" or "source": "fallback" response).
- DoneStep's specialist list renders within a reasonable time (no infinite "Loading
  specialists...").

Push to claude/url-scan-agent-provision-bugs-lt6gk1 and update this draft PR's
description with a summary of what changed vs. this plan (note any deviations).
```
