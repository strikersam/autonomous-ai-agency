# Implementation Plan — DB-persisted, UI-switchable Brain (no redeploy)

> **Status:** Ready-to-execute spec for a dedicated session. Self-contained — an
> agent can implement this end-to-end from this document.
> **Owner request:** change the agency's "brain" (provider + the planner /
> executor / verifier / judge models) **from the UI, in one click, persisted in
> the database, with no redeploy.** Today this requires editing Render env vars
> and redeploying — which is the pain this removes.

---

## 0. Why this exists (root cause this fixes)

The live deploy had `AGENT_EXECUTOR_MODEL=nvidia/nemotron-3-super-120b-a12b` set
in Render — a **retired model that returns HTTP 410 Gone**. Every agent call
(plan/execute/verify/judge) hit a dead endpoint, which is why "NIM only produces
hallucinated/failed work." Changing it required a redeploy. The model choice
must become **runtime-mutable, validated, and UI-driven**, so a dead or
rate-limited model is swapped in seconds, not a deploy.

The agent role models are resolved at **import time** today
(`agent/loop.py:114-127` → `DEFAULT_PLANNER_MODEL` / `DEFAULT_EXECUTOR_MODEL` /
`DEFAULT_VERIFIER_MODEL`, each `os.environ.get(...) or <default>`), so even a DB
value wouldn't take effect without a restart. The core change is moving model
resolution to **call time**.

---

## 1. Hard constraints (from the owner)

1. **Never land on a dead model.** The API must **probe the provider for
   liveness before saving** a model, and refuse to persist a model that 404/410s.
   Always keep a known-good fallback so a bad choice can't brick the agency.
2. **No quota/gate that expires in ~2 days.** Prefer providers with *sustained*
   free tiers, and design **multi-provider auto-failover** so no single quota or
   rate limit can stop the loop. (See §4 provider strategy.)
3. **One-click change from the UI**, persisted in the DB, **no redeploy**.
4. **Don't break the freshly-healed `master`.** Risky surfaces (brain resolution
   + admin auth) — follow `risky-module-review`, add tests, gate on CI.

---

## 2. Provider strategy (the recommendation)

Don't rely on a single NIM model. Use a **priority chain across sustainable free
tiers**, each validated live, with automatic failover:

| Priority | Provider | Env key | Why | Notes |
|---|---|---|---|---|
| 1 | **Cerebras** | `CEREBRAS_API_KEY` | Wafer-scale inference, ~10–20× faster than NIM, sustained free tier, strong Qwen3-Coder | Best default for speed + coding |
| 2 | **Groq** | `GROQ_API_KEY` | LPU inference, fast, free tier (Llama/Qwen/Kimi/DeepSeek-distill) | Fallback |
| 3 | **NVIDIA NIM** | `NVIDIA_API_KEY` | Largest catalogue, free, but shared-queue latency + ~40 RPM | Tertiary; `deepseek-ai/deepseek-v4-flash` if used |
| 4 | **Local Ollama** | `OLLAMA_BASE` | Only when the Windows box is up | Already wired |

**"No dead model" guard:** the default the switcher ships with must be the
**known-working** `nvidia/llama-3.3-nemotron-super-49b-v1` (verified live), and
the UI only promotes a new choice *after* its pre-save liveness probe passes.

**"No 2-day quota" guard:** the resolver round-robins/falls-through providers on
429/410/5xx with per-provider cooldown (the repo already has 429/419 backoff in
`agent/loop.py` and a provider chain in `provider_router.py` — extend, don't
rebuild). The agency therefore keeps working even when one provider's daily/free
quota is exhausted.

> Liveness/availability of exact model IDs must be confirmed against the live
> API (blocked from the CI sandbox; run on the deploy or the owner's machine):
> ```bash
> for M in <model-id> ...; do
>   curl -s https://<provider-base>/v1/chat/completions \
>     -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
>     -d "{\"model\":\"$M\",\"messages\":[{\"role\":\"user\",\"content\":\"ok\"}],\"max_tokens\":5}" | head -c 200
> done
> ```

---

## 3. Architecture

```
UI "Brain" card  ──PATCH /admin/api/policy/brain──►  BrainConfigStore (Mongo + sqlite mirror)
                                                        │  (validates liveness before save)
agent run ──get_active_brain()──────────────────────────┘
   (call-time resolution: DB → env → safe default)
```

### 3a. Store — `services/brain_config_store.py` (new)
- Pydantic model `BrainConfig { primary_provider: Literal[...], planner_model, executor_model, verifier_model, judge_model, max_tokens: int = 4096, updated_at, updated_by }`.
- Persistence: one document in Mongo collection `app_settings` keyed `_id="brain_config"`, **mirrored to a sqlite row** for the no-Mongo path (follow the existing dual-storage pattern used by `key_store.py` / company storage).
- In-process cache with a short TTL (e.g. 5 s) + explicit `invalidate()` on write, so a UI change is picked up by the next agent run without a restart.
- `async def get_brain_config() -> BrainConfig` and `async def set_brain_config(patch, *, actor) -> BrainConfig`.

### 3b. Call-time resolution — `agent/loop.py`
- Replace the module-level `DEFAULT_*_MODEL` constants' *use* with a helper
  `def _resolve_role_model(role: str, requested: str|None) -> str` that reads, in
  order: explicit `requested_model` → **BrainConfig (DB)** → env var → safe default.
- Keep the env vars working (so nothing regresses) but DB wins over env when set.
- Touch points (already mapped): planner `loop.py:616-618`, executor `657-663`,
  verifier `671`, judge `455`. Also fold into `brain_policy.resolve_free_nvidia_brain`
  / the workflow orchestrator's `_resolve_brain_provider` so the *provider* (not
  just NIM model id) is honored.

### 3c. Admin API — `backend/server.py`
- `GET /admin/api/policy/brain` → current `BrainConfig` + per-provider key-present flags + last liveness results. (admin-auth gated — reuse the existing admin dependency.)
- `PATCH /admin/api/policy/brain` → validate body (Pydantic), **probe liveness** of each changed model against its provider, refuse (422) any that fail, persist + invalidate cache on success. Returns the applied config + the probe report.
- `POST /admin/api/policy/brain/test` → probe a {provider, model} without saving (powers the UI "Test" button).
- All three: never log key values; redact in responses.

### 3d. UI — `webui/frontend/src/pages` (+ `webui/router.py` / `providers.py`)
- A **"Brain" card** on the Routing/Providers screen: provider dropdown (only
  providers whose key is present), four model fields (planner/executor/verifier/
  judge) with sensible presets per provider, a **"Test"** button (calls
  `/test`), and **"Apply"** (calls `PATCH`, shows the probe result, green = live).
- Show the currently-active config + "last applied by/at".

---

## 4. Tests (required — risky surfaces)
- `tests/test_brain_config_store.py` — get/set round-trip, cache invalidation, sqlite-fallback, defaults.
- `tests/test_brain_config_api.py` — auth required; PATCH rejects a dead model (mock probe → 410) with 422; PATCH accepts a live model; GET shape contract; keys never leaked.
- `tests/test_brain_resolution.py` — `_resolve_role_model` precedence (requested → DB → env → default); DB change takes effect without re-import (call-time).
- Extend `tests/test_model_router.py` for any registry additions.
- Mock all provider probes (no live network in CI).

## 5. Rollout / verification
1. Land behind a safe default (`nvidia/llama-3.3-nemotron-super-49b-v1`) so even
   a fresh deploy is healthy.
2. After merge, in the live UI: Test → Apply **Cerebras (Qwen3-Coder)**; confirm
   an agent task runs and lands a PR using it.
3. Then remove the four `AGENT_*_MODEL` Render env overrides (now DB-driven).

## 6. Risks & mitigations
- *Brain resolution is hot-path* → keep the resolver pure + cached; cover with tests; never throw (fall back to safe default on store error).
- *Admin auth surface* → reuse the existing admin dependency, don't invent new auth; `risky-module-review`.
- *Dead-model save* → mandatory pre-save liveness probe; known-good default; auto-failover chain.
- *Secrets* → config stores **model ids and provider names only**, never keys; keys stay in env.

---

## 7. One-paragraph prompt (paste to kick off the build session)

> Implement a DB-persisted, UI-switchable "brain" config for the agency so the
> provider and the planner/executor/verifier/judge models can be changed from the
> admin UI in one click, persisted in Mongo (sqlite-mirrored), with **no redeploy**.
> Move agent model resolution from import-time env (`agent/loop.py:114-127`) to a
> call-time resolver with precedence requested → DB → env → safe default. Add
> `services/brain_config_store.py`, admin endpoints `GET/PATCH /admin/api/policy/brain`
> and `POST /admin/api/policy/brain/test` that **probe provider liveness before
> saving and refuse dead models (410/404)**, and a "Brain" card on the
> Routing/Providers screen with Test + Apply. Default the chain to Cerebras
> (Qwen3-Coder) → Groq → NIM → Ollama with per-provider 429/quota failover, but
> ship the safe default `nvidia/llama-3.3-nemotron-super-49b-v1`. Config stores
> model ids/provider names only — never API keys. Full tests for store, API
> (auth + dead-model rejection), and resolution precedence. Follow
> `risky-module-review`; PR → CI green → merge → verify in the live UI.
