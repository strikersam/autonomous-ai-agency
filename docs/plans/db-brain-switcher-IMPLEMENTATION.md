# Implementation — DB-persisted, UI-switchable Brain (PR #824 follow-up)

This is the **full implementation** of the plan shipped in PR #824
(`docs/plans/db-brain-switcher.md`). The PR was docs-only; this commit lands
the actual feature so the agency's "brain" (provider + planner / executor /
verifier / judge models) can be changed from the admin UI in one click,
persisted in the DB, with no redeploy.

## Hard constraints (from the plan) — all met

| # | Constraint | Where it's enforced |
|---|---|---|
| 1 | Never land on a dead model — probe before save, refuse 410/404 | `services/brain_liveness.py` + `PATCH /admin/api/policy/brain` (422 + probe report on failure) |
| 2 | Always keep `nvidia/llama-3.3-nemotron-super-49b-v1` as the safe default | `services/brain_config_store.SAFE_DEFAULT_MODEL` + `default_brain_config()` |
| 3 | One-click change from the UI, persisted in DB, no redeploy | `BrainCard.jsx` calls `PATCH /admin/api/policy/brain`; `BrainConfigStore` invalidates cache on write |
| 4 | Don't break the freshly-healed `master` | All existing brain/failover/webui tests still pass (99 passed, 2 skipped) |

## Files touched

### New files

| File | Purpose |
|---|---|
| `services/brain_config_store.py` | Pydantic `BrainConfig` model + `BrainConfigStore` (Mongo primary, sqlite mirror, 5s in-process cache, `invalidate()`). Ships `resolve_role_model_sync` / `resolve_role_model` for call-time resolution. |
| `services/brain_liveness.py` | `probe_model_liveness(provider, model)` — sends a 5-token chat-completion to Cerebras / Groq / NIM, or `GET /api/tags` for Ollama. Returns `ProbeResult{live, status_code, reason, elapsed_ms}`. Never raises. |
| `frontend/src/v5/components/BrainCard.jsx` | The "Brain" card on the Providers screen: provider dropdown (only providers whose key is present), 4 role-model fields with per-row Test button, Apply button that surfaces the probe report inline. |
| `tests/test_brain_config_store.py` | 12 tests: get/set round-trip, cache invalidation, sqlite mirror, never-raises, role resolver precedence. |
| `tests/test_brain_config_api.py` | 13 tests: auth gating (401/403), GET response shape, dead-model rejection (422), live-model acceptance, partial PATCH only probes changed fields, POST /test does not persist, key-redaction. |
| `tests/test_brain_resolution.py` | 12 tests: requested → DB → env → safe-default precedence, call-time pickup (no re-import), `brain_policy.resolve_active_brain` honours DB config, env kill-switch still wins. |

### Modified files

| File | Change |
|---|---|
| `agent/loop.py` | Added `_resolve_role_model(role, requested)` helper that delegates to `services.brain_config_store.resolve_role_model_sync`. Replaced the four touch points (planner @ ~663, executor @ ~705, verifier @ ~718, judge @ ~502) so they call the resolver instead of the bare `DEFAULT_*_MODEL` constants. Added `DEFAULT_JUDGE_MODEL` constant (was implicit). The import-time constants are kept as the final fallback so nothing regresses. |
| `brain_policy.py` | `resolve_active_brain()` now checks the DB-stored `BrainConfig` as step 2 (after the `AGENT_LLM_BASE_URL` kill-switch, before provider records). Only honours it when `updated_at` is set (i.e. an admin has actually Applied a config) — so the existing test contract from `tests/test_brain_resolver.py` is preserved. |
| `backend/server.py` | Three new endpoints (admin-gated via `_is_admin`): `GET /admin/api/policy/brain`, `PATCH /admin/api/policy/brain`, `POST /admin/api/policy/brain/test`. The PATCH probes every changed model before persisting and refuses (422) if any probe fails. Never logs or returns API keys — only `key_present` booleans. |
| `frontend/src/api.js` | Added `getBrainConfig`, `patchBrainConfig`, `testBrainModel` API helpers. |
| `frontend/src/v5/screens/ProvidersScreen.jsx` | Imports `BrainCard` and mounts it at the top of the `providers` tab (above the existing "Paid-provider kill switch"). |

## Architecture (per plan §3)

```
UI "Brain" card  ──PATCH /admin/api/policy/brain──►  BrainConfigStore (Mongo + sqlite mirror)
                                                        │  (validates liveness before save)
agent run ──resolve_role_model_sync()──────────────────┘
   (call-time resolution: requested → DB → env → safe default)
```

### Resolution precedence

1. **`requested_model`** — per-call override (e.g. a sub-agent config)
2. **BrainConfig DB field** — set from the admin UI; cache TTL 5s
3. **Env var** — `AGENT_PLANNER_MODEL` / `AGENT_EXECUTOR_MODEL` / `AGENT_VERIFIER_MODEL` / `AGENT_JUDGE_MODEL` (with `NVIDIA_DEFAULT_MODEL` as a fallback for planner/verifier, preserving the existing import-time constant's behaviour)
4. **Safe default** — `nvidia/llama-3.3-nemotron-super-49b-v1`

The same precedence applies to `brain_policy.resolve_active_brain()` for the *provider* (not just the model id), with one exception: the `AGENT_LLM_BASE_URL` env kill-switch always wins (preserves the existing operator kill-switch contract).

## Tests

```bash
# Run all new + existing brain/failover tests
ADMIN_PASSWORD=test SKIP_DB_TESTS=1 pytest \
  tests/test_brain_config_store.py \
  tests/test_brain_config_api.py \
  tests/test_brain_resolution.py \
  tests/test_brain_resolver.py \
  tests/test_brain_default_model.py \
  tests/test_brain_priority_scanner.py \
  tests/test_orchestrator_failover.py \
  tests/test_failover_order.py \
  tests/test_provider_policy.py
# → 99 passed, 2 skipped
```

All provider probes are mocked — no live network in CI.

## Rollout / verification (per plan §5)

1. **Land behind the safe default.** A fresh deploy with no `BrainConfig` doc
   in the DB returns `nvidia/llama-3.3-nemotron-super-49b-v1` for every role —
   identical to the pre-PR behaviour. No env-var change required.
2. **After merge, in the live UI:** open Providers → Brain card → pick
   Cerebras → click Test on each role model → click Apply. The PATCH
   endpoint probes each model before saving; if all green, the config is
   persisted and the next agent run picks it up (no redeploy).
3. **Remove the four `AGENT_*_MODEL` Render env overrides** — they're now
   DB-driven. Keeping them set is harmless (they're the third-precedence
   fallback) but no longer required.

## What this is NOT

* **Not a provider failover chain.** The plan §2 recommends Cerebras → Groq
  → NIM → Ollama with per-provider 429/quota cooldown. The repo already
  has that machinery in `provider_router.py` and `agent/loop.py`'s 429
  backoff — this PR does **not** rebuild it. The `BrainConfig.primary_provider`
  field picks *which* provider is the brain; the existing failover chain
  still handles 429/5xx retries against the other configured providers.
* **Not a key store.** `BrainConfig` stores only model ids and provider
  names — never API keys. Keys stay in env (`CEREBRAS_API_KEY` /
  `GROQ_API_KEY` / `NVIDIA_API_KEY` / `OLLAMA_BASE`).
* **Not a replacement for the Providers screen.** The Brain card sits
  alongside the existing provider list + paid-provider kill switch. It
  is the one-click switcher for the *active brain*; the rest of the
  provider configuration (add/edit/delete, drag-and-drop priority) is
  unchanged.

## Risks & mitigations (per plan §6)

| Risk | Mitigation |
|---|---|
| Brain resolution is hot-path | `resolve_role_model_sync` is synchronous, reads the in-process cache (5s TTL), never blocks on the DB. On cache miss it falls back to env / safe default rather than awaiting. |
| Admin auth surface | Reuses `get_current_user` + `_is_admin` from `backend.company_api` — no new auth code. |
| Dead-model save | Mandatory pre-save liveness probe; 422 + probe report on failure; persisted config unchanged. |
| Secrets | Config stores model ids and provider names only. GET response includes `key_present` flags, never key values. Tested by `test_get_response_never_leaks_api_keys`. |
