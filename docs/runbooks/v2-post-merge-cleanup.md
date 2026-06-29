# Post-Merge Environment Cleanup Guide

After merging PR #896 (V2.0 Modernization) to master, clean up these
environment variables + secrets across systems.

## What to clean up

### 1. Render (production backend + worker)

**Nothing to remove.** The V2.0 migration is purely internal — no env vars
were renamed or removed. All existing env vars continue to work:

| Var | Status | Notes |
|---|---|---|
| `BRAIN_PREFERENCE` | Keep | Honored by `packages.ai.brain_config` (was `services.brain_config_store`) |
| `NVIDIA_API_KEY` | Keep | Read by `packages.ai.brain_config.provider_api_key()` |
| `CEREBRAS_API_KEY` | Keep | Same |
| `GROQ_API_KEY` | Keep | Same |
| `OLLAMA_BASE` | Keep | Read by `packages.ai.brain_config.resolve_ollama_base_url()` |
| `ALLOW_PAID_BRAIN` | Keep | Read by `packages.ai.brain.allow_paid_brain()` |
| `SERVICE_TOKEN` | Keep | Read by `packages.auth.service_token.verify_service_token()` |
| `JWT_SECRET` | Keep | Read by `packages.auth.admin` (was `admin_auth.py`) |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Keep | Read by `backend/server.py` (unchanged) |
| `API_KEYS` | Keep | Read by `proxy.py` (unchanged) |

### 2. Cloudflare Worker (frontend)

**Nothing to remove.** The frontend code is unchanged in V2.0 Phase 6 —
only dead code (`remote-admin/`) was removed, and that was never deployed
to the Worker.

### 3. Local development machines

Clean up these **local-only** artifacts:

```bash
# Remove the brain_config sqlite mirror (will be re-created on next start)
rm -f .data/agency.db_brain.db

# Remove stale cached brain config (in case a test polluted it)
# (No manual action needed — the autouse test fixture handles this in CI)
```

### 4. GitHub secrets

**Nothing to remove.** All GitHub secrets (`GH_PAT`, `CI_ADMIN_PASSWORD`,
`TELEGRAM_BOT_TOKEN`, etc.) are still in use.

### 5. MongoDB collections

**Nothing to remove.** The `app_settings` collection (which holds the
`brain_config` document) is still in use — `packages.ai.brain_config`
reads/writes it via the same singleton as before.

## What changed (informational)

These files moved location but the env vars they read are unchanged:

| Old path | New path | Env vars read |
|---|---|---|
| `provider_router.py` | `packages/ai/router.py` | `PROVIDER_COOLDOWN_SECONDS`, `PROVIDER_RATELIMIT_COOLDOWN_SECONDS`, `PROVIDER_RATELIMIT_COOLDOWN_MAX_SECONDS` |
| `brain_policy.py` | `packages/ai/brain.py` | `ALLOW_PAID_BRAIN`, `BRAIN_PREFERENCE`, `NVIDIA_API_KEY`, `NVidiaApiKey`, `NVIDIA_BASE_URL`, `NVIDIA_DEFAULT_MODEL`, `AGENT_LLM_BASE_URL`, `AGENT_LLM_API_KEY`, `AGENT_LLM_MODEL`, `OLLAMA_BASE` |
| `services/brain_config_store.py` | `packages/ai/brain_config.py` | `NVIDIA_API_KEY`, `CEREBRAS_API_KEY`, `GROQ_API_KEY`, `OLLAMA_BASE`, `OLLAMA_BASE_URL`, `SQLITE_DB_PATH`, `BRAIN_PREFERENCE`, `HERMES_BASE_URL` |
| `services/brain_watchdog.py` | `packages/ai/watchdog.py` | `BRAIN_WATCHDOG_MAX_FAILURES` |
| `admin_auth.py` | `packages/auth/admin.py` | `JWT_SECRET`, `JWT_ALGORITHM`, `ADMIN_PASSWORD` |
| `social_auth.py` | `packages/auth/oauth.py` | `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `FRONTEND_URL` |
| `rbac.py` | `packages/auth/rbac.py` | (none — reads from user dict) |
| `services/service_token.py` | `packages/auth/service_token.py` | `SERVICE_TOKEN` |
| `agent/scheduler.py` | `packages/scheduler/scheduler.py` | (none — uses scheduler_store) |
| `services/scheduler_store.py` | `packages/scheduler/store.py` | `MONGO_URL`, `DB_NAME`, `STORAGE_BACKEND`, `SQLITE_DB_PATH` |
| `db/mongo_store.py` | `packages/storage/mongo.py` | `MONGO_URL`, `DB_NAME`, `MONGO_SELECTION_TIMEOUT_MS` |
| `db/sqlite_store.py` | `packages/storage/sqlite.py` | `SQLITE_DB_PATH`, `STORAGE_BACKEND` |

## Post-merge verification checklist

After merging + deploying:

1. **Backend health**: `curl https://autonomous-ai-agency.onrender.com/health` → 200
2. **Brain resolver**: `curl https://autonomous-ai-agency.onrender.com/api/autonomy/status` → `brain.provider` matches `BRAIN_PREFERENCE`
3. **Admin login**: POST `/api/auth/login` with `ADMIN_EMAIL` + `ADMIN_PASSWORD` → 200 + JWT
4. **Brain policy**: GET `/admin/api/policy/brain` with the JWT → 200 + `config.primary_provider`
5. **Frontend**: Visit `https://autonomous-ai-agency.strikersam.workers.dev/` → dashboard loads
6. **Social login**: Click GitHub + Google buttons → redirect to OAuth provider
7. **Scheduler**: GET `/api/schedules` → 200 + list of scheduled jobs

## Rollback

If anything breaks after merge, revert the merge commit:

```bash
git revert -m 1 <merge-commit-sha>
git push origin master
```

The backward-compat shims at the old paths ensure production keeps working
even if the `packages/` versions are removed.
