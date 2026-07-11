## Summary

All 8 units from the 8-unit execution plan — combined in this single PR as requested.

### UNIT 1 — Fix duplicate ceo_direct tasks ✅

**Problem:** Both `ceo_direct` task-creation blocks in `backend/server.py` created tasks WITHOUT `source_id`. Every tick minted a new task for the same GitHub issue — duplicates piled up.

**Fix:**
- New idempotent helper `tasks/issue_intake.py::create_task_from_oldest_open_issue()` — iterates issues, checks `find_by_source_id()` before creating, sets `source_id=issue_source_id(repo, number)`
- Replaced BOTH duplicated blocks with calls to this helper
- Self-heal now has a BACKFILL pass (parse issue # from legacy titles → set `source_id`) + DEDUP pass (keep `in_progress > done > oldest-created`)
- Tests: `tests/test_ceo_direct_dedup.py` (4 tests)

### UNIT 2 — Portfolio → task materializer (default ON) ✅

**Problem:** Portfolio initiatives never became tasks — no converter existed.

**Fix:**
- New `tasks/portfolio_intake.py` — content-derived `source_id` (hash of source|title) survives rebuilds
- `materialize_committed()` takes initiatives from `allocate_capacity()` with status in {PROPOSED, APPROVED}, source != "pr", WSJF desc, cap 3
- Hooked into `POST /api/portfolio/refresh` + new `POST /api/portfolio/materialize` endpoint
- Flag `PORTFOLIO_MATERIALIZE_ENABLED` (default true) in `packages/config/settings.py`
- Tests: `tests/test_portfolio_intake.py` (7 tests)

### UNIT 3 — Config hygiene (zero behavior change) ✅

- Deleted dead `AGENT_LLM_BASE_URL`/`AGENT_LLM_MODEL`/`AGENT_LLM_API_KEY` from `deploy-cloudflare.yml`
- Fixed `safe_default` in GET `/admin/api/policy/brain` to use imported `SAFE_DEFAULT_PROVIDER`/`SAFE_DEFAULT_MODEL`
- Removed 2 duplicate `meta/llama-3.3-70b-instruct` entries in `services/cost_attribution.py`
- Removed duplicate `nvidia/llama-3.3-nemotron-super-49b-v1.5` entry in `.github/scripts/nvidia_models.py`
- Updated stale Nemotron comments in `.env.example` and `render.yaml` to reference `z-ai/glm-5.2`

### UNIT 4 — Commit model catalog `config/models.yaml` ✅

**New committed YAML file** is the single source of truth for per-provider metadata (display name, tier, key/base-url env vars, default base URL), role presets (planner/executor/verifier/judge), and the ordered failover candidate list.

- `packages/ai/brain_config.py` loads the YAML at module import via `_load_models_yaml()`. The existing hardcoded dicts are now overridable — when the YAML is present and valid it overrides them in place; when missing or corrupt the module falls back to the in-module defaults so a bad YAML edit can never brick the agent loop.
- New module-level dicts: `PROVIDER_CANDIDATES` (per-provider ordered failover list), `PROVIDER_DISPLAY_NAMES`, `PROVIDER_TIERS` (free/paid/local)
- New helper functions: `get_provider_candidates(provider)`, `get_provider_display_name(provider)`, `get_provider_tier(provider)`, `all_provider_ids()`
- Tests: `tests/test_model_catalog.py` (31 tests — YAML parses, every Literal provider has a YAML entry, every YAML provider is in the Literal, all required fields present, all four roles preset, candidates non-empty list, tier values valid, all module dicts populated from YAML, helpers return expected values, graceful degradation on missing/corrupt/wrong-shape YAML, parity between YAML and hardcoded defaults)
- Added `PyYAML>=6.0.2` to `requirements.txt`

### UNIT 5 — UI exposes all 14 providers ✅

**Problem:** The BrainCard dropdown was hardcoded to 4 providers (Cerebras/Groq/NVIDIA/Ollama) — even though the `BrainProvider` Literal and `config/models.yaml` catalog knew about 14. Adding a provider to the catalog silently dropped it from the UI.

**Fix:**
- `_brain_provider_status()` in `backend/server.py` now iterates `all_provider_ids()` (which reads the Literal via `typing.get_args`). Adding a provider to the catalog automatically surfaces it in the UI with no parallel list to keep in sync.
- Each provider entry now includes `display_name`, `tier` (free/paid/local), and `candidates` (the ordered failover list)
- `frontend/src/v5/components/BrainCard.jsx` removed the 4-entry hardcoded `PROVIDER_LABELS` map; the dropdown now calls a `providerLabel(p)` helper that prefers the server-supplied `display_name` and falls back to a 14-entry `PROVIDER_LABEL_FALLBACK` map
- A new `tierBadge(tier)` helper renders a `[free]`/`[paid]`/`[local]` tag in each dropdown option
- Tests: `tests/test_unit5_ui_provider_surface.py` (10 tests)

### UNIT 6 — `resolve_component_model()` — single entry point ✅

**Problem:** Three duplicate preset tables each mirrored `PROVIDER_PRESETS`:
1. `telegram_bot.cmd_setbrain` had a 4-provider inline table
2. `backend/server._default_agent_role_models` had a hardcoded NIM/Ollama split with stale model ids (`qwen/qwen3-coder-480b-a35b-instruct` and `deepseek-ai/deepseek-v4-pro` were never in the catalog)
3. `services/brain_failover._PROVIDER_REGISTRY` had a 14-provider table with `default_model`/`models` fields that drifted from the catalog

**Fix:** Single `resolve_component_model(component, role, provider, requested)` function in `packages/ai/brain_config.py`. Precedence: (1) per-call `requested` override, (2) DB-saved BrainConfig model for this role (when the requested provider matches the active primary AND the cache is fresh), (3) catalog preset `PROVIDER_PRESETS[provider][role]`, (4) env var `AGENT_<ROLE>_MODEL` (backward compat), (5) `SAFE_DEFAULT_MODEL`. Never raises.

- `telegram_bot.cmd_setbrain` now accepts all 14 catalog providers (was 4)
- `backend/server._default_agent_role_models` — stale `qwen/qwen3-coder-480b-a35b-instruct` and `deepseek-ai/deepseek-v4-pro` ids gone
- `services/brain_failover._PROVIDER_REGISTRY` — derives `default_model` (first catalog candidate) and `models` (full candidate list) from `PROVIDER_CANDIDATES` at module import time
- Tests: `tests/test_unit6_resolve_component_model.py` (18 tests)

### UNIT 7 — Catalog propagation to all remaining call sites ✅

Every remaining call site that hardcoded model ids now consults the catalog:

1. `router/model_router._default_model()` and `_default_reasoning_model()` — were hardcoded `qwen/qwen2.5-coder-32b-instruct` (NVIDIA) / `deepseek-ai/deepseek-r1` (NVIDIA) / `deepseek-r1:32b` (Ollama) / `qwen3-coder:30b` (Ollama); now call `resolve_component_model("router", role, provider)`
2. `agents/profiles._get_defaults()` — was a hardcoded NIM/DeepSeek/Groq/DashScope/Ollama split; now consults `_catalog_defaults()` first (preserves the coder ≠ reviewer asymmetry via `_CRISPY_TO_BRAIN_ROLE`: architect/scout/coder → executor, reviewer → judge, verifier → verifier). Falls back to the legacy table only if the catalog import fails.
3. `runtimes/adapters/jcode.py` and `runtimes/adapters/opencode.py` — `__init__` was hardcoded `meta/llama-3.3-70b-instruct` as the default model; now each calls a local `_resolve_default_executor_model(component)` helper
4. `runtimes/adapters/internal_agent._NVIDIA_DEFAULT_MODEL` — now derived from `PROVIDER_CANDIDATES["nvidia"][0]` (the catalog preset) at module import time
5. `render.yaml` — removed the `AGENT_PLANNER_MODEL` / `AGENT_EXECUTOR_MODEL` / `AGENT_VERIFIER_MODEL` / `AGENT_JUDGE_MODEL` env vars from all 3 services (web/worker/hermes). The catalog + DB BrainConfig are now the single source of truth; `resolve_component_model()`'s env-var fallback is kept for backward compat with existing deployments that have these set, but render.yaml no longer pins them.
6. `.env.example` — documented the removal
- Tests: `tests/test_unit7_catalog_propagation.py` (14 tests)

### UNIT 8 — Model catalog sync `packages/ai/model_catalog.py` (flag OFF) ✅

Advisory-only mirror of the model catalog (`config/models.yaml` + the active BrainConfig) to the DB so external services can query which models are available without re-implementing the catalog loader.

**Hard constraints:**
1. **Flag-gated, default OFF.** The `FREELLM_API_MODEL_CATALOG_ENABLED` flag defaults to `false`; the `GET /api/catalog/models` endpoint and `POST /api/admin/maintenance/sync-catalog` endpoint both return 503 when the flag is off. The flag is the rollout lever.
2. **Advisory-only.** The catalog mirror NEVER changes brain routing — `resolve_component_model()` is still the single source of truth for model resolution.
3. **Dual-storage.** Mongo primary (`app_settings` collection, doc id `model_catalog`), sqlite mirror (`model_catalog_mirror` table) — same pattern as `brain_config.py`. Either backend failing is non-fatal; falls back to building the catalog in-memory.
4. **Never raises.** All public methods swallow exceptions and return safe defaults.

**New module:** `packages/ai/model_catalog.py` (`ModelCatalogStore`, `CatalogMirror`, `CatalogProviderEntry`, `CatalogActiveBrain`, `get_catalog()`, `sync_catalog()`, `is_catalog_enabled()`, `invalidate_catalog_cache()`)

**New endpoints:**
- `GET /api/catalog/models` — returns the mirror (503 when flag off)
- `POST /api/admin/maintenance/sync-catalog` — admin-only, forces a rebuild + persist (503 when flag off)

**Tests:** `tests/test_unit8_model_catalog.py` (25 tests)

## Test plan

- [x] `tests/test_ceo_direct_dedup.py` (UNIT 1) — 4 tests
- [x] `tests/test_portfolio_intake.py` (UNIT 2) — 7 tests
- [x] `tests/test_model_catalog.py` (UNIT 4) — 31 tests
- [x] `tests/test_unit5_ui_provider_surface.py` (UNIT 5) — 10 tests
- [x] `tests/test_unit6_resolve_component_model.py` (UNIT 6) — 18 tests
- [x] `tests/test_unit7_catalog_propagation.py` (UNIT 7) — 14 tests
- [x] `tests/test_unit8_model_catalog.py` (UNIT 8) — 25 tests
- [x] All existing brain/router/crispy/runtime/telegram tests still pass (484 tests in the affected scope)
- [x] Changelog parity: `python scripts/check_changelog_parity.py` → PARITY OK
- [x] No `os.environ.get()` calls added in config modules outside `packages/config/settings.py`

## Rollout notes

- **UNIT 8 flag is OFF by default** — `FREELLM_API_MODEL_CATALOG_ENABLED=false`. Flip it on a single instance to verify the catalog endpoint shape before enabling everywhere. The catalog mirror is advisory-only and does NOT change brain routing.
- **`AGENT_*_MODEL` env vars removed from render.yaml** — existing deployments that have these set in their Render dashboard will continue to work (the resolver chain still consults env vars as step 4). New deployments get the catalog/DB-driven defaults instead.
- **All 14 providers are now /setbrain-eligible** — the Telegram `/setbrain` command previously rejected anything outside the 4-element hardcoded set. Now any of the 14 catalog providers can be set via Telegram.

## Checklist

- [x] Each unit has regression tests
- [x] Each new endpoint has pytest coverage
- [x] Changelog parity (CHANGELOG.md == docs/changelog.md)
- [x] No duplicate preset tables added — only deleted
- [x] All 8 units committed on `claude/unify-model-config-isqt2o` branch
