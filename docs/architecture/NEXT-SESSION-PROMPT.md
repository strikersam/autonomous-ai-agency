# Handoff prompt — paste into a new Claude Cowork session

> Copy everything inside the fenced block below into a fresh Cowork session.
> A fresh session also loads the `graphify` skill — use it to read the codebase
> from `graph.json` instead of raw files to save tokens.

```
You are a principal engineer continuing a multi-session effort to transform the
`local-llm-server` repo into a reliable "Agency Core" platform. Most groundwork is
done and lives on an open PR; finish the remaining, clearly-scoped work and get the
PR to green CI so it can merge to master.

== START HERE (read in this order) ==
1. Run the `graphify` skill / read graph.json to map the codebase cheaply.
2. Read CLAUDE.md (repo rules: typed I/O, async, no secrets in source, risky
   modules need review, every meaningful commit updates docs/changelog.md).
3. Read docs/architecture/agency-core-audit-2026-05-22.md (audit + target
   architecture + 7-phase migration plan).
4. Read docs/architecture/agency-core-progress.md (resumable status log — the
   single source of truth for what's done / not done).

== REPO / PR STATE ==
- Work branch: agency-core-migration (open as DRAFT PR #218, base master).
- DONE on the branch: audit; Phase 0 stabilization (7 autonomous GH workflows
  quarantined to workflow_dispatch-only; dead root shims removed);
  scripts/doctor.py + `make doctor`; full V5 frontend under frontend/src/v5
  (AppShell + all 15 screens at route /v5, lazy, ESLint+Babel clean); README
  purpose + page catalog; master merged in; Python pinned to 3.13; a devcontainer;
  scripts/e2e_smoke.py + .github/workflows/e2e.yml.
- Keep it a DRAFT until CI is fully green; do NOT push to master directly
  (protected). Merge only via the PR on green CI.

== ENVIRONMENT CONSTRAINTS (these bit the last session) ==
- The Cowork live repo is mounted via virtiofs which FORBIDS file deletion, so git
  cannot run in the live tree. Do all git in a throwaway clone:
    SRC=<mounted repo path>; URL=$(git -C "$SRC" config --get remote.origin.url)
    git clone "$SRC" /tmp/llm && cd /tmp/llm && git remote add gh "$URL"
    git fetch gh agency-core-migration && git checkout -B agency-core-migration gh/agency-core-migration
    # change, commit, then: git push gh agency-core-migration
  Redact tokens from push output:
    sed -E 's/ghp_[A-Za-z0-9]+/<redacted>/g; s#//[^@]*@#//<redacted>@#g'
- SECURITY: the remote URL embeds a plaintext GitHub PAT in .git/config — never
  print it; tell the user to rotate it. 10 Dependabot alerts on master (1 high).
- Cowork sandbox runs Python 3.10 (platform-fixed); CI uses 3.13; no MongoDB
  locally. You CANNOT run pytest faithfully in-sandbox. Validate as below.

== HOW TO VALIDATE (so you never push red CI) ==
- CI: pytest -x on Python 3.13 + a mongo:7 service; a frontend job runs `npm test`
  and `npm run build` with CI=true (ESLint WARNINGS become errors).
- Frontend: symlink the live node_modules into the clone's frontend, then
  (a) Babel: transformFileSync with require.resolve('babel-preset-react-app');
  (b) ESLint: npx eslint --no-eslintrc -c {"extends":["react-app"]} --ext .js,.jsx
      — ZERO warnings allowed.
- Python: `python -m py_compile <file>` matches CI's syntax-check. For real pytest
  use the devcontainer (python:3.13) or CI.

== REMAINING WORK (in order; commit each as its own part to the PR) ==
1) CI-PARITY HARDENING (do first; lower risk):
   - Make backend/server.py module-level AsyncIOMotorClient LAZY (getter on first
     use) so importing the app never connects; route all `client` usages through it.
   - Ensure tests/conftest.py skips Mongo-dependent tests cleanly when MONGO_URL is
     unreachable. Document `make ci-parity`. Risky module -> follow review rule.
   - Acceptance: pytest -x green in CI; unit subset runs locally without Docker.
2) PHASE 1 — TYPED AGENT CONTRACT (kills signature-drift bug class):
   - Add agent/contract.py: Pydantic AgentJobRequest + AgentJobResult (audit S4).
     Provider/runtime selection behind policy objects, not loose kwargs.
   - Migrate every AgentRunner( site: proxy.py (4), backend/server.py,
     direct_chat.py, runtimes/adapters/internal_agent.py.
   - Contract test rejecting unknown kwargs (extend test_agent_runner_no_stale_kwargs).
3) FRONTEND — wire V5 (frontend/src/v5) to live data:
   - Replace mock data with real src/api.js (axios) calls; gate /v5 behind
     AuthContext; show the real signed-in user (not hardcoded "Sam Striker").
   - Dashboard: Promise.allSettled per widget (partial-failure tolerant).
   - Keep ESLint clean; tighten the scoped eslint-disable headers as handlers go live.
   - When stable, consider making /v5 the default UI.
4) REAL-API E2E (real calls, not unit/integration):
   - scripts/e2e_smoke.py hits /health, /v1/models, /v1/chat/completions vs
     RELAY_BASE_URL with RELAY_API_KEY. Extend to task creation, agent run, doctor,
     onboarding. .github/workflows/e2e.yml runs it on workflow_dispatch using the
     GitHub `test` environment. Run, read failures, fix features, repeat.
   - The user must create the `test` environment (Settings -> Environments) with
     secret RELAY_API_KEY and variable RELAY_BASE_URL (a RUNNING relay URL — the
     github.io page is a static landing page, not a relay).
5) PHASES 2-7 (per audit): one router, one backend on sqlite (fold backend/ into
   proxy.py, drop Mongo from hot path), one runtime, doctor + dashboard resilience,
   workflow engine + safe agency, onboarding/company-graph engine.

== DEFINITION OF DONE ==
- PR #218 CI fully green (Python + lint + frontend test + build + E2E); user marks
  Ready -> merges to master. Update docs/changelog.md and agency-core-progress.md
  as you go. Prioritize reliability and clarity over feature count. Never push code
  you cannot validate; if blocked, say so and leave a clear resume note.
```
