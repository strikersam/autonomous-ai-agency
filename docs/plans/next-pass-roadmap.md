# Next-Pass Roadmap — Detailed Implementation Specs

> **Planning only — nothing here is implemented yet.** This document is the
> successor to `docs/plans/autonomy-uplift-roadmap.md` (whose §3a–§3e shipped via
> PRs #838/#851/#853). It captures the *next* pass of work, written so a
> low-powered LLM (or a cold human) can pick up any single item and implement it
> without further context.
>
> **Status legend:** ✅ done & merged · 🟡 in flight · ⬜ pending · 🔭 deferred.
>
> **Ground rules for whoever implements these** (from `CLAUDE.md` / `AGENTS.md`):
> - Run `pytest -x` before and after. New behaviour → new test; bug fix → regression test.
> - Keep `CHANGELOG.md` ↔ `docs/changelog.md` `[Unreleased]` in parity.
> - No secrets in source. Git auth via `GH_PAT` only.
> - Auth/key/agent-tool changes require the `risky-module-review` skill.
> - One item ≈ one focused PR. Don't bundle.

---

## 0. The goal (unchanged)

The repo keeps itself up to date, learns, and self-heals, surfacing only the
decisions that matter through a Telegram gate the operator can act on *if and
only if* needed.

## 1. Shipped in the previous pass ✅ (recap, do not redo)

- **§3a** slop-gate wired into all sibling auto-PR scripts.
- **§3b** our own in-repo Hermes server (`services/hermes_server.py`).
- **§3c** CRISPY phase-sequence enforcement + workspace isolation; promoted to **EXPERIMENTAL**.
- **§3d** auto-PR codebase grounding + pre-commit `pytest -x` verification.
- **§3e** reliability-spine *modules* written & tested: `services/brain_watchdog.py`, `services/weekly_digest.py` (+ `loops/registry.yaml` entries).
- Repo-wide slop cleanup (#851, #854); secrets-shaped-file guard + doc-only-boilerplate guard.

> ⚠️ **Important honesty note that drives item N1 below:** §3e shipped the
> watchdog and digest as *modules with registry entries and unit tests*, but they
> are **not actually running yet** — see N1.

---

## 2. Pending ⬜ — detailed implementation specs

Priority order: **N1 → N2 → N3 → N4 → N5**. N1 is highest value (it makes
already-merged code real); N4/N5 are larger and touch the auth surface.

---

### N1. Activate the reliability spine — wire the watchdog, schedule the digest ⬜  (size: M, risk: low)

**Why.** `services/brain_watchdog.py` and `services/weekly_digest.py` are merged,
tested, and catalogued in `loops/registry.yaml` — but nothing invokes them. Grep
proof at time of writing:
- `get_watchdog` / `BrainWatchdog(...)` appear **only** in `tests/test_brain_watchdog.py` — the watchdog is never called from any provider code path.
- `weekly_digest` is referenced by **no** workflow in `.github/workflows/` — the registry entry says `trigger: schedule` but no cron exists.

So the registry advertises two loops that don't run. This item closes that gap.

**N1a — wire the watchdog into the provider failover path.**
- File: `provider_router.py` (the `ProviderRouter` failover logic) — the place that already detects a provider 5xx/timeout and fails over.
- On each provider failure, call `services.brain_watchdog.get_watchdog().record_failure(provider_id)`; on success call `.record_success(provider_id)`.
- Import lazily inside the method (avoid import-time cycles), mirroring how `_trigger_failover` resolves `brain_config_store`. **Use a single, consistent module path** (`import services.brain_config_store as bcs`) to avoid the dual-module-identity bug that broke #853's tests (top-level `brain_config_store` vs `services.brain_config_store` are different `sys.modules` objects).
- The watchdog persisting a new provider must **not** block the request path — it already persists via `BrainConfigStore`; just fire-and-forget and swallow/log errors.

**N1b — schedule the weekly digest.**
- New workflow: `.github/workflows/weekly-readiness-digest.yml`.
- `on: schedule: - cron: "0 7 * * 1"` (Mon 07:00 UTC, matching the registry entry) + `workflow_dispatch`.
- Step: `python -m services.weekly_digest` with `env: GH_PAT: ${{ secrets.GH_PAT }}` and the brain/telegram env the digest needs (read `services/weekly_digest.py` for the exact vars).
- Must degrade gracefully when Telegram isn't configured (the module already supports `--dry`); the workflow should fail loudly only on an unexpected exception, not on "telegram not configured".

**Files:** `provider_router.py`, new `.github/workflows/weekly-readiness-digest.yml`.
**Tests:** extend `tests/test_provider_router.py` — assert `record_failure` is called on a failover (monkeypatch `get_watchdog`); a workflow-lint/`loop-audit` already validates the registry, so confirm `python -m agent.loop_registry audit` stays green (the workflow now exists, so drift clears).
**Acceptance:** `get_watchdog()` is invoked in prod code; `loop-audit` shows `weekly-readiness-digest` as backed by a real workflow; both loops move from "advertised" to "running".

---

### N2. Surface Hermes (and all runtimes) status in the Doctor/Runtimes UI ⬜  (size: S, risk: low)

**Why.** Our own Hermes server (§3b) is reachable via `runtimes/adapters/hermes.py`
`health_check()`, but the operator can't see it. The backend already exposes
`GET /runtimes/` (`runtimes/api.py::list_runtimes`, backed by the runtime manager's
health) and the frontend has `frontend/src/v5/screens/DoctorScreen.jsx`.

**Steps.**
1. Confirm the Hermes adapter is **registered** with the runtime manager so it appears in `GET /runtimes/health`. If it isn't, register it (read how `internal_agent`/other adapters are registered in the manager's bootstrap).
2. Ensure `HermesAdapter.health_check()` returns a structured `RuntimeHealth` (online/offline + version from the `/health` payload — the server already returns `{status, runtime, ours, version}`).
3. In `DoctorScreen.jsx`, render each runtime from `GET /runtimes/health` with an online/offline badge and the version; Hermes should show **online** when `HERMES_BASE_URL` points at a running server, **offline** otherwise — never crash the screen if the list is empty.

**Files:** `runtimes/api.py` (verify only), the runtime-manager bootstrap (register hermes if missing), `frontend/src/v5/screens/DoctorScreen.jsx`, maybe `frontend/src/api.js`.
**Tests:** a backend test asserting `GET /runtimes/health` includes a `hermes` entry (adapter health mocked); a small frontend render test if the screen has a test harness.
**Acceptance:** with a Hermes server running, the Doctor screen shows Hermes **online + version**; with it down, **offline** with a hint — no third-party setup.

---

### N3. Real CI-failure autofix — close the "Agency: cannot fix tests" loop (issue #398) ⬜  (size: L, risk: medium)

**Why.** Issue #398 ("cannot fix tests") produced placeholder slop (closed PR #852:
a `assertTrue(True)` fake test). The existing `scripts/agency_fix.py` +
`.github/workflows/ci-failure-autofix.yml` need to *actually* fix a failing test,
verified, or decline — never emit a placeholder.

**Spec.**
1. **Capture the real failure.** On a red CI run, collect the failing `pytest`
   node ids + tracebacks (the `Test (Python 3.13)` job already uploads
   `.pytest_cache/`; or re-run `pytest -x --tb=short -q` in the autofix job to get
   the first failure deterministically).
2. **Ground the model.** Build the prompt from: the failing test file, the module(s)
   under test (resolve from the import in the test + the traceback frames), and the
   exact assertion/error. Reuse the path-extraction helper added in
   `.github/scripts/autonomous_agent.py` (`_extract_mentioned_paths` /
   `_read_grounding_files`).
3. **Verify before PR.** After applying the edit, run `pytest -x` on the touched
   files **and** the originally-failing node ids. Abort (no PR) unless they pass.
   This reuses the §3d verification pattern.
4. **Gate.** Run it through `slop_gate` (`is_destructive_overwrite`,
   `looks_like_secret_file`, `is_doc_only_boilerplate`) — a real test fix touches
   code, so a doc-only diff is rejected automatically.
5. **Decline cleanly.** If the model can't produce a green diff, exit 0 with a
   comment on the issue ("could not auto-fix; needs a human") — **no PR, no placeholder.**

**Files:** `scripts/agency_fix.py`, `.github/workflows/ci-failure-autofix.yml`.
**Tests:** `tests/test_agency_fix.py` — given a known failing test + a fixture module, assert the agent produces a diff that turns the node green, and that a model returning a placeholder is rejected by the gate.
**Acceptance:** a deliberately-broken test in a sandbox is fixed and verified green by the loop; a non-fixable case declines with an issue comment instead of opening a slop PR. Then **close issue #398** as genuinely resolved.

---

### N4. Promote CRISPY from EXPERIMENTAL → stable after burn-in ⬜  (size: M, risk: medium — `risky-module-review`)

**Why.** §3c promoted `crispy_workflow` to **EXPERIMENTAL** in `features/matrix.py`.
Promotion to stable needs evidence, not a flag flip.

**Spec.**
1. Define burn-in criteria in this doc's acceptance: N successful CRISPY runs with
   per-phase artifact validation passing, zero phase-sequence violations, and no
   workspace-isolation escapes, over a defined window.
2. Add a lightweight CRISPY run-history metric (count of completed runs + failures
   by phase) — surface it in `GET /api/loops` or `/api/autonomy/status` so the
   evidence is observable.
3. Once criteria are met, flip `crispy_workflow` to the stable maturity in
   `features/matrix.py` and update `loops/registry.yaml` (level/maturity).

**Files:** `features/matrix.py`, `workflow/engine.py` (metric emission), `loops/registry.yaml`, the autonomy/loops API + screen.
**Tests:** update `tests/test_feature_matrix.py` / `tests/test_feature_maturity.py`; add a metric test.
**Acceptance:** CRISPY shows a real run-history; promotion is backed by data, reviewed via `risky-module-review`.

---

### N5. Mutating Telegram control (switch brain / merge PR from the phone) 🔭→⬜  (size: M, risk: high — `risky-module-review`)

**Why.** Carried over from the previous roadmap's Deferred list. Today Telegram is
read-only (`/autonomy`, `/loops`). Mutating control (switch brain, approve/merge a
PR) needs a backend **service-token** — a new auth surface.

**Spec (must go through `risky-module-review`).**
1. Add a backend service-token mechanism (env-provisioned, hashed-compare, never
   logged) that authorizes a narrow allowlist of mutating endpoints
   (`PATCH /admin/api/policy/brain`, a guarded "merge PR #N" action).
2. Telegram bot gains gated commands (`/setbrain <provider>`, `/merge <pr>`) that
   call those endpoints with the service-token, behind an operator-allowlist chat id.
3. Every mutating action is logged to the decision log and echoed back to Telegram
   for confirmation.

**Files:** `admin_auth.py` (or a new `service_token.py`), `backend/server.py` /
`runtimes/api.py` (gated endpoints), `telegram_bot.py`.
**Tests:** auth tests (valid/invalid/absent token → 200/401/401); command tests with the HTTP layer mocked.
**Acceptance:** operator can switch the brain and merge an approved PR from Telegram; every path is token-gated, allowlisted, logged, and `risky-module-review` signed off.

---

## 3. Deferred 🔭

| Item | Why |
|------|-----|
| **Auto-promote loops L1→L2→L3** based on the loop-audit readiness score | Needs a stable scoring history first (depends on N4's metric work). |
| **Multi-region / paid-provider failover policy in the watchdog** | Cost/policy decision; revisit after N1 proves the watchdog in prod. |

## 4. Operating notes (unchanged, for implementers)

- **Recommended brain:** set `CEREBRAS_API_KEY` → in-app brain *and* auto-PR scripts use Cerebras; NIM 49B is the always-on floor.
- **Local GPU as brain:** Providers → Brain → Ollama → paste tunnel URL → Test → Apply.
- **Watch the fleet:** the **Loops** screen, or `/loops` / `/autonomy` on Telegram.
- **Auto-PRs** are slop-gated (secrets-shaped + doc-only + destructive guards) — still eyeball the +/- before merging.
- **Run the loop audit:** `python -m agent.loop_registry audit` — every cron workflow must have a registry entry or the `loop-audit` gate fails the PR.
