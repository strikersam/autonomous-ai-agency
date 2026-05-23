# Changelog

## [Unreleased]

### Fixed
- `tests/test_chat_mode_regressions.py`: `server.db` was already migrated to
  `get_db()` (lazy Motor client); monkeypatch now patches `server.get_db` to
  return a `Mock` whose `chat_sessions.insert_one` raises `RuntimeError`, giving
  the test the DB-outage scenario it needs without touching the real client.
- `frontend/.eslintrc.json` (new): adds `{ "extends": "react-app" }` so
  `react-scripts build` loads all CRA plugins (including `eslint-plugin-jsx-a11y`)
  before processing `eslint-disable jsx-a11y/anchor-is-valid` comments; without
  this CRA treats the unknown-rule disable comment as an error under `CI=true`.


### Fixed
- `frontend/package.json` overrides: removed `axios` (cannot override a direct
  dependency; caused `EOVERRIDE` in CI `npm install`).
- `tests/test_chat_mode_regressions.py`: replaced
  `monkeypatch.setattr("backend.server.db.chat_sessions.insert_one", ...)` with
  the object form `monkeypatch.setattr(server.db.chat_sessions, "insert_one", ...)`
  — the dotted-string form triggers a module-import attempt in pytest ≥9 which
  fails because `backend.server` is a file, not a package.


### Added
- `activation.py` — Ed25519-signed instance activation system; instanceId generated on
  first run, token verified against embedded owner public key; tamper-proof even if repo
  is forked (relay validates same token server-side).
- `activation_api.py` — FastAPI routes: `GET /api/activation/status` (public),
  `POST /api/activation/activate` (admin), `GET/PUT /api/activation/users/{id}/onboarding`
  (admin toggle), `GET /api/activation/audit-log` (admin). Persists state to
  `.activation_token` / `.onboarding_state.json` (git-ignored).
- `frontend/src/v5/screens/ActivationGate.jsx` — pre-login activation wizard; shows
  instanceId, email-draft link, token input; unlocks the whole app on success.
- `frontend/src/v5/screens/AdminOnboardingPanel.jsx` — admin panel: activation status,
  per-user onboarding_allowed toggle, audit log table.
- `setup/api.py` — `_require_onboarding_gate()` guard on all step/complete endpoints;
  returns `403` with structured error if instance not activated or user not allowed.
- `frontend/package.json` npm `overrides` — pins vulnerable transitive deps to safe
  versions: nth-check ≥2.1.1, serialize-javascript ≥6.0.2, postcss ≥8.4.31, ws ≥8.17.1,
  svgo ≥2.8.0, jsonpath ≥1.1.1, qs ≥6.11.0, uuid ≥9.0.0, bfj ≥8.0.0 (fixes 1 high,
  8 moderate, 1 low Dependabot alerts).

### Changed
- `frontend/src/v5/V5App.jsx` — entire app now wrapped in `<ActivationGate>`; shows
  activation wizard before login if instance is not yet activated.
- `frontend/src/v5/screens/AdminScreen.jsx` — `ActivationPanel` replaced with server-
  backed `AdminOnboardingPanel`; removed old client-side HMAC helpers.
- `README.md` — full rewrite: plain-English use-case explanation, non-technical quick
  start, activation flow guide, team-management docs, developer reference.
- `.gitignore` — added `.instance_id`, `.activation_token`, `.onboarding_state.json`,
  `.activation_audit.jsonl`.

### Security
- Replaced client-side HMAC activation (reversible) with server-side Ed25519 JWT
  verification; private key never committed to repo; bypass at UI layer does not grant
  relay access.
- npm dependency overrides resolve 10 Dependabot CVEs (1 high, 8 moderate, 1 low).


### Added
- `docs/architecture/NEXT-SESSION-PROMPT.md` — detailed, self-contained handoff prompt for a fresh Cowork session (Sonnet-friendly) covering all remaining work.
- `scripts/e2e_smoke.py` + `.github/workflows/e2e.yml` — real-API end-to-end smoke (health, models, chat completion) runnable manually against a live relay via a GitHub `test` environment (`RELAY_BASE_URL` var + `RELAY_API_KEY` secret); skips cleanly when unconfigured.
- `.devcontainer/devcontainer.json` — Python 3.13 + Node 20 dev container matching CI, for CI/local parity.

### Changed
- `.python-version` — pinned to `3.13` to match CI (was `3.12.13`).

### Added
- `frontend/src/v5/` — **Agency Core V5 redesign, part 2**: ported all remaining screens from the Claude Design handoff and wired them into `V5App` at `/v5` — Dashboard (healthy/partial-failure-tolerant), Tasks (job-lifecycle board), Agents, Schedules, Skills, Intelligence, Knowledge, Providers, Logs, Company (operating context), Onboarding (URL→stack wizard), Doctor, Admin, plus the always-on Alerts bell and Quick Notes overlays. ESLint-clean under the CRA `react-app` ruleset (build passes with `CI=true`); `target="_blank"` links hardened with `rel="noreferrer"`. Screens use mock data; live API wiring follows in a later part.

### Added
- `frontend/src/v5/` — **V5.0 "Agency Core" frontend redesign, part 1** (ported from the Claude Design handoff). `AppShell` (sectioned desktop sidebar + mobile top-bar/bottom-nav, agency-status pill, `Icon` set), the unified **Chat** screen (auto/explicit agent picker, sticky company/repo/task context chips, humanized agent-progress panel with phase breadcrumb + live event timeline, final-result card with PR/diff/test links, chat history), and `V5App` mounted at **`/v5`** (lazy route; existing dashboard untouched). Remaining screens (dashboard, tasks, onboarding, company, doctor, agents, schedules, skills, intelligence, knowledge, providers, logs, admin) land in later parts.

### Added
- `scripts/doctor.py` + `make doctor` — claw-code-style environment & CI-parity diagnostics (Python version vs CI 3.13, required env, core-dep import, MongoDB/Ollama reachability, Node, git state). Pure stdlib; never raises; `--strict` exits non-zero on hard failures. Directly addresses "why didn't this run?" / "why did CI fail but local pass?".
- `docs/runbooks/doctor.md` — how/why to use the doctor.
- `docs/architecture/frontend-redesign-prompt.md` — frontend redesign brief for the Agency Core UI.

### Changed
- `.github/workflows/{agency-cycle,ci-failure-autofix,continuous-improvement,openclaw-security-automation,process-quick-note,weekly-trend-digest,auto-merge}.yml` — **QUARANTINED**: disabled `schedule`/`push`/`workflow_run` auto-triggers (kept `workflow_dispatch` for manual runs) pending Agency Core stabilization. These autonomous workflows auto-committed AI-generated patches and dispatched CEO directives faster than they could be verified — the primary source of unverified churn. Re-enable by restoring the commented trigger blocks. See `docs/architecture/agency-core-audit-2026-05-22.md`.

### Removed
- `agent_loop.py`, `agent_models.py`, `agent_tools.py`, `agent_state.py`, `agent_prompts.py` — Removed dead backward-compat root shims that only re-exported from the `agent/` package; confirmed no module imports them.

### Added
- `docs/architecture/agency-core-audit-2026-05-22.md` — Ruthless architecture audit, Agency Core target design, and phased migration plan (the "before coding" deliverable).
- `.gitignore` — Ignore Fabric pattern test scratch files (`tmp_*`, `scaffold_test_*`) under `.claude/skills/fabric-patterns/patterns/` to prevent test leakage.

### Fixed
- `.claude/hooks/post-commit` — apply same `flock -n /tmp/graphify-update.lock` guard as Stop hook so post-commit and Stop/SessionStart updates are serialised; fallback to plain background run when `flock` is absent
- `graphify-out/graph.json` and `.graphify_labels.json` — removed from git tracking and gitignored. Node IDs in `graph.json` embed the absolute checkout path (`home_user_local_llm_server_…`), making the file non-portable across contributors; large non-semantic diffs would occur on every `graphify update` from a different path. `GRAPH_REPORT.md` (portable text, no path-derived IDs) remains committed. The `SessionStart` hook regenerates `graph.json` locally on each session open.
- `.claude/settings.json` — Stop hook guards `flock` availability: uses `flock -n /tmp/graphify-update.lock` when present (Linux), falls back to a plain background run on platforms without `flock` (macOS without util-linux, etc.) so the hook never breaks silently
- `.claude/settings.json` — Stop hook now uses `flock -n /tmp/graphify-update.lock` so concurrent `graphify update` runs (SessionStart + Stop + post-commit) are serialised; a second run skips silently instead of racing on `graphify-out/` writes.
- `.gitignore` — Added `graphify-out/.graphify_root` and `graphify-out/manifest.json`; both contain machine-specific absolute paths and must not be versioned. Removed both files from git tracking.
- `CLAUDE.md` — Fixed duplicate step numbers in working sequence (was `4, 4, 6`; now `4, 5, 6`).
- `.claude/skills/graphify/SKILL.md` — Added `text` language tag to all untagged fenced code blocks (MD040).

### Added
- `.claude/hooks/post-commit` — Git hook that runs `graphify update .` in the background after every commit, keeping the knowledge graph in sync with committed state automatically.
- `.claude/settings.json` `Stop` hook — fires after every Claude turn and runs `graphify update .` silently in the background. Means any AI session editing files gets a fresh graph on the very next query, with no manual steps. Combined with the existing `SessionStart` hook, the graph is self-maintaining across new sessions, existing sessions, and git commits.
- `.claude/skills/graphify/SKILL.md` — New skill integrating [graphify](https://github.com/safishamsi/graphify) knowledge-graph tool. Converts the codebase into a queryable `graph.json` (local AST parsing, no API calls for code files) so AI sessions query the graph instead of reading raw source files — upstream benchmark: 71.5x fewer tokens per query on large corpora. Includes token-savings table, Claude query protocol (check `GRAPH_REPORT.md` → `graphify query` → open files only for edits), and complementary relationship with the existing `repowise-intelligence` skill.
- `.claude/settings.json` — `SessionStart` hook that runs `graphify . --update` at the beginning of every Claude Code session, keeping the knowledge graph incrementally current. Reports node count and a one-line reminder to use `graphify query` instead of raw file reads.
- `.gitignore` — Added `graph.html` and `cache/` (graphify local artifacts). `graph.json` and `GRAPH_REPORT.md` remain committed for team-shared graph queries.

### Changed
- `CLAUDE.md` — "How Claude Should Work" sequence now lists querying `graph.json` via `graphify` as step 2 (before opening source files). Skill table now includes `graphify` as the first entry for exploration/token-saving tasks.

### Fixed
- `.github/workflows/deploy-backend.yml` — Replaced unsafe nested-quote `echo` (Python one-liner inside `$()` inside escaped double-quotes) with a simple portable `echo "Deploy triggered successfully (HTTP $HTTP_CODE)"`. The previous syntax caused Bash on GitHub Actions Ubuntu runners to exit with `syntax error near unexpected token` and report workflow failure on every master push, even though the Render deploy hook already accepted the request (HTTP 202).

### Fixed
- `runtimes/manager.py` — Added missing `list_runtimes() -> list[dict]` method; `runtimes/api.py` `GET /runtimes/` was calling it and crashing with `AttributeError`, causing a 500 on `/api/agents/runtimes` for all users.

### Changed
- `backend/server.py` — Bumped FastAPI app title/version to `LLM Relay v4.1` / `4.1.0` to match the frontend.

### Fixed
- `.github/workflows/deploy-backend.yml` — Added `permissions: contents: read` to limit GITHUB_TOKEN scope (CodeQL P1). Expanded `push.paths` to cover all files copied by `Dockerfile.backend`: `agents/**`, `mcp_server/**`, `schedules/**`, `docker/**`, `sync/**`, `setup/**`, `hardware/**`, `rbac.py`, `secrets_store.py`, `commercial_equivalent.py`, `tokens.py` — previously missing paths caused silent workflow skips on backend-only changes (Codex P1).

### Fixed
- `runtimes/adapters/internal_agent.py` — Removed `provider_chain=None` kwarg from `AgentRunner()` construction; `AgentRunner.__init__` never accepted this parameter, causing `TypeError: __init__() got an unexpected keyword argument 'provider_chain'` on every `InternalAgentAdapter.execute()` call and silently keeping all runtime-backed tasks idle.
- `agent/loop.py` — Added public `AgentRunner.plan()` coroutine wrapper; `direct_chat.py` called `runner.plan()` which raised `AttributeError: 'AgentRunner' object has no attribute 'plan'` on every in-context agent execution.
- `agent/loop.py` — Added `metadata: dict | None = None` parameter to `AgentRunner.plan()` and `AgentRunner.run()`; `direct_chat.py` passed `metadata=req.metadata` to `run()`, causing `TypeError` on every agent job.
- `frontend/src/pages/DashboardHome.js` — Replaced `Promise.all([…])` with `Promise.allSettled(…)`: a single failing API endpoint (e.g. `/api/stats` blip) previously blanked the entire dashboard with `AxiosError: Network Error`. Now shows partial data with a non-blocking amber warning banner.
- `agent/agency.py` — Added directive de-duplication: directives whose title matches an already-pending/running directive are skipped, preventing the CEO from re-dispatching the same task every cycle and flooding the scheduler.
- `tasks/dispatcher.py` — Added `_first_seen` time tracking and no-pickup diagnostics: tasks pending >2 min log a `WARNING` with a pointer to `/runtimes/health`; time-to-pickup logged at `INFO` on every dispatch.
- `.github/scripts/implement_agent.py` — `TOOL_DISPATCH` now uses `.get()` with key fallbacks (`cmd`/`command`/`shell` for bash, `path`/`file` for read/write) so NVIDIA NIM Qwen3-coder alternate key names no longer cause `KeyError` crashes (#208).
- `agent/state.py` — Added SQLite schema migrations for `repo_url`, `repo_ref`, `active_objective`, and `event_count` columns so older databases upgrade automatically without manual intervention.
- `runtimes/manager.py` — Exposed `get_policy()` on `RuntimeManager` for runtime policy introspection.

### Added
- `scripts/test_ci.sh` — CI-parity helper: starts MongoDB via Docker, installs deps in a fresh venv, sets identical env vars to `ci.yml`, runs `pytest -x -v`. Invoked via `make ci-parity`.
- `Makefile` — `ci-parity` target runs `scripts/test_ci.sh`.
- `tests/test_fixes_reliability.py` — 11 regression tests covering all fixes above.

### Added
- `frontend/src/pages/ChatPage.js` — Auto-escalation: `handleSend()` now detects strong execution intent (multi-reason or execution-signal keywords) and silently upgrades to agent mode, so users never need to manually toggle Agent Mode for coding/repo tasks.
- `frontend/src/components/AgentStatusPanel.jsx` — Humanized `JobProgressPanel`: when a job is running but no agent cards have spawned yet, shows the current phase label ("Planning the change", "Editing files", etc.), a live event timeline from `progress_events`, and a phase breadcrumb — instead of "No active agents".
- `tests/test_direct_chat_evolution.py` — `test_agent_runner_no_stale_kwargs`: regression guard that verifies `AgentRunner.__init__` is no longer called with the removed `provider_chain`, `allow_commercial_fallback`, or `tool_callback` kwargs.
- `frontend/src/__tests__/chatPage.test.jsx` — Two new tests: `auto-escalates to agent mode for messages with clear execution intent` and `does NOT auto-escalate for simple explanation-only messages`.

### Fixed
- `direct_chat.py` — Removed stale `provider_chain`, `allow_commercial_fallback`, and `tool_callback` kwargs from `AgentRunner(...)` instantiation; the `_on_tool_call` closure and orphaned `import time as _time` import were also removed. Previously caused `TypeError` on every agent-mode execution via the `/api/chat/send` route.
- `agent/loop.py` — Initialized `self._mcp = None` in `AgentRunner.__init__` so `write_file` and other MCP-aware dispatch paths work without a sidecar; previously raised `AttributeError: 'AgentRunner' object has no attribute '_mcp'` on every non-MCP invocation.
- `backend/server.py` — Removed stale `provider_chain` and `model_overrides` kwargs from `AgentRunner` calls (both dropped from the public API); previously caused `TypeError` and silent job failures in e2e tests.
- `backend/server.py` — Changed default `serverSelectionTimeoutMS` for the Motor AsyncIOMotorClient from 30 000 ms to 2 000 ms (configurable via `MONGO_SELECTION_TIMEOUT_MS` env var); previously all tests touching the backend auth/login endpoint silently waited 30 s before falling back to the env-based admin.
- `runtimes/manager.py` — Added sync `get_runtime(runtime_id)` method returning `{"runtime_id": …, "health": {…}}` so `tasks/service.py` scoring logic can call `runtime_manager.get_runtime(agent.runtime_id)` without `AttributeError`.
- `tasks/service.py` — Runtime health scoring no longer crashes when `get_runtime` is absent from `RuntimeManager`.
- `scripts/fabric_cli.py` — Added `FABRIC_PATTERNS_DIR` env-var override so tests (and CI) can redirect pattern writes to a temp dir instead of the repo's `.claude/skills/` tree.
- `tests/test_fabric_patterns.py` — `test_save_and_show_roundtrip` and `test_new_scaffolds_pattern` now use an isolated `tmp_path` patterns dir via `FABRIC_PATTERNS_DIR`; previously failed with `PermissionError` when the sandbox mounted `.claude/skills/` read-only.
- `tests/test_direct_chat_interactive_approval.py` — Patched `_get_github_token_for_user` to return immediately instead of waiting up to 30 s for a MongoDB connection; fixed test message to avoid `plan_only` intent classification that bypassed the approval gate.
- `tests/test_e2e_agent_chat.py` — All `httpx.Response(...)` mock helpers now attach a dummy `httpx.Request` so `raise_for_status()` no longer raises `RuntimeError` in newer httpx versions.
- `tests/test_direct_chat_doctor.py` — Switched to `@pytest.mark.asyncio` + `await` pattern (removed legacy `asyncio.get_event_loop().run_until_complete()` call).

### Added
- `runtimes/manager.py` — `get_runtime(runtime_id: str) -> dict | None`: sync helper that returns the last cached health snapshot for a runtime without triggering an async poll.


### Security
- `.github/workflows/ci-failure-autofix.yml` — Rewrote workflow to fix four CodeQL findings: (1/2) code injection: all `workflow_run` context values (`head_branch`, `head_sha`, `id`) moved to job-level `env:` vars and referenced as `$VAR` in shell — never as `${{ }}` inside `run:` steps; (3/4/5) untrusted code checkout: switched from checking out the PR branch to checking out master only, fetching the failing branch as a non-executed ref, and diffing via `git diff` — untrusted branch code is never executed in the privileged runner context. Added fork guard (`head_repository.full_name == github.repository`).

### Fixed
- `proxy.py` — Fixed timing side-channel in admin authentication by always calling `hmac.compare_digest` (P1-A).
- `proxy.py` — Implemented weak-secret guard to prevent starting with empty or common placeholder `ADMIN_SECRET` values (P1-B).
- `agent/tools.py` — Strengthened path traversal prevention in `_resolve_path` using `Path.resolve()` and robust prefix validation to prevent symlink-based escapes (P1-C).
- `proxy.py` — Added `threading.Lock` to the in-memory rate limiter to prevent race conditions and potential bypasses during concurrent requests (P1-D).
- `admin_auth.py` — Fixed handle leak and initialization in Windows `LogonUserW` implementation (P1-E).

### Fixed
- `handlers/anthropic_compat.py` — Added validation to ensure the `model` field is non-empty and non-whitespace (P2-A).
- `proxy.py` — Removed silent fallback to unauthenticated local MongoDB in production environments (P2-B).
- `agent/loop.py` — Improved fallback reporting when MCP servers are unreachable, marking results as `[DEGRADED]` (P2-C).
- `langfuse_obs.py` — Future-proofed synchronous HTTP usage by explicitly marking internal sync functions and updating all async call sites (P2-D).
- `.github/workflows/ci-failure-autofix.yml` — Fixed non-fast-forward push rejection (Codex P1): the "Commit and push" step previously committed on master's history then pushed to the feature branch, which is rejected because the branch has diverged. Now: restore master to clean state, create a local branch at `origin/$AUTOFIX_BRANCH`, apply the verified patch with `git apply --3way --index` (tolerates minor context differences), commit, and push as a true fast-forward. Emits a workflow warning if the patch does not apply to the branch tree.
- `provider_router.py` — Bedrock routing affinity now also enforced in the last-resort cooldown-bypass loop; previously a Bedrock model ID could be silently routed to Nvidia NIM when all providers were on cooldown (P1 bug reported by Codex review).
- `provider_router.py` — `from_env()` default Bedrock model changed from `us.anthropic.claude-opus-4-7` (requires AWS Sales approval) to `us.anthropic.claude-opus-4-6-v1`; fixes `AccessDeniedException` for accounts without Opus 4.7 access (P1 CodeRabbit finding).
- `render.yaml` — Updated Bedrock comment to reflect `us.anthropic.claude-opus-4-6-v1` as the confirmed-accessible default.
- `tests/test_bedrock_live.py` — Default `_MODEL_ID` changed from `us.anthropic.claude-opus-4-7` (requires AWS Sales approval) to `us.anthropic.claude-opus-4-6-v1` so live tests pass with the current account's access level when `BEDROCK_MODEL_ID` env var is not set (P2 bug reported by Codex review).
- `tests/test_bedrock_live.py` — Moved `from __future__ import annotations` to before module docstring (Python 3.13 compatibility); replaced `print()` with `log.info()` via module-level logger; added `-> None` return type annotations to all 4 test functions.
- `tests/test_bedrock_provider.py` — `test_bedrock_default_model` updated to assert `us.anthropic.claude-opus-4-6-v1` as default; added `-> None` return type annotations to all new test methods in `TestIsBedrockModelId` and `TestBedrockRoutingAffinity`.
- `tests/test_all_providers_discovery.py` — `test_bedrock_discovery` updated to assert new default model `us.anthropic.claude-opus-4-6-v1`.

### Added
- `.github/workflows/ci-failure-autofix.yml` — CI failure auto-fix workflow: triggers on any CI failure on non-master branches, reproduces the failure, calls Claude Sonnet 4.6 via Anthropic API to generate a patch, applies and verifies it, then commits the fix directly to the branch. Opens a GitHub issue if the fix is too complex or the patch fails verification.
- `tests/test_bedrock_provider.py` — `test_bedrock_affinity_preserved_in_cooldown_bypass`: asserts that NIM is not attempted for Bedrock model IDs even in the cooldown-bypass path.
- `provider_router.py` — `_is_bedrock_model_id()` helper and Bedrock routing affinity: requests whose model ID starts with `us.anthropic.*`, `eu.anthropic.*`, `global.anthropic.*`, `arn:aws:bedrock:*`, or `anthropic.claude-*` are now routed exclusively to the `bedrock` provider, bypassing Nvidia NIM and other providers that cannot serve them.
- `router/registry.py` — Added `us.anthropic.claude-opus-4-6-v1` (Opus 4.6, confirmed accessible) and `us.anthropic.claude-haiku-4-5-20251001-v1:0` to the model capability registry.
- `tests/test_bedrock_provider.py` — Tests for `_is_bedrock_model_id` (10 cases) and Bedrock routing affinity (3 integration tests including NIM bypass and primary-provider correctness).
- `tests/test_bedrock_live.py` — Live E2E tests for AWS Bedrock (auto-skipped without credentials): direct boto3 ping, model accessibility, ProviderRouter round-trip, health check.

### Changed
- `render.yaml` — All agent role models (`AGENT_PLANNER_MODEL`, `AGENT_EXECUTOR_MODEL`, `AGENT_VERIFIER_MODEL`, `AGENT_JUDGE_MODEL`) and coding runtime models (`OPENCODE_MODEL`, `AIDER_MODEL`, `GOOSE_MODEL`) set to `us.anthropic.claude-opus-4-6-v1` (Claude Opus 4.6 via AWS Bedrock — highest confirmed-accessible Opus model). Previous defaults were Nvidia NIM free-tier models.
- `render.yaml` — Added `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `BEDROCK_MODEL_ID` env var entries (documented for Render dashboard sync).
- `render.yaml` — `BEDROCK_MODEL_ID` default set to `us.anthropic.claude-opus-4-6-v1`; Opus 4.7 requires AWS Sales approval.
- `router/model_router.py` — Added `_opus_model()` helper that detects Bedrock (AWS keys + region) or direct Anthropic API key and returns the appropriate Opus model ID (`us.anthropic.claude-opus-4-6-v1` for Bedrock, `claude-opus-4-6` for Anthropic direct). The built-in model map and default functions continue to use NVIDIA NIM / Ollama aliases (routable by the proxy); `_opus_model()` is for use by agent/loop.py only.
- `agent/loop.py` — Agent role defaults (planner, executor, verifier, judge) now prefer Claude Opus 4.6 (`us.anthropic.claude-opus-4-6-v1` via Bedrock, `claude-opus-4-6` via Anthropic direct) over NVIDIA NIM. NVIDIA NIM models remain the fallback when Opus is not configured. Added `_bedrock_ready()` helper requiring an AWS region env var to prevent generic S3-only credentials from enabling Bedrock routing. When Opus credentials are present, `AgentRunner` promotes Anthropic/Bedrock providers to priority=-20 in the ProviderRouter so they are tried before NVIDIA NIM (priority=-10), fixing the routing bypass identified by Codex review.
- `.github/scripts/review_agent.py` — Council review now calls Claude Opus via `ANTHROPIC_API_KEY` as the primary model; NVIDIA NIM models are the fallback when Anthropic is not configured. Defensive text-block type check added when reading Anthropic response.
- `.github/scripts/implement_agent.py` — Implementation agent now runs a native Anthropic tool-use loop (`claude-opus-4-6`) as primary; falls back to the existing NVIDIA NIM loop when `ANTHROPIC_API_KEY` is absent. Transient Anthropic API errors now retry with backoff instead of aborting. NVIDIA fallback starts with a fresh turn budget.
- `.github/scripts/apply_review.py` — Review-application agent now calls Claude Opus via Anthropic SDK as primary; falls back to NVIDIA NIM models when Anthropic is not configured. Transient Anthropic API errors now retry with backoff instead of returning False immediately.
- `requirements.txt` — Added `anthropic>=0.40.0` so the Anthropic SDK is available in CI and server environments.
- `.github/workflows/process-quick-note.yml` — Added `ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}` to the `implement`, `review_apply`, and `review` step env blocks so Opus-primary routing is actually exercised in normal workflow runs (previously only `NVIDIA_API_KEY` was passed, silently bypassing Opus). Renamed "Apply review comments (NVIDIA NIM)" step to "Apply review comments".
### Fixed
- `.github/workflows/*.yml` — Downgraded futuristic GitHub Action versions (e.g., `actions/checkout@v6`, `actions/setup-python@v6`) to current stable releases (`v4`, `v5`, etc.) across all workflow files to prevent "Action not found" errors.
- `.github/scripts/*.py` — Fixed `from __future__ import annotations` placement; moved to the very beginning of files (before docstrings) to ensure compatibility with Python 3.13.
- `.github/workflows/openclaw-security-automation.yml` & `.github/scripts/security_fix_agent.py` — Changed OpenClaw working directory from `/app/openclaw` to `${{ github.workspace }}/openclaw` to avoid permission issues in GitHub Actions environments.
- `.github/workflows/ci.yml` — Updated Git initialization to use `master` as the default branch for consistency with the repository's primary branch.
- `.github/workflows/openclaw-security-automation.yml` — Made `git push origin master` non-fatal; the push fails when branch protection requires PRs, which was causing the whole workflow run to fail. Now emits a workflow warning instead of a hard failure.
### Fixed
- `.github/workflows/pull-request.yml` — Fixed three bugs: (1) `- '!master'` was indented as a sibling of `branches:` rather than a child, so master pushes incorrectly triggered the workflow; (2) missing `GH_TOKEN` env on the "Check if PR already exists" step caused `gh` CLI to fail auth silently; (3) `gh pr create --label auto-created` returned HTTP 422 when the `auto-created` label didn't exist — added a prior step that upserts the label.
- `.github/workflows/openclaw-security-automation.yml` — `issues.create()` with `labels: ['security', 'automated']` returned HTTP 422 (Unprocessable Entity) when those labels didn't exist in the repo; added a label-upsert guard (getLabel → createLabel on 404) before issue creation.
- `frontend/package.json` — Added `jest.moduleNameMapper` for `react-router-dom` and `react-router` so jest 27 (react-scripts v5) can resolve react-router-dom v7's exports-only package without falling back to the non-existent `dist/main.js` entry.

### Security
- `.github/workflows/changelog-check.yml` — Move `PR_TITLE`, `BASE_SHA`, `HEAD_SHA` to `env:` block to prevent shell injection (CWE-78).
- `.github/workflows/process-quick-note.yml` — Move `issue_number` workflow input to `ISSUE_NUMBER_OVERRIDE` env var to prevent shell injection.

### Fixed
- `.github/workflows/agency-cycle.yml` — Change `pip install bandit safety 2>&1 | tail -2` to `-q` so pip errors are not silently swallowed.
- `pytest.ini` — Add `filterwarnings = ignore::pytest.PytestUnraisableExceptionWarning` to suppress Python 3.13 GC timing noise.
- `tests/conftest.py` — Add `_gc_before_loop_close` session fixture to force GC before the event loop closes on Python 3.13, preventing `PytestUnraisableExceptionWarning` from orphaned subprocess transports.

### Added
- `agent/repowise.py`, `agent/tools.py` — Implemented Repowise-inspired codebase intelligence tools: `get_overview`, `get_context`, `get_risk`, and `get_why` for enhanced agent reasoning.
### Fixed
- `.github/workflows/weekly-trend-digest.yml` — Fixed failing "Fetch & Digest AI Trends" job: the workflow was installing only `httpx`, but importing `agent.trend_watcher` triggers `agent/__init__.py` which pulls in the full agent stack (`agent.loop`, `provider_router`, `router`, etc.). Changed to install `requirements.txt` so all transitive dependencies are available.
- `.github/workflows/auto-merge.yml`, `.github/workflows/pull-request.yml` — Removed reference to non-existent `actions/setup-cli@v1` action (marketplace returns 404). `gh` CLI is pre-installed on `ubuntu-latest` runners; no setup step is needed.
- `.github/workflows/openclaw-security-automation.yml` — Replaced binary-corrupted YAML file with a clean, valid workflow. Also fixed OpenClaw installation to clone from `github.com/openclaw/openclaw` (git clone) instead of `npm install openclaw@latest` (package does not exist on npm).
- `.github/workflows/agency-cycle.yml` (PR #185) — Fixed invalid `actions/checkout@v6` and `actions/setup-python@v6` references; bumped to `@v4` and `@v5` respectively (highest available versions).
- Updated primary LLM to `nvidia/nemotron-3-super-120b-a12b` and configured `MoonshotAI: Kimi K2.6` as high-priority fallback to resolve 404/429 errors in GitHub Actions and improve routing reliability.
- `.github/workflows/openclaw-maintenance.yml`, `docs/runbooks/openclaw-setup.md`, `docs/architecture/agent-orchestration.md` — Updated OpenClaw repository URLs to point to the new location at `github.com/openclaw/openclaw`.
- `agent/github_tools.py` — Fixed syntax errors regarding misplaced future imports.
- `agent/loop.py` — Enforced 'real work' requirement for edit/create tasks; increased max tool calls per step to 50.
- `runtimes/health.py` — Increased health check timeouts to 60s and circuit-breaker threshold to 10 failures to improve system uptime and reduce transient 'offline' status.
- `runtimes/api.py` — Sanitized error messages to prevent stack trace and internal information exposure.
- `agent/tools.py` — Implemented strict path traversal prevention using robust prefix validation.
- `.github/scripts/security_fix_agent.py` — Fixed OpenClaw execution path.
- `.github/workflows/openclaw-security-automation.yml` — Restored corrupted workflow file.
- `direct_chat.py` — Improved triviality filters to better handle coding-related requests in agent mode; fixed syntax errors.


### Fixed
- `runtimes/control.py` — Expanded Docker-socket error detection to handle overlay mount failures in CI; added port-conflict resolution by killing existing processes on target ports before starting local runtimes.
- `runtimes/api.py` — Updated `/start` and `/stop` endpoints to return informational 200 payloads for remote-managed or Docker-unavailable environments; sanitized error messages to prevent stack trace exposure.
- `agent/github_tools.py` — Fixed directory creation for local workspaces to ensure parent directories exist; added input sanitization to prevent path injection.
- `direct_chat.py` — Add Git/GitHub preflight checks for repo-related agent prompts: validates presence of GitHub token and 'git' binary and performs best-effort token validation (GitHub API) to detect invalid tokens or missing 'repo' scopes.
- `agent/job_manager.py` — Normalize job results to expose a canonical `result.response` and `final_message` for client consumption; preserve raw runner payload under `result.raw`.
- `runtimes/adapters/internal_agent.py` — Conservative health probe: when Ollama is used (no NVIDIA key), perform a lightweight probe and mark the runtime unavailable if Ollama is unreachable to avoid routing into broken local runtimes.

### Changed
- `runtimes/adapters/internal_agent.py` — Increased default `max_steps` from 8 to 30 and improved task success criteria to allow purely informational tasks to succeed.
- `agent/prompts.py` — Raised planner step limit to 30 to support advanced coding tasks.
- `.github/scripts/implement_agent.py` — Enhanced with `search_code` tool and increased turn limits to match backend capabilities.

### Removed
- None.

## [v4.1.0] — 2026-05-09

### Added
- `agent/repowise.py`, `agent/tools.py` — Implemented Repowise-inspired codebase intelligence tools: `get_overview`, `get_context`, `get_risk`, and `get_why` for enhanced agent reasoning.
- **Vision request routing** (`router/registry.py`, `router/model_router.py`) — the proxy now auto-detects `image_url` content parts in incoming chat requests and routes them to the highest-tier vision-capable model registered in the capability registry. Vision capability is declared via the new `vision: bool` field on `ModelCapability`. Affected models: `gemma4:27b`, `gemma4:9b`, `gemma4:latest`, `llama4-maverick:17b`, `llama4-scout:17b`, `qwen3.6:35b`. Set `VISION_MODEL=<name>` env var to pin to a specific vision model. Manual `X-Model-Override` header still takes priority.

### Added
- **`CLAUDE_CODE_SESSION_ID` / `X-Session-Id` propagation in Langfuse traces** (`langfuse_obs.py`, `chat_handlers.py`) — the proxy now extracts `X-Session-Id` and `X-Claude-Code-Session-Id` request headers and attaches them to Langfuse traces as `sessionId` (groups all turns from one session under a single trace in Langfuse) and as a `session:<id>` tag. All streaming and non-streaming paths are covered. The `session_id` field also appears in the trace metadata dict.

### Added
- **`FEATURE_DISABLE` / `FEATURE_ENABLE` bulk env vars** (`features/matrix.py`) — operators can now enable or disable multiple features at once via comma-separated lists, e.g. `FEATURE_DISABLE=jcode_runtime,social_auth`. `FEATURE_DISABLE` is authoritative (wins over `FEATURE_ENABLE` if both list the same ID). Unknown IDs in either list emit a WARNING log. Single-feature `FEATURE_<ID>=<tier>` overrides continue to work.

### Added
- **`FeatureMatrix.check()` alias** (`features/matrix.py`) — adds `check(feature_id)` as a direct alias for `check_available()`, matching the originally-planned public API.

### Added
- **`FeatureMatrix.summary()` method** (`features/matrix.py`) — returns a compact list of all features (feature_id, display_name, maturity, enabled) suitable for status endpoints and admin UI consumers.

### Added
- **`proxy_endpoints` feature entry** (`features/matrix.py`) — added the missing stable `proxy_endpoints` registry entry so `FeatureMatrix.check("proxy_endpoints")` works correctly.

### Added
- **`as_dict()` enhancements** (`features/matrix.py`) — `FeatureMatrix.as_dict()` now returns `schema_version: "1"`, a top-level `entries` list (for consumers that prefer arrays over keyed maps), and a top-level `by_maturity` dict alongside the existing `features` dict and `summary` block.

### Fixed (CI)
- `AdminScreen.jsx`: recovered `INITIAL_USERS`, `INITIAL_REQUESTS`, `INITIAL_KEYS`, `roleConfig`, `RoleBadge`, `setUserOnboardingFlag` constants accidentally removed with old HMAC helpers
- `ActivityPage.js`: added missing lucide-react imports (`MessageSquare`, `BookOpen`, `Upload`, `Shield`, `AlertCircle`, `ArrowUpRight`, `Clock`)
- `tests/test_chat_mode_regressions.py`: moved `_auth_headers()` call before `monkeypatch.setattr(server, "get_db", ...)` so login runs against the real CI MongoDB; previously the bare `Mock()` caused non-async attribute calls in the login/bootstrap path
