# Agency Core — Progress & Resume Log

> **Purpose:** Single source of truth for the Agency Core migration. Read this
> first to resume work. Updated as phases land.
> **Last updated:** 2026-05-22
> **Working branch:** `agency-core-migration` (based on GitHub `master`)
> **Companion docs:** `docs/architecture/agency-core-audit-2026-05-22.md` (the audit + target design)

---

## TL;DR — where we are

> **Session-2 update (2026-05-22):** Draft **PR #218** opened
> (https://github.com/strikersam/local-llm-server/pull/218) — kept as a draft so
> master's `auto-merge` cannot merge it on green CI. Branch tip now `c23df7d`.
> Added the **Doctor** diagnostics (`scripts/doctor.py` + `make doctor`).
> **Blocked:** implementing the `Agency Core.html` frontend design — the design
> SPA can't be fetched (no rendered browser, likely auth-gated) and no Chrome is
> connected. Unblock by saving `Agency Core.html` into the repo folder, or
> connecting the Chrome extension.

- ✅ **Audit delivered** (Sections 1–5) → `agency-core-audit-2026-05-22.md`.
- ✅ **Phase 0 pushed** → branch `agency-core-migration`, commit `713184a`.
- ⏳ **Next:** CI-parity hardening (make the unit suite runnable without MongoDB),
  then Phase 1 (typed agent contract).
- ❗ **No PR opened yet** — intentionally (see "Open risks" below).

---

## How to resume (read before doing anything)

### Environment constraints discovered this session
1. **Git cannot run in the live working tree.** The repo is mounted via
   **virtiofs**, which permits create/write but **forbids unlink/delete**. `git`
   needs to remove/rename files in `.git`, so `git add/commit/rm/push` all fail
   there. There is also a **stale `.git/index.lock` from 2026-05-22 09:58** that
   cannot be removed from inside the sandbox. **All git work was done in a
   throwaway clone under `/tmp` and pushed from there.**
2. **CI cannot be faithfully reproduced in the sandbox.** CI needs **Python
   3.13** + a **MongoDB 7 service** + Node 20; the sandbox is **Python 3.10**
   with no Docker/Mongo and 2026-pinned deps that don't resolve on 3.10. So any
   code change made from a sandbox session must be validated by the **branch's CI
   run on push**, not locally.

### To resume from a developer machine (recommended — has Python 3.13 + Docker)
```bash
# 1. Clear the stale lock if present
rm -f .git/index.lock

# 2. Sync remotes (local origin/* refs are stale; only master + gh-pages + this branch exist)
git fetch origin --prune

# 3. Get the work branch
git switch agency-core-migration      # or: git checkout agency-core-migration

# 4. Establish the baseline (this is the parity command)
make ci-parity                        # == bash scripts/test_ci.sh  (needs Docker for Mongo)
```

### To resume from another sandbox session
- Re-clone to `/tmp` (NOT the virtiofs mount) to run git.
- The push remote URL currently embeds a **plaintext PAT** in `.git/config`
  (`remote.origin.url`). See "Open risks".

---

## What's DONE

### Audit (committed)
- `docs/architecture/agency-core-audit-2026-05-22.md` — brutal truth, Keep/
  Salvage/Replace/Remove table, chosen foundation (Claude Code + oh-my-codex +
  claw-code + CompanyHelm hybrid), Agency Core design, 7-phase migration plan.

### Phase 0 — Stabilize & quarantine (commit `713184a`, pushed)
- **Quarantined 7 autonomous workflows** to `workflow_dispatch`-only (triggers
  commented, not deleted → reversible):
  `agency-cycle`, `ci-failure-autofix`, `continuous-improvement`,
  `openclaw-security-automation`, `process-quick-note`, `weekly-trend-digest`,
  `auto-merge`. These auto-committed AI patches / dispatched CEO directives /
  auto-merged green PRs faster than they could be verified — the main churn
  source.
- **Removed 5 dead root shims** (`agent_loop.py`, `agent_models.py`,
  `agent_tools.py`, `agent_state.py`, `agent_prompts.py`) — confirmed zero
  importers.
- **`.gitignore`**: ignore Fabric pattern test scratch files
  (`tmp_*`, `scaffold_test_*`) under `.claude/skills/fabric-patterns/patterns/`.
- **Changelog** updated.

### Key findings (so we don't re-investigate)
- The local `fix/reliability-hardening-2026-05-22` branch's reliability commit
  (`7956c3e`) and the 4 "uncommitted WIP" files are **byte-identical to current
  `master`** — that work already shipped via PRs **#210 / #214 / #215**. Nothing
  was lost; nothing needed re-committing.
- **GitHub remote has only `master` + `gh-pages`** (and now
  `agency-core-migration`). All the `origin/*` feature refs in the local repo are
  **stale**. There were **no open feature-branch PRs** on the remote.
- Structural rot confirmed (detail in the audit): **2 backends** (`proxy.py` +
  `backend/server.py`/MongoDB), **5 routers** (`provider_router.py`, `router/`,
  `routing/`, `runtimes/routing.py`, `agent/v4_router.py`), **3 execution
  substrates**, untyped `AgentRunner` boundary (signature-drift bug class).
- **Mongo is technically optional for tests already** (module-level Motor client
  with 2s `serverSelectionTimeoutMS`, env-auth fallback in "limited mode",
  per-test patching in `test_backend_runtime_bootstrap.py` etc.). The CI Mongo
  service is belt-and-suspenders. This makes the parity fix tractable.

---

## What's NOT done (the backlog, in order)

| Phase | Scope | Status | Notes |
|---|---|---|---|
| **CI-parity hardening** | Make unit suite run without a Mongo service + pin dev Python 3.13 | TODO (do next) | Lower risk than Phase 1; *creates* a runnable baseline. See plan below. |
| **Phase 1** | Typed `AgentJobRequest`/`AgentJobResult` contract; migrate all `AgentRunner(` call sites; contract test rejecting unknown kwargs | TODO | Kills `provider_chain`/`metadata`/`tool_callback`/`model_overrides` drift permanently. Needs green baseline first. |
| **Phase 2** | One router — extract `ProviderPolicy` from `provider_router.py`; delete `routing/`, `runtimes/routing.py`, `agent/v4_router.py` | TODO | Update `tests/test_model_router.py`. |
| **Phase 3** | One backend on sqlite — fold `backend/server.py` endpoints into `proxy.py`; drop Motor/MongoDB from default path | TODO | Pairs with parity fix. |
| **Phase 4** | One runtime — consolidate `runtimes/` + `agent/loop.py`; worktree isolation; demote opencode/aider/goose/openclaw behind a flag | TODO | Fix dispatcher↔runtime reconciliation (idle-runtime bug). |
| **Phase 5** | Doctor + dashboard resilience — consolidate `agent/doctor.py` + `runtimes/health.py`; `/api/doctor`; partial-failure-tolerant frontend everywhere | TODO | Extends the `Promise.allSettled` fix already on master. |
| **Phase 6** | Workflow engine + safe agency — persisted state machine; redesign CEO/specialists branch/PR-safe with verified issue closure | TODO | |
| **Phase 7** | Onboarding/discovery engine + company graph (the product vision: URL → stack inference → tailored questions → specialists) | TODO | Greenfield on the stabilized core. |

### Planned CI-parity hardening (the immediate next commit)
1. Make the module-level `AsyncIOMotorClient` in `backend/server.py` (line ~1779)
   **lazy** (created on first use via a getter), so `import backend.server`
   doesn't attempt a connection. Route all `client` usages through the getter.
2. Add a `tests/conftest.py` guard: if `MONGO_URL` is unreachable, ensure
   Mongo-dependent tests `pytest.skip(...)` cleanly instead of hanging/erroring.
3. Pin dev Python to **3.13** (`.python-version`) and document it in
   `scripts/test_ci.sh` so "local" and "CI" Python match.
4. **Validation:** push → branch CI runs the real matrix (3.13 + Mongo service).
   Locally, `make ci-parity` should then pass *without* Docker for the unit
   subset.
   *(This change touches backend auth-adjacent code; treat as risky-module
   review per CLAUDE.md. Do NOT merge until CI is green E2E.)*

---

## Open risks / must-know before merging

1. **Do not open the PR until ready to merge.** The quarantine of `auto-merge.yml`
   only takes effect *after* it lands on `master`; until then, master's live
   `auto-merge.yml` will squash-merge this PR (with `--admin`, bypassing branch
   protection) the instant CI goes green. Keep the PR unopened, or open it as a
   **draft**.
2. **CI runs on every push** to any branch (`push: branches: ["**"]`). If a push
   fails CI, master's still-live `ci-failure-autofix.yml` could auto-commit a
   patch to the branch. Watch the first CI run.
3. **Exposed credential:** `.git/config` `remote.origin.url` contains a plaintext
   GitHub PAT (`ghp_…`). **Rotate it** and switch to a credential helper / env var.
4. **Dependabot:** GitHub reports **10 vulnerabilities on master** (1 high, 8
   moderate, 1 low). Address during Phase 2/3 dependency audit.
5. **GitHub MCP connector** is now available in-session (was connecting earlier);
   it can be used to open/manage the PR via API instead of the compare URL.

## Quick links
- Create PR (when ready): `https://github.com/strikersam/local-llm-server/pull/new/agency-core-migration`
- Branch: `agency-core-migration` @ `713184a`
- Base: `master` @ `9174718` (#216)
