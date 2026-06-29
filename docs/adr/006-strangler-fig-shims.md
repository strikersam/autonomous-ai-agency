---
title: ADR-006: Strangler Fig migration with backward-compat shims
status: accepted
date: 2026-06-28
---

# ADR-006: Strangler Fig migration with backward-compat shims

## Context

The V2.0 Modernization Program (Phases 2-5) moves production code from
scattered root-level modules (`provider_router.py`, `brain_policy.py`,
`admin_auth.py`, `agent/scheduler.py`, `db/mongo_store.py`, etc.) into
the new `packages/` directory structure.

A "big bang" rewrite — updating every import in every file at once —
would touch 100+ files and 300+ test cases in a single commit, making
review nearly impossible and rollback catastrophic.

## Decision

Use the **Strangler Fig pattern** with **backward-compat shims**:

1. **Move the real code** to `packages/<area>/<module>.py` via `git mv`.
2. **Leave a thin shim** at the old location that re-exports every symbol
   (public + private) from the new location.
3. **Tests that mutate module-level singletons** (e.g. `_store`) are
   updated to import the real module: `import packages.ai.brain_config
   as mod` — the shim re-exports symbols but module-level writes don't
   propagate to the real singleton.
4. **Storage modules** use `sys.modules` aliasing (registering the real
   module under the old name) so `importlib.reload()` and module-level
   writes both work without test changes.

## Consequences

**Positive:**
- Existing imports keep working — zero churn in production code.
- Each phase is independently reviewable + revertable.
- Tests can be updated incrementally.
- The shims serve as a migration map: `grep -r "from provider_router"`
  shows every caller that still needs updating.

**Negative:**
- Two import paths for the same code until the shim is removed.
- Tests that inspect module SOURCE (e.g. `inspect.getsource()`) must
  load the real file, not the shim.
- Module-level singleton writes require care — shims must use
  `sys.modules` aliasing, not `from X import *`.

## Migration path

Once all callers import from `packages/`, the shims can be deleted in a
follow-up PR. Until then, they document the migration state.

## Examples

- `provider_router.py` → `packages/ai/router.py` (shim re-exports all symbols)
- `brain_policy.py` → `packages/ai/brain.py` (shim re-exports all symbols)
- `services/brain_config_store.py` → `packages/ai/brain_config.py` (shim + test import update)
- `admin_auth.py` → `packages/auth/admin.py` (shim re-exports all symbols)
- `agent/scheduler.py` → `packages/scheduler/scheduler.py` (shim + test import update)
- `db/mongo_store.py` → `packages/storage/mongo.py` (sys.modules alias)
- `db/sqlite_store.py` → `packages/storage/sqlite.py` (sys.modules alias)
