# V2.0 Modernization — Runbook

This runbook covers the operational aspects of the V2.0 modernization
(Phases 1-8). For the architectural rationale, see
[REWRITE_PLAN.md](../REWRITE_PLAN.md) and the [ADRs](adr/).

## Module map (old → new)

| Old path | New path | Notes |
|---|---|---|
| `provider_router.py` | `packages/ai/router.py` | Shim re-exports all symbols |
| `brain_policy.py` | `packages/ai/brain.py` | Shim re-exports all symbols |
| `services/brain_config_store.py` | `packages/ai/brain_config.py` | Shim re-exports; tests import real module |
| `services/brain_watchdog.py` | `packages/ai/watchdog.py` | Shim re-exports all symbols |
| `admin_auth.py` | `packages/auth/admin.py` | Shim re-exports all symbols |
| `social_auth.py` | `packages/auth/oauth.py` | Shim re-exports all symbols |
| `rbac.py` | `packages/auth/rbac.py` | Shim re-exports all symbols |
| `services/service_token.py` | `packages/auth/service_token.py` | Shim; tests load real file via importlib |
| `agent/scheduler.py` | `packages/scheduler/scheduler.py` | Shim re-exports; tests import real module |
| `services/scheduler_store.py` | `packages/scheduler/store.py` | Shim re-exports; tests import real module |
| `db/mongo_store.py` | `packages/storage/mongo.py` | `sys.modules` alias — writes + reload work |
| `db/sqlite_store.py` | `packages/storage/sqlite.py` | `sys.modules` alias — writes + reload work |
| `remote-admin/` | (deleted) | Old admin SPA, replaced by v5 React dashboard |

## Importing new code

**New code should import from `packages/`:**

```python
# OLD (still works via shim)
from provider_router import ProviderRouter
from brain_policy import resolve_active_brain
from services.brain_config_store import BrainConfig
from admin_auth import ADMIN_AUTH
from agent.scheduler import AgentScheduler

# NEW (preferred)
from packages.ai.router import ProviderRouter
from packages.ai.brain import resolve_active_brain
from packages.ai.brain_config import BrainConfig
from packages.auth.admin import ADMIN_AUTH
from packages.scheduler.scheduler import AgentScheduler
```

## Test migration

Tests that mutate module-level singletons must import the REAL module,
not the shim:

```python
# OLD (writes don't propagate through shim)
import services.brain_config_store as mod
mod._store = my_store  # writes to shim's globals, not real singleton

# NEW (writes hit the real singleton)
import packages.ai.brain_config as mod
mod._store = my_store  # ✓
```

Same pattern for:
- `services.scheduler_store._store` → `packages.scheduler.store._store`
- `db.mongo_store._client` → `packages.storage.mongo._client`
- `brain_policy._cached_brain` → `packages.ai.brain._cached_brain`

## Adding a new provider adapter

1. Create `packages/ai/adapters/<provider>.py` implementing the
   `Provider` interface (`chat()`, `stream()`, `health()`, `cost()`,
   `limits()`).
2. Register the model in `packages/ai/registry.py`.
3. Add the adapter to `ProviderManager` in `packages/ai/manager.py`.
4. The old `provider_router.py` path still works via shim — no need to
   update callers until you're ready.

## Removing the shims (future cleanup)

Once every caller imports from `packages/`, delete the shims:

```bash
# Find remaining shim users
grep -rn "from provider_router\|from brain_policy\|from services.brain_config_store\|from services.brain_watchdog\|from admin_auth\|from social_auth\|from rbac\|from services.service_token\|from agent.scheduler\|from services.scheduler_store" --include="*.py" | grep -v __pycache__ | grep -v packages/

# After all callers updated, delete shims
git rm provider_router.py brain_policy.py services/brain_config_store.py services/brain_watchdog.py
git rm admin_auth.py social_auth.py rbac.py services/service_token.py
git rm agent/scheduler.py services/scheduler_store.py
# db/__init__.py stays (it's the public entry point for get_store())
```

## CI

The branch-protection checks on `master` are:
- `Test (Python 3.13)` — full pytest suite with MongoDB service container
- `Frontend test + build` — Jest + npm build
- `Lint check` — flake8 / ruff
- `Secret / Credential Scan` — trufflehog
- `Dependency CVE Audit` — pip-audit
- `Bandit SAST` — bandit
- `Analyze (python)` + `Analyze (javascript-typescript)` — CodeQL
- `Security Gate — No New Alerts`

All must be green before merge.

## Rollback

Each phase is a separate commit. To roll back a phase:

```bash
git revert <phase-commit-sha>
git push origin feat/v2-modernization
```

The shims make rollback safe — production code continues to work via
the old import paths even if the `packages/` versions are removed.
