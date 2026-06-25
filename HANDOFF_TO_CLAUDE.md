# Autonomous AI Agency — Full Handoff Prompt for Claude Code

## Context

You are continuing work on the Autonomous AI Agency (https://github.com/strikersam/autonomous-ai-agency). The agency is a self-hosted AI platform that provisions specialist agents from a single URL, runs them 24x7, and brings only decisions that matter for human approval. It's deployed on Render (free tier) at https://local-llm-server.onrender.com.

## What was done (33+ PRs merged)

### Autonomy Pipeline Fixes (PRs #775-#789)
- **Schedule persistence**: Fixed `ScheduledJob.status` AttributeError, rewrote `ScheduleStore` to support both Mongo and SQLite, fixed APScheduler thread event-loop binding via `run_coroutine_threadsafe`
- **Self-bootstrap**: Fixed stale URL defaults (old repo name), added stale-env-var detection, added specialist re-provisioning, added direct company creation fallback, made `/api/autonomy/status` trigger `ensure_self_company()`, fixed `list_companies` resilience against stale rows, added `'archived'` to valid `onboarding_status` Literal

### CEO Agency Fixes (PRs #790-#798)
- **Provider routing**: Free NVIDIA brain always wins over stale DB provider records (MiniMax 401 fix)
- **CEO force-start**: `/api/autonomy/status` force-starts the CEO agency regardless of `AGENCY_CEO_ENABLED`
- **GitHub repo derivation**: `_gh_repo()` derives repo from `SELF_REPO_URL` when `GITHUB_REPOSITORY` is missing
- **Scheduler wiring**: `/api/autonomy/status` wires `scheduler.on_fire` before CEO fires

### Task Dispatch Fixes (PRs #800-#804)
- **Direct task creation**: `/api/autonomy/status` creates tasks directly from GitHub issues (bypasses scheduler's broken fire-and-forget)
- **Bypass coordinator**: Executes via `InternalAgentAdapter.execute()` directly (bypasses coordinator's stuck in-memory lock)
- **Force pending_agent_run**: Explicit `pending_agent_run=True` + 500ms sync wait

### NVIDIA NIM Fixes (PRs #805, #813)
- **Dead model (410 Gone)**: Switched from `nvidia/nemotron-3-super-120b-a12b` to `nvidia/llama-3.3-nemotron-super-49b-v1` across 25+ files
- **400 Bad Request**: Removed Ollama-specific fields (`thinking_token_budget`, `options`, `keep_alive`) from NVIDIA NIM payload; added `max_tokens: 4096` for NIM
- **429/419 rate limiting**: Added exponential backoff retry (1s, 2s, 4s) for 429/419 responses

### All-Issues Processing (PR #812)
- CEO now fetches ALL open issues (not just `quick-note` labelled)
- Dispatch creates tasks for any issue type (bugs, features, trend digests)

### Non-blocking Status (direct pushes)
- `/api/autonomy/status` returns instantly (CEO cycle runs in background)
- CEO + dispatch run as `asyncio.create_task` with 30s timeout
- Added GitHub Actions cron workflow (`autonomous-cycle.yml`) that hits the endpoint every 2 minutes

### Other Fixes (PR #799)
- E2E tests: disable all autonomy loops to fix Playwright timeout
- NVIDIA 419 rate limit handling alongside 429
- README: honest about Hermes and external runtimes being optional sidecars
- README: updated runtime table and feature maturity matrix

## Current State

### Working ✅
- `/api/autonomy/status` returns instantly with CEO + dispatch status
- `/api/doctor/public` works
- Brain: NVIDIA NIM `nvidia/llama-3.3-nemotron-super-49b-v1` (live model)
- CEO: fires on every status check, fetches 15 open issues from GitHub
- Task creation: creates tasks for the oldest open issue
- GitHub Actions cron: hits the endpoint every 2 minutes (keeps Render warm)
- Self-bootstrap: company created, onboarding complete
- All 4 autonomy loops running (log_monitor, self_healing, improvement_loop, trend_watcher)

### Known Issues
1. **Render free tier spin-down**: Instance spins down ~15s after HTTP response, killing background tasks. The cron workflow mitigates this by hitting every 2 min, but task execution may not complete in a single cycle.
2. **NVIDIA 429 rate limiting**: Free tier allows ~40 req/min. The retry logic handles this but heavy task execution may still hit limits.
3. **Stale DB provider records**: The Mongo DB may still have provider records with the old model name (`nemotron-3-super-120b-a12b`). These need to be cleaned up via the Providers screen or direct DB update.
4. **NVIDIA_DEFAULT_MODEL on Render dashboard**: If this env var is still set to the old model, it overrides the code default. Must be updated or deleted on the Render dashboard.

### Open Issues (16 total)
- 6 quick-note issues (URLs to evaluate + integrate)
- 8 GitHub-repo research issues
- 1 trend digest
- 1 agency setup issue

## What to do next

1. **Monitor the autonomous-cycle workflow**: Check https://github.com/strikersam/autonomous-ai-agency/actions/workflows/autonomous-cycle.yml — it should show a run every 2 minutes with the CEO + dispatch status.

2. **Check for new PRs**: The agency creates tasks for open issues and executes them via NVIDIA NIM. Successful execution should push a branch and open a PR.

3. **Clean up stale DB provider records**: Go to the Providers screen (https://local-llm-server.onrender.com → login → Providers) and delete any provider records that reference the old model `nemotron-3-super-120b-a12b`.

4. **Update NVIDIA_DEFAULT_MODEL on Render**: Render dashboard → local-llm-server → Environment → either update `NVIDIA_DEFAULT_MODEL` to `nvidia/llama-3.3-nemotron-super-49b-v1` or delete it entirely.

5. **Consider Render Starter ($7/mo)**: Always-on instance would let background tasks complete without being killed by spin-down. This is the single biggest improvement for full autonomy.

6. **Process open issues**: Each hit of `/api/autonomy/status` processes one issue. The cron workflow does this every 2 minutes. At that rate, 16 issues = ~32 minutes to process the full backlog (assuming NVIDIA NIM doesn't rate-limit).

## Key Files

- `agent/agency.py` — CEO agency loop, quick-note fetch, directive dispatch
- `agent/loop.py` — AgentRunner, `_chat_text()` (NVIDIA NIM call with rate-limit retry)
- `agent/scheduler.py` — APScheduler with `attach_main_loop()` + `run_coroutine_threadsafe`
- `agent/schedule_store.py` — Durable schedule persistence (Mongo + SQLite)
- `services/self_bootstrap.py` — Self-onboarding (company creation, specialist provisioning)
- `services/company_agency.py` — 24x7 cadence creation (6 schedules per company)
- `services/background.py` — Background service startup (CEO, dispatcher, loops)
- `services/workflow_orchestrator.py` — `resolve_provider_for()` (free NVIDIA brain first)
- `runtimes/adapters/internal_agent.py` — InternalAgentAdapter (NVIDIA NIM runtime)
- `tasks/service.py` — TaskExecutionCoordinator
- `tasks/dispatcher.py` — TaskDispatcher (background poll loop)
- `backend/server.py` — `/api/autonomy/status` (non-blocking, triggers CEO + dispatch)
- `provider_router.py` — Provider chain with 429/419 rate-limit handling
- `brain_policy.py` — Free-brain policy (NVIDIA first, paid Anthropic opt-in)
- `.github/workflows/autonomous-cycle.yml` — Cron workflow (every 2 min)

## Environment Variables (Render dashboard)

Must be set correctly:
- `NVIDIA_API_KEY` — Free NVIDIA NIM key (set ✅)
- `NVIDIA_DEFAULT_MODEL` — Must be `nvidia/llama-3.3-nemotron-super-49b-v1` or deleted
- `GH_PAT` or `GITHUB_TOKEN` — GitHub PAT for issue fetch + PR creation (set ✅)
- `GITHUB_REPOSITORY` — `strikersam/autonomous-ai-agency` (may be missing — code falls back to SELF_REPO_URL)
- `SELF_BOOTSTRAP_ENABLED` — `true`
- `RUN_BACKGROUND_IN_WEB` — `true`
- `STORAGE_BACKEND` — `mongo` (Render has Mongo) or `sqlite`
