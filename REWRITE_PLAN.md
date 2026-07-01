# REWRITE_PLAN.md — Phased Migration Strategy

> **This document defines the migration from the current architecture to the target architecture.**
> One subsystem at a time. No big-bang rewrites. Application must work after every merge.
> See `ARCHITECTURE.md` for the target design and `CLAUDE.md` for the operating manual.

---

## Zero Regression Policy

Before touching ANY code:
1. Write characterization tests that pin current behaviour
2. Run tests before AND after every change
3. If behaviour changes unexpectedly → rollback immediately
4. Old code is deleted ONLY after new code is verified in production for 7 days

---

## Phase 1: Foundation (Weeks 1-2)

**Goal**: Create the target structure without moving any code yet.

### Step 1.1: Create package skeleton
- [ ] Create `apps/`, `packages/`, `infra/`, `docs/adr/` directories
- [ ] Add `__init__.py` to each package
- [ ] Add README.md to each explaining its purpose
- [ ] No code moves — just empty directories with docs

### Step 1.2: Centralize configuration
- [ ] Create `packages/config/settings.py` — typed `Settings` class
- [ ] Move ALL `os.environ.get()` calls to this module (one by one, with tests)
- [ ] Every module imports `from packages.config import settings`
- [ ] Remove direct `os.environ` access from non-config modules
- [ ] **Characterization test**: verify all env vars are still read correctly

### Step 1.3: Split backend/server.py
- [ ] Extract routes into `apps/api/routes/` modules (one per domain)
- [ ] Keep `backend/server.py` as the entry point that imports + mounts routers
- [ ] Each route module: ~200-400 lines max
- [ ] **Characterization tests**: every existing API test must still pass
- [ ] Priority order: auth → activation → providers → tasks → scheduler → doctor → voice → autonomy

### Step 1.4: Consolidate OAuth
- [ ] Verify `social_auth.py` is the single source of truth for OAuth
- [ ] Remove any duplicate token-exchange logic from `backend/server.py`
- [ ] Both GitHub + Google callbacks use `social_auth.py` helpers
- [ ] **Test**: social login E2E (GitHub redirect → callback → JWT → /api/auth/me)

---

## Phase 2: Provider Abstraction (Weeks 3-4)

**Goal**: One provider interface, one failover manager, one brain config.

### Step 2.1: Define Provider interface
- [ ] Create `packages/ai/provider.py` — abstract base class
- [ ] Define: `chat()`, `stream()`, `health()`, `cost()`, `limits()`
- [ ] **No implementations yet** — just the interface

### Step 2.2: Migrate provider implementations
- [ ] Move NVIDIA logic from `provider_router.py` to `packages/ai/adapters/nvidia.py`
- [ ] Move Cerebras logic → `packages/ai/adapters/cerebras.py`
- [ ] Move Groq logic → `packages/ai/adapters/groq.py`
- [ ] Move Ollama logic → `packages/ai/adapters/ollama.py`
- [ ] Each adapter implements the Provider interface
- [ ] **Characterization test**: same API responses for same inputs

### Step 2.3: Create ProviderManager
- [ ] Move failover logic from `provider_router.py` to `packages/ai/registry.py`
- [ ] ProviderManager uses the adapter implementations
- [ ] Brain watchdog integration preserved
- [ ] Exponential backoff preserved
- [ ] **Test**: 429 failover, 410 removal, 419 per-model skip

### Step 2.4: Consolidate brain config
- [ ] Merge `brain_policy.py` + `services/brain_config_store.py` → `packages/ai/brain.py`
- [ ] One `BrainConfig` model, one `get_brain_config()`, one `set_brain_config()`
- [ ] **Test**: brain config persistence, liveness probe, watchdog failover

---

## Phase 3: Auth Consolidation (Week 5)

**Goal**: One auth system, one module, no duplicates.

### Step 3.1: Create auth package
- [ ] Create `packages/auth/` with: `jwt.py`, `oauth.py`, `api_key.py`, `service_token.py`, `rbac.py`
- [ ] Move `get_current_user`, `get_optional_user`, `_require_admin` → `packages/auth/jwt.py`
- [ ] Move `social_auth.py` → `packages/auth/oauth.py`
- [ ] Move `admin_auth.py` → `packages/auth/admin.py`
- [ ] Move `services/service_token.py` → `packages/auth/service_token.py`
- [ ] Move `rbac.py` → `packages/auth/rbac.py`

### Step 3.2: Update imports
- [ ] All modules import from `packages.auth` instead of scattered locations
- [ ] **Characterization test**: every auth flow still works (JWT, API key, service token, OAuth)

---

## Phase 4: Scheduler Redesign (Week 6)

**Goal**: Clean separation of scheduler, queue, worker, state.

### Step 4.1: Create scheduler package
- [ ] Move `agent/scheduler.py` → `packages/scheduler/scheduler.py`
- [ ] Move `services/scheduler_store.py` → `packages/scheduler/store.py`
- [ ] Extract cleanup logic → `packages/scheduler/cleanup.py`

### Step 4.2: Fix root causes
- [ ] Ensure `force_cleanup()` runs on every tick + startup (already done)
- [ ] Ensure nuclear `delete_many` runs on startup (already done)
- [ ] Add test: schedule multiplication cannot happen (create + restart + verify count)

---

## Phase 5: Storage Abstraction (Week 7)

**Goal**: One database interface, swappable backends.

### Step 5.1: Create storage package
- [ ] Move `db/mongo_store.py` → `packages/storage/mongo.py`
- [ ] Move `db/sqlite_store.py` → `packages/storage/sqlite.py`
- [ ] Define `StorageInterface` in `packages/storage/interface.py`
- [ ] Both backends implement the same interface

### Step 5.2: Motor event-loop fix (already done)
- [ ] `reset_store()` clears motor client singleton (already done)
- [ ] `client` fixture calls `reset_store()` (already done)
- [ ] **Test**: motor event-loop isolation (already done)

---

## Phase 6: Frontend Cleanup (Week 8)

**Goal**: Clean component structure, no dead code.

### Step 6.1: Remove dead components
- [ ] Delete `frontend/src/v5/screens/LoginScreen.jsx` (unused, LoginPage.js is active)
- [ ] Delete any unused screens/components
- [ ] Remove dead CSS

### Step 6.2: Consolidate API calls
- [ ] All frontend API calls go through `frontend/src/api.js`
- [ ] No direct `fetch()` calls in components (except social login click handler)

### Step 6.3: Admin-only nav items
- [ ] `providers` marked `adminOnly` (already done)
- [ ] `admin` marked `adminOnly` (already done)
- [ ] `loops`, `logs`, `github` → review if admin-only

---

## Phase 7: Dead Code Removal (Week 9)

**Goal**: Remove everything that's not used.

### Inventory of suspected dead code
- [ ] `admin_gui.py` — old admin GUI (replaced by React dashboard)
- [ ] `commercial_equivalent.py` — appears to be a one-off analysis script
- [ ] `graphify-out/` — generated output directory
- [ ] `scratch/` — temporary files
- [ ] `roadmap/` — old roadmap docs (superseded by `docs/plans/`)
- [ ] `config-export/` — exported config snapshots
- [ ] `.emergent/` — emergent integrations (check if used)
- [ ] `.agent_memory/` — old agent memory (check if used)
- [ ] `.Codex/` — Codex config (check if used)
- [ ] Root-level scripts: `run*.bat`, `run*.sh`, `start*.sh`, `stop*.sh`, `setup_*.py`, `install.sh`
- [ ] `remote-admin/` — old admin SPA (replaced by v5 dashboard)
- [ ] `webui/` — old web UI (check if used)

### Process
1. Search for imports/references to each file
2. If no references found → delete
3. If references found → trace + decide
4. **Test after each deletion**

---

## Phase 8: Documentation Finalization (Week 10)

**Goal**: Every component documented, every decision recorded.

### Step 8.1: Architecture docs
- [ ] Update `README.md` with current architecture
- [ ] Add deployment diagram
- [ ] Add data flow diagram
- [ ] Add secrets inventory

### Step 8.2: ADRs
- [ ] Write ADR for every significant decision made during migration
- [ ] Format: Context → Decision → Consequences

### Step 8.3: Runbooks
- [ ] Deploy runbook (Render + Cloudflare + GitHub Pages)
- [ ] Incident runbook (NVIDIA 410, schedule multiplication, CDN cache)
- [ ] Onboarding runbook (new developer setup)

---

## Migration Safety Checklist

Before starting each phase:
- [ ] All existing tests pass
- [ ] Characterization tests written for the subsystem being migrated
- [ ] Feature flag created (if needed)
- [ ] Rollback plan documented

After completing each phase:
- [ ] All existing tests still pass
- [ ] New tests written for the migrated code
- [ ] CI green (22/22 checks)
- [ ] Production deployment verified
- [ ] Old code marked for deletion (with deletion date)
- [ ] Changelog updated

---

## Current Status

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1: Foundation | Not started | Directory structure + config centralization |
| Phase 2: Providers | Not started | Provider abstraction + failover |
| Phase 3: Auth | Not started | Auth consolidation |
| Phase 4: Scheduler | Partially done | force_cleanup + nuclear delete done; package extraction pending |
| Phase 5: Storage | Partially done | Motor fix done; package extraction pending |
| Phase 6: Frontend | Partially done | Dead LoginScreen.jsx still exists; admin-only nav done |
| Phase 7: Dead code | Not started | Inventory complete, deletion pending |
| Phase 8: Docs | This document | Architecture framework created |

### Already completed (pre-migration fixes)
- ✅ Social login CDN cache fix (worker `not_found_handling: "none"`)
- ✅ SAM Voice endpoints added to backend/server.py
- ✅ NVIDIA model updated (v1 → meta/llama-3.3-70b-instruct)
- ✅ Schedule multiplication fix (nuclear delete_many + force_cleanup)
- ✅ Onboarding gate fix (frontend checks /api/activation/settings)
- ✅ Provider admin-only gate (GET /api/providers + nav item)
- ✅ Hermes merged into backend (in-process on port 8100)
- ✅ Motor event-loop isolation (reset_store clears motor client)
- ✅ Loop readiness: 58/D → 100/A
- ✅ CI: 22/22 checks green
